"""Local Video Creator — local AI motion advice with human approval.

Motion recommendations are not applied to video automatically.
Approved motions are saved separately from approved photo descriptions.
"""

import base64
import json
import math
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.vision import DEFAULT_MODEL, OLLAMA_URL, load_existing_approval

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOTION_FOLDER = PROJECT_ROOT / "projects" / "first-cli-test" / "motion"
MOTION_KINDS = {
    "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"
}
DEFAULT_MOTION = {
    "kind": "zoom_in",
    "zoom_percent": 2.0,
    "focal_point": [0.5, 0.5],
    "reason": "Safe default motion selected by the user.",
}


def validate_recommendation(data: dict) -> dict:
    """Validate and normalize an untrusted motion recommendation."""
    if not isinstance(data, dict):
        raise ValueError("Motion recommendation must be a JSON object.")
    kind = data.get("kind")
    if kind not in MOTION_KINDS:
        raise ValueError(f"Unsupported motion kind: {kind!r}")
    zoom = data.get("zoom_percent")
    if isinstance(zoom, bool) or not isinstance(zoom, (int, float)):
        raise ValueError("zoom_percent must be a number.")
    if not math.isfinite(zoom) or not 0 <= zoom <= 5:
        raise ValueError("zoom_percent must be between 0 and 5.")
    focal = data.get("focal_point")
    if not isinstance(focal, list) or len(focal) != 2:
        raise ValueError("focal_point must be a two-number array.")
    for value in focal:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("focal_point coordinates must be numbers.")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("focal_point coordinates must be between 0 and 1.")
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a nonempty string.")
    return {
        "kind": kind,
        "zoom_percent": float(zoom),
        "focal_point": [float(focal[0]), float(focal[1])],
        "reason": reason.strip(),
    }


def recommend_motion(
    photo_path: Path, model: str = DEFAULT_MODEL, timeout: int = 180
) -> dict:
    """Ask local Qwen for a recommendation; never auto-approve."""
    photo_path = Path(photo_path).expanduser()
    if not photo_path.is_file():
        raise FileNotFoundError(f"Photograph not found: {photo_path}")
    if photo_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("Supported image formats: JPG, JPEG, PNG.")

    existing = load_existing_approval(photo_path)
    description = (
        existing["approved_description"] if existing else
        "No human-approved description is available. Rely on the image."
    )
    prompt = (
        "You are advising a gentle Ken Burns effect for a still-photo video. "
        "Use the image as the visual source and the human-approved description "
        "as context; do not invent objects. Suggest exactly one motion. "
        "Allowed kind: zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down. "
        "zoom_percent is a subtle 0 to 5 percent. "
        "focal_point is [x,y], each normalized from 0 to 1. "
        "Return ONLY a JSON object with keys kind, zoom_percent, focal_point, reason. "
        'Example: {"kind":"zoom_in","zoom_percent":2.0,'
        '"focal_point":[0.5,0.5],"reason":"Draw attention to the path."}.\n'
        f"Approved description: {description}"
    )
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": "json",
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(photo_path.read_bytes()).decode("ascii")],
        }],
        "options": {"temperature": 0.2},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(
            "Ollama motion recommendation failed or timed out."
        ) from error
    content = result.get("message", {}).get("content", "")
    try:
        return validate_recommendation(json.loads(content))
    except (ValueError, TypeError) as error:
        raise RuntimeError(
            f"Invalid Qwen motion recommendation: {error}"
        ) from error


def motion_path_for(
    photo_path: Path, output_folder: Path = DEFAULT_MOTION_FOLDER
) -> Path:
    return Path(output_folder) / f"{Path(photo_path).stem}.motion.json"


def load_approved_motion(
    photo_path: Path, output_folder: Path = DEFAULT_MOTION_FOLDER
) -> dict | None:
    path = motion_path_for(photo_path, output_folder)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read motion approval: {path}") from error
    if not isinstance(data, dict):
        raise RuntimeError("Existing motion approval has an invalid format.")
    if data.get("source_photo") != str(Path(photo_path).resolve()):
        raise RuntimeError("Motion approval belongs to another photograph.")
    if data.get("approved") is not True:
        return None
    try:
        data["approved_motion"] = validate_recommendation(data["approved_motion"])
    except (KeyError, ValueError, TypeError) as error:
        raise RuntimeError("Saved motion approval is invalid.") from error
    return data


