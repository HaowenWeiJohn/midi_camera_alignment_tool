# Anchor table

The anchor table is the per-camera-clip list of alignment anchors — the raw data behind Phase 2 of the [two-phase approach](../1-motivation/two-phase-approach.md). It lives at the bottom of Level 2 with a fixed maximum height of 200 px.

## Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [Alignment Anchors] [ Add Anchor (A) ]                    [Delete Selected]  │ ← header row
├───┬──────────────┬─────────────┬──────────────┬────────────┬───────────────┬────┤
│ # │ MIDI File    │ MIDI Time(s)│ Camera Frame │ Probe(x,y) │ Derived Shift │ L  │*│
├───┼──────────────┼─────────────┼──────────────┼────────────┼───────────────┼────┤
│ 1 │ trial_001.mid│ 12.456      │ 2987         │ (812, 430) │ 0.0123        │    │*│ ← active
│ 2 │ trial_001.mid│ 47.802      │ 11487        │ —          │ 0.0125        │    │ │
│ 3 │ trial_002.mid│ 4.105       │ 984          │ (210, 380) │ 0.0112        │    │ │ ← greyed out
└───┴──────────────┴─────────────┴──────────────┴────────────┴───────────────┴────┘
```

## Columns

| # | Column | Meaning |
|---|---|---|
| 0 | `#` | 1-based row number (resizes to fit) |
| 1 | `MIDI File` | `anchor.midi_filename` |
| 2 | `MIDI Time (s)` | `anchor.midi_timestamp_seconds`, 3 decimals |
| 3 | `Camera Frame` | `anchor.camera_frame` |
| 4 | `Probe (x,y)` | `(anchor.probe_x, anchor.probe_y)` — source-pixel coords of the intensity probe dot that was active when the anchor was added. Renders `—` if the anchor was created with no dot active. |
| 5 | `Derived Shift (s)` | `compute_anchor_shift` output, 4 decimals. `N/A` if the anchor's MIDI file isn't in the current session. |
| 6 | `Label` | `anchor.label` (free text, optional). **Editable in place** — double-click the cell (or press ++f2++ on a selected row) to open the editor; ++enter++ commits, ++esc++ cancels. |
| 7 | `Active` | `*` if this row's anchor is the active one; blank otherwise. Centered; dark green background + white text when active. |

All columns stretch to fit the available width except `#` and `Active`, which resize to their contents. Only the **Label** column is editable; every other cell is read-only.

## Header buttons

