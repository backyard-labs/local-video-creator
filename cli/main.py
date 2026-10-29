
"""
Local Video Creator
Stage 1 - Guided Command-Line Interface
Version 0.10

Features:
- Discover photographs
- Preserve an existing storyboard by default
- Explicitly regenerate a storyboard with backup
- Generate a numbered contact sheet
- Analyze photographs using local Ollama
- Reuse approved AI descriptions
- Resume interrupted batch analysis
- Save batch progress summaries
- Optionally add background music to the rendered video
- Optionally add a minimal cinematic title to the video
- Choose photo folders and MP3 files using Windows dialogs or typed paths
- Optional local AI title suggestions or custom titles; prefer music source
- Separate named project folders, with existing-project reuse
"""

import json
import re
import shutil
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from src.audio import add_background_music
from src.titles import add_cinematic_title
from src.contact_sheet import create_contact_sheet
from src.renderer import render_storyboard
from src.storyboard import Storyboard, StoryboardEntry
from src.vision import (
    analyze_photo,
    load_existing_approval,
    review_description,
    save_approved_description,
)


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FOLDER = PROJECT_ROOT / "projects" / "default-project"
ANALYSIS_FOLDER = OUTPUT_FOLDER / "analysis"
STORYBOARD_PATH = OUTPUT_FOLDER / "storyboard.csv"


def choose_project_folder() -> Path:
    """Choose a named project without changing or deleting existing projects."""
    projects_root = PROJECT_ROOT / "projects"
    print("PROJECT SETUP")
    print("Each project has its own storyboard, analysis, and videos.")
    while True:
        name = input("Project name (e.g., Autumn Morning Walk): ").strip()
        if not name:
            print("Please enter a project name.")
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug or len(slug) > 64 or slug in {".", ".."}:
            print("Please use a shorter name with letters or numbers.")
            continue
        folder = projects_root / slug
        print(f"Project folder: {folder.resolve()}")
        if folder.exists():
            if not folder.is_dir():
                print("That project name points to a file. Choose another name.")
                continue
            if not ask_yes_no("Existing project found. Reuse this folder?"):
                continue
        else:
            if not ask_yes_no("Create this new project?"):
                continue
            folder.mkdir(parents=True, exist_ok=False)
        return folder


