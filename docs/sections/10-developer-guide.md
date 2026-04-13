# 10. Developer Guide

This section is for developers maintaining or extending the tool.

## 10.1 Invariants to Preserve

These are load-bearing guarantees — do not break them without updating the docs and thinking through implications.

### 1. `alignment_engine.py` stays Qt-free

The module is intentionally importable without PyQt5. That gives:

- A natural seam for unit tests (none currently exist, but the surface is ready).
- Portability — any future batch script or analysis tool can import the math functions directly.

**Rule:** do not import `PyQt5.*` from `alignment_engine.py` or put anything Qt-specific in it.

### 2. Anchors store raw evidence; derive everything else

Never add `anchor_shift` as a persisted field on `Anchor` or `CameraFileInfo`. The whole durability strategy assumes anchors are `(midi_filename, midi_timestamp_seconds, camera_frame, label)` and everything else is recomputed via `compute_anchor_shift`. Adding cached derived fields would introduce drift bugs.

### 3. Strict phase ordering is enforced at every write path

Any code path that mutates `global_shift_seconds` must either:

- verify `total_anchor_count() == 0`, **or**
- explicitly call `clear_all_anchors()` after user confirmation.

Currently enforced in `Level1Widget._on_apply_shift` and `Level2View._on_compute_shift`. If you add a third entry point (e.g., a keyboard shortcut, a menu action, a scripting API), you must replicate the check.

### 4. The FrameWorker thread owns its `cv2.VideoCapture`

No other code touches `_capture` on `FrameWorker`. Serializing everything through `pyqtSlot` signals means you can't introduce a race by calling `seek` from the UI thread. If you want a second consumer of video frames, add another slot — don't share the handle.

### 5. Every `QImage` from cv2 must be `.copy()`'d

`numpy`'s buffer is reused by `cv2.VideoCapture.read()`. A `QImage` wrapping that buffer without copying is a dangling pointer after the next read. The current code does this correctly in `FrameWorker.request_frame`; keep it that way.

### 6. JSON persistence only stores decisions and cached metadata

Anything that can be re-derived from source media (file paths, total_frames, tempo, ticks_per_beat) is re-derived at load time. Conversely, anything the operator decided (global_shift, anchors, active_anchor_index, participant_id) must round-trip. If you add a field, decide which category it belongs to and don't bridge them.

## 10.2 Adding a Feature — Common Scenarios

### Adding a new keyboard shortcut in Level 2

Edit `Level2View._setup_shortcuts`. The helper `shortcut(key, slot)` already uses `Qt.WidgetWithChildrenShortcut`, so the binding works regardless of which child widget currently has focus. Update the hint line in `_update_status_line` and [UI Walkthrough §6.5](./06-ui-walkthrough.md).

### Adding a new column to the anchor table

1. Bump `QTableWidget(0, N)` in `AnchorTableWidget.__init__`.
2. Add a header label in `setHorizontalHeaderLabels`.
3. Populate it in `_refresh()`.
4. Decide whether `_on_cell_clicked` should treat the new column specially.

### Adding a field to the JSON schema

1. Add the field to the appropriate dataclass in `models.py`.
2. Add a serializer line in `persistence.save_alignment`.
3. Add a deserializer line in `persistence.load_alignment`, with a sensible default for backward compatibility (`data.get("new_field", default)`).
4. Update [Data Model and Persistence](./08-data-model-persistence.md).

### Supporting a new camera format

The FX30 XML adapter is at `camera_adapter.py`. For a new format:

- Write a new adapter with the same external shape: a `to_file_info() -> CameraFileInfo` method plus `get_frame(frame_index)` if needed.
- Modify `ParticipantLoader.load` to dispatch on filename extension (or factor out a registry of adapters).

Keep the `raw_unix_start`, `capture_fps`, `total_frames` semantics identical — the alignment math is tied to them.

## 10.3 Performance Notes

