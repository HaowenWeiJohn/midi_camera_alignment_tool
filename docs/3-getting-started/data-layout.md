# Data layout

Before the tool can open a participant, the participant's recordings must be arranged in a specific folder structure on disk.

## The expected tree

Each participant is a single folder containing two subdirectories:

```
participant_042/
├── disklavier/
│   ├── trial_001.mid
│   ├── trial_002.mid
│   └── ...
└── overhead camera/
    ├── C0001.MP4
    ├── C0001M01.XML
    ├── C0002.MP4
    ├── C0002M01.XML
    └── ...
```

- The top-level folder name is used as `participant_id` in the session and in the saved JSON file.
- **`disklavier/`** contains one `.mid` file per trial. The order is determined alphabetically, so `trial_001.mid` appears before `trial_010.mid` if you use zero-padded names.
- **`overhead camera/`** contains matching `.MP4` and `.XML` pairs. The XML filename is derived from the MP4 stem by appending `M01.XML`, e.g. `C0001.MP4` ↔ `C0001M01.XML`. A case-insensitive fallback is used if the exact uppercase name isn't present.

## Required files per clip

Each camera clip needs both files:

- `C####.MP4` — the video itself.
- `C####M01.XML` — the Sony "non-real-time metadata" sidecar, from which the tool reads `capture_fps` and `duration_frames`.

A clip with a missing XML sidecar is skipped at load time with a warning. See [folder scanning](../2-how-data-is-derived/folder-scanning.md) for the full list of warnings you might see.

## Preserve file modification times

This is the single most important data-handling rule. The tool derives each file's wall-clock end time from its **mtime** (`os.path.getmtime`). If a copy, re-save, or export tool updates the mtime to "now," every `unix_start` and `unix_end` in the resulting session will be wrong by however long ago the recording actually happened.

| Platform | How to copy while preserving mtimes |
|---|---|
| Linux / macOS | `cp --preserve=timestamps src dst` — or `rsync -a src/ dst/` (archive mode preserves times by default) |
| Windows PowerShell | `robocopy src dst /E /COPY:DAT /DCOPY:T` |
| Drag-and-drop in a file manager | Usually preserves mtimes — verify by checking the properties dialog on a copied file |
| Zip / tar archives | Preserve mtimes through compression and extraction; verify after `unzip` / `tar -x` |

If you suspect mtimes have been corrupted, the fastest recovery is to re-align manually: mark one keystroke in a MIDI file, mark the same keystroke in the video, and click **Compute Global Shift** (see [First alignment](../4-tutorials/first-alignment.md)).

## What isn't used

The tool ignores anything outside `disklavier/` and `overhead camera/`: session notes, audio files, extra video formats, thumbnails, and subfolders are all silently skipped. You can keep them in the participant folder without affecting the tool.