def _windows_picker(kind: str) -> Path | None:
    """Open a native selection dialog; return None on cancel or failure."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
            root.update()
            if kind == "folder":
                selected = filedialog.askdirectory(
                    parent=root,
                    title="Select folder containing photographs",
                )
            elif kind == "mp3":
                selected = filedialog.askopenfilename(
                    parent=root,
                    title="Select background music (MP3)",
                    filetypes=[("MP3 audio", "*.mp3"), ("All files", "*.*")],
                )
            else:
                raise ValueError(f"Unsupported picker type: {kind}")
        finally:
            root.destroy()
        return Path(selected) if selected else None
    except (ImportError, OSError, RuntimeError) as error:
        print(f"Windows picker unavailable ({error}). Please paste the path instead.")
        return None


def ask_photo_folder() -> Path:
    while True:
        answer = input(
            "Photograph folder (press Enter to browse, or paste full path): "
        ).strip().strip('"')
        folder = Path(answer).expanduser() if answer else _windows_picker("folder")
        if folder is None:
            print("No folder selected. Try again or paste its path.\n")
            continue
        if folder.is_dir():
            return folder
        print("Folder not found. Please try again.\n")


def ask_mp3_file() -> Path:
    while True:
        answer = input(
            "MP3 music file (press Enter to browse, or paste full path): "
        ).strip().strip('"')
        music_path = Path(answer).expanduser() if answer else _windows_picker("mp3")
        if music_path is None:
            print("No music file selected. Try again or paste its path.\n")
            continue
        if music_path.is_file() and music_path.suffix.lower() == ".mp3":
            return music_path
        print("MP3 file not found. Please select a valid MP3 file.\n")


def suggest_title_locally(photos: list[Path]) -> str | None:
    """Generate a suggestion using approved descriptions and local Ollama only."""
    descriptions = []
    for photo in photos:
        try:
            approval = load_existing_approval(photo, ANALYSIS_FOLDER)
            if approval and approval.get("approved_description"):
                descriptions.append(str(approval["approved_description"]).strip())
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not descriptions:
        print("No approved photo descriptions available. Choose a custom title.")
        return None
    print(f"Using {len(descriptions)} approved descriptions for a local suggestion.")
    prompt = (
        "Suggest one original, short, elegant title for a personal photo-memory video. "
        "Use only the descriptions below. Return ONLY the title, no explanation, "
        "2 to 7 words, at most 60 characters.\n\n"
        + "\n".join(f"- {d[:350]}" for d in descriptions[:20])
    )
    def request_title(max_tokens: int) -> dict:
        payload = json.dumps({
            "model": "qwen3.5:9b",
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.5, "num_predict": max_tokens},
        }).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)

    try:
        result = request_title(256)
        answer = result.get("response") or ""
        if not str(answer).strip():
            print("Model returned no final text; retrying with a larger output limit...")
            result = request_title(1024)
            answer = result.get("response") or ""
        lines = str(answer).strip().splitlines()
        if not lines:
            print("Local AI did not produce a final title. Choose a custom title.")
            return None
        title = lines[0].strip().strip('"“”').strip("'").strip("*").strip()
        if not title or len(title) > 60 or not 2 <= len(title.split()) <= 10:
            print("Local AI returned no usable short title. Choose a custom title.")
            return None
        return title
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError) as error:
        print(f"Local AI suggestion unavailable: {error}")
        return None


def choose_cinematic_title(photos: list[Path]) -> str | None:
    while True:
        print("\nTITLE TEXT")
        print("  1. Suggest a title with local AI")
        print("  2. Enter my own title")
        print("  3. No title")
        choice = input("Choose 1, 2, or 3 [default 2]: ").strip() or "2"
        if choice == "3":
            return None
        if choice == "2":
            title = input("Enter title text: ").strip()
            if title:
                return title
            print("Title cannot be blank.")
        elif choice == "1":
            title = suggest_title_locally(photos)
            if title:
                print(f"Suggested title: {title}")
                if ask_yes_no("Use this title?"):
                    return title
        else:
            print("Please enter 1, 2, or 3.")


def discover_photos(folder: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )


def create_default_storyboard(
    photos: list[Path],
) -> Storyboard:
    entries = [
        StoryboardEntry(
            position=index,
            photo_path=photo,
            duration=3.0,
            photo_id=f"{index:02d}",
        )
        for index, photo in enumerate(photos, start=1)
    ]

    storyboard = Storyboard(entries)
    storyboard.validate()

    return storyboard


def backup_storyboard(path: Path) -> Path:
    """Create a timestamped backup of an existing storyboard."""

    backup_folder = path.parent / "storyboard-history"
    backup_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    backup_path = backup_folder / (
        f"{path.stem}.{timestamp}.bak.csv"
    )

    shutil.copy2(path, backup_path)

    return backup_path


def validate_storyboard_photos(
    storyboard: Storyboard,
    photos: list[Path],
) -> None:
    """
    Ensure the storyboard references exactly the photographs
    discovered in the selected folder.
    """

    discovered = {
        photo.resolve()
        for photo in photos
    }

    referenced = [
        entry.photo_path.resolve()
        for entry in storyboard.entries
    ]

    if len(referenced) != len(set(referenced)):
        raise ValueError(
            "Existing storyboard contains duplicate photographs."
        )

    if set(referenced) != discovered:
        raise ValueError(
            "Existing storyboard does not match the selected "
            "photograph folder. No changes were made."
        )


def prepare_storyboard(
    photos: list[Path],
    photos_folder: Path,
) -> Storyboard:
    """Load an existing storyboard or explicitly regenerate it."""

    OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    if STORYBOARD_PATH.is_file():
        print("\nEXISTING STORYBOARD FOUND")
        print(f"Path: {STORYBOARD_PATH.resolve()}")

        storyboard = Storyboard.load_csv(
            STORYBOARD_PATH,
            photos_folder,
        )

        validate_storyboard_photos(
            storyboard,
            photos,
        )

        print(
            f"Duration: {storyboard.total_duration:.1f}s"
        )

        choice = input(
            "\nPress Enter to reuse this storyboard, "
            "or type R to regenerate: "
        ).strip().lower()

        if choice != "r":
            print(
                "\nExisting storyboard reused. "
                "No changes made."
            )
            return storyboard

        print("\nStoryboard regeneration requested.")

        backup_path = backup_storyboard(
            STORYBOARD_PATH
        )

        print(
            f"Previous storyboard backed up: "
            f"{backup_path.resolve()}"
        )

    storyboard = create_default_storyboard(
        photos
    )

    storyboard.save_csv(
        STORYBOARD_PATH
    )

    print("\nStoryboard created successfully!")
    print(
        f"Total duration: "
        f"{storyboard.total_duration:.1f} seconds"
    )
    print(
        f"Storyboard: "
        f"{STORYBOARD_PATH.resolve()}"
    )

    return storyboard


def ask_yes_no(question: str) -> bool:
    while True:
        answer = input(
            f"{question} [Y/N]: "
        ).strip().lower()

        if answer in {"y", "yes"}:
            return True

        if answer in {"n", "no"}:
            return False

        print("Please enter Y or N.")


def save_batch_summary(
    photos: list[Path],
) -> Path:
    approved = []
    pending = []

    for photo in photos:
        existing = load_existing_approval(
            photo,
            ANALYSIS_FOLDER,
        )

        if existing:
            approved.append(photo.name)
        else:
            pending.append(photo.name)

    summary = {
        "updated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_photographs": len(photos),
        "approved_count": len(approved),
        "pending_count": len(pending),
        "approved_photographs": approved,
        "pending_photographs": pending,
    }

    summary_path = (
        OUTPUT_FOLDER / "analysis-summary.json"
    )

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return summary_path


def analyze_batch(photos: list[Path]) -> None:
    total = len(photos)

    print("\n" + "=" * 50)
    print("BATCH AI PHOTO ANALYSIS")
    print("=" * 50)

    print(f"\nPhotographs in batch: {total}")
    print("Existing approvals will be reused.")
    print("You can stop after any new approval.\n")

    for index, photo in enumerate(
        photos, start=1
    ):
        print("\n" + "-" * 50)
        print(f"Photograph {index} of {total}")
        print(f"File: {photo.name}")
        print("-" * 50)

        try:
            existing = load_existing_approval(
                photo,
                ANALYSIS_FOLDER,
            )

            if existing:
                print("\nAlready approved:")
                print(
                    existing["approved_description"]
                )
                print(
                    "\nReusing existing approval."
                )
                continue

            print(
                "\nAnalyzing with local Qwen..."
            )

            ai_description = analyze_photo(
                photo
            )

            approved_description = (
                review_description(
                    ai_description
                )
            )

            output_path = (
                save_approved_description(
                    photo_path=photo,
                    ai_description=ai_description,
                    approved_description=approved_description,
                    output_folder=ANALYSIS_FOLDER,
                )
            )

            print(
                "\nApproved analysis saved:"
            )
            print(
                output_path.resolve()
            )

            if index < total:
                if not ask_yes_no(
                    "\nContinue to next photograph?"
                ):
                    print(
                        "\nBatch paused by user."
                    )
                    break

        except (
            FileNotFoundError,
            ValueError,
            RuntimeError,
            OSError,
        ) as error:
            print(f"\nERROR: {error}")
            print(
                "Batch stopped to protect existing work."
            )
            break

    summary_path = save_batch_summary(
        photos
    )

    print("\n" + "=" * 50)
    print("BATCH SUMMARY")
    print("=" * 50)

    summary = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    print(
        f"Approved: "
        f"{summary['approved_count']}"
        f"/{summary['total_photographs']}"
    )
    print(
        f"Pending: "
        f"{summary['pending_count']}"
    )
    print(
        f"Summary: "
        f"{summary_path.resolve()}"
    )


def main() -> None:
    print("\n" + "=" * 50)
    print("LOCAL VIDEO CREATOR")
    print("Stage 1 - Guided CLI, Version 0.10")
    print("=" * 50 + "\n")

    global OUTPUT_FOLDER, ANALYSIS_FOLDER, STORYBOARD_PATH
    OUTPUT_FOLDER = choose_project_folder()
    ANALYSIS_FOLDER = OUTPUT_FOLDER / "analysis"
    STORYBOARD_PATH = OUTPUT_FOLDER / "storyboard.csv"

    folder = ask_photo_folder()
    photos = discover_photos(
        folder
    )

    if not photos:
        print(
            "\nNo supported photographs found."
        )
        print(
            "Supported formats: JPG, JPEG, PNG"
        )
        return

    print(
        f"\nFound {len(photos)} photographs:\n"
    )

    for index, photo in enumerate(
        photos, start=1
    ):
        print(
            f"  {index:02d}. {photo.name}"
        )

    try:
        storyboard = prepare_storyboard(
            photos,
            folder,
        )
    except (
        FileNotFoundError,
        ValueError,
        OSError,
    ) as error:
        print(
            f"\nSTORYBOARD ERROR: {error}"
        )
        print(
            "Existing storyboard was not overwritten."
        )
        return

    print(
        "\nGenerating numbered contact sheet..."
    )

    contact_sheet_path = (
        OUTPUT_FOLDER / "contact-sheet.jpg"
    )

    create_contact_sheet(
        photos=photos,
        output_path=contact_sheet_path,
    )

    print(
        "Contact sheet created successfully!"
    )
    print(
        f"Contact sheet: "
        f"{contact_sheet_path.resolve()}"
    )

    print("\n" + "=" * 50)
    print("PROJECT SUMMARY")
    print("=" * 50)

    print(
        f"Photographs: {len(photos)}"
    )
    print(
        f"Duration: "
        f"{storyboard.total_duration:.1f}s"
    )
    print(
        f"Output folder: "
        f"{OUTPUT_FOLDER.resolve()}"
    )

    if ask_yes_no(
        "\nRun AI analysis for these photographs?"
    ):
        analyze_batch(
            photos
        )
    else:
        print(
            "\nAI analysis skipped."
        )

    if ask_yes_no("\nRender video now?"):
        print("\nRENDER MODE")
        print("  1. Static photographs")
        print("  2. Ken Burns motion (approved AI motion where available)")
        while True:
            mode = input("Choose 1 or 2: ").strip()
            if mode in {"1", "2"}:
                break
            print("Please enter 1 or 2.")

        output = OUTPUT_FOLDER / "final-video.mp4"
        if output.exists() and not ask_yes_no(
            f"Output already exists: {output.name}. Replace it?"
        ):
            print("Rendering skipped; existing video preserved.")
        else:
            try:
                render_storyboard(
                    storyboard=storyboard,
                    output_path=output,
                    motion_enabled=(mode == "2"),
                    use_approved_motion=(mode == "2"),
                )
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
                print(f"\nRENDER ERROR: {error}")
    else:
        print("\nVideo rendering skipped.")

    video_path = OUTPUT_FOLDER / "final-video.mp4"
    music_output = OUTPUT_FOLDER / "final-video-with-music.mp4"
    title_output = OUTPUT_FOLDER / "final-video-with-title.mp4"

    if video_path.is_file() and ask_yes_no("\nAdd background music to the video?"):
        music_path = ask_mp3_file()

        if music_output.exists() and not ask_yes_no(
            f"Output already exists: {music_output.name}. Replace it?"
        ):
            print("Music processing skipped; existing output preserved.")
        else:
            print("\nAdding background music (1s fade-in, 2s fade-out)...")
            try:
                created = add_background_music(
                    video_path=video_path,
                    music_path=music_path,
                    output_path=music_output,
                )
                print(f"\nVideo with music created: {created}")
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
                print(f"\nMUSIC ERROR: {error}")
                print("Original video was preserved.")
    elif not video_path.is_file():
        print("\nMusic processing unavailable: no final-video.mp4 found.")
    else:
        print("\nBackground music skipped.")

    title_source = None
    if video_path.is_file() and ask_yes_no("\nAdd a cinematic title to the video?"):
        if music_output.is_file():
            print("\nWhich video should receive the cinematic title?")
            print("  1. Original video (without background music)")
            print("  2. Video with background music [Recommended]")
            while True:
                choice = input("Choose 1 or 2 [default 2]: ").strip() or "2"
                if choice in {"1", "2"}:
                    break
                print("Please enter 1 or 2.")
            title_source = music_output if choice == "2" else video_path
        else:
            print("Using original video (no music version available).")
            title_source = video_path

    if title_source is not None:
        title = choose_cinematic_title(photos)
        if title is None:
            print("\nCinematic title skipped by user.")
        elif title_output.exists() and not ask_yes_no(
            f"Output already exists: {title_output.name}. Replace it?"
        ):
            print("Title processing skipped; existing output preserved.")
        else:
            print("\nAdding cinematic title (first 4 seconds)...")
            try:
                created = add_cinematic_title(
                    input_video=title_source,
                    output_video=title_output,
                    title=title,
                    start=0.0,
                    duration=4.0,
                    fade_in=0.5,
                    fade_out=0.5,
                    overwrite=title_output.exists(),
                )
                print(f"\nVideo with title created: {created}")
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
                print(f"\nTITLE ERROR: {error}")
                print("Input video was preserved.")
    elif not video_path.is_file():
        print("\nTitle processing unavailable: no final-video.mp4 found.")
    else:
        print("\nCinematic title skipped.")

    print("\nCLI session completed.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nVideo creation cancelled by user.")
        print("Previously saved project files have not been intentionally deleted.")
        print("Goodbye!")
        raise SystemExit(130)