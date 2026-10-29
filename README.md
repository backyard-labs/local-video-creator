# Local Video Creator

Local Video Creator is a guided, Windows-first Python command-line application for turning photographs into vertical videos. It creates a numbered contact sheet and CSV storyboard, renders still images or gentle Ken Burns motion, and can add MP3 background music and a cinematic title. Optional **local Ollama AI** can describe photographs and suggest titles.

**Status:** Early, experimental CLI release (v0.10). A graphical editor, Windows installer, and broad cross-platform support are **not** included in the published release.

## How AI is used

**Core video creation does not require AI.** Python, Pillow, and FFmpeg handle photo preparation, storyboard creation, conventional Ken Burns motion, background music, titles, and video rendering. These features work when Ollama is unavailable or skipped.

**Optional AI features require Ollama.** The only integrated AI inference provider in v0.10 is a local Ollama service. The tested model, `qwen3.5:9b`, supports photograph descriptions and title suggestions. The renderer can also use **previously saved, human-approved** motion recommendations where available; the main video-creation CLI does **not** automatically request new AI motion recommendations during rendering. Otherwise it uses conventional fallback motion.

AI-generated descriptions and suggestions require human review. No cloud AI provider automatically takes over if Ollama is unavailable.

**AI-assisted development is different from AI-powered operation:** AI coding assistants contributed to building this software, but no AI model is required to create a video.

## Quick start (Windows / PowerShell)

### Prerequisites

- **Python:** Developed and tested with Python 3.14; other versions have not been verified for this release.
- **FFmpeg and FFprobe:** Install an FFmpeg distribution containing both executables and make sure both are on your `PATH`.
- **Pillow:** Installed from `requirements.txt`.
- **Optional Ollama:** Needed only for local AI features. The tested model is `qwen3.5:9b`.

### Get and run the application

Clone the public repository with Git:

```powershell
git clone https://github.com/backyard-labs/local-video-creator.git
cd local-video-creator
python -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
python -m cli.main
```

Alternatively, download the repository's source ZIP from GitHub, extract it, open PowerShell in the extracted project directory, and run the installation and launch commands starting with `python -m pip install -r requirements.txt`.

If `python`, `ffmpeg`, or `ffprobe` is not recognized, install the missing program, check your `PATH`, and reopen PowerShell.

### Enable optional local AI

Install and start Ollama, then download the tested model:

```powershell
ollama pull qwen3.5:9b
ollama list
python -m cli.main
```

The AI integration expects a local Ollama service at `http://127.0.0.1:11434`. Internet access is needed to obtain Ollama and download the model, but the application is designed to send its AI requests to the local Ollama endpoint. Without Ollama, skip AI analysis and enter a title manually if desired.

## User manual

### 1. Create or reopen a project

Launch `python -m cli.main`. Enter a descriptive project name when prompted. **Spaces are allowed** and the application converts the name into a folder-friendly slug: for example, `Autumn Morning Walk` becomes `projects/autumn-morning-walk/`. Confirm creation of a new project or reuse of an existing one.

Projects have separate storyboards, analysis records, and output videos. Reopening a project does not automatically delete existing files.

### 2. Choose photographs

At the **Photograph folder** prompt, press **Enter** to open the Windows folder picker or paste the full folder path. The folder may have **any name**; it does not need to be called `ai-ready`.

Supported formats are `.jpg`, `.jpeg`, and `.png` (case-insensitive). The CLI finds supported files **directly in the selected folder**, not recursively in subfolders, and displays a numbered list. By default, photographs are discovered in filename order.

### 3. Create or reuse the storyboard and contact sheet

The application creates `storyboard.csv` and `contact-sheet.jpg` in the named project folder. A new default storyboard assigns **3 seconds per photograph**. Review the printed total duration and numbered contact sheet before rendering.

If a storyboard already exists, press **Enter** to reuse it or type **R** to regenerate it. Regeneration saves a timestamped copy of the previous CSV under `storyboard-history/`. The existing storyboard must match the photographs discovered in the selected folder; if it does not, the CLI reports an error rather than silently replacing it.

The CSV stores photo order and duration. This release is a guided CLI workflow, not an interactive drag-and-drop storyboard editor.

### 4. Optionally analyze photographs with local AI

Answer **Y** to **Run AI analysis for these photographs?** to analyze them through Ollama, or **N** to skip. The CLI presents descriptions for acceptance or editing, saves approved results, and can reuse earlier approvals. Batch analysis can be paused and resumed by rerunning the project; an `analysis-summary.json` file records approved and pending counts.

AI descriptions can be inaccurate. Review them before accepting. If Ollama is unavailable, choose **N** and continue creating the video without AI.

### 5. Render the video

Answer **Y** to **Render video now?** and select:

- **1 — Static photographs:** A still-image video.
- **2 — Ken Burns motion:** Gentle pan/zoom effects. Previously saved, human-approved motion settings may be used when found; otherwise the renderer uses its built-in fallback motion.

The base output is `final-video.mp4`, rendered in a **1080 × 1920 vertical (9:16)** format with the default settings. The CLI asks before replacing an existing base video.

**Current limitation:** The renderer's default approved-motion lookup is not explicitly scoped to the active named project by the main CLI. Consequently, motion approvals stored under a named project's own folder should **not** be assumed to load automatically. The built-in Ken Burns fallback remains available. This behavior is tracked for investigation; it is not a prerequisite for rendering.

Answering **N** skips rendering. If no `final-video.mp4` already exists, later music and title steps will report that processing is unavailable. This is expected, not a crash.

