
import tempfile
import unittest
from pathlib import Path

from src.storyboard import Storyboard, StoryboardEntry


class TestStoryboard(unittest.TestCase):

    def test_valid_storyboard(self):
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "photo.jpg"
            photo.touch()

            storyboard = Storyboard([
                StoryboardEntry(1, photo, 3.0),
                StoryboardEntry(2, photo, 2.5),
            ])

            storyboard.validate()
            self.assertEqual(storyboard.total_duration, 5.5)

    def test_missing_photo(self):
        storyboard = Storyboard([
            StoryboardEntry(
                1, Path("nonexistent_photo.jpg"), 3.0
            )
        ])

        with self.assertRaises(FileNotFoundError):
            storyboard.validate()

    def test_invalid_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "photo.jpg"
            photo.touch()

            storyboard = Storyboard([
                StoryboardEntry(1, photo, -2.0)
            ])

            with self.assertRaises(ValueError):
                storyboard.validate()

    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "autumn.jpg"
            photo.touch()

            original = Storyboard([
                StoryboardEntry(
                    position=1,
                    photo_path=photo,
                    duration=3.5,
                    photo_id="07",
                )
            ])

            csv_path = root / "storyboard.csv"
            original.save_csv(csv_path)

            loaded = Storyboard.load_csv(csv_path, root)

            self.assertEqual(loaded.total_duration, 3.5)
            self.assertEqual(loaded.entries[0].photo_id, "07")
            self.assertEqual(
                loaded.entries[0].photo_path, photo
            )

    def make_three_photo_storyboard(self, root):
        photos = []

        for number in range(1, 4):
            photo = root / f"photo{number}.jpg"
            photo.touch()
            photos.append(photo)

        return Storyboard([
            StoryboardEntry(
                position=index,
                photo_path=photo,
                duration=3.0,
                photo_id=f"{index:02d}",
            )
            for index, photo in enumerate(photos, start=1)
        ])

    def test_move_photo_forward(self):
        with tempfile.TemporaryDirectory() as folder:
            storyboard = self.make_three_photo_storyboard(
                Path(folder)
            )

            storyboard.move_photo(1, 3)

            self.assertEqual(
                [entry.photo_id for entry in storyboard.entries],
                ["02", "03", "01"],
            )
            self.assertEqual(
                [entry.position for entry in storyboard.entries],
                [1, 2, 3],
            )
            self.assertEqual(storyboard.total_duration, 9.0)

    def test_move_photo_backward(self):
        with tempfile.TemporaryDirectory() as folder:
            storyboard = self.make_three_photo_storyboard(
                Path(folder)
            )

            storyboard.move_photo(3, 1)

            self.assertEqual(
                [entry.photo_id for entry in storyboard.entries],
                ["03", "01", "02"],
            )
            storyboard.validate()

    def test_move_photo_invalid_position(self):
        with tempfile.TemporaryDirectory() as folder:
            storyboard = self.make_three_photo_storyboard(
                Path(folder)
            )

            with self.assertRaises(ValueError):
                storyboard.move_photo(1, 4)

            with self.assertRaises(ValueError):
                storyboard.move_photo(0, 2)

            self.assertEqual(
                [entry.photo_id for entry in storyboard.entries],
                ["01", "02", "03"],
            )

    def test_set_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            storyboard = self.make_three_photo_storyboard(
                Path(folder)
            )

            storyboard.set_duration(2, 4.5)

            self.assertEqual(
                storyboard.entries[1].duration, 4.5
            )
            self.assertEqual(storyboard.total_duration, 10.5)

    def test_set_duration_invalid_values(self):
        with tempfile.TemporaryDirectory() as folder:
            storyboard = self.make_three_photo_storyboard(
                Path(folder)
            )

            for value in (0, -1, float("nan"), float("inf")):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        storyboard.set_duration(2, value)

            with self.assertRaises(ValueError):
                storyboard.set_duration(4, 2.0)

            self.assertEqual(
                storyboard.entries[1].duration, 3.0
            )

    def test_edited_storyboard_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            storyboard = self.make_three_photo_storyboard(root)

            storyboard.move_photo(3, 1)
            storyboard.set_duration(1, 4.5)

            csv_path = root / "edited-storyboard.csv"
            storyboard.save_csv(csv_path)

            loaded = Storyboard.load_csv(csv_path, root)

            self.assertEqual(
                [entry.photo_id for entry in loaded.entries],
                ["03", "01", "02"],
            )
            self.assertEqual(
                [entry.duration for entry in loaded.entries],
                [4.5, 3.0, 3.0],
            )
            self.assertEqual(loaded.total_duration, 10.5)


if __name__ == "__main__":
    unittest.main()