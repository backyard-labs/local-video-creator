
"""
Local Video Creator
Local AI Vision Module - Version 0.4

Features:
- Analyze photographs using local Ollama
- Disable thinking explicitly
- Accept or edit AI descriptions
- Store approved analyses inside the project workspace
- Reuse existing approvals by default
- Require explicit permission to reanalyze
- Back up an existing approval before replacement

No cloud services or API keys required.
"""

import base64
import json
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen3.5:9b"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ANALYSIS_FOLDER = (
    PROJECT_ROOT
    / "projects"
    / "first-cli-test"
    / "analysis"
)

VISION_PROMPT = """
Analyze this photograph for a short cinematic photo video.

Describe only what is visibly present.

Include:
- Main subjects and objects
- Composition and perspective
- Lighting and colors
- Overall visual mood

Do not invent objects, people, locations, or events.
Do not suggest a storyboard yet.

Keep your response under 120 words.
""".strip()


def analysis_path_for(
    photo_path: Path,
    output_folder: Path = DEFAULT_ANALYSIS_FOLDER,
) -> Path:
    """Return the project's analysis path for a photograph."""

    return Path(output_folder) / (
        Path(photo_path).stem + ".analysis.json"
    )


def load_existing_approval(
    photo_path: Path,
    output_folder: Path = DEFAULT_ANALYSIS_FOLDER,
) -> dict | None:
    """Load an existing approved analysis, if available."""

    path = analysis_path_for(photo_path, output_folder)

    if not path.is_file():
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not read existing analysis: {path}"
        ) from error

    if not isinstance(data, dict):
        raise RuntimeError(
            "Existing analysis has an invalid format."
        )

    if data.get("approved") is not True:
        return None

    if not data.get("approved_description"):
        raise RuntimeError(
            "Existing approval has no description."
        )

    saved_source = data.get("source_photo")
    current_source = str(Path(photo_path).resolve())

    if saved_source != current_source:
        raise RuntimeError(
            "Existing analysis belongs to a different "
            "source photograph. Refusing to reuse it."
        )

    return data


def analyze_photo(
    photo_path: Path,
    model: str = DEFAULT_MODEL,
    timeout: int = 180,
) -> str:
    """Analyze one photograph using local Ollama."""

    photo_path = Path(photo_path).expanduser()

    if not photo_path.is_file():
        raise FileNotFoundError(
            f"Photograph not found: {photo_path}"
        )

    if photo_path.suffix.lower() not in {
        ".jpg", ".jpeg", ".png"
    }:
        raise ValueError(
            "Supported image formats: JPG, JPEG, PNG."
        )

    encoded_image = base64.b64encode(
        photo_path.read_bytes()
    ).decode("ascii")

    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": [
            {
                "role": "user",
                "content": VISION_PROMPT,
                "images": [encoded_image],
            }
        ],
        "options": {
            "temperature": 0.2,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout
        ) as response:
            result = json.load(response)

    except urllib.error.URLError as error:
        raise RuntimeError(
            "Could not contact Ollama. "
            "Check that Ollama is running."
        ) from error

    except TimeoutError as error:
        raise RuntimeError(
            "Ollama analysis timed out."
        ) from error

    description = (
        result.get("message", {})
        .get("content", "")
        .strip()
    )

    if not description:
        raise RuntimeError(
            "Ollama returned an empty description."
        )

    return description


def review_description(ai_description: str) -> str:
    """Let the user accept or edit an AI description."""

    print("\nAI PHOTO ANALYSIS")
    print("-" * 50)
    print(ai_description)
    print("-" * 50)

    while True:
        choice = input(
            "\n[A] Accept  [E] Edit: "
        ).strip().lower()

        if choice == "a":
            return ai_description

        if choice == "e":
            print("\nEnter your corrected description.")
            print(
                "Press Enter on an empty line to finish."
            )

            lines = []

            while True:
                line = input()

                if not line.strip():
                    break

                lines.append(line)

            corrected = "\n".join(lines).strip()

            if corrected:
                return corrected

            print("\nDescription cannot be empty.")

        else:
            print("Please enter A or E.")


def backup_existing_analysis(path: Path) -> Path | None:
    """Back up an existing analysis before overwriting it."""

    if not path.is_file():
        return None

    backup_folder = path.parent / "history"
    backup_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    backup_path = backup_folder / (
        f"{path.stem}.{timestamp}.bak.json"
    )

    shutil.copy2(path, backup_path)

    return backup_path


def save_approved_description(
    photo_path: Path,
    ai_description: str,
    approved_description: str,
    model: str = DEFAULT_MODEL,
    output_folder: Path = DEFAULT_ANALYSIS_FOLDER,
) -> Path:
    """Save an approval, backing up any existing analysis."""

    photo_path = Path(photo_path)
    output_folder = Path(output_folder)

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = analysis_path_for(
        photo_path,
        output_folder,
    )

    data = {
        "photo": photo_path.name,
        "source_photo": str(photo_path.resolve()),
        "model": model,
        "thinking_enabled": False,
        "reviewed_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "ai_description": ai_description,
        "approved_description": approved_description,
        "edited": (
            ai_description != approved_description
        ),
        "approved": True,
    }

    backup_path = backup_existing_analysis(
        output_path
    )

    output_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    if backup_path:
        print(
            f"\nPrevious approval backed up: "
            f"{backup_path.resolve()}"
        )

    return output_path


def main() -> None:
    print("\nLOCAL VIDEO CREATOR")
    print("AI Vision Review - Version 0.4")
    print("=" * 50)

    answer = input(
        "\nEnter photograph path: "
    ).strip().strip('"')

    photo_path = Path(answer).expanduser()

    try:
        if not photo_path.is_file():
            raise FileNotFoundError(
                f"Photograph not found: {photo_path}"
            )

        existing = load_existing_approval(
            photo_path
        )

        if existing:
            print("\nEXISTING APPROVED DESCRIPTION")
            print("-" * 50)
            print(existing["approved_description"])
            print("-" * 50)

            choice = input(
                "\nPress Enter to reuse this approval, "
                "or type R to reanalyze: "
            ).strip().lower()

            if choice != "r":
                print(
                    "\nExisting approval reused. "
                    "No AI analysis performed."
                )
                return

            print(
                "\nReanalysis explicitly requested."
            )

        print("\nAnalyzing photograph...")

        ai_description = analyze_photo(
            photo_path
        )

        approved_description = review_description(
            ai_description
        )

        output_path = save_approved_description(
            photo_path=photo_path,
            ai_description=ai_description,
            approved_description=approved_description,
        )

        print("\nREVIEW COMPLETED")
        print("-" * 50)
        print(approved_description)
        print("-" * 50)
        print(f"Saved to: {output_path.resolve()}")

    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
        OSError,
    ) as error:
        print(f"\nERROR: {error}")


if __name__ == "__main__":
    main()