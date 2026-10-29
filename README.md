# Local Video Creator

A guided, Windows-first Python command-line tool for turning a folder of photographs into a vertical video. Build a storyboard, review a numbered contact sheet, render static or gently animated images, and optionally add background music and a cinematic title. Optional local Ollama analysis helps describe photographs and suggest a title.

**Status:** Early CLI release (v0.10). This is a personal, experimental tool, not a polished graphical editor. The `gui/` directory is not part of the documented release workflow.

## How AI is used

Local Video Creator combines a conventional video-processing engine with optional AI assistance.

**Core video creation — no AI required**

Python, Pillow, and FFmpeg handle photograph processing, storyboard creation, Ken Burns zoom/pan effects, background music, cinematic titles, and video rendering. These features work without Ollama.

**AI-assisted features — Ollama required**

Ollama is currently the application's only supported AI inference provider. The tested local model, `qwen3.5:9b`, supports photograph analysis and AI-generated title suggestions. AI-generated motion recommendations may also be used when available and approved.

If Ollama is not installed or AI analysis is skipped, the application continues using its conventional video-processing capabilities. No alternative AI provider automatically takes over.

**AI-assisted development is different from AI-powered operation.** AI coding assistants helped develop this application, but users do not need an AI model to create videos.

## Quick start (Windows / PowerShell)

### Prerequisites

- **Python:** Developed and tested using Python 3.14. Other versions have not been verified for this release.
- **FFmpeg:** Install an FFmpeg distribution containing both `ffmpeg` and `ffprobe`; ensure both executables are available on your system `PATH`.
- **Pillow:** Installed using `requirements.txt`.
- **Optional — Ollama:** Install and run Ollama if you want local AI photograph analysis or title suggestions. Ollama is the only AI provider currently supported. The tested model is `qwen3.5:9b`. Video creation does not require Ollama when AI features are skipped.

From the repository root:

```powershell
python -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
python -m cli.main
```

If Python is not found, install Python and reopen PowerShell. If FFmpeg commands are not found, fix the FFmpeg installation and `PATH` before rendering.

For optional local AI, start Ollama, ensure the model is available, and then run the CLI:

```powershell
ollama pull qwen3.5:9b
ollama list
python -m cli.main
```

The AI integration expects a local Ollama service (normally `http://localhost:11434`). Ollama setup and model download require an internet connection; the analysis itself is intended to run locally once the model is installed.

## User manual

### 1. Create or reopen a project

Launch `python -m cli.main`. At the project prompt, **enter a descriptive project name. Spaces are allowed; folder names are generated automatically.** For example, `Autumn Morning Walk` becomes `projects/autumn-morning-walk/`. Confirm creation, or choose to reuse an existing project folder.

Each project has its own storyboard, analysis files, and video outputs. Reusing a project does not automatically erase its previous storyboard or video.

### 2. Select photographs

At **Photograph folder**, press **Enter** to browse for a folder, or paste its full path. The folder can have **any name**; it does not need to be called `ai-ready`. Supported photograph extensions are **JPG, JPEG, and PNG**. Review the numbered list of discovered photographs.

### 3. Review the storyboard and contact sheet

The CLI creates a `storyboard.csv` and a numbered `contact-sheet.jpg`. When an existing storyboard is detected, press **Enter** to reuse it or type **R** to regenerate it. Check the displayed total duration and the contact sheet before rendering. A regenerated storyboard can change ordering or timing, so review it before proceeding.

### 4. Optional local AI analysis

Answer **Y** to analyze photographs with the configured local Ollama model, or **N** to skip. The CLI provides an approval/review workflow for descriptions. AI output is a suggestion: review it rather than assuming every description is accurate. You can render a video without running AI analysis.

### 5. Render the video

Answer **Y** at **Render video now?** and select a mode:

- **1 — Static photographs:** Standard still-image video.
- **2 — Ken Burns motion:** Gentle zoom/pan movement; uses saved, approved AI motion settings where available, with fallback motion otherwise.

Rendering produces `final-video.mp4`. Answer **N** to skip rendering; without an existing `final-video.mp4`, subsequent music/title stages will report that they are unavailable. That message is expected, not a crash.

### 6. Optional background music

If a rendered video exists, choose whether to add music. Select an **MP3** by browsing or pasting a full path. The CLI produces `final-video-with-music.mp4`, preserving the original video. The music stage applies a short fade-in and fade-out.

Only use audio you own or have permission to include, particularly for social media uploads.

### 7. Optional cinematic title

If a video exists, choose whether to add a title. If a music version is available, you can title either the original video or the music version. Choose a locally suggested title (when available), enter your own title, or skip. The title is burned into a new `final-video-with-title.mp4`, using a lower-third style during the first few seconds.

**Which file should I share?** Use `final-video-with-title.mp4` if you added a title, `final-video-with-music.mp4` if you added music but no title, or `final-video.mp4` if you used neither. Inspect the chosen file before uploading it.

## Where files are saved

Each named project lives under `projects/<project-name>/` in the repository root. Common outputs include:

```text
projects/
  autumn-morning-walk/
    storyboard.csv
    contact-sheet.jpg
    analysis/                   # when AI analysis is used
    final-video.mp4             # after rendering
    final-video-with-music.mp4  # if music is added
    final-video-with-title.mp4  # if a title is added
```

Some files appear only after their corresponding step. Project data, photographs, generated media, and local music are excluded from Git by the supplied `.gitignore`. Keep personal media outside the repository when possible, and always inspect `git status` before publishing.

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| `No module named PIL` | Run `python -m pip install -r requirements.txt` using the same Python that launches the CLI. |
| `ffmpeg` or `ffprobe` not found | Install FFmpeg with FFprobe, add its `bin` directory to `PATH`, reopen PowerShell, and run `ffmpeg -version` and `ffprobe -version`. |
| No photographs found | Confirm the selected folder exists and contains `.jpg`, `.jpeg`, or `.png` files directly in the selected folder. |
| Folder browser does not appear | Paste the full folder path at the prompt instead. |
| Ollama connection/model error | Start Ollama, check `ollama list`, and install `qwen3.5:9b` if needed; or answer **N** to skip AI analysis. |
| Existing storyboard prompt appears | Press **Enter** to reuse; type **R** only when you want to regenerate. |
| Music/title processing unavailable | Render a video first, or confirm `final-video.mp4` exists in the current project's output folder. |
| MP3 rejected | Select an existing `.mp3` file; other audio formats are not supported by the current picker. |
| Title fails to render | Check that FFmpeg supports the `drawtext` filter (`ffmpeg -filters`) and that the configured font exists. The default font path is Windows-specific. |
| A brief console window flashes | Current Windows subprocess calls use `CREATE_NO_WINDOW`; if flashing persists, record which stage triggered it. |
| `No module named pytest` | For development tests only, install `pytest` with `python -m pip install pytest`. |

## Testing

From the repository root, with `pytest` installed:

```powershell
python -m pytest -q
```

The development environment reported **10 tests and 4 subtests passing** after the console-window update. This is not a guarantee of compatibility on every machine. Check the output MP4 in a video player before publishing.

## Privacy, safety, and limitations

- Video processing uses locally installed Python, Pillow, and FFmpeg. Optional AI analysis uses a locally configured Ollama endpoint; the application is not intended to upload your photographs to a cloud AI service.
- Verify the model endpoint and any local configuration before processing private photographs. Other software or services you choose to use may have their own privacy policies.
- The application is currently guided through the **CLI**; a polished GUI, automated installer, and broad cross-platform testing are not provided.
- The cinematic-title default font is a Windows font; non-Windows environments may require code/configuration changes.
- AI descriptions and title suggestions can be inaccurate. Users remain responsible for reviewing outputs and ensuring rights to photographs and music.
- Existing outputs may require explicit confirmation before replacement. Keep backups of important projects.

## AI-assisted development and attribution

**Local Video Creator is a human-directed, AI-assisted software project developed under the Backyard Labs initiative.**

The project owner defined the goals, requirements, creative direction, workflows, and acceptance criteria. AI coding assistants contributed substantially to Python implementation, debugging, documentation, and technical problem-solving. Development involved iterative experimentation, hands-on testing, evaluation, and refinement.

**No claim is made that all source code was manually authored by the project owner.** The project explores how human direction and AI-assisted development can turn a practical idea into a working creative tool.

## License

Local Video Creator is distributed under the MIT License. See [LICENSE](LICENSE) for details.