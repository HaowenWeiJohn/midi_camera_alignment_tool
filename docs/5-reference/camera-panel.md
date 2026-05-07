# Camera panel

The camera panel shows video frames for the currently-selected camera clip, with frame-accurate navigation, zoom-and-pan, and a right-click pixel-intensity probe.

## Anatomy

```
┌─────────────────────────────────────┐
│                                     │  ← frame area (QLabel, dark #222 bg)
│          [ video frame ]            │
│              ● (probe dot if any)   │
│                                     │
├─────────────────────────────────────┤
│ Frame: 2987 / 107999 |              │
│ Time: 12.467s / 450.134s | Zoom: 3× │  ← counter label
└─────────────────────────────────────┘
```

The frame area has a minimum size of **320 × 240**. The background is `#222` (dark grey) until a frame is decoded.

## Counter label

Below the frame, one of:

| State | Text |
|---|---|
| No video loaded | `No video loaded` |
| Zoom == 1.0× | `Frame: N / max \| Time: X.XXXs / max.s` |
| Zoom > 1.0× | `Frame: N / max \| Time: X.XXXs / max.s \| Zoom: N.Nx` |

`max = total_frames − 1` (the index of the last frame). Time is computed as `frame / capture_fps`.

## Frame decoding

Video frames are decoded by a background `FrameWorker` (a `QObject` moved onto a dedicated `QThread`). It keeps an LRU cache of the last 32 decoded frames so small back-and-forth scrubbing is fast. Opening a new clip increments an internal generation counter; in-flight decode requests queued before the latest `open_video` are silently discarded.

While a frame decode is in flight, the counter updates immediately but the pixmap only refreshes when the worker replies. On clips where the cv2 capture cannot be opened, the frame area turns **dark red** (`#7a1f1f`) and shows `Video unavailable: {msg}`.

## Zoom

| Input | Action |
|---|---|
| Wheel up | Zoom in by factor `1.25`, centered on cursor |
| Wheel down | Zoom out by factor `0.8`, centered on cursor |
| Double-click (left) | Reset zoom to `1.0×` and pan to `(0, 0)` |

Zoom range is **[1.0×, 20.0×]**. `1.0×` means fit-to-label. Cursor-centered zoom keeps the source pixel under the cursor fixed as the zoom level changes.

At `zoom == 1.0×` the pan is forced to `(0, 0)` — you cannot pan the image off-center when it's fit to the label.

## Pan

When `zoom > 1.0×`, left-mouse press-and-drag pans the image:

- Drag right → image moves right relative to the label (you see more of the left side of the frame).
- Pan is clamped so you can never drag the image past its own edge.
- Pan is reset on double-click and on clip swap.

## Intensity probe

Three ways to drop a **single intensity probe dot** at a source pixel — they all flow through the same `_drop_dot` helper that emits `dot_dropped(src_x, src_y, current_frame)`:

1. **Right-click** (`contextMenuEvent`): drops the dot at the clicked source pixel. Clicks outside the image (e.g. in the letterbox) are silently ignored.
2. **Public method `drop_dot(src_x, src_y)`**: programmatic drop at the given source coords on the current frame. Caller-supplied coords are clamped to `[0, source_w−1] × [0, source_h−1]`. Used by Level 2 when the user double-clicks an anchor's `Probe (x,y)` cell (see [§5.8 Anchor table](anchor-table.md)) and when the user presses ++r++ to re-sample at the current frame (see [§5.7 Intensity plot](intensity-plot.md)).
3. **Property `current_dot_xy → tuple[int, int] | None`**: read the active dot's source coords (or `None` if no dot is set). Level 2 reads this when an anchor is being added so the dot's coords get saved on the new anchor.

Visual: a 5-radius red circle (`rgba(255, 60, 60, 220)`) with a 1 px white outline is drawn on top of the frame. Level 2 forwards every `dot_dropped` to the `IntensityWorker` on its own `QThread` to sample ±120 frames of luma. Dropping a new dot replaces the old one.

The dot persists through scrubbing, zooming, and panning until the clip is swapped, the user calls `clear_dot()` (wired to **Back**), or a new drop replaces it.

## Out-of-range display

In Locked mode, when the MIDI drives the camera and the target frame falls outside the clip, the frame area switches to a neutral grey background (`#555`) with centered white text: `"Camera clip starts in X.XX s"` or `"Camera clip ended X.XX s ago"`. Navigating the camera directly (e.g. wheel, click-drag pan, ++left++/++right++) restores the normal display.

## Keyboard stepping (driven from Level 2)

When the camera panel is the active panel:

- ++left++ / ++right++ — step **1 frame**.
- ++shift+left++ / ++shift+right++ — step **10 frames**.

All seeks clamp to `[0, total_frames − 1]`.

## Signals emitted

| Signal | When |
|---|---|
| `position_changed(int)` | Any time `set_frame` or `step` updates the current frame |
| `user_interacted()` | On wheel, left-click, or double-click (not on programmatic updates from Level 2) |
| `dot_dropped(int, int, int)` | Right-click drops an intensity probe (src_x, src_y, center_frame) |
| `dot_cleared()` | Clip swap, `clear_dot()`, or `close_video()` |
