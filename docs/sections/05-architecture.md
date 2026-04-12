# 5. Architecture

## 5.1 High-Level Shape

The application is a single-window Qt app with a two-level drill-down.

```
QApplication
└── MainWindow (alignment_tool/main_window.py)
    ├── Menu bar: File → Open / Save / Load / Exit
    ├── Status bar
    └── QStackedWidget
        ├── Placeholder ("No participant loaded")
        ├── Level1Widget    → timeline overview (Level1Widget.pair_selected → drill down)
        └── Level2View      → alignment detail view (back_requested → return)
```

`MainWindow` owns the `AlignmentState` dataclass and routes signals between widgets.

## 5.2 Module Map

The code is flat inside `alignment_tool/`. There are three tiers of modules:

### Tier 1 — Pure / non-UI (no PyQt imports)

| File | Role |
|---|---|
| `models.py` | Dataclasses: `Anchor`, `MidiFileInfo`, `CameraFileInfo`, `AlignmentState`. |
| `alignment_engine.py` | Pure time-math: `compute_anchor_shift`, `get_effective_shift_for_camera`, `midi_unix_to_camera_frame`, `camera_frame_to_midi_seconds`, `out_of_range_delta`, etc. |
| `midi_adapter.py` | `MidiAdapter` wraps `mido` + `pretty_midi`; builds `MidiFileInfo`. |
| `camera_adapter.py` | `CameraAdapter` wraps Sony FX30 XML sidecar + `cv2`; builds `CameraFileInfo`; exposes `get_frame()` for one-off reads. |
| `participant_loader.py` | `ParticipantLoader.load(folder, utc_offset)` → `AlignmentState`. |
| `persistence.py` | `save_alignment` / `load_alignment` — JSON round-trip. |

### Tier 2 — Widgets (PyQt, no app orchestration)

| File | Role |
|---|---|
| `level1_timeline.py` | `TimelineCanvas` (custom `QPainter` bar chart) + `Level1Widget` (container with global-shift controls). |
| `level2_view.py` | `Level2View` composite — the whole detail page. |
| `midi_panel.py` | `MidiCanvasWidget` (falling-keys + piano bottom) + `MidiPanelWidget` (with info label). |
| `camera_panel.py` | `CameraPanelWidget` — video frame display that delegates to a `FrameWorker`. |
| `frame_worker.py` | `FrameWorker(QObject)` — lives on a `QThread`, owns the `cv2.VideoCapture`, caches frames as `QImage` in a 32-slot `OrderedDict` LRU. |
| `overlap_indicator.py` | `OverlapIndicatorWidget` — dual-track clickable navigation bar. |
| `anchor_table.py` | `AnchorTableWidget` — CRUD table for anchors. |

### Tier 3 — App shell

| File | Role |
|---|---|
| `__main__.py` | Entry: calls `app.main()`. |
| `app.py` | Creates `QApplication`, instantiates `MainWindow`, runs the event loop. |
| `main_window.py` | Menu, stacked widget, state wiring, Save/Load dialogs, UTC-offset prompt. |

## 5.3 Data-flow and Signal Wiring

### Loading

```
File → Open Participant
  ↓ MainWindow._on_open_participant
  ↓ QFileDialog.getExistingDirectory + QInputDialog.getDouble (UTC offset)
  ↓ ParticipantLoader.load(folder, utc_offset)
    ├── MidiAdapter per .mid → MidiFileInfo
    └── CameraAdapter per .MP4/.XML → CameraFileInfo
  ↓ AlignmentState
  ↓ MainWindow._set_state
    ├── Level1Widget.set_state(state)    # renders timeline
    └── stack.setCurrentWidget(level1)
```

### Drill-down (Level 1 → Level 2)

```
User clicks MIDI bar + camera bar, double-clicks (or "Open Selected Pair")
  ↓ TimelineCanvas.pair_selected(midi_index, camera_index)
  ↓ Level1Widget.pair_selected (re-emitted)
  ↓ MainWindow._on_pair_selected
  ↓ Level2View.load_pair(state, midi_index, camera_index)
    ├── Populates combos, loads MidiAdapter (re-parsed for note list)
    ├── MidiPanelWidget.load_midi + CameraPanelWidget.load_video
    ├── AnchorTableWidget.set_data(camera, midi_lookup, global_shift)
    └── OverlapIndicatorWidget.set_clips
  ↓ stack.setCurrentWidget(level2)
```

