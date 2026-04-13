# 9. Module Reference

Per-file summary of the code in `alignment_tool/`. Line numbers are approximate and based on the current repository.

## `__main__.py`

Tiny entry point — imports `main` from `app.py` and calls it.

## `app.py`

```python
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MIDI-Camera Alignment Tool")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
```

No CLI flags, no configuration.

## `models.py`

All dataclasses (`Anchor`, `CameraFileInfo`, `MidiFileInfo`, `AlignmentState`). See [Data Model](./08-data-model-persistence.md). Zero logic beyond convenience methods.

## `alignment_engine.py`

Pure functions. **No Qt import** — must stay that way. Public API:

| Function | Purpose |
|---|---|
| `compute_anchor_shift(anchor, camera, midi, global_shift) -> float` | Derive per-anchor shift. |
| `compute_effective_shift(global_shift, anchor_shift) -> float` | Simple sum; exists for symmetry / readability. |
| `get_effective_shift_for_camera(camera, global_shift, midi_files: dict) -> float` | Convenience: honors the active anchor (or returns `global_shift`). |
| `midi_unix_to_camera_frame(midi_unix, effective_shift, camera) -> int \| None` | Rounded integer frame or None if out of range. |
| `camera_frame_to_midi_seconds(frame, effective_shift, camera, midi) -> float \| None` | Seconds-from-MIDI-file-start or None if out of range. |
| `camera_frame_to_unix(frame, camera) -> float` | `raw_unix_start + frame / capture_fps`. |
| `midi_seconds_to_unix(seconds_from_start, midi) -> float` | `unix_start + seconds_from_start`. |
| `compute_global_shift_from_markers(midi_unix, camera_unix) -> float` | `midi_unix - camera_unix`. |
| `out_of_range_delta(midi_unix, effective_shift, camera) -> float \| None` | Signed seconds to nearest edge; None means in range. |

All formulas are reproduced in [Alignment Concepts §4.2](./04-alignment-concepts.md).

## `midi_adapter.py`

`MidiAdapter(filepath)` wraps `mido.MidiFile` + `pretty_midi.PrettyMIDI`.

- Constants `NOTE_NAMES`, `MIDI_TO_NOTE`, `NOTE_TO_MIDI` for pitch labels (not currently consumed outside this module but exported for future use).
- `_extract_tempo()` — returns `(tempo_usec, has_tempo_changes)`. Uses the first `set_tempo` if multiple exist.
- Properties: `ticks_per_beat`, `tempo`, `time_resolution` (seconds/tick), `sample_rate` (ticks/sec), `duration` (via `PrettyMIDI.get_end_time()` — honors tempo maps), `notes` (list from the first instrument).
- `get_recording_time_range(fmt)` — reads `os.path.getmtime(filepath)` as the recording end, subtracts `duration` to get the start → `(start, end, duration)`.
- `to_file_info() -> MidiFileInfo`.

## `camera_adapter.py`

`CameraAdapter(xml_path, mp4_path)` wraps Sony FX30 XML sidecar + `cv2`.

- Namespace: `urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20`.
- `_parse_xml` extracts `duration_frames`, `capture_fps`, `format_fps`. (`CreationDate` is no longer read — end time comes from MP4 mtime.)
- `_parse_mp4_properties` opens the MP4 briefly to get `mp4_fps`, `mp4_frame_count`, `mp4_width`, `mp4_height`.
- `duration` property = `duration_frames / capture_fps`.
- `get_recording_time_range(fmt)` — `end = os.path.getmtime(mp4_path)`; `start = end − duration`.
- `to_file_info() -> CameraFileInfo`.
- Frame extraction: `open()` / `close()` / `get_frame(frame_index)` for single-use reads. (The Level 2 panel does not call these — it uses `FrameWorker` instead.)

## `participant_loader.py`

`ParticipantLoader.load(folder) -> AlignmentState` — the only static method.

1. Treats `Path(folder).name` as `participant_id`.
2. Iterates `disklavier/*.mid` alphabetically; builds `MidiFileInfo`s.
3. Iterates `overhead camera/*.MP4` alphabetically; for each, derives the XML sidecar name (`<stem>M01.XML`). Skips files with a missing XML (prints a warning).
4. Returns the populated `AlignmentState`.

## `persistence.py`

- `save_alignment(state, filepath)` — JSON dump with `indent=2`.
- `load_alignment(filepath) -> AlignmentState` — reconstruction; sets `total_frames=0` (re-scan needed for Level 2), `ticks_per_beat=0`, `tempo=500000.0`.

Schema: [Data Model §8.3](./08-data-model-persistence.md).

## `main_window.py`

`MainWindow(QMainWindow)` orchestrates the UI.

- Holds `_state: AlignmentState | None` and routes state changes.
- Sets up File menu (Open / Save / Load / Exit).
- Owns the `QStackedWidget` with placeholder / Level1Widget / Level2View.
- Slots:
  - `_on_open_participant` — folder picker, then calls `ParticipantLoader.load(folder)`.
  - `_on_save` / `_on_load` — JSON dialogs.
  - `_on_pair_selected(midi_index, camera_index)` — switches to Level 2.
  - `_on_back_to_level1` — refresh Level 1, switch back.
  - `_on_state_modified` — refresh status bar text.

## `level1_timeline.py`

Two classes:

- `TimelineCanvas(QWidget)` — custom `paintEvent` bar chart.
  - `set_state(state)` refits the view; `refresh()` just repaints.
  - Stores per-paint hit-test rectangles for click detection.
  - `mousePressEvent` toggles selection on click; empty-space click initiates pan.
  - `mouseMoveEvent` pans or shows a tooltip.
  - `wheelEvent` zooms around cursor, clamped to `[1, 100000]` s viewport.
  - `pair_selected(int, int)` signal on double-click with both selections.
  - Exposes `selected_midi_index`, `selected_camera_index` properties.
