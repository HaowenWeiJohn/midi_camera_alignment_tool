# MIDI panel

The MIDI panel shows a falling-keys piano roll for the currently-selected MIDI file. Notes fall from the top of the canvas toward a red playhead line near the bottom. A fixed piano keyboard is drawn below the falling notes for orientation.

## Coverage

- Pitch range: **MIDI 21 (A0) to 108 (C8)** — the full 88-key piano.
- Keyboard strip is **40 px tall** at the bottom of the canvas.
- Playhead line sits at **97 %** of the canvas height (just above the keyboard).

## Note colouring

Notes are coloured by **velocity**, interpolated across four stops:

| Velocity | Colour |
|---|---|
| 0 | soft blue |
| 64 | green |
| 100 | yellow |
| 127 | loud red |

Hovering a note overlays a 2 px white outline. Hover is cleared when the mouse leaves the panel.

## Time axis

- Notes fall from top (future) to bottom (past); the playhead is at `97 %` from the top.
- **Grid lines** appear every **0.5 s** by default. At wider zooms the interval widens:
    - viewport > 10 s → 1 s grid.
    - viewport > 20 s → 2 s grid.
- Tick labels (e.g. `12.5s`) are drawn in the top-left corner of each grid line.

## Zoom

Mouse wheel zooms the time axis:

- Wheel up → factor `0.8` (zoom in — fewer seconds visible).
- Wheel down → factor `1.25` (zoom out).
- Clamped to **[0.5 s, 60 s]** seconds-per-viewport.

Emits `user_interacted`, so scrolling also activates the MIDI panel for arrow-key navigation.

## Scrub (drag)

Left-mouse **press and drag vertically** to scrub:

- Dragging **down** moves forward in time (notes fall, playhead advances).
- Dragging **up** moves backward.
- The drag uses the live pixels-per-second derived from the current zoom, so the scrub speed scales naturally.

Dragging emits `user_interacted` once at press time and `position_changed` as the time updates.

## Double-click a note

Left double-clicking on a note snaps the playhead to that note's **start** time. The drag state from the preceding press is cancelled so a tiny jitter before release can't move the playhead back. Double-click on empty space has no effect.

## Info label

Below the canvas, a centered label shows:

```
Time: 12.456s / 187.4s  |  Tick: 23913
```

Where `Time` is the current playhead position and MIDI file duration, and `Tick` is the current position expressed in ticks (derived via `current_time × sample_rate`, rounded).

When no MIDI is loaded, the label reads `No MIDI loaded` and the canvas paints `No MIDI loaded` as well.

## Keyboard strip

- White keys are drawn first as light rectangles with faint grey outlines.
- Black keys are drawn on top as narrower (70 % key width) dark rectangles covering the upper 65 % of the keyboard strip.
- C-octave labels (`C1`, `C2`, ..., `C8`) are drawn in the keyboard strip at each C.

The keyboard is purely informational — clicks on it do not trigger anything.

## Arrow-key stepping (driven from Level 2)

When the MIDI panel is the **active panel** (see [§5.3](level-2-view.md) for how activation works), the following shortcuts apply:

- ++left++ / ++right++ — step **1 tick** (`time_resolution` seconds, typically ~0.5 ms at 240 bpm / 480 tpb).
- ++shift+left++ / ++shift+right++ — step **100 ticks**.

Both step amounts are rounded against the MIDI file's duration (`set_position` clamps to `[0, duration]`).

## Out-of-range display

In **Locked** mode, when the camera drives the MIDI and the resulting MIDI time falls outside the MIDI file's range, the canvas is hidden and the info label changes to a plain message (`"MIDI file starts in X.XX s"` or `"MIDI file ended X.XX s ago"`). Navigating MIDI directly (e.g. a drag) restores the normal canvas display.

## Signals emitted

| Signal | When |
|---|---|
| `position_changed(float)` | Any time the playhead moves (via drag, arrow keys, double-click, or `set_position`) |
| `user_interacted()` | On left-mouse press or wheel (not on programmatic updates like arrow keys driven from Level 2) |
