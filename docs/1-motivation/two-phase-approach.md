# The two-phase approach

The tool models a participant's alignment state with two layers of correction:

1. A single **global shift** (seconds) that captures the host-clock offset for the whole participant.
2. Optional per-clip **anchors** that pin a specific MIDI keystroke to a specific camera frame, refining just that clip.

Both layers are simple scalar corrections applied to the *camera* side of the equation. MIDI timestamps are treated as ground truth in seconds from the start of each `.mid` file.

## Phase 1 — Global shift

`AlignmentState.global_shift_seconds` (see `alignment_tool/core/models.py:47-65`) is a **single scalar** applied to every camera clip for the participant. It is the best-effort single number that lines the two tracks up.

You set it by either:

- typing a seconds value into the Level 1 **Global Shift** spinbox and clicking **Apply**, or
- marking one MIDI keystroke and its matching video frame in Level 2 and clicking **Compute Global Shift**.

The two are intended to be used **in sequence**, not as alternatives:

1. **Rough pass on Level 1** — enter an approximate seconds value into the spinbox and click **Apply**. The camera row visibly slides toward the MIDI row; adjust the number until the two tracks are roughly overlapping on the timeline. This is an eyeball exercise — you're aiming for "close enough that the clips overlap," not frame accuracy.
2. **Precise pass on Level 2** — once the tracks visually align, select a MIDI/camera pair and drill into Level 2. There's now enough overlap for you to find the same keystroke in both panels, mark it with ++m++ and ++c++, and click **Compute Global Shift** to derive the exact value from those two markers.

Doing the rough pass first makes the Level 2 step much easier: before the rough alignment, you'd be scrubbing through minutes of empty video looking for a matching keystroke; after the rough alignment, the matching frame is within a few seconds of the MIDI event.

In both cases the tool enforces one **critical invariant**: *changing the global shift invalidates every anchor.* Anchors are defined relative to the current global shift, so a different global shift changes what each anchor means. Rather than silently rewriting them, the tool prompts you to confirm clearing them (`alignment_tool/services/alignment_service.py:27-44`).

## Phase 2 — Per-clip anchors

If the global shift leaves some specific camera clip slightly misaligned (for example, because the camera was briefly stopped and restarted and the mtime-based start time is a little off), you can add an `Anchor` to that clip.

An anchor is a pair of points:

- `midi_filename` + `midi_timestamp_seconds` — the MIDI keystroke, in seconds from the start of that MIDI file.
- `camera_frame` — the 0-indexed frame where the same physical keystroke occurs.

It also carries advisory metadata that the alignment math ignores but the UI uses for navigation: a free-text `label`, and `probe_x` / `probe_y` — the source-pixel coordinates of the intensity probe dot (if any) that was active when the anchor was added. The probe coords let you re-drop the same dot from the anchor table later (see [§5.8 Anchor table](../5-reference/anchor-table.md)) and survive save/load; they are never consulted by `compute_anchor_shift`.

Each camera clip can hold many anchors; exactly one of them may be **active** at a time (`CameraFileInfo.active_anchor_index` in `core/models.py:14-31`). Only the active anchor contributes to that clip's alignment.

## The math

The tool composes both phases into a single `effective_shift` per camera clip. The formulas are in `alignment_tool/core/engine.py:16-52`; stated plainly:

**Anchor shift** — the correction that makes the active anchor exactly match:

```
anchor_shift = (midi.unix_start + anchor.midi_timestamp_seconds)
             − (camera.raw_unix_start + anchor.camera_frame / capture_fps)
             − global_shift
```

**Effective shift** — what actually gets applied to a clip:

```
effective_shift = global_shift + anchor_shift
```

If a clip has **no active anchor**, `anchor_shift` is zero and `effective_shift` equals `global_shift`.

To convert between MIDI time and camera frame (the "Locked" mode's job):

```
camera_unix = midi_unix − effective_shift
camera_frame = round((camera_unix − camera.raw_unix_start) × capture_fps)
```

Out-of-range MIDI times map to "clip starts in X s" or "clip ended X s ago" messages rather than a nonsense frame.

## Session vs. persisted state

Most state persists to the JSON save file. One field deliberately does not:

- `CameraFileInfo.active_anchor_index` is **session-only** — it is reset every time a new pair is loaded in Level 2, every time you press **Back** or **Esc**, and every time a fresh session is started (`core/persistence.py:122-134` has no `active_anchor_index` key). This prevents confusion when reloading a session: all anchors start inactive, and you activate whichever you want.

Everything else — the global shift, every anchor on every clip, every MIDI and camera file descriptor — round-trips through save/load unchanged.