### Scrubbing in Level 2

Two peer panels publish positions; `Level2View` is the broker.

```
MidiPanelWidget.position_changed(time_seconds)
  ↓ Level2View._on_midi_position_changed
    ├── OverlapIndicator.set_midi_playhead(midi_unix)
    └── if locked: midi_unix_to_camera_frame → CameraPanelWidget.set_frame
                                             or show_out_of_range(message)

CameraPanelWidget.position_changed(frame)
  ↓ Level2View._on_camera_position_changed
    ├── OverlapIndicator.set_camera_playhead(camera_unix + eff)
    └── if locked: camera_frame_to_midi_seconds → MidiPanelWidget.set_position
                                                or show_out_of_range(message)
```

### Overlap indicator navigation

The overlap bar is clickable; clicking either track emits `midi_time_clicked` or `camera_frame_clicked` → `Level2View` routes those to the corresponding panel's `set_position` / `set_frame`. Moving the panels then re-publishes the playhead positions via the loop above.

### Anchor changes

```
User clicks "Active" cell in anchor table
  ↓ AnchorTableWidget._on_cell_clicked  (toggles active_anchor_index on CameraFileInfo)
  ↓ anchor_activated / anchor_deactivated signal
  ↓ Level2View._apply_anchor_lock_rule (if locked: may auto-switch MIDI file)
  ↓ Level2View._update_overlap (recomputes effective_shift, repaints indicator)
  ↓ state_modified → MainWindow updates status bar
```

### Global-shift changes (from Level 2)

```
User hits M and C markers, then "Compute Global Shift"
  ↓ Level2View._on_compute_shift
    ├── QMessageBox.question (confirm apply)
    └── if existing anchors: QMessageBox.warning (confirm wipe)
  ↓ AlignmentState.clear_all_anchors + assign new global_shift_seconds
  ↓ state_modified
```

### Global-shift changes (from Level 1)

```
User edits the spinner on Level 1 and clicks Apply
  ↓ Level1Widget._on_apply_shift
    └── Same anchor-clear confirmation, then canvas.refresh()
```

## 5.4 Threading Model

The application is single-threaded **except for one background thread** dedicated to video frame I/O:

- `CameraPanelWidget.__init__` creates a `QThread` and moves a `FrameWorker(QObject)` onto it.
- Requests are Qt-signal-dispatched (`request_frame(int)`, `open_video(str)`, `close_video()`), and `FrameWorker.frame_ready(int, QImage)` is emitted back to the main thread.
- `FrameWorker` owns the `cv2.VideoCapture` exclusively; no other thread touches it.
- A 32-entry LRU cache (`OrderedDict`) in `FrameWorker` holds recent `QImage`s so short scrubs are instant.

`CameraPanelWidget._on_frame_ready` discards any frame that doesn't match the currently-requested index — this avoids flicker when the operator scrubs quickly and multiple requests are in flight.

## 5.5 Rendering Choices

Two custom-painted widgets:

- **`TimelineCanvas`** (`level1_timeline.py`) draws MIDI + camera bars with `QPainter`, implements zoom via `wheelEvent`, pan via mouse drag on empty space, and per-bar click selection with hit-test rectangles stored each paint.
- **`MidiCanvasWidget`** (`midi_panel.py`) draws a falling-piano-roll with:
  - A `NoteData` helper that sorts notes by start and uses `bisect` to extract only the visible subset per paint.
  - A velocity→color interpolation (soft=blue → medium=green → yellow → loud=red).
  - An 88-key piano keyboard at the bottom (white + black keys + C labels).
  - Drag-to-scrub, wheel-to-zoom (0.5 s–60 s viewport), and a fixed-fraction playhead at 75% of the canvas height.

`QGraphicsScene` is not used — direct `QPainter` in `paintEvent` is both simpler and faster for these use cases.

## 5.6 State Ownership

Mutable alignment state lives in exactly one place: `MainWindow._state: AlignmentState | None`. All widgets that display or modify it are given a reference (`set_state` / `set_data` / `load_pair`) — they read and mutate the same object. `state_modified` signals allow the main window to refresh derived UI (status bar) without owning a reactive store.

This simple ownership model works because:

- There is one participant, one window, one operator at a time.
- Every widget that reads state does so during paint events from the up-to-date reference.
- There is no partial-commit concept — changes to `AlignmentState` happen immediately when the operator confirms an action.
