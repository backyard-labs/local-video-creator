"""Optional FFmpeg background-music post-processing for Local Video Creator."""

from pathlib import Path
import subprocess
import os
import tempfile


def add_background_music(
    video_path: str | Path,
    music_path: str | Path,
    output_path: str | Path,
    *,
    fade_in: float = 1.0,
    fade_out: float = 2.0,
    ffmpeg_executable: str = "ffmpeg",
    ffprobe_executable: str = "ffprobe",
) -> Path:
    """Copy video without re-encoding and add AAC music trimmed to its duration.

    Writes to a temporary MP4 first, so failures don't damage an existing output.
    The caller must obtain overwrite approval before calling this function.
    """
    video = Path(video_path).expanduser().resolve()
    music = Path(music_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    for label, path in (("Video", video), ("Music", music)):
        if not path.is_file():
            raise FileNotFoundError(f"{label} file not found: {path}")
    if output in (video, music):
        raise ValueError("Output must differ from the input video and music files.")
    if fade_in < 0 or fade_out < 0:
        raise ValueError("Fade durations must be nonnegative.")

    probe = subprocess.run(
        [ffprobe_executable, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True, check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        duration = float(probe.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("Could not determine video duration.") from exc
    if duration <= 0:
        raise ValueError("Video duration must be positive.")

    fade_in = min(fade_in, duration)
    fade_out = min(fade_out, max(0.0, duration - fade_in))
    filters = []
    if fade_in:
        filters.append(f"afade=t=in:st=0:d={fade_in:.3f}")
    if fade_out:
        filters.append(f"afade=t=out:st={duration - fade_out:.3f}:d={fade_out:.3f}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".audio-render-", suffix=".mp4", dir=output.parent, delete=False
        ) as temp:
            temporary_path = Path(temp.name)
        command = [
            ffmpeg_executable, "-hide_banner", "-nostdin", "-y",
            "-i", str(video), "-i", str(music),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        ]
        if filters:
            command.extend(["-af", ",".join(filters)])
        command.extend(["-t", f"{duration:.3f}", "-movflags", "+faststart", str(temporary_path)])
        subprocess.run(
            command, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        temporary_path.replace(output)
        return output
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
