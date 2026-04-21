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

## Documentation

**📖 [Read the docs](https://haowenweijohn.github.io/midi_camera_alignment_tool/)**

## Tests

```bash
pytest tests/ -v
```

All 58 tests are Qt-free and run in well under a second.
