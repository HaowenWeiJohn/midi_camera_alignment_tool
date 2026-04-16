# Folder scanning

When you choose **File → Open Participant**, the tool runs `ParticipantLoader.load(folder)` to build a fresh `AlignmentState` from everything it can find on disk. This page documents exactly what it scans, what it skips, and which warnings you can expect to see.

Source: `alignment_tool/io/participant_loader.py`.

## Expected layout

```
participant_042/                  ← you select this folder
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

The `participant_id` shown in the status bar and window title is simply the **last component** of the folder path (`participant_042` in the example above).

Both subdirectories are optional at load time:

- If `disklavier/` is missing, no MIDI files are loaded and the MIDI side of the timeline is empty.
- If `overhead camera/` is missing, no camera clips are loaded.
- If **both** are missing, you get a warning dialog reading *"No .mid or .MP4 files found in: …"* and the participant is not opened.

## How MIDI files are discovered

`disklavier/` is listed, sorted alphabetically, and every file with a `.mid` extension (case-insensitive) is passed to `MidiAdapter`. If the adapter raises a `MediaLoadError`, that file is skipped and the error reason is added to the warnings list.

## How camera clips are matched

For each `.MP4` in `overhead camera/` (also case-insensitive), the loader constructs the expected XML sidecar name by appending `M01.XML` to the MP4 stem:

```
C0001.MP4 → C0001M01.XML
```

If that exact uppercase filename isn't present, the loader falls back to a **case-insensitive scan** of the camera directory for a matching stem. This handles filesystems where the XML came back from the camera with lowercase extensions, or where a previous copy normalized names.

If no XML sidecar can be found by either rule, the MP4 is skipped and the warning `"C0001.MP4: XML sidecar not found"` is added to the list. If both files are present but either adapter (XML parse, cv2 open) fails, the clip is skipped with the adapter's reason as the warning.

## Warnings

All warnings from a load are aggregated into a single `QMessageBox.warning` shown after the main window updates. The format is:

```
N file(s) were skipped:

• trial_007.mid: reason…
• C0004.MP4: XML sidecar not found
```

A non-empty warnings list does not block loading — everything that parsed successfully is still available on the timeline. You can re-open the participant later after fixing the files on disk.

## What is NOT scanned

The loader does not look at any files outside `disklavier/` and `overhead camera/`. Extra files, other subfolders, and hidden files are ignored silently. There is no recursion — only the direct children of each expected subdirectory are read.

## After loading

Once the state is built, all numeric fields come from the adapters described on the previous two pages ([MIDI](midi-files.md), [Camera](camera-files.md)). No automatic alignment is attempted — `global_shift_seconds` starts at `0.0` and every camera clip has an empty `alignment_anchors` list. The rest of the workflow is your job.
