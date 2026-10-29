"""Minimal cinematic text overlays for Local Video Creator.

Requires FFmpeg with the drawtext filter. Creates a new MP4 without modifying
its source. Video is re-encoded because text is burned into the frames.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


DEFAULT_FONT = Path(r"C:\Windows\Fonts\segoeuil.ttf")


def _escape_drawtext(value: str) -> str:
    """Escape a string for FFmpeg's drawtext filter parser."""
    return (value.replace("\\", "\\\\")
                 .replace(":", r"\:")
                 .replace("'", r"\'")
                 .replace("%", r"\%")
                 .replace("[", r"\[")
                 .replace("]", r"\]"))


def add_cinematic_title(
    input_video: str | Path,
    output_video: str | Path,
    title: str = "Autumn Along the Paths",
    *,
    start: float = 0.0,
    duration: float = 4.0,
    fade_in: float = 0.5,
    fade_out: float = 0.5,
    font_path: str | Path = DEFAULT_FONT,
    font_size: int = 64,
    crf: int = 18,
    overwrite: bool = False,
) -> Path:
    """Burn a white, subtly shadowed lower-third title into an MP4.

    Retains source audio if present; writes to a temporary output and renames
    only after successful encoding. Callers must explicitly allow replacement.
    """
    source = Path(input_video).expanduser().resolve()
    destination = Path(output_video).expanduser().resolve()
    font = Path(font_path).expanduser()

    if not source.is_file():
        raise FileNotFoundError(f"Video not found: {source}")
    if not font.is_file():
        raise FileNotFoundError(f"Font not found: {font}")
    if source == destination:
        raise ValueError("Input and output paths must be different.")
    if not title.strip():
        raise ValueError("Title must not be empty.")
    if start < 0 or duration <= 0 or fade_in < 0 or fade_out < 0:
        raise ValueError("Invalid title timing.")
    if fade_in + fade_out > duration:
        raise ValueError("Title fades cannot exceed title duration.")
    if font_size <= 0 or not 0 <= crf <= 51:
        raise ValueError("Invalid font size or CRF.")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.stem + ".partial" + destination.suffix)
    if temp.exists():
        raise FileExistsError(f"Temporary output already exists: {temp}")

    # Using textfile avoids multiple levels of escaping for user-provided titles.
    text_file = destination.with_name(destination.stem + ".title-text.tmp")
    if text_file.exists():
        raise FileExistsError(f"Temporary title file already exists: {text_file}")
    text_file.write_text(title, encoding="utf-8")
    try:
        # Use forward slashes and escape drive-letter colons for FFmpeg.
        font_arg = _escape_drawtext(font.as_posix())
        text_arg = _escape_drawtext(text_file.as_posix())
        end = start + duration
        fade_out_start = end - fade_out
        # FFmpeg expression commas must be escaped within the filter argument.
        alpha = (
            f"if(lt(t\\,{start})\\,0\\,"
            f"if(lt(t\\,{start + fade_in})\\,(t-{start})/{max(fade_in, 0.000001)}\\,"
            f"if(lt(t\\,{fade_out_start})\\,1\\,"
            f"if(lt(t\\,{end})\\,({end}-t)/{max(fade_out, 0.000001)}\\,0))))"
        )
        filter_string = (
            f"drawtext=fontfile='{font_arg}':textfile='{text_arg}':"
            f"fontsize={font_size}:fontcolor=white:"
            "x=(w-text_w)/2:y=h*0.79-text_h/2:"
            "shadowcolor=black@0.65:shadowx=2:shadowy=2:"
            f"alpha='{alpha}'"
        )
        command = [
            "ffmpeg", "-hide_banner", "-nostdin", "-y",
            "-i", str(source),
            "-vf", filter_string,
            "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-c:a", "copy",
            "-movflags", "+faststart", str(temp),
        ]
        subprocess.run(
            command, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        os.replace(temp, destination)
        return destination
    finally:
        text_file.unlink(missing_ok=True)
        # Remove partial outputs only; never touch an existing final file.
        temp.unlink(missing_ok=True)