- **Add Anchor (A)** — injected by Level 2 into the header row (see `add_header_action`). Disabled until both markers are set. Clicking opens an input dialog for an optional label, then calls `AlignmentService.add_anchor` with the anchor built from the markers. The label can also be revised later by editing the **Label** cell directly; see [Editing a label](#editing-a-label) below.
- **Delete Selected** — disabled until a row is selected. Deletes the currently-selected anchor via `AlignmentService.delete_anchor`, which also repairs `active_anchor_index` if the deleted anchor was active (sets it to `None`) or earlier in the list than the active one (shifts it down by 1).

## Filtering

Anchors whose **`midi_filename` doesn't match the currently-selected MIDI combo** are rendered greyed out (grey foreground text) and made non-selectable. They still show every column for reference, but:

- Clicking the `Active` cell is ignored.
- Double-clicking the `MIDI Time` / `Camera Frame` / `Probe (x,y)` cells is ignored.
- The row cannot be selected, so **Delete Selected** cannot be invoked on them.

This prevents confusion when the same camera clip is viewed against a different MIDI file — only anchors tied to the shown MIDI are actionable.

## Interactions

| Input | Action |
|---|---|
| **Single-click** on the `Active` cell (col 7) | Toggle active. If this row is already active → deactivate (`set_active_anchor(None)`, emit `anchor_deactivated`). Otherwise → activate (`set_active_anchor(row)`, emit `anchor_activated(row)`). Ignored for greyed rows. |
| **Double-click** on `MIDI Time (s)` (col 2) | Emit `midi_time_jump_requested(seconds)` → Level 2 jumps the MIDI panel to that time and makes it the active panel. Ignored for greyed rows. |
| **Double-click** on `Camera Frame` (col 3) | Emit `camera_frame_jump_requested(frame)` → Level 2 jumps the camera panel to that frame and makes it the active panel. Ignored for greyed rows. |
| **Double-click** on `Probe (x,y)` (col 4) | Emit `probe_jump_requested(src_x, src_y)` → Level 2 calls `CameraPanelWidget.drop_dot` so a probe dot is placed at those source coords on the **currently visible** camera frame, and the intensity worker re-samples ±120 frames around the current frame. Ignored for greyed rows and no-op if the cell is `—`. |
| **Double-click** on `Label` (col 6) | Opens an inline editor in the cell. ++enter++ commits the new label via `AlignmentService.set_anchor_label`, then emits `anchor_label_changed(row)`. ++esc++ cancels with no write. Ignored for greyed rows (the cell is non-editable). |
| **Row selection** | Enables/disables **Delete Selected**. Multiple selection is disabled. |

## Editing a label

The **Label** column is the only editable cell in the table. To edit:

1. **Double-click** the Label cell (or select the row and press ++f2++). An inline editor opens over the cell.
2. Type the new label. While the editor is open, letter shortcuts like ++m++, ++c++, ++a++, ++l++ are absorbed by the editor, not the Level 2 shortcuts — click outside or press ++enter++/++esc++ to release focus.
3. Press ++enter++ to commit, or ++esc++ to cancel.

Committing routes the change through `AlignmentService.set_anchor_label(camera_index, anchor_index, label)` — the single mutation boundary — so the session is marked dirty via the `anchor_label_changed → state_modified` signal chain. Greyed-out rows (anchors tied to a different MIDI file) are not editable, matching the rule that only anchors for the currently-selected MIDI are actionable. Labels are stored as-is, including whitespace and empty strings; no validation is applied.

## Signals

| Signal | When |
|---|---|
| `anchor_activated(int)` | A row's Active cell was clicked, setting that row active |
| `anchor_deactivated()` | A row's Active cell was clicked while already active |
| `anchor_deleted(int)` | A row was successfully deleted via **Delete Selected** |
| `anchor_label_changed(int)` | The Label cell was edited in place and committed |
| `midi_time_jump_requested(float)` | Double-click on col 2 |
| `camera_frame_jump_requested(int)` | Double-click on col 3 |
| `probe_jump_requested(int, int)` | Double-click on col 4 when both `probe_x` and `probe_y` are set |

Level 2 catches all seven and re-syncs the panels, refreshes the overlap bar, and marks the session dirty as appropriate.

## When probe coords get captured

`probe_x` / `probe_y` are read from the camera panel **at the moment Add Anchor is clicked / ++a++ is pressed**, not when ++m++ or ++c++ are pressed. Practical consequences:

- Drop a dot, mark M/C, press A → the anchor stores that dot's coords.
- Drop a dot, mark M/C, drop a *different* dot, press A → the anchor stores the **latest** dot. The dot is not snapshot-bound to the markers.
- Mark M/C without dropping any dot → both fields are `None` and the cell shows `—`. The anchor is still fully valid.
- Drop a dot, then switch clips (which calls `clear_dot`), then add an anchor → both fields are `None`.

The probe coords are advisory metadata: they let you re-drop the same dot later via double-click, but they are **never** consulted by the alignment math (`engine.compute_anchor_shift` only reads `midi_filename`, `midi_timestamp_seconds`, `camera_frame`).

## What the table doesn't do

- The anchor's MIDI time, camera frame, and probe coords are immutable once created — only the **Label** column supports in-place editing. To adjust any of those values, delete the anchor and add a new one.
- No multi-select or bulk delete.
- No import/export outside the main save/load. Anchors travel with the session JSON.
