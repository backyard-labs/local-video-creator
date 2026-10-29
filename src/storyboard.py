
import csv
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StoryboardEntry:
    position: int
    photo_path: Path
    duration: float
    photo_id: str = ""

    def validate(self) -> None:
        if self.position < 1:
            raise ValueError("Position must be at least 1.")

        if not math.isfinite(self.duration) or self.duration <= 0:
            raise ValueError("Photo duration must be a positive, finite number.")

        if not self.photo_path.is_file():
            raise FileNotFoundError(
                f"Photo not found: {self.photo_path}"
            )


@dataclass
class Storyboard:
    entries: list[StoryboardEntry]

    @property
    def total_duration(self) -> float:
        return round(
            sum(entry.duration for entry in self.entries), 3
        )

    def validate(self) -> None:
        if not self.entries:
            raise ValueError("Storyboard cannot be empty.")

        positions = [entry.position for entry in self.entries]

        if sorted(positions) != list(
            range(1, len(self.entries) + 1)
        ):
            raise ValueError(
                "Storyboard positions must be consecutive."
            )

        for entry in self.entries:
            entry.validate()

    def move_photo(
        self, from_position: int, to_position: int
    ) -> None:
        """Move a photograph and renumber storyboard positions."""
        self.validate()

        count = len(self.entries)

        if not 1 <= from_position <= count:
            raise ValueError(
                f"Source position must be between 1 and {count}."
            )

        if not 1 <= to_position <= count:
            raise ValueError(
                f"Destination position must be between 1 and {count}."
            )

        ordered = sorted(
            self.entries, key=lambda item: item.position
        )

        entry = ordered.pop(from_position - 1)
        ordered.insert(to_position - 1, entry)

        for position, item in enumerate(ordered, start=1):
            item.position = position

        self.entries = ordered
        self.validate()

    def set_duration(
        self, position: int, seconds: float
    ) -> None:
        """Update the duration of one storyboard entry."""
        self.validate()

        if not 1 <= position <= len(self.entries):
            raise ValueError(
                f"Position must be between 1 and {len(self.entries)}."
            )

        seconds = float(seconds)

        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(
                "Photo duration must be a positive, finite number."
            )

        entry = next(
            item for item in self.entries
            if item.position == position
        )

        entry.duration = seconds
        self.validate()

    def save_csv(self, csv_path: Path) -> None:
        csv_path = Path(csv_path)

        with csv_path.open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.writer(file)
            writer.writerow(
                ["Position", "PhotoID", "Filename", "Seconds"]
            )

            for entry in sorted(
                self.entries, key=lambda item: item.position
            ):
                writer.writerow([
                    entry.position,
                    entry.photo_id,
                    entry.photo_path.name,
                    entry.duration,
                ])

    @classmethod
    def load_csv(
        cls, csv_path: Path, photos_folder: Path
    ) -> "Storyboard":
        csv_path = Path(csv_path)
        photos_folder = Path(photos_folder)

        entries = []

        with csv_path.open(
            "r", newline="", encoding="utf-8-sig"
        ) as file:
            reader = csv.DictReader(file)

            required = {
                "Position", "PhotoID", "Filename", "Seconds"
            }

            if not required.issubset(reader.fieldnames or []):
                raise ValueError(
                    "Storyboard CSV has missing columns."
                )

            for row in reader:
                filename = Path(row["Filename"])

                if filename.name != str(filename):
                    raise ValueError(
                        "Filename must not contain a path."
                    )

                entries.append(
                    StoryboardEntry(
                        position=int(row["Position"]),
                        photo_path=photos_folder / filename,
                        duration=float(row["Seconds"]),
                        photo_id=row["PhotoID"],
                    )
                )

        storyboard = cls(entries)
        storyboard.validate()
        return storyboard