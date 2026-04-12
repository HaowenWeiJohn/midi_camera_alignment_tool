# 6. User Interface Walkthrough

## 6.1 The Main Window

`MainWindow` (`alignment_tool/main_window.py`) is the single top-level window. It is sized to `1400 × 800` by default, titled *"MIDI-Camera Alignment Tool"* (suffixed with `"— Participant <id>"` once one is loaded).

### Menu

- **File → Open Participant…** (Ctrl+O) — folder picker + UTC-offset prompt.
- **File → Save Alignment…** (Ctrl+S) — JSON save dialog. Disabled until a participant is loaded.
- **File → Load Alignment…** (Ctrl+L) — JSON load dialog.
- **File → Exit** (Ctrl+Q).

### Status bar

Shows the participant ID, number of MIDI files, number of camera clips, current `global_shift`, and total anchor count. Updated whenever state changes (`_update_status`).

### Central stack

A `QStackedWidget` with three pages:

1. A centered `QLabel` placeholder when no participant is loaded.
2. `Level1Widget` — the timeline overview.
3. `Level2View` — the alignment detail view.

Switching is handled by `MainWindow` in response to `pair_selected` (go to Level 2) and `back_requested` (return to Level 1).

---

## 6.2 Level 1 — Timeline Overview

Source: `alignment_tool/level1_timeline.py`.

### Layout

```
┌──────────────────────────────────────────────────────────┐
│ [ Global Shift (s): 0.000 ] [Apply] [Open Selected Pair] │
├──────────────────────────────────────────────────────────┤
│ MIDI    ████████   ████  ████████   ████████              │
│                                                            │
│ Camera     ████   ██  ███████   ██████                    │
│                                                            │
│              0s       60s       120s ...  Time (s)        │
└──────────────────────────────────────────────────────────┘
```

### Bars

- **Top row (blue)** — each MIDI file, at `unix_start` with width `duration`. Filename is rendered inside if it fits.
- **Bottom row (orange)** — each camera clip, at `raw_unix_start + effective_shift` with width `duration`. The effective shift comes from `get_effective_shift_for_camera`, so selecting a different active anchor on a clip will shift that bar.

### Interactions

- **Hover** — tooltip with filename, duration, start/end unix timestamps, and (for camera) capture FPS and aligned start.
- **Click a MIDI bar** — selects it (yellow outline). Click again to deselect.
- **Click a camera bar** — selects it (yellow outline). Click again to deselect.
- **Click empty space + drag** — pan the time axis.
- **Mouse wheel** — zoom in/out around the cursor. View clamped to [1 s … 100 000 s].
- **Double-click anywhere when both are selected** — emits `pair_selected`, drilling into Level 2.
- **"Open Selected Pair" button** — same as double-click.

### Global-shift controls

- `QDoubleSpinBox` with range `[-100000, 100000]`, 3 decimals, step 0.1.
- **Apply** compares the new value to the current one; if different and any anchors exist, shows the confirm-wipe dialog (see [Alignment Concepts §4.4](./04-alignment-concepts.md)). On confirm, calls `AlignmentState.clear_all_anchors` and assigns the new value.
- The apply button in Level 1 only accepts a typed value — it does **not** have a "compute from markers" feature (that is a Level 2 affordance, since it needs navigable panels).

---

## 6.3 Level 2 — Alignment Detail View

Source: `alignment_tool/level2_view.py`. This is where all the sync work happens.

### Layout

```
┌──────────────────────────────────────────────────────────┐
│ [<Back]  MIDI:[combo▼]  Camera:[combo▼]  [Mode: Independent] │
├──────────────────────────────────────────────────────────┤
│ Mode + hotkey hint line                                  │
├──────────────────────────────────────────────────────────┤
│ Overlap indicator (dual-track, blue+orange+green)        │
├────────────────────────────┬─────────────────────────────┤
│                            │                              │
│   MIDI falling-keys         │    Camera video frame        │
│   + playhead + piano        │    + frame/time counter      │
│                            │                              │
├────────────────────────────┴─────────────────────────────┤
│ MIDI mark: ...   Camera mark: ...   [Compute Global Shift] [Add Anchor] │
├──────────────────────────────────────────────────────────┤
│ Anchor table (columns: # | MIDI File | MIDI s | Frame |  │
│   Derived Shift | Label | Active)       [Delete Selected]│
└──────────────────────────────────────────────────────────┘
```

### Top bar

- **Back** button → `back_requested` → Level 1. (Esc also returns.)
- **MIDI combo** — pick any MIDI file from the participant. When locked **and** an anchor is active, the combo is disabled and forced to the anchor's `midi_filename`.
- **Camera combo** — pick any camera clip.
- **Mode button** — toggles between Independent (default) and Locked.

### Status / hint line

A faint gray line that always shows: current mode, which panel is "active" (for arrow-key navigation — see §6.5), and the shortcut legend.

### Overlap indicator

Source: `alignment_tool/overlap_indicator.py`. A 30-pixel-tall widget drawn with `QPainter`:

