# midi_camera_alignment_tool

A PyQt5 desktop tool for temporally aligning overhead camera recordings (Sony FX30, ~240 fps) to Disklavier MIDI files across a multi-participant piano study. The two recording systems run on unsynchronized clocks with a 1–20 minute constant offset per participant; the tool provides a manual two-phase workflow (global offset → per-clip anchor refinement) and persists the result as JSON.

## Install

```bash
python -m pip install PyQt5 mido pretty_midi opencv-python numpy
```

## Run

```bash
python -m alignment_tool
```

## Expected participant folder layout

```
participant_042/
  disklavier/
    trial_001.mid
    trial_002.mid
    ...
  overhead camera/
    C0001.MP4
    C0001M01.XML
    C0002.MP4
    C0002M01.XML
    ...
```

## Workflow

1. **File → Open Participant** — select the participant folder.
2. **Level 1 — Timeline** — rough bar chart of every MIDI and camera clip by unix timestamp. Enter a "global shift" in seconds and click Apply to move every camera clip until the two tracks roughly line up. Double-click a MIDI/camera pair to drill into Level 2.
3. **Level 2 — Detail View** — side-by-side falling-keys MIDI piano roll + video frame. Mark one MIDI keypress (`M`), mark the same keypress in the video (`C`), then either "Compute Shift" (set the global shift from these two markers) or "Add Anchor" (record a per-clip refinement).
4. **Mode: Locked** — when engaged, scrubbing either panel drives the other using the current effective shift. Use this to spot-check alignment quality.
5. **File → Save Alignment** — writes everything to JSON. **File → Load Alignment** — restores a saved session with no need to re-open the folder.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```bash
pytest tests/ -v
```

All 58 tests are Qt-free and run in well under a second.
