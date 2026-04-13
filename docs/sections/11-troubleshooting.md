# 11. Troubleshooting and FAQ

## 11.1 Loading Problems

### "No .mid or .MP4 files found" after picking a folder

The participant folder must contain `disklavier/` and `overhead camera/` subdirectories exactly (case-sensitive on Linux/macOS; case-insensitive on Windows). Only files ending in `.mid` and `.MP4` are considered. `.midi`, `.mp4` (lowercase), or other variants are ignored by the current loader (`participant_loader.py`).

### "Warning: XML sidecar not found for C00XX.MP4, skipping"

The loader expects a sidecar at `<stem>M01.XML`. If your recordings use a different naming (e.g., `M02`, `M00`), modify `participant_loader.py:48`. MP4s without a sidecar are skipped because the adapter reads `duration_frames` and `capture_fps` from the XML — without it, the clip's wall-clock duration can't be computed. (End time is taken from the MP4's mtime, which *is* always available, but duration still requires the XML.)

### MIDI or camera clip is placed far from where I expect on the Level 1 timeline

Clip start/end are derived from the file's mtime (`os.path.getmtime`) minus duration. If a file has been copied or touched by a tool that doesn't preserve modification times, its mtime reflects *the copy*, not the recording. Symptoms: a single participant's clips look shifted relative to the others, or all clips collapse to roughly the same moment (the time of the bulk copy). The global-shift + anchor workflow can still recover alignment, but the bulk offset will be larger than the usual 1–20 minutes.

### Load is slow

`MidiAdapter.__init__` parses the MIDI file twice (with `mido` and `pretty_midi`). For ~300 s files this is usually tens of milliseconds. If a participant has many very long files it adds up — but it's a one-time cost per Open Participant.

## 11.2 Level 1 Timeline

### All camera bars are far to the right (or left) of the MIDI bars

Expected before Phase 1. Set the global shift to bring them into rough alignment (see [Workflows §7.1](./07-workflows.md)).

### A camera bar shifted when I activated an anchor

Expected. The Level 1 bar for a camera clip is drawn at `raw_unix_start + effective_shift`, where `effective_shift` depends on the active anchor. Activating a different anchor yields a slightly different derived shift, hence a slightly different bar position.

## 11.3 Level 2 — Locked Mode

### The camera panel shows "Camera clip starts in …" and won't update

You're in locked mode but the driver position is outside the follower's range. Either scrub the driver into the overlap region, or press `O` to jump to the overlap start.

### The MIDI combo is grayed out

An anchor is active and locked mode is on. The anchor-lock rule forces the MIDI panel to the anchor's referenced MIDI file. To free the combo, either deactivate the anchor (anchor table → click the `*` cell) or switch to Independent mode.

### Moving one panel doesn't move the other

Check the mode toggle — you may be in Independent mode (the default on entry). Press `L` to switch.

### Arrow keys don't do what I expect

Level 2 has an "active panel" concept — arrows drive whichever is active. The border color indicates it (blue = MIDI, orange = camera). Press `Tab` to switch. See [UI Walkthrough §6.5](./06-ui-walkthrough.md).

## 11.4 Anchors

### "Derived Shift (s)" shows "N/A"

The anchor references a MIDI filename that's not present in the currently loaded state. This can happen after loading a JSON where a `.mid` file was since moved or renamed. Re-open the correct participant folder and ensure the filenames match.

### Anchors disappeared after I changed the global shift

Working as intended. See [Alignment Concepts §4.4](./04-alignment-concepts.md) for the rationale. The confirmation dialog required you to approve this; if you clicked past it quickly, use File → Load Alignment to restore from your last save.

### I can't click "Add Anchor"

Both markers must be set. Press `M` while the MIDI panel is visible to set the MIDI marker; press `C` to set the camera marker. The button's tooltip spells this out.

## 11.5 Video Playback

### Frames look laggy or tear briefly when scrubbing fast

`FrameWorker` processes requests serially. `CameraPanelWidget._on_frame_ready` drops stale frames (any frame index that's no longer the current one), so you'll see the final frame after your scrub settles. Brief visual lag at high scrub speeds is expected.

### `FrameWorker: cannot open <path>`

Prints to stdout when `cv2.VideoCapture` can't open the file. Usually a missing codec or a corrupted file. Check with `ffprobe` or by playing the file in a standard player.

## 11.6 Save / Load

### Loading JSON and entering Level 2 shows "No MIDI loaded" or black frames

Expected after a pure JSON load. `mp4_path`, `file_path`, and `total_frames` are not in the JSON (by design — see [Data Model §8.3](./08-data-model-persistence.md)). To edit a previously-saved alignment in Level 2, use File → Open Participant… to re-scan the media. Level 1 works from the JSON alone.

### Save didn't write the file I expected

The save dialog uses whatever filename you type. There is no default filename suggestion and no automatic `.json` extension if you omit it. Type `name.json` explicitly.

### JSON file is partial / corrupted

There is no atomic-write. If the process is killed mid-write, the file may be truncated. Save early and often; keep versioned copies.

## 11.7 Development Questions

### Where's the math?

`alignment_tool/alignment_engine.py`. All of it. No Qt imports in that module.

### How do I add a test?

There's currently no test scaffolding. You can write a script at the repo root that imports `alignment_tool.alignment_engine` and `alignment_tool.models` and runs assertions — no Qt needed. See [Developer Guide §10.6](./10-developer-guide.md) for suggested first tests.

### How do I add a dependency?

Install it into `.venv/` directly; there's no `requirements.txt` or `pyproject.toml`. If you intend to commit the dependency, add a short install note here and/or in the top-level `CLAUDE.md`.

### The UI freezes when I open a long video

Video metadata (`CameraAdapter._parse_mp4_properties`) opens and closes the file briefly, which can block the UI thread for a moment on slow disks. Level 2 frame reads are off the UI thread, but file **opening** in `ParticipantLoader.load` is synchronous. A wait cursor is shown during the scan; that's the current mitigation.

## 11.8 Known Quirks

- `Level2View._load_midi_file` jumps to `self._midi_adapter.notes[0].start` on load. `PrettyMIDI` orders its notes by note-off, so `notes[0]` is the earliest-*ending* note, not the earliest-*starting*. The difference is usually negligible — see the inline comment in `level2_view.py`.
- Sony FX30 `captureFps`/`formatFps` strings sometimes carry a trailing `p` or `i`. The adapter strips these via `rstrip('pi')` — if another camera uses a trailing `f` (film) or similar, you'll need to extend the parsing.
- `AlignmentState.participant_folder` is kept in memory but not serialized to JSON. This is intentional for portability — absolute folder paths don't round-trip across machines.