- The Level 1 canvas repaints the full bar chart every `update()`. For ~30 bars it's negligible. If you add hundreds of bars, consider pre-computing and caching `QRectF`s outside `paintEvent`.
- `MidiCanvasWidget.paintEvent` uses `NoteData.visible_range` (a `bisect` range) to avoid iterating all notes per paint. Keep any new visual decoration (cursor crosshairs, region highlights) inside the visible range too.
- Video seek is the main latency source. The 32-slot LRU in `FrameWorker` absorbs short scrubs. If you need faster long scrubs, consider asynchronously pre-fetching frames ahead of / behind the current position.
- MIDI adapter loading re-parses the full MIDI file twice (once for `mido`, once for `pretty_midi`). For ~300 s files this is tens of milliseconds — fine. If it becomes an issue, the mido handle already has everything needed to compute duration without `pretty_midi`.

## 10.4 Known Limitations (by design)

- **No auto-save.** File → Save is explicit. This is intentional; see [Getting Started](./02-getting-started.md).
- **JSON does not store file paths.** Reloading alignment JSON requires re-opening the participant folder to populate `mp4_path`/`file_path`/`total_frames` for Level 2. Level 1 works on pure JSON.
- **No tempo-map awareness in tick stepping.** The MIDI panel uses a constant `time_resolution` derived from the first `set_tempo`. Files with tempo changes will still render notes correctly (since `PrettyMIDI.get_end_time()` handles that), but `step_ticks` will use a constant seconds/tick assumption. Acceptable for the current dataset.
- **Single active anchor per clip.** The table UI only allows one. All the math can handle multiple — the deliberate choice is to simplify operator workflow.
- **No multi-select in Level 1.** Exactly one MIDI + one camera at a time.
- **Single participant at a time.** There is no batch tool.

## 10.5 Where to Look for a Behavior

When you're trying to trace a specific UI behavior, this table maps symptom → file:

| Symptom / feature | File |
|---|---|
| Startup / window size / menu | `main_window.py` |
| Opening a participant folder | `main_window.py` → `participant_loader.py` → `midi_adapter.py` + `camera_adapter.py` |
| Timeline bar chart | `level1_timeline.py` |
| Clicking into a pair | `level1_timeline.py` (`pair_selected` signal) → `main_window.py` → `level2_view.py` |
| Any time-math | `alignment_engine.py` |
| Piano roll / falling keys | `midi_panel.py` |
| Video frame display | `camera_panel.py` (main thread) + `frame_worker.py` (bg thread) |
| Locked-mode sync | `level2_view.py` → `_on_midi_position_changed` / `_on_camera_position_changed` |
| Overlap bar at top of Level 2 | `overlap_indicator.py` |
| Anchor table (CRUD, derived shift display) | `anchor_table.py` |
| Save/Load dialogs | `main_window.py` → `persistence.py` |

## 10.6 Suggested First Tests

If you add a test suite, start here. All of these can target `alignment_engine.py` and `models.py` without instantiating Qt:

1. `compute_anchor_shift` — synthesize a `MidiFileInfo` and `CameraFileInfo`, place an anchor, verify the returned shift inverts correctly via `midi_unix_to_camera_frame` and back.
2. `out_of_range_delta` — boundary behavior at `raw_unix_start`, `raw_unix_end`, and one frame past each.
3. `compute_global_shift_from_markers` — trivially `midi - camera`.
4. `get_effective_shift_for_camera` with no active anchor → equals `global_shift`; with active anchor referencing a known MIDI file → uses it; with active anchor referencing unknown MIDI file → falls back to `global_shift` (not crashes).
5. `AlignmentState.clear_all_anchors` — wipes every clip's `alignment_anchors` and sets every `active_anchor_index` to `None`.
6. `persistence.save_alignment` + `persistence.load_alignment` — round-trip a fabricated state; check equality of semantic fields (ignore `file_path` / `mp4_path` / `total_frames` / `ticks_per_beat` / `tempo` / `participant_folder` which are not persisted).

## 10.7 Agent / Claude Code notes

Per the project `CLAUDE.md`:

- When spawning subagents via the Agent tool, use `model: "opus"` to get the most capable model.
- The spec document `docs/implementation_history_doc/ALIGNMENT_TOOL_SPEC.md` is the original design artifact. This documentation set is the current, implementation-aligned source. Prefer this set; treat the spec as history.