def backup_existing_motion(path: Path) -> Path | None:
    if not path.is_file():
        return None
    history = path.parent / "history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = history / f"{path.stem}.{stamp}.bak.json"
    shutil.copy2(path, backup)
    return backup


def save_approved_motion(
    photo_path: Path,
    ai_recommendation: dict,
    approved_motion: dict,
    model: str = DEFAULT_MODEL,
    output_folder: Path = DEFAULT_MOTION_FOLDER,
) -> Path:
    """Save an explicitly accepted or edited motion, backing up old data."""
    photo_path = Path(photo_path)
    if not photo_path.is_file():
        raise FileNotFoundError(f"Photograph not found: {photo_path}")
    original = validate_recommendation(ai_recommendation)
    approved = validate_recommendation(approved_motion)
    path = motion_path_for(photo_path, output_folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "photo": photo_path.name,
        "source_photo": str(photo_path.resolve()),
        "model": model,
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "ai_recommendation": original,
        "approved_motion": approved,
        "edited": original != approved,
        "approved": True,
    }
    backup = backup_existing_motion(path)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if backup:
        print(f"Previous motion approval backed up: {backup.resolve()}")
    return path


def review_motion(recommendation: dict) -> dict | None:
    """Return approved motion or None when rejected."""
    recommendation = validate_recommendation(recommendation)
    print("\nQWEN MOTION RECOMMENDATION (NOT APPROVED)")
    print(json.dumps(recommendation, indent=2))
    while True:
        choice = input("\n[A] Accept  [E] Edit  [R] Reject: ").strip().lower()
        if choice == "a":
            return recommendation
        if choice == "r":
            return None
        if choice != "e":
            print("Please enter A, E, or R.")
            continue
        print("\nPress Enter to keep each existing value.")
        try:
            kind = input(f"Motion kind [{recommendation['kind']}]: ").strip()
            zoom = input(f"Zoom percent [{recommendation['zoom_percent']}]: ").strip()
            x = input(f"Focal X [{recommendation['focal_point'][0]}]: ").strip()
            y = input(f"Focal Y [{recommendation['focal_point'][1]}]: ").strip()
            reason = input(f"Reason [{recommendation['reason']}]: ").strip()
            candidate = {
                "kind": kind or recommendation["kind"],
                "zoom_percent": float(zoom) if zoom else recommendation["zoom_percent"],
                "focal_point": [
                    float(x) if x else recommendation["focal_point"][0],
                    float(y) if y else recommendation["focal_point"][1],
                ],
                "reason": reason or recommendation["reason"],
            }
            candidate = validate_recommendation(candidate)
        except ValueError as error:
            print(f"Invalid edit: {error}. Try again.")
            continue
        print("\nEDITED MOTION")
        print(json.dumps(candidate, indent=2))
        confirm = input("Accept this edited motion? [Y/N]: ").strip().lower()
        if confirm in {"y", "yes"}:
            return candidate
        print("Edit not accepted; returning to original recommendation.")


def main() -> None:
    print("\nLOCAL VIDEO CREATOR — AI MOTION REVIEW")
    photo = Path(input("Enter photograph path: ").strip().strip('"')).expanduser()
    try:
        if not photo.is_file():
            raise FileNotFoundError(f"Photograph not found: {photo}")
        existing = load_approved_motion(photo)
        if existing:
            print("\nEXISTING APPROVED MOTION")
            print(json.dumps(existing["approved_motion"], indent=2))
            choice = input(
                "Press Enter to reuse, or type R for a new recommendation: "
            ).strip().lower()
            if choice != "r":
                print("Existing motion approval reused. No changes saved.")
                return
        print("\nRequesting local Qwen recommendation...")
        suggested = recommend_motion(photo)
        approved = review_motion(suggested)
        if approved is None:
            print("\nRecommendation rejected. No changes saved.")
            print("Safe session fallback (not saved):")
            print(json.dumps(DEFAULT_MOTION, indent=2))
            return
        path = save_approved_motion(photo, suggested, approved)
        print(f"\nApproved motion saved: {path.resolve()}")
        print(json.dumps(approved, indent=2))
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        print(f"\nERROR: {error}")


if __name__ == "__main__":
    main()