# Intensity plot

A fixed 120 px tall line-plot widget that shows per-frame pixel luma for the currently-dropped probe dot. Sits below the main splitter in Level 2.

## Anatomy

```
┌────────────────────────────────────────────────────┐
│  220.0│                                            │
│       │    ┌─────┐                                 │
│  150.0│────┘     ╲       ● ● ●                     │
│       │    ● ● ●  ╲     ╱                          │
│   80.0│           ▓ ● ●                            │
│       └──────────────▒────────────────────────────│
│        2860    2880   │2900    2920    2940   (frame)
│                       │↑ drop frame (dotted grey)
│                       ▓ playhead (red)             │
└────────────────────────────────────────────────────┘
```

Dimensions:

- Height: **120 px** (fixed).
- Margins: left 44, right 12, top 10, bottom 20.
- Background: dark grey (`rgb(25, 25, 30)`).

## States

| State | What you see |
|---|---|
| No dot dropped (initial / cleared) | Placeholder text centered: *"Right-click a pixel on the camera to probe its intensity across ±120 frames."* |
| Sampling | Placeholder replaced with *"Sampling ±120 frames…"* (shown immediately on right-click) |
| Sampling failed | *"Sampling failed: {reason}"* |
| Data ready | Full plot as shown above |

## Sample window

Always `±120` frames around the drop frame, clipped to the valid clip range. Out-of-range positions (before frame 0 or past `total_frames − 1`) appear as **gaps** in the polyline, not interpolated across.

Values are **Rec.601 luma** (`0.299 R + 0.587 G + 0.114 B`) averaged over a **3 × 3** patch around the dropped pixel (edge-clamped if the dot is near the frame border).

## Re-centering on the current frame (++r++)

After scrubbing far from the original drop frame, the plot can fall entirely outside `±120` of the playhead, leaving the red playhead line invisible. Press ++r++ to re-sample the same pixel with the **current camera frame** as the new center. Internally this calls `CameraPanelWidget.drop_dot(*current_dot_xy)`, which re-fires the existing `dot_dropped` pipeline; the plot repaints with new bounds and a new dotted-grey center marker. ++r++ is a silent no-op when no probe dot is active.

## Axes and ticks

- **Y axis**: three labels — min, midpoint, and max of the observed luma, with 10 % padding on each side. For totally flat traces, the range is padded symmetrically so the line lands mid-plot.
- **X axis**: tick interval picked from `[1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]` to target about 8 ticks across the visible frame range.

Grid lines are dashed grey; axis labels are lighter grey.

## Markers

- **Drop frame**: dotted grey vertical line at the center frame (where the dot was dropped).
- **Playhead**: red 2 px vertical line at the current camera frame. Only drawn while the playhead is inside the sampled window; falls silent when the camera scrubs outside the window.

## Click to seek

Left-click inside the plot frame emits `frame_seek_requested(frame)`. The frame is clamped to the sampled window; Level 2 re-clamps to the clip's `[0, total_frames − 1]` when it forwards the seek to the camera panel. Hover tracking is not used.

Clicks outside the plot frame (in the margins) are ignored.

## Staleness filter

The underlying `IntensityWorker` processes requests serially — once a `request_window` call starts walking the decoder, it cannot be cancelled mid-loop. Instead, Level 2 stores the `(center_frame, src_x, src_y)` tuple of the latest dot it is waiting on, and when a result arrives, discards it unless the tuple still matches. This covers two races:

1. Clip swap mid-sample — the tuple was nulled, so the late result is dropped.
2. New dot on the same clip mid-sample — the tuple advanced to the new dot, so the old sample is dropped.

The plot therefore always reflects the latest dropped dot or the most recent placeholder message, never a stale trace.

## Persistence

The probe dot's source-pixel coordinates are **saved on each anchor** at `Add Anchor` time as `probe_x` / `probe_y` (see [§5.8 Anchor table](anchor-table.md) and [§6.1 JSON schema](../6-project-files/json-schema.md)). The sampled luma values themselves are not persisted — only the coordinates. To re-render the trace later, double-click the **Probe (x, y)** cell in the anchor table; that re-drops the dot at the same pixel on whatever frame the camera is currently showing and a fresh ±120-frame sample runs.