- `Level1Widget(QWidget)` — container:
  - Global-shift `QDoubleSpinBox` + Apply button.
  - "Open Selected Pair" button.
  - Hosts the canvas.
  - `_on_apply_shift` — enforces the anchor-wipe confirmation rule.

## `level2_view.py`

`Level2View(QWidget)` is the composite alignment page.

- Top bar: Back button, MIDI combo, Camera combo, Mode toggle.
- Status line, overlap indicator, horizontal splitter with MIDI + camera panels.
- Marker row + action buttons.
- Anchor table.
- Owns:
  - `_state: AlignmentState | None`
  - `_midi_index`, `_camera_index`
  - `_midi_adapter: MidiAdapter | None` (re-parsed when loading a MIDI pair so the piano-roll can render notes)
  - `_locked: bool`, `_active_panel: "midi" | "camera"`
  - `_midi_marker: (filename, seconds) | None`, `_camera_marker: int | None`
- Keyboard shortcuts installed via `_setup_shortcuts` with `WidgetWithChildrenShortcut` context.
- Signals out: `back_requested`, `state_modified`.

Key internal methods:

- `load_pair(state, midi_index, camera_index)` — entry point from Level 1.
- `_load_midi_file(index)` / `_load_camera_file(index)` — re-parse & reload one panel.
- `_toggle_mode()` — flips `_locked`; on lock-on, applies anchor-lock rule and re-syncs.
- `_apply_anchor_lock_rule()` — on locked+active, forces MIDI combo to anchor's file.
- `_on_midi_position_changed` / `_on_camera_position_changed` — the core sync logic; updates overlap indicator playheads in both modes; in locked mode drives the other panel via `alignment_engine`.
- `_on_compute_shift` — compute + confirm + wipe anchors + apply `global_shift`.
- `_on_add_anchor` — prompts for label, appends anchor.
- `_jump_to_overlap` — compute overlap intersection; navigate both panels or warn.

## `midi_panel.py`

Two classes:

- `MidiCanvasWidget(QWidget)` — falling-keys renderer.
  - `_note_data: NoteData` — pre-sorted starts/ends/pitches/velocities, binary-searched visibility.
  - `_time_resolution: float` — from adapter (seconds per tick).
  - `_seconds_per_viewport: float` — zoom; clamped to `[0.5, 60]`.
  - `_playhead_frac: float = 0.75` — fixed playhead position on the canvas.
  - `_time_to_y(t)` maps time to Y with playhead at `height * 0.75`.
  - `set_position(time_seconds)` — sets the playhead, clamped to `[0, duration]`, emits `position_changed(float)`.
  - `step_ticks(ticks)` — `set_position(current + ticks * resolution)`.
  - `paintEvent`: grid lines, vertical C-note separators, note rectangles (color = velocity), playhead line, piano keyboard at bottom.
  - `wheelEvent` zooms; `mouseMoveEvent` drags.
- `MidiPanelWidget(QWidget)` — hosts canvas + info label, relays signals.

## `camera_panel.py`

`CameraPanelWidget(QWidget)` — frame display.

- Owns a `QThread` and a `FrameWorker`; forwards requests via queued signals.
- `load_video(camera_info)` — `open_video(mp4_path)` + request frame 0.
- `set_frame(frame)` — clamps, requests, emits `position_changed(int)`.
- `step(delta)` — `set_frame(current + delta)`.
- `_on_frame_ready(frame_index, QImage)` — **discards stale frames** (only displays if `frame_index == self._current_frame`).
- `show_out_of_range(message)` / `show_normal()` — toggle display vs gray text.
- `cleanup()` — releases worker; called from `closeEvent` too.

## `frame_worker.py`

`FrameWorker(QObject)` — lives on a background `QThread`.

- Slots: `open_video(mp4_path)`, `request_frame(int)`, `close_video()`.
- Owns `_capture: cv2.VideoCapture | None` and a 32-slot `OrderedDict` LRU of `int → QImage`.
- On `request_frame(N)`: returns from cache if present; otherwise seeks and reads. The numpy buffer from `cap.read()` is copied into the `QImage` via `.copy()` before caching (cv2 reuses the buffer — without the copy you'd corrupt later reads).
- Signal: `frame_ready(int, QImage)`.

## `overlap_indicator.py`

`OverlapIndicatorWidget(QWidget)` — fixed 30-pixel-height dual-track nav bar.

- `set_clips(midi, camera, effective_shift)` — supplies geometry.
- `set_midi_playhead(midi_unix_time)` / `set_camera_playhead(aligned_camera_unix_time)` — two independent playheads.
- Mouse: clicking / dragging on top half (y < 15) emits `midi_time_clicked(float)`; on bottom half emits `camera_frame_clicked(int)`.
- Paint: MIDI bar (blue), aligned camera bar (orange), overlap rectangle (green), two white playhead lines.

## `anchor_table.py`

`AnchorTableWidget(QWidget)` — `QTableWidget` wrapper.

- `set_data(camera_info, midi_lookup, global_shift)` — rebuilds the rows.
- `add_anchor(anchor)` — appends then refreshes.
- `_on_cell_clicked(row, col)` — if col == 6 (Active column), toggles `active_anchor_index` on the underlying `CameraFileInfo`.
- `_on_delete` — pops the selected row and adjusts `active_anchor_index`.
- Emits `anchor_activated(int)`, `anchor_deactivated()`, `anchor_deleted(int)` for the parent view to relay.
- Derived shift is recomputed every refresh via `compute_anchor_shift`.
