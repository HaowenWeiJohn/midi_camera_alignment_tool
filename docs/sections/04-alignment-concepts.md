# 4. Alignment Concepts and Math

This section is the single source of truth for the math. All of it lives in `alignment_tool/alignment_engine.py`, which has **no Qt imports** and can be exercised without a GUI.

## 4.1 Shifts

### Global Shift — `global_shift_seconds`

A single scalar per participant, held in `AlignmentState.global_shift_seconds`. Applied identically to **every** camera clip. Its default is `0.0`.

It is meant to absorb the participant-wide clock offset between the Disklavier and the Sony FX30.

### Anchor Shift — `anchor_shift` (derived)

An **anchor** is a pair of matched events:

```python
Anchor(
    midi_filename="20250815_144525_pia02_s009_001.mid",
    midi_timestamp_seconds=45.123,   # seconds from MIDI file start
    camera_frame=5678,               # cv2-compatible 0-indexed capture frame
    label="C4 onset"                 # optional operator note
)
```

The derived shift, computed by `compute_anchor_shift` (`alignment_engine.py:10`), is:

```
midi_unix_at_anchor   = midi.unix_start + anchor.midi_timestamp_seconds
camera_unix_at_anchor = camera.raw_unix_start + anchor.camera_frame / camera.capture_fps

anchor_shift          = midi_unix_at_anchor - camera_unix_at_anchor - global_shift
```

`anchor_shift` is **not stored** — it is always recomputed from the anchor pair plus the current `global_shift`. This keeps the raw evidence (the two matched events) as the durable artifact.

> Note: `anchor_shift` depends on `global_shift` in the formula. But because changing `global_shift` clears all anchors (see §4.4), `anchor_shift` is always computed against a stable `global_shift` value — so the dependency is never a source of drift.

### Effective Shift — `effective_shift`

```
effective_shift = global_shift + anchor_shift
```

When no anchor is active (or no anchor exists yet), `anchor_shift = 0` and `effective_shift == global_shift`. Implemented by `compute_effective_shift` / `get_effective_shift_for_camera`:

```python
def get_effective_shift_for_camera(camera, global_shift, midi_files: dict):
    anchor = camera.get_active_anchor()
    if anchor is None:
        return global_shift
    midi = midi_files.get(anchor.midi_filename)
    if midi is None:
        return global_shift
    a_shift = compute_anchor_shift(anchor, camera, midi, global_shift)
    return compute_effective_shift(global_shift, a_shift)
```

## 4.2 Coordinate Conversions

All translations below are used by Level 2 locked-mode navigation (see `level2_view.py`) and by the overlap indicator.

### MIDI → camera (locked mode, MIDI is driver)

```python
camera_unix = midi_unix - effective_shift
frame       = round((camera_unix - camera.raw_unix_start) * camera.capture_fps)
```

Implemented by `midi_unix_to_camera_frame` (`alignment_engine.py:48`). Returns `None` if `frame < 0` or `frame >= camera.total_frames` — the caller uses `out_of_range_delta` to pick an appropriate message.

### Camera → MIDI (locked mode, camera is driver)

```python
camera_unix = camera.raw_unix_start + frame / camera.capture_fps
midi_unix   = camera_unix + effective_shift
midi_seconds_from_file_start = midi_unix - midi.unix_start
```

Implemented by `camera_frame_to_midi_seconds` (`alignment_engine.py:65`). Returns `None` if the result falls outside `[0, midi.duration]`.

### Helpers

- `camera_frame_to_unix(frame, camera)` → `camera.raw_unix_start + frame / camera.capture_fps`.
- `midi_seconds_to_unix(seconds_from_start, midi)` → `midi.unix_start + seconds_from_start`.
- `compute_global_shift_from_markers(midi_unix, camera_unix)` → `midi_unix - camera_unix` (used by the "Compute Global Shift" button in Level 2).

### Out-of-range detection

