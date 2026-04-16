# Anchor table

The anchor table is the per-camera-clip list of alignment anchors — the raw data behind Phase 2 of the [two-phase approach](../1-motivation/two-phase-approach.md). It lives at the bottom of Level 2 with a fixed maximum height of 200 px.

## Layout

```
┌────────────────────────────────────────────────────────────────────┐
│ [Alignment Anchors] [ Add Anchor (A) ]          [Delete Selected]  │ ← header row
├───┬──────────────┬─────────────┬──────────────┬───────────────┬────┤
│ # │ MIDI File    │ MIDI Time(s)│ Camera Frame │ Derived Shift │ L  │*│
├───┼──────────────┼─────────────┼──────────────┼───────────────┼────┤
│ 1 │ trial_001.mid│ 12.456      │ 2987         │ 0.0123        │    │*│ ← active
│ 2 │ trial_001.mid│ 47.802      │ 11487        │ 0.0125        │    │ │
│ 3 │ trial_002.mid│ 4.105       │ 984          │ 0.0112        │    │ │ ← greyed out
└───┴──────────────┴─────────────┴──────────────┴───────────────┴────┘
```

## Columns

| # | Column | Meaning |
|---|---|---|
| 0 | `#` | 1-based row number (resizes to fit) |
| 1 | `MIDI File` | `anchor.midi_filename` |
| 2 | `MIDI Time (s)` | `anchor.midi_timestamp_seconds`, 3 decimals |
| 3 | `Camera Frame` | `anchor.camera_frame` |
| 4 | `Derived Shift (s)` | `compute_anchor_shift` output, 4 decimals. `N/A` if the anchor's MIDI file isn't in the current session. |
| 5 | `Label` | `anchor.label` (free text, optional) |
| 6 | `Active` | `*` if this row's anchor is the active one; blank otherwise. Centered; dark green background + white text when active. |

All columns stretch to fit the available width except `#` and `Active`, which resize to their contents. Rows are not editable.

## Header buttons

- **Add Anchor (A)** — injected by Level 2 into the header row (see `add_header_action`). Disabled until both markers are set. Clicking opens an input dialog for an optional label, then calls `AlignmentService.add_anchor` with the anchor built from the markers.
- **Delete Selected** — disabled until a row is selected. Deletes the currently-selected anchor via `AlignmentService.delete_anchor`, which also repairs `active_anchor_index` if the deleted anchor was active (sets it to `None`) or earlier in the list than the active one (shifts it down by 1).

## Filtering

Anchors whose **`midi_filename` doesn't match the currently-selected MIDI combo** are rendered greyed out (grey foreground text) and made non-selectable. They still show every column for reference, but:

- Clicking the `Active` cell is ignored.
- Double-clicking the `MIDI Time` / `Camera Frame` cells is ignored.
- The row cannot be selected, so **Delete Selected** cannot be invoked on them.

This prevents confusion when the same camera clip is viewed against a different MIDI file — only anchors tied to the shown MIDI are actionable.

## Interactions

| Input | Action |
|---|---|
| **Single-click** on the `Active` cell (col 6) | Toggle active. If this row is already active → deactivate (`set_active_anchor(None)`, emit `anchor_deactivated`). Otherwise → activate (`set_active_anchor(row)`, emit `anchor_activated(row)`). Ignored for greyed rows. |
| **Double-click** on `MIDI Time (s)` (col 2) | Emit `midi_time_jump_requested(seconds)` → Level 2 jumps the MIDI panel to that time and makes it the active panel. Ignored for greyed rows. |
| **Double-click** on `Camera Frame` (col 3) | Emit `camera_frame_jump_requested(frame)` → Level 2 jumps the camera panel to that frame and makes it the active panel. Ignored for greyed rows. |
| **Row selection** | Enables/disables **Delete Selected**. Multiple selection is disabled. |

## Signals

| Signal | When |
|---|---|
| `anchor_activated(int)` | A row's Active cell was clicked, setting that row active |
| `anchor_deactivated()` | A row's Active cell was clicked while already active |
| `anchor_deleted(int)` | A row was successfully deleted via **Delete Selected** |
| `midi_time_jump_requested(float)` | Double-click on col 2 |
| `camera_frame_jump_requested(int)` | Double-click on col 3 |

Level 2 catches all five and re-syncs the panels, refreshes the overlap bar, and marks the session dirty as appropriate.

## What the table doesn't do

- No in-place editing — the anchor's MIDI time, camera frame, and label are immutable once created. To "edit" an anchor, delete it and add a new one.
- No multi-select or bulk delete.
- No import/export outside the main save/load. Anchors travel with the session JSON.