- Top half — MIDI clip extent (blue).
- Bottom half — camera clip extent (orange, positioned with `effective_shift` applied).
- Green rectangle over both — overlap region.
- Two independent white vertical lines — MIDI playhead (top track) and camera playhead (bottom track, drawn at aligned position).
- Click / drag on the **top half** jumps the MIDI panel; click / drag on the **bottom half** jumps the camera panel. The split is at y=15.

This gives spatial awareness ("where am I in the overlap?") without cluttering the main panels.

### MIDI panel

Source: `alignment_tool/midi_panel.py`.

- **Falling keys**: notes are rectangles colored by velocity; they scroll down toward a red horizontal playhead at 75% of the canvas height.
- **Piano keyboard** at the bottom (88 keys, with C labels on each octave).
- **Drag vertically** on the canvas → scrub time; **mouse wheel** → zoom the time axis (`_seconds_per_viewport` clamped to `[0.5, 60]`).
- **Out-of-range mode** (`show_out_of_range(message)`) hides the canvas and puts the message in the info label — used by Level 2 when the locked follower goes past the file.
- Info label under the canvas shows `Time: T.sss s / D.s  |  Tick: N`.

Note data is preprocessed into a `NoteData` helper (sorted by start time, with binary-search visibility lookup), so repainting at 60+ Hz stays cheap even for files with thousands of notes.

### Camera panel

Source: `alignment_tool/camera_panel.py`.

- `QLabel` that displays the decoded `QImage`, scaled `KeepAspectRatio` with `SmoothTransformation`.
- Under it, a counter label `Frame: N / Total  |  Time: T.sss s`.
- Frame extraction runs on a `QThread` (see `frame_worker.py`): the panel calls `worker.request_frame(frame)` and displays the result when `frame_ready(frame_index, QImage)` fires — but only if the frame index still matches `self._current_frame` (so stale frames from fast scrubs never render).
- An `out_of_range` state changes the `QLabel` styling to a gray background and displays a text message instead of an image.

### Marker row

Two labels (`MIDI mark:` and `Camera mark:`) and two action buttons:

- **Compute Global Shift** — enabled only when both markers are set. Opens a confirmation; if the user accepts, also shows the anchor-wipe confirmation if anchors exist, then commits the new `global_shift`.
- **Add Anchor (A)** — prompts for an optional label, then appends a new `Anchor(midi_filename, midi_seconds, camera_frame, label)` to the current camera clip's anchor list.

Setting a marker briefly flashes the label background (blue-gray) via `QTimer.singleShot(400, …)`.

### Anchor table

Source: `alignment_tool/anchor_table.py`. `QTableWidget` with 7 columns:

| # | MIDI File | MIDI Time (s) | Camera Frame | Derived Shift (s) | Label | Active |
|---|---|---|---|---|---|---|

- The **Active** column shows `*` centered on a dark-green background for the active row.
- Clicking the Active cell toggles activation (one anchor active at a time; clicking the active anchor deactivates).
- **Delete Selected** removes the selected anchor and shifts `active_anchor_index` if needed.
- **Derived Shift** is computed on the fly via `compute_anchor_shift` against the current `global_shift` — so if all anchors on a clip show similar derived shifts, the alignment is consistent; divergence indicates a wrong match or clock drift.

---

## 6.4 Navigation Modes

### Independent mode (default)

- Panels are decoupled. Scrubbing one doesn't affect the other.
- Use for Phase 1 (before `global_shift` is known) and for fine-tuning anchor positions separately on each side.

### Locked mode

- Scrubbing either panel moves the other, via `effective_shift = global_shift + anchor_shift`.
- If `effective_shift == 0` (e.g., `global_shift = 0` and no anchor), locking is still allowed but the follower almost certainly shows "out of range" because the clocks are minutes apart.
- When entering locked mode with an active anchor, the **anchor-lock rule** fires (`Level2View._apply_anchor_lock_rule`): the MIDI combo is disabled and forced to the anchor's referenced MIDI file. Exit by deactivating the anchor or switching to Independent.
- Locked mode always re-syncs the MIDI follower to the current camera position on activation (`_sync_from_camera`).

---

## 6.5 Keyboard Shortcuts (Level 2)

All are installed via `QShortcut` with `Qt.WidgetWithChildrenShortcut` context, so they work regardless of which child widget currently has focus.

| Key | Action |
|---|---|
| `M` | Mark MIDI: store `(current_midi_filename, current_time_seconds)` |
| `C` | Mark Camera: store current frame index |
| `L` | Toggle Independent ↔ Locked |
| `A` | Add anchor (only if both markers are set) |
| `O` | Jump both panels to the start of the overlap region |
| `Tab` | Switch the "active" panel (which arrow keys drive) |
| `←` / `→` | Step active panel by one unit (MIDI: 1 tick; camera: 1 frame) |
| `Shift + ← / →` | Larger step (MIDI: 100 ticks; camera: 10 frames) |
| `Esc` | Back to Level 1 |

The active panel is shown with a colored border: blue for MIDI, orange for camera. Switch with `Tab`. The initial active panel is **camera** (`_active_panel = "camera"` in `Level2View.__init__`).