```python
def out_of_range_delta(midi_unix, effective_shift, camera) -> float | None:
    camera_unix = midi_unix - effective_shift
    if camera_unix < camera.raw_unix_start:
        return camera.raw_unix_start - camera_unix   # positive: starts in X s
    if camera_unix > camera.raw_unix_end:
        return camera.raw_unix_end - camera_unix     # negative: ended X s ago
    return None
```

Positive → camera clip hasn't started yet. Negative → already ended. `None` → in range.

Level 2 turns this into user-facing gray panels with messages like *"Camera clip starts in 1.25 s"* or *"MIDI file ended 8.42 s ago"*.

## 4.3 The Aligned-Time Formula

For any camera file, the aligned (MIDI-equivalent) unix time of a given capture frame is:

```
aligned_camera_unix(frame) = camera.raw_unix_start + frame / camera.capture_fps + effective_shift
```

Equivalently, projected onto the MIDI timeline:

```
aligned_camera_start = camera.raw_unix_start + effective_shift
aligned_camera_end   = camera.raw_unix_end   + effective_shift
```

This is exactly what the Level 1 timeline (`level1_timeline.py:144-147`) uses to position camera bars, and what the overlap indicator (`overlap_indicator.py:73-75`) uses to draw the aligned camera track.

## 4.4 Strict Phase Ordering

The tool enforces a **strict ordering** between Phase 1 and Phase 2:

- **Phase 1** — set `global_shift`. This should be done first, because anchors created in Phase 2 are calibrated relative to whatever `global_shift` is current.
- **Phase 2** — add anchors per camera clip. Each anchor implicitly depends on `global_shift` being fixed, because the operator found matching keypresses by browsing in locked mode under that `global_shift`.

### Rule

> Changing `global_shift` clears **all** anchors across **all** camera clips for the current participant.

Implemented in two places:

- `Level1Widget._on_apply_shift` (`level1_timeline.py:391`) — the user changes the spinner value and clicks Apply.
- `Level2View._on_compute_shift` (`level2_view.py:365`) — the user computes and applies a new global shift from markers.

Both paths count existing anchors via `AlignmentState.total_anchor_count()`, show a confirmation dialog ("Changing global shift will remove all N anchors across M camera clips. Continue?"), and only call `AlignmentState.clear_all_anchors()` on confirm. If the user cancels, the shift is **not** changed.

### Rationale

1. The operator created anchors by visually matching keypresses. If the `global_shift` was "wrong" at that time, those matches may have been against the wrong candidates — clearing anchors forces re-verification.
2. Even if the matches were correct, the **displayed** `anchor_shift` values would all change by exactly `-Δglobal_shift` (the total `effective_shift` is mathematically invariant). That is confusing to review. Clearing keeps the interpretation simple.

## 4.5 The Timeline-Overlap Cases

Once `effective_shift` is applied, the MIDI file occupies `[midi.unix_start, midi.unix_end]` and the camera clip occupies `[raw_cam_start + eff, raw_cam_end + eff]` on the same timeline. There are five cases:

1. **Camera fully within MIDI** — common; camera was recording a subset of a MIDI trial.
2. **MIDI fully within camera** — camera started before MIDI and ran past the end.
3. **Partial overlap — MIDI starts first** — MIDI has data before camera; camera has data after MIDI.
4. **Partial overlap — camera starts first** — symmetric to case 3.
5. **No overlap** — typical during Phase 1 before `global_shift` is set (clips are minutes apart).

In Level 1 all five are visually obvious from the bar chart. In Level 2:

- **Independent mode** — not affected; each panel navigates its own full range.
- **Locked mode** — the driver panel shows data normally; the follower panel either shows data, or a gray "starts in X s" / "ended X s ago" message computed via `out_of_range_delta`.

The `O` key in Level 2 (`_jump_to_overlap`) computes `max(midi_start, aligned_cam_start)` and jumps both panels there, or shows "No Overlap" if the intersection is empty.
