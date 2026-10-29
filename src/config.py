from dataclasses import dataclass


@dataclass
class VideoSettings:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    zoom_percent: float = 2.0
    crf: int = 21

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Video dimensions must be positive.")
        if self.fps <= 0:
            raise ValueError("Frame rate must be positive.")
        if not 0 <= self.zoom_percent <= 20:
            raise ValueError("Zoom must be between 0% and 20%.")
        if not 0 <= self.crf <= 51:
            raise ValueError("CRF must be between 0 and 51.")


DEFAULT_SETTINGS = VideoSettings()
