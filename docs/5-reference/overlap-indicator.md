# Overlap indicator

A 30 px dual-track navigation bar sitting between the Level 2 top bar and the main splitter. It gives you a shared-time-axis view of the MIDI file and camera clip with their overlap region highlighted, and it is clickable for quick seeking.

## Anatomy

```
┌──────────────────────────────────────────────────────────────────┐
│ ░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░ │ blue MIDI track     │  ← y=2..14
│       ╱╱╱ green overlap region ╱╱╱                               │
│      ██████████████████████████████████████ │ orange Camera track│  ← y=16..28
└──────────────────────────────────────────────────────────────────┘
           ▲                    ▲
           │                    │
     MIDI playhead        Camera playhead
     (white 2 px line)    (white 2 px line)
```

- Top track (y = 2..14) shows the MIDI clip's wall-clock extent in translucent blue.
- Bottom track (y = 16..28) shows the camera clip's wall-clock extent in translucent orange, *after* `effective_shift` has been applied.
- The intersection of the two tracks is drawn as a translucent green overlay across both rows.
- Two white 2 px vertical lines show the current MIDI and camera playheads independently.

The bar is fixed at 30 px tall, inset by 10 px horizontal margins on either side. The cursor is a pointing hand over the widget.

## Time axis

The bar maps the full span `[min(midi_start, aligned_cam_start), max(midi_end, aligned_cam_end)]` onto the drawable width (`width - 20`). Both tracks share the axis, so their relative position is literally what you see.

Changing `effective_shift` redraws the camera track at a new position on the axis; the MIDI track never moves.

## Click to seek

The bar is split horizontally at y = 15:

- **y < 15** — clicking drives the **MIDI panel**. The click's x position is converted to a unix time, then inverted with `midi_unix_start` to get seconds-from-MIDI-start, clamped to `[0, duration]`. The MIDI panel is made the active panel and jumps to that time.
- **y ≥ 15** — clicking drives the **camera panel**. The click's x is converted to a unix time, then to a camera frame via `(t − effective_shift − raw_unix_start) × capture_fps`, clamped to `[0, total_frames − 1]`. The camera panel is made active and jumps to that frame.

## Drag to scrub

Left-mouse press + drag on either track continuously emits seek signals as the cursor moves. Release ends the drag. You can start on the MIDI track and drag into the camera track — the drag stays locked to the track that was clicked first.

## Playheads

Playheads are **independent** from clip extents:

- `set_midi_playhead(midi_unix_time)` places the top track's white line.
- `set_camera_playhead(aligned_camera_unix_time)` places the bottom track's white line.

When a panel is scrubbed, Level 2 pushes its own playhead explicitly. When the two are locked, Level 2 pushes both to the **same** unix timestamp (derived from the frame grid) so the int-pixel rounding can't cause a visible 1-px drift between them.

A playhead that falls outside `[t_min, t_max]` is simply not drawn.

## No playhead when no clip

Calling `clear()` wipes both playheads and both clips; the widget renders an empty dark grey rectangle until a new pair is attached.