### 6. Optionally add MP3 background music

When a base video exists, answer **Y** to add music. Press **Enter** to browse for an MP3 or paste its full path. The application produces `final-video-with-music.mp4` while retaining `final-video.mp4`. The audio processing uses a **1-second fade-in** and **2-second fade-out**, adjusted when necessary for short videos.

Use only music you own or are authorized to use, especially for social-media posts.

### 7. Optionally add a cinematic title

When a base video exists, choose whether to add a title. If a music version exists, the CLI lets you choose between titling the original video and the music version (music is the default selection).

You can enter your own title, request a local AI suggestion, or skip the title. **AI title suggestions require both a working Ollama service and previously approved photo descriptions**; without those, enter a title yourself. A suggested title must be reviewed and accepted before use.

The title is burned into `final-video-with-title.mp4` in a lower-third style during the **first four seconds**, with fade-in and fade-out. The original input video is preserved.

**Which MP4 should I share?** Select `final-video-with-title.mp4` if you added a title; otherwise `final-video-with-music.mp4` if you added music; otherwise `final-video.mp4`. Preview the selected file before posting.

## Project files and outputs

Each project is stored under `projects/<project-slug>/` within the repository checkout. Example:

```text
projects/
  autumn-morning-walk/
    storyboard.csv
    storyboard-history/           # only after storyboard regeneration
    contact-sheet.jpg
    analysis/                     # approved photo descriptions, if used
    analysis-summary.json         # after a batch AI-analysis run
    final-video.mp4               # after rendering
    final-video-with-music.mp4    # if music is added
    final-video-with-title.mp4    # if a title is added
```

Previously saved motion approval records may exist in a `motion/` directory when created through the separate motion-advisor workflow; see the current limitation under **Render the video**. Not every file or folder appears in every project.

The supplied `.gitignore` excludes `projects/`, `music-library/`, generated video and audio formats, caches, and common local secret files. These exclusions help avoid accidental commits but are not a substitute for reviewing `git status` before publishing.

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| `python` not found | Install Python, confirm it is available on `PATH`, and reopen PowerShell. |
| `No module named PIL` | Run `python -m pip install -r requirements.txt` with the same Python used to launch the CLI. |
| `ffmpeg` or `ffprobe` not found | Install both tools, add the FFmpeg `bin` directory to `PATH`, reopen PowerShell, and verify `ffmpeg -version` and `ffprobe -version`. |
| No photographs found | Check that the chosen folder directly contains JPG, JPEG, or PNG files; subfolders are not scanned. |
| Windows folder or file picker unavailable | Paste the full path at the prompt instead. |
| Existing storyboard does not match photos | Recheck the selected photograph folder and filenames; the CLI protects the existing storyboard instead of overwriting it. |
| Existing storyboard prompt appears | Press **Enter** to reuse or **R** to regenerate with a backup. |
| Ollama connection or model error | Start Ollama, check `ollama list`, install `qwen3.5:9b` if necessary, or skip AI analysis. |
| AI title suggestion unavailable | Confirm that Ollama is running **and** approved photograph descriptions exist, or enter a custom title. |
| Ken Burns motion does not reflect a saved AI recommendation | The main CLI may not locate approvals in the active named project's motion directory; fallback motion can still render. |
| Music/title processing unavailable | Render a base video first or confirm `final-video.mp4` exists in the active project folder. |
| MP3 selection rejected | Choose an existing `.mp3` file; the current picker does not accept other audio formats. |
| Title rendering fails | Check that FFmpeg includes the `drawtext` filter (`ffmpeg -filters`) and that the configured Windows font exists. |
| A brief console window flashes | Windows subprocess calls attempt to suppress extra console windows; note the stage if flashing persists. |
| `No module named pytest` | For development tests only, run `python -m pip install pytest`. |

## Testing

Install `pytest` if you want to run the included development tests:

```powershell
python -m pip install pytest
python -m pytest -q
```

In the original development environment, **10 tests and 4 subtests passed** after the Windows console-window update. This is a historical test result, not a guarantee for every machine. Always play and inspect the resulting MP4 before publishing.

## Privacy, rights, and limitations

- Video processing uses locally installed Python, Pillow, and FFmpeg. The application's optional AI requests target a locally configured Ollama endpoint; it is **not designed to upload photographs to a cloud AI service**.
- Verify your Ollama endpoint and other installed software before using sensitive photographs. Third-party software and services have their own terms and privacy behavior.
- This is a **CLI application**, not a graphical editor. No Windows installer or broad cross-platform compatibility is provided in v0.10.
- The title renderer uses a Windows-specific default font; other operating systems may need configuration changes.
- AI-generated descriptions, titles, and motion advice may be incorrect or unsuitable; review and approve outputs yourself.
- Users are responsible for having rights to the photographs, audio, fonts, and other media they distribute.
- The CLI asks before replacing several existing video outputs; retain backups of important work.

## AI-assisted development and attribution

**Local Video Creator is a human-directed, AI-assisted software project developed under the Backyard Labs initiative.**

The project owner defined the goals, requirements, creative direction, workflows, and acceptance criteria. AI coding assistants contributed substantially to Python implementation, debugging, documentation, and technical problem-solving. Development involved iterative experimentation, hands-on testing, evaluation, and refinement.

**No claim is made that all source code was manually authored by the project owner.** The project explores how human direction and AI-assisted development can turn a practical idea into a working creative tool.

## License

Local Video Creator is distributed under the **MIT License**. See [LICENSE](LICENSE) for the full terms. The software license does not grant rights to third-party photographs, music, fonts, or other media.