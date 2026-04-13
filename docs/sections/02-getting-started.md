# 2. Getting Started

## Prerequisites

- **Python** with a virtual environment set up at `.venv/` in the repository root.
- **Dependencies** (installed directly into `.venv/`; no `requirements.txt` or `pyproject.toml` is committed):
  - `PyQt5` — GUI framework.
  - `mido` — MIDI file parsing.
  - `pretty_midi` — MIDI duration and note-list extraction.
  - `opencv-python` (`cv2`) — MP4 frame reading and capture properties.
  - `numpy` — image buffer handling.

## Running the Application

From the repository root:

```bash
# Windows (Git Bash / WSL / PowerShell — adjust path separator as needed)
.venv/Scripts/activate
python -m alignment_tool
```

The entry point is `alignment_tool/__main__.py`, which calls `alignment_tool.app.main()`. That function instantiates a `QApplication`, creates a `MainWindow`, and starts the Qt event loop.

No command-line arguments are currently supported.

## There Are No Tests, Lint, or Build Steps

By design, the current repository has:

- no `tests/` directory
- no linter configuration
- no packaging build

`alignment_engine.py` is deliberately Qt-free and can be imported and tested independently if you choose to add tests later (see [Developer Guide](./10-developer-guide.md)).

## First Run Walkthrough

1. **Launch the app.** You see an empty window with a "No participant loaded" placeholder and a `File` menu.
2. **File → Open Participant** (Ctrl+O). A folder picker appears — choose a participant folder that contains `disklavier/` and `overhead camera/` subdirectories.
3. **Loading.** The tool parses each `.mid` file (using `mido` + `pretty_midi`) and each `.MP4`+`.XML` pair (using XML sidecar + `cv2`). End times are taken from each file's mtime; start times are derived by subtracting the parsed duration. A wait cursor is shown while scanning.
4. **Level 1 timeline appears.** A bar chart with MIDI files (blue, top row) and camera files (orange, bottom row) plotted against a shared time axis.
5. **Apply a global shift** (Phase 1) or **drill into a pair** (Phase 2) — see [Workflows](./07-workflows.md).

## Saving and Loading Alignment State

- **File → Save Alignment…** (Ctrl+S) — pick a destination and the state is written as JSON. See [Data Model and Persistence](./08-data-model-persistence.md) for the schema.
- **File → Load Alignment…** (Ctrl+L) — pick a previously saved JSON. The tool repopulates the state dataclasses, but note that **file paths, `total_frames`, `ticks_per_beat`, and `tempo` are NOT in the JSON**. Level 2 (which needs those) requires re-scanning the participant folder — a current limitation; see [Troubleshooting and FAQ](./11-troubleshooting.md).

## Expected Folder Layout

The loader expects exactly this structure inside the participant folder:

```
<participant_folder>/
├── disklavier/
│   ├── <name>.mid
│   └── ...
└── overhead camera/
    ├── C0001.MP4
    ├── C0001M01.XML     ← XML sidecar name is derived: .MP4 → M01.XML
    ├── C0002.MP4
    ├── C0002M01.XML
    └── ...
```

MP4 files without a matching `M01.XML` sidecar are skipped with a warning printed to stdout.

See [Data Sources and File Layout](./03-data-sources.md) for details on the file formats themselves.
