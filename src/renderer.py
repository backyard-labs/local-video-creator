
"""Local Video Creator: static and deterministic/approved Ken Burns video renderer."""

import math
import shutil
import subprocess
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from src.config import VideoSettings
from src.storyboard import Storyboard


@dataclass(frozen=True)
class MotionSettings:
    """Validated camera movement for a single photograph."""

    kind: str = "zoom_in"
    zoom_percent: float = 2.0
    focal_x: float = 0.5
    focal_y: float = 0.5

    def validate(self) -> None:
        if self.kind not in {
            "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"
        }:
            raise ValueError(f"Unsupported motion kind: {self.kind}")
        if not math.isfinite(self.zoom_percent) or not 0 <= self.zoom_percent <= 10:
            raise ValueError("Zoom percentage must be between 0 and 10.")
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in (self.focal_x, self.focal_y)):
            raise ValueError("Focal coordinates must be between 0 and 1.")


def approved_motion_for(photo_path: Path, motion_folder: Path | None = None) -> MotionSettings | None:
    """Read an existing human-approved motion; never invoke the AI advisor."""
    from src.motion_advisor import load_approved_motion

    if motion_folder is None:
        approval = load_approved_motion(photo_path)
    else:
        approval = load_approved_motion(photo_path, output_folder=motion_folder)
    if approval is None:
        return None
    data = approval["approved_motion"]
    result = MotionSettings(
        kind=data["kind"],
        zoom_percent=data["zoom_percent"],
        focal_x=data["focal_point"][0],
        focal_y=data["focal_point"][1],
    )
    result.validate()
    return result


def prepare_frame(photo_path: Path, output_path: Path, width: int, height: int) -> None:
    """Keep the previously verified static frame composition unchanged."""
    with Image.open(photo_path) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        background = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(radius=35))
        foreground = ImageOps.contain(source, (width, height), method=Image.Resampling.LANCZOS)
        x = (width - foreground.width) // 2
        y = (height - foreground.height) // 2
        background.paste(foreground, (x, y))
        background.save(output_path, format="PNG")


def motion_frame(base: Image.Image, progress: float, motion: MotionSettings) -> Image.Image:
    """Apply a gentle, edge-safe camera movement to a full-frame composition."""
    motion.validate()
    progress = min(1.0, max(0.0, progress))
    eased = progress * progress * (3.0 - 2.0 * progress)
    width, height = base.size
    amount = motion.zoom_percent / 100.0

    if motion.kind == "zoom_out":
        scale = 1.0 + amount * (1.0 - eased)
    elif motion.kind == "zoom_in":
        scale = 1.0 + amount * eased
    else:
        scale = 1.0 + amount

    crop_w = width / scale
    crop_h = height / scale
    extra_x = width - crop_w
    extra_y = height - crop_h

    if motion.kind == "pan_left":
        left = extra_x * (1.0 - eased)
        top = extra_y * motion.focal_y
    elif motion.kind == "pan_right":
        left = extra_x * eased
        top = extra_y * motion.focal_y
    elif motion.kind == "pan_up":
        left = extra_x * motion.focal_x
        top = extra_y * (1.0 - eased)
    elif motion.kind == "pan_down":
        left = extra_x * motion.focal_x
        top = extra_y * eased
    else:
        left = extra_x * motion.focal_x
        top = extra_y * motion.focal_y

    left = max(0.0, min(left, extra_x))
    top = max(0.0, min(top, extra_y))
    return base.transform(
        (width, height),
        Image.Transform.EXTENT,
        (left, top, left + crop_w, top + crop_h),
        resample=Image.Resampling.BICUBIC,
    )


def render_storyboard(
    storyboard: Storyboard,
    output_path: Path,
    settings: VideoSettings | None = None,
    motion_enabled: bool = False,
    motion: MotionSettings | None = None,
    use_approved_motion: bool = False,
    motion_folder: Path | None = None,
) -> Path:
    """Render storyboard, optionally using saved human-approved motion per photo.

    Static mode is the default. To use approvals, pass both
    motion_enabled=True and use_approved_motion=True.
    """
    storyboard.validate()
    if settings is None:
        settings = VideoSettings()
    settings.validate()
    if motion is None:
        motion = MotionSettings(zoom_percent=settings.zoom_percent)
    if motion_enabled:
        motion.validate()
    if use_approved_motion and not motion_enabled:
        raise ValueError("use_approved_motion=True requires motion_enabled=True.")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("FFmpeg was not found on the system PATH.")
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(storyboard.entries, key=lambda entry: entry.position)

    # Preflight all approvals before rendering any segment. Invalid approvals
    # fail clearly rather than silently replacing a user's approved settings.
    selected_motions: list[tuple[MotionSettings, bool]] = []
    if motion_enabled:
        for entry in ordered:
            selected = (
                approved_motion_for(entry.photo_path, motion_folder)
                if use_approved_motion else None
            )
            selected_motions.append(
                (selected if selected is not None else motion, selected is not None)
            )

    with tempfile.TemporaryDirectory(prefix="local-video-creator-") as folder:
        temporary_path = Path(folder)
        segments = []
        for index, entry in enumerate(ordered, start=1):
            print(f"Preparing photograph {index}/{len(ordered)}: {entry.photo_path.name}")
            frame_path = temporary_path / f"frame-{index:04d}.png"
            segment_path = temporary_path / f"segment-{index:04d}.mp4"
            prepare_frame(entry.photo_path, frame_path, settings.width, settings.height)
            frame_count = max(1, round(entry.duration * settings.fps))

            if motion_enabled:
                selected_motion, was_approved = selected_motions[index - 1]
                if use_approved_motion:
                    source = "approved" if was_approved else "fallback"
                    print(
                        f"  Motion ({source}): "
                        f"{selected_motion.kind}, {selected_motion.zoom_percent:g}%"
                    )
                command = [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v",
                    f"{settings.width}x{settings.height}", "-r", str(settings.fps),
                    "-i", "pipe:0", "-frames:v", str(frame_count),
                    "-c:v", "libx264", "-preset", "medium", "-crf", str(settings.crf),
                    "-pix_fmt", "yuv420p", "-an", str(segment_path),
                ]
                with Image.open(frame_path) as base, subprocess.Popen(
                    command, stdin=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                ) as process:
                    try:
                        for frame_number in range(frame_count):
                            progress = frame_number / max(1, frame_count - 1)
                            frame = motion_frame(base, progress, selected_motion)
                            process.stdin.write(frame.tobytes())
                            frame.close()
                    except (BrokenPipeError, OSError):
                        process.stdin.close()
                        process.wait()
                        raise RuntimeError(
                            "FFmpeg stopped while receiving motion frames."
                        )
                    process.stdin.close()
                    if process.wait() != 0:
                        raise RuntimeError("FFmpeg motion segment encoding failed.")
            else:
                command = [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-framerate", str(settings.fps),
                    "-i", str(frame_path), "-frames:v", str(frame_count),
                    "-c:v", "libx264", "-preset", "medium", "-crf", str(settings.crf),
                    "-pix_fmt", "yuv420p", "-r", str(settings.fps),
                    "-an", str(segment_path),
                ]
                subprocess.run(
                    command, check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            segments.append(segment_path)

        concat_path = temporary_path / "segments.txt"
        with concat_path.open("w", encoding="utf-8") as file:
            for segment in segments:
                file.write(f"file '{segment.name}'\n")
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-c", "copy", "-movflags", "+faststart", str(output_path),
        ]
        print("\nCombining video segments...")
        subprocess.run(
            command, check=True, cwd=temporary_path,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    print(f"\nVideo created: {output_path}")
    return output_path