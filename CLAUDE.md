# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Desktop PyQt5 application for temporally aligning overhead camera recordings (Sony FX30, ~240fps) to Disklavier MIDI files in a piano study. Two unsynchronized recording systems have a constant clock offset (1-20 min) per participant. The tool provides a two-phase manual alignment workflow: a global offset applied to all clips, then per-clip anchor refinement.

## Running the Application

```bash
# Activate the virtual environment first
.venv/Scripts/activate    # Windows
# Then run:
python -m alignment_tool
```

There are no tests, linting, or build steps configured. Dependencies are installed directly in `.venv/` (no requirements.txt or pyproject.toml).

## Architecture

The app uses a two-level drill-down UI built with PyQt5's `QStackedWidget`:

**Level 1** (`level1_timeline.py`) — Timeline overview showing all MIDI and camera clips as horizontal bars. Click a MIDI bar + camera bar to drill down to Level 2.

**Level 2** (`level2_view.py`) — Side-by-side alignment detail view containing:
- `midi_panel.py` — Piano roll visualization (custom QPainter, uses cached `NoteData`)
- `camera_panel.py` — Video frame display (delegates to `frame_worker.py` QThread for async cv2 frame extraction with LRU cache)
- `overlap_indicator.py` — Dual-track navigation bar showing temporal overlap
- `anchor_table.py` — CRUD for alignment anchors

**Core non-UI modules:**
- `alignment_engine.py` — Pure functions for all time-math (no Qt dependency). This is the mathematical heart of the tool: anchor shift derivation, effective shift computation, bidirectional MIDI-to-camera frame conversion.
- `models.py` — Dataclasses: `AlignmentState`, `MidiFileInfo`, `CameraFileInfo`, `Anchor`
- `midi_adapter.py` — Wraps `mido` + `pretty_midi` for MIDI file parsing. Derives start time from track_name end-time metadata minus duration.
- `camera_adapter.py` — Parses Sony FX30 XML sidecar metadata + cv2 for MP4 frame count.
- `participant_loader.py` — Discovers files in expected folder structure: `disklavier/*.mid` and `overhead camera/*.MP4` + `.XML` pairs.
- `persistence.py` — JSON serialization of `AlignmentState` (anchors + global shift + metadata; file paths are NOT persisted).

## Key Concepts

**Time representations:**
- `unix` — absolute unix timestamp (float seconds since epoch)
- `midi_timestamp_seconds` — seconds from MIDI file start (relative)
- `camera_frame` — 0-indexed frame number
- `global_shift` — single constant offset per participant (seconds), applied to all camera files
- `anchor_shift` — per-clip refinement derived from an anchor (not stored directly; computed from anchor pair)
- `effective_shift` = `global_shift + anchor_shift`

**Alignment formulas (in `alignment_engine.py`):**
- `anchor_shift = (midi_unix_start + midi_timestamp_seconds) - (raw_camera_unix_start + camera_frame / capture_fps) - global_shift`
- MIDI-driven camera lookup: `frame = round((midi_unix - effective_shift - camera.raw_unix_start) * capture_fps)`
- Camera-driven MIDI lookup: `midi_seconds = (camera.raw_unix_start + frame / capture_fps + effective_shift) - midi.unix_start`

**Locked vs Independent mode (Level 2):** In locked mode, scrubbing one panel drives the other via effective_shift. In independent mode, panels move separately for fine-tuning anchor placement.

## Participant Folder Structure

```
participant_folder/
├── disklavier/
│   ├── file1.mid
│   └── file2.mid
└── overhead camera/
    ├── C0001.MP4
    ├── C0001M01.XML    # XML sidecar derived: .MP4 → M01.XML
    ├── C0002.MP4
    └── C0002M01.XML
```

## Patterns and Conventions

- All custom drawing uses `QPainter` directly (no QGraphicsScene) for performance
- Background video frame extraction runs in a `QThread` (`FrameWorker`) with a 32-frame `OrderedDict` LRU cache
- Inter-widget communication uses PyQt signals/slots exclusively
- Private attributes prefixed with `_`; signals use `snake_case`
- `alignment_engine.py` must remain pure (no Qt imports) so it can be tested independently
