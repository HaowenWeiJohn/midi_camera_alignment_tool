# MIDI-Camera Alignment Tool — Rebuild Design

**Date:** 2026-04-13
**Status:** Design, awaiting user review before implementation planning
**Target version:** v2.0
**Target platform:** Windows only

## 1. Purpose and scope

Rebuild the existing `midi_camera_alignment_tool` (v1.0, PyQt5) from scratch as v2.0 on PySide6. Preserve every user-facing feature and the two-level UI workflow. Fix the known bugs found during the pre-rebuild audit. Introduce a clean architectural separation between pure-Python logic and Qt code so the math and state-transition logic can be unit-tested without a `QApplication`.

### In scope

- Feature-parity with v1.0 (Level 1 timeline, Level 2 detail view, anchors, global shift, JSON persistence, keyboard shortcuts, overlap indicator, status feedback).
- Migration to PySide6.
- Concrete bug fixes listed in §10.
- JSON schema redesign (v2) — no backward compatibility with v1 JSONs is required.
- Unit tests for the math core (`core/engine.py`) and service layer (`core/service.py`).
- Replacement of the 575-line `Level2View` god widget with a thin view over an `AlignmentService` + `AlignmentSession`.

### Out of scope (explicitly)

- New features: playback mode, undo/redo, in-place anchor label editing, multi-anchor visualization, batch cross-participant views.
- Cross-platform support (macOS/Linux). Code may use cross-platform idioms where cheap but will be tested only on Windows.
- UI test automation.
- Migration tooling for v1 JSONs (none exist that need preserving).

## 2. Goals and non-goals

### Goals

1. **Trustworthy math.** Every alignment formula is covered by round-trip unit tests. Sign conventions documented in docstrings.
2. **Testable state transitions.** The anchor-lock rule, global-shift-clears-anchors rule, and active-anchor dispatch all live in pure Python and are covered by tests that do not import PySide6.
3. **Clean threading.** Camera frame decoding runs on a real background thread via queued signal dispatch. Proper shutdown on close.
4. **Robust persistence.** JSONs save atomically and load back into a fully functional tool (including Level 2) without needing the user to re-open the participant folder.
5. **Feature parity.** A v1 operator can sit down at v2 and perform the same workflow with the same shortcuts and the same visual structure.

### Non-goals

1. Speed improvements beyond what falls out of the architectural cleanup.
2. A different UX paradigm. The two-level drill-down stays.
3. Backward-compatible JSON loading.

## 3. Architectural approach

Approach chosen: **pure service layer + thin Qt adapter** (“Approach 3” from brainstorming).

Two tiers:

- **Core tier (pure Python).** `core/` and `io/` — data classes, math, state service, session state, persistence, file adapters. No `PySide6` import anywhere under these directories. This is what unit tests import directly.
- **Qt tier.** `qt/` — `AlignmentController(QObject)` shim + all widgets + frame worker. Widgets never touch `AlignmentService`, `AlignmentSession`, or model dataclasses for mutation — they go through the controller.

The controller is a thin facade: each of its methods calls one service method, catches typed exceptions, and emits a Qt signal describing the state change. Widgets subscribe to signals and render.

**Key discipline.** No widget mutates `AlignmentState`, `CameraFileInfo.alignment_anchors`, `active_anchor_index`, or `AlignmentState.global_shift_seconds` directly. All mutations go through `AlignmentController` → `AlignmentService`. This is the v1 bug that made the codebase hard to reason about; v2 makes the boundary explicit.

## 4. Package structure

```
alignment_tool/
├── __init__.py
├── __main__.py              # python -m alignment_tool entry
├── app.py                   # QApplication bootstrap
│
├── core/                    # PURE PYTHON — no PySide6 imports
│   ├── __init__.py
│   ├── models.py            # dataclasses
│   ├── engine.py            # alignment math (pure functions)
│   ├── service.py           # AlignmentService + AlignmentSession
│   ├── persistence.py       # JSON v2 serialize/deserialize
│   └── errors.py            # typed exceptions
│
├── io/                      # PURE PYTHON — file parsing adapters
│   ├── __init__.py
│   ├── midi_adapter.py
│   ├── camera_adapter.py
│   ├── midi_cache.py        # per-file caching of parsed MIDI (NEW)
│   └── participant_loader.py
│
├── qt/                      # QT-COUPLED — depends on PySide6
│   ├── __init__.py
│   ├── controller.py        # AlignmentController(QObject)
│   ├── main_window.py
│   ├── level1/
│   │   ├── __init__.py
│   │   ├── widget.py        # Level1Widget
│   │   └── timeline_canvas.py
│   ├── level2/
│   │   ├── __init__.py
│   │   ├── view.py          # Level2View (~200 lines, not 575)
│   │   ├── midi_panel.py
│   │   ├── camera_panel.py
│   │   ├── anchor_table.py
│   │   ├── overlap_indicator.py
│   │   ├── marker_bar.py    # extracted from v1 Level2View
│   │   └── shortcut_router.py  # extracted from v1 Level2View
│   └── workers/
│       ├── __init__.py
│       └── frame_worker.py
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures.py
    ├── test_engine.py
    ├── test_service.py
    └── test_persistence.py
```

**Boundary rule.** Nothing under `core/` or `io/` may import `PySide6`. Audited with a single grep during CI (even if "CI" is just a pre-commit hook).

**Entry point.** `python -m alignment_tool` runs `__main__.py`, which calls `app.main()`, which builds a `QApplication`, constructs `MainWindow`, runs `exec()`.

## 5. Data model

All dataclasses live in `core/models.py`. No Qt dependency.

```python
@dataclass(frozen=True)
class Anchor:
    midi_filename: str              # basename of .mid
    midi_timestamp_seconds: float   # seconds from MIDI file start
    camera_frame: int               # 0-indexed cv2 frame
    label: str = ""

@dataclass
class MidiFileInfo:
    filename: str
    file_path: Path                 # absolute; not persisted in JSON
    unix_start: float
    unix_end: float
    duration: float
    sample_rate: float

@dataclass
class CameraFileInfo:
    filename: str
    file_path: Path                 # absolute MP4 path
    xml_path: Path                  # absolute XML sidecar path
    raw_unix_start: float
    raw_unix_end: float
    duration: float                 # seconds
    capture_fps: float
    total_frames: int               # REQUIRED — persisted in JSON v2
    alignment_anchors: list[Anchor] = field(default_factory=list)
    active_anchor_index: int | None = None

@dataclass
class AlignmentState:
    participant_id: str
    participant_folder: Path        # NEW — persisted in JSON v2
    global_shift_seconds: float = 0.0
    midi_files: list[MidiFileInfo] = field(default_factory=list)
    camera_files: list[CameraFileInfo] = field(default_factory=list)
    alignment_notes: str = ""
```

**Decisions.**
- `Anchor` is frozen (immutable). Mutations replace the whole anchor object; indices stay stable because the list itself is not frozen.
- `total_frames` is required on `CameraFileInfo`. `persistence.load_alignment` refuses to return a state with zero-frames entries (fixes audit item 5).
- `participant_folder` is canonical — `file_path` / `xml_path` on file entries are reconstructed from it on load and are never persisted in the JSON.

## 6. Math core (`core/engine.py`)

Pure functions, identical sign conventions to v1. A positive shift means MIDI clock is ahead of camera clock.

**Function signatures (preserved from v1):**

```python
def compute_anchor_shift(anchor: Anchor, camera: CameraFileInfo,
                         midi: MidiFileInfo, global_shift: float) -> float: ...

def compute_effective_shift(global_shift: float, anchor_shift: float) -> float: ...

def get_effective_shift_for_camera(state: AlignmentState,
                                   camera: CameraFileInfo) -> float: ...

def midi_unix_to_camera_frame(midi_unix: float, effective_shift: float,
                              camera: CameraFileInfo) -> int | None: ...

def midi_unix_to_camera_frame_exact(midi_unix: float, effective_shift: float,
                                    camera: CameraFileInfo) -> float | None: ...  # NEW

def camera_frame_to_midi_seconds(frame: int, effective_shift: float,
                                 camera: CameraFileInfo,
                                 midi: MidiFileInfo) -> float | None: ...

def compute_global_shift_from_markers(midi_unix: float, camera_unix: float) -> float: ...

def out_of_range_delta(frame: int, camera: CameraFileInfo) -> float | None: ...

def midi_seconds_to_unix(seconds: float, midi: MidiFileInfo) -> float: ...

def camera_frame_to_unix(frame: int, camera: CameraFileInfo) -> float: ...
```

**Formulas (from audit, verbatim sign-preserved):**

- `compute_global_shift_from_markers`: `shift = midi_unix - camera_unix`
- `compute_anchor_shift`: `midi_unix_at_anchor = midi.unix_start + anchor.midi_timestamp_seconds; camera_unix_at_anchor = camera.raw_unix_start + anchor.camera_frame / camera.capture_fps; anchor_shift = midi_unix_at_anchor - camera_unix_at_anchor - global_shift`
- `compute_effective_shift`: `effective_shift = global_shift + anchor_shift`
- `midi_unix_to_camera_frame`: `camera_unix = midi_unix - effective_shift; frame = round((camera_unix - camera.raw_unix_start) * camera.capture_fps)`; returns `None` if `frame < 0` or `frame >= camera.total_frames`.
- `camera_frame_to_midi_seconds`: `camera_unix = camera.raw_unix_start + frame / camera.capture_fps; midi_unix = camera_unix + effective_shift; midi_seconds = midi_unix - midi.unix_start`; returns `None` if `midi_seconds < 0` or `midi_seconds > midi.duration`.
- `out_of_range_delta`: returns signed seconds; positive = clip hasn't started (at current frame target), negative = clip already ended, `None` = in range.

**New helper `midi_unix_to_camera_frame_exact`** returns the unrounded float frame. Used internally when the service chains conversions (avoids rounding drift — audit item 23). The display layer still calls the `round()` version.

**Docstring discipline.** Each function documents its sign convention and returns a clear statement of when `None` is returned. Prevents the kind of sign-flip bug the audit flagged at item 6.

## 7. Service layer (`core/service.py`)

Two classes. No Qt import.

### `AlignmentService`

Owns the persistent `AlignmentState`. All mutations go through its methods. Queries never mutate.

```python
@dataclass
class GlobalShiftResult:
    new_shift: float
    anchors_to_clear: int         # 0 if no confirmation needed
    clips_affected: int
    pending_token: object | None  # opaque; pass to confirm_global_shift

class AlignmentService:
    state: AlignmentState

    # loading
    def load_state(self, state: AlignmentState) -> None

    # mutations — global shift
    def set_global_shift(self, new_shift: float) -> GlobalShiftResult
    def confirm_global_shift(self, result: GlobalShiftResult) -> None

    # mutations — anchors
    def add_anchor(self, camera_idx: int, anchor: Anchor) -> None
    def delete_anchor(self, camera_idx: int, anchor_idx: int) -> None
    def activate_anchor(self, camera_idx: int, anchor_idx: int | None) -> None

    # mutations — notes
    def set_alignment_notes(self, text: str) -> None

    # queries
    def effective_shift_for(self, camera_idx: int) -> float
    def active_anchor(self, camera_idx: int) -> Anchor | None
    def midi_by_filename(self, name: str) -> tuple[int, MidiFileInfo] | None  # (index in state.midi_files, info)
    def total_anchor_count(self) -> int
```

**`set_global_shift` behavior.** If the new shift differs meaningfully (`abs(a-b) >= 1e-9`) from the current one and any anchors exist anywhere, the method returns a `GlobalShiftResult` with `anchors_to_clear > 0` and does not mutate state. The caller must call `confirm_global_shift(result)` to commit. If no anchors exist, `anchors_to_clear == 0` and the mutation is applied immediately. This shape keeps dialogs in the Qt layer.

**Error handling.** Service raises typed exceptions from `core/errors.py`:

- `InvalidAnchorError` — anchor index out of range, or anchor created with `camera_frame >= total_frames` / negative frame, or `midi_timestamp_seconds` outside the referenced MIDI's duration.
- `MissingMidiError` — anchor's `midi_filename` not found in state.
- `InvalidCameraError` — camera index out of range.
- `InvalidStateError` — operation attempted before state is loaded.

Controller catches, emits `error_occurred(message)`.

### `AlignmentSession`

Pure Python session/UI state (not persisted). Anchor-lock rule and marker state are reified here so tests can verify them.

```python
class AlignmentSession:
    current_midi_index: int | None
    current_camera_index: int | None
    mode: Literal["independent", "locked"] = "independent"
    active_panel: Literal["midi", "camera"] = "camera"
    midi_marker: tuple[str, float] | None = None     # (filename, seconds)
    camera_marker: int | None = None                  # frame

    def set_mode(self, mode) -> None
    def set_active_panel(self, panel) -> None
    def set_midi_selection(self, idx) -> None
    def set_camera_selection(self, idx) -> None
    def set_marker_midi(self, filename: str, seconds: float) -> None
    def set_marker_camera(self, frame: int) -> None
    def clear_markers(self) -> None

    # rule helpers (called by view AND tests)
    def markers_ready(self) -> bool
    def anchor_lock_target_midi(self, service: AlignmentService) -> int | None
    def midi_combo_enabled(self, service: AlignmentService) -> bool
```

**Anchor-lock rule** (from v1 docs, now pure-Python and testable):
- If `mode == "locked"` and the current camera clip has an active anchor whose `midi_filename` resolves, `anchor_lock_target_midi` returns the corresponding MIDI index and `midi_combo_enabled` returns `False`.
- Otherwise `anchor_lock_target_midi` returns `None` and the combo is free.

## 8. Qt controller + UI (`qt/`)

### `AlignmentController(QObject)`

Thin shim. Owns one `AlignmentService` and one `AlignmentSession`. ~150 lines.

Signals (fine-grained so widgets can subscribe narrowly):

```python
state_loaded = Signal()
global_shift_changed = Signal(float)
anchors_changed = Signal(int)            # camera_idx
active_anchor_changed = Signal(int)      # camera_idx
mode_changed = Signal(str)
marker_changed = Signal()
selection_changed = Signal()             # current midi/camera indices changed
error_occurred = Signal(str)
```

Facade methods mirror service/session methods one-to-one, add exception translation, emit signals. Example:

```python
def add_anchor(self, camera_idx: int, anchor: Anchor) -> None:
    try:
        self._service.add_anchor(camera_idx, anchor)
    except (InvalidAnchorError, MissingMidiError, InvalidCameraError) as e:
        self.error_occurred.emit(str(e))
        return
    self.anchors_changed.emit(camera_idx)
```

For `set_global_shift` specifically, the controller exposes `request_global_shift(new)` that returns the `GlobalShiftResult`; the caller (menu action / button handler) decides whether to show the confirmation dialog and then calls `controller.confirm_global_shift(result)`.

### Widget hierarchy (visually identical to v1)

```
MainWindow
├── menuBar: File (Open / Save / Load / Exit)
├── statusBar: StatusLine
└── centralWidget: QStackedWidget
    ├── Level1Widget
    │   ├── HeaderBar  (shift spinner, Apply btn, Open Pair btn)
    │   └── TimelineCanvas
    └── Level2View
        ├── TopBar  (Back, midi combo, camera combo, mode toggle)
        ├── StatusHintLine
        ├── OverlapIndicator
        ├── QSplitter [MidiPanelWidget | CameraPanelWidget]
        ├── MarkerBar  (midi mark, cam mark, Compute btn, Add Anchor btn)
        └── AnchorTable
```

Decomposition away from the v1 god widget:

- Marker state and marker-flash animation → `MarkerBar`.
- Keyboard shortcut routing → `ShortcutRouter` (not a widget; owned by `Level2View`). Maps key → `controller.*` call.
- MIDI re-parsing on combo change → `io/midi_cache.MidiCache` keyed by `file_path`. A single instance is constructed by `app.py` and injected into `Level2View`. No more re-parsing on every switch.
- Mode toggle, anchor-lock rule enforcement → `AlignmentSession` (pure Python).

### Threading — proper queued dispatch

`FrameWorker` lives on a `QThread`; cross-thread calls go through signals, not direct method invocations.

```python
class CameraPanelWidget(QWidget):
    frame_requested = Signal(int)
    video_open_requested = Signal(str)
    video_close_requested = Signal()

    def __init__(self, ...):
        super().__init__(...)
        self._worker = FrameWorker()
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        self.frame_requested.connect(self._worker.request_frame)
        self.video_open_requested.connect(self._worker.open_video)
        self.video_close_requested.connect(self._worker.close_video)
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker_thread.start()

    def set_frame(self, frame: int) -> None:
        self._current_frame = frame
        self.frame_requested.emit(frame)

    def cleanup(self) -> None:
        self.video_close_requested.emit()
        self._worker_thread.quit()
        self._worker_thread.wait(2000)
```

`MainWindow.closeEvent` invokes `cleanup()` on active Level 2 widgets before accepting the event.

Stale-frame protection: `_on_frame_ready(frame_index, image)` discards the image if `frame_index != self._current_frame`.

### Panel focus

`MidiPanelWidget` and `CameraPanelWidget` each handle `mousePressEvent` to emit a `focus_requested` signal connected to `controller.set_active_panel("midi" | "camera")`. Arrow-key steps then go to the last-clicked panel (fixes audit item 22).

### Shortcuts (PySide6 idioms)

- `Qt.ShortcutContext.WidgetWithChildrenShortcut` (scoped enum).
- `QKeySequence("Shift+Left")` instead of `Qt.SHIFT + Qt.Key_Left`.

Same key map as v1: `M`, `C`, `L`, `A`, `O`, `Tab`, `←/→`, `Shift+←/→`, `Esc`, plus menu `Ctrl+O`, `Ctrl+S`, `Ctrl+L`, `Ctrl+Q`.

## 9. Persistence (JSON schema v2)

### Schema

```json
{
  "schema_version": 2,
  "participant_id": "P042",
  "participant_folder": "C:/data/piano_study/P042",
  "global_shift_seconds": -342.5123,
  "alignment_notes": "",
  "saved_at_unix": 1776051599.0,
  "midi_files": [
    {
      "filename": "trial_03.mid",
      "unix_start": 1776048000.0,
      "unix_end": 1776048180.5,
      "duration": 180.5,
      "sample_rate": 1920.0
    }
  ],
  "camera_files": [
    {
      "filename": "C0042.MP4",
      "xml_filename": "C0042M01.XML",
      "raw_unix_start": 1776048030.0,
      "raw_unix_end": 1776048090.0,
      "duration": 60.0,
      "capture_fps": 239.76,
      "total_frames": 14385,
      "alignment_anchors": [
        {
          "midi_filename": "trial_03.mid",
          "midi_timestamp_seconds": 12.345,
          "camera_frame": 2880,
          "label": "first C4"
        }
      ],
      "active_anchor_index": 0
    }
  ]
}
```

### Changes vs v1

1. `schema_version` (top level, integer) — future migrations bump this.
2. `participant_folder` — absolute path; enables re-resolution of media.
3. `total_frames` per camera file — eliminates the "zero-frames after load" bug.
4. `saved_at_unix` — provenance timestamp.
5. `file_path` / `xml_path` fields are gone — reconstructed on load from `participant_folder` + `filename`/`xml_filename`.

### Save behavior (atomic)

```python
tmp = filepath.with_suffix(filepath.suffix + ".tmp")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
os.replace(tmp, filepath)
```

Interrupted save leaves the original untouched.

### Load behavior

1. Read JSON, check `schema_version == 2`, else raise `SchemaVersionError`.
2. If `participant_folder` does not exist on disk, raise `MediaNotFoundError` carrying the stored path. Caller (Qt layer) shows a relocation dialog and retries load with a user-picked folder path.
3. Re-scan the folder (`participant_loader`) to rebuild `file_path` / `xml_path` for each entry. Any entry whose basename is missing from disk is dropped with a logged warning (kept out of state).
4. Verify `total_frames` against a fresh `cv2.VideoCapture` probe; if they diverge, log a warning but keep the JSON value (could indicate re-transcoded file).
5. Validate each anchor:
   - If `midi_filename` not in `state.midi_files`, anchor is kept but the containing clip's `active_anchor_index` is reset to `None` if it was pointing to that anchor. (Fixes audit item 7.)
   - If `camera_frame` not in `[0, total_frames)` or `midi_timestamp_seconds` not in `[0, midi.duration]`, raise `InvalidAnchorError`.
6. Validate each clip's `active_anchor_index` is `None` or in range; clamp to `None` otherwise.

## 10. Bug fixes carried into rebuild

The following audit findings are fixed as part of v2:

| # | Audit item | Fix location |
|---|---|---|
| 1 | FrameWorker called directly across threads | §8 (queued signal dispatch) |
| 2 | QThread shutdown leak | §8 (explicit `quit()`/`wait()`) |
| 4 | `participant_folder` not persisted | §9 (persisted in schema) |
| 5 | `total_frames=0` after load | §9 (persisted in schema) |
| 7 | Anchor on missing MIDI silently falls back | §9 (auto-deactivate on load) |
| 11 | String `.replace("\\","/").split` path parsing | Use `Path(...).name` throughout |
| 17 | `MidiAdapter.notes` only returns `instruments[0]` | Aggregate across all instruments |
| 18 | Qt5 unscoped-enum access | PySide6 scoped enums |
| 19 | `pyqtSignal` / `pyqtSlot` | Replaced with `Signal` / `Slot` |
| 21 | `CameraAdapter.__del__` on shutdown | Context manager + explicit `close()` |
| 22 | Panel active state only via Tab | §8 (`mousePressEvent` → controller) |
| 23 | Float creep in locked-mode round-trip | §6 (`_exact` helper internally) |
| 24 | `.mp4` lowercase silently ignored | Case-insensitive extension match (`suffix.lower() in {".mp4"}`) in `participant_loader` |
| 26 | Non-atomic save | §9 (`.tmp` + `os.replace`) |
| 27 | Float `==` comparison on spinner | Tolerance `abs(a-b) < 1e-9` |

**Deferred, not fixed in v2:** audit items 3 (QImage buffer lifetime, already mitigated), 13 (sanity warning on suspicious shift magnitudes — UX call), 16 (tempo-pass perf — minor), 20 (QAction stylistic).

## 11. Testing strategy

Test scope: **math core + service layer**. No Qt in tests.

### Layout

```
tests/
├── conftest.py
├── fixtures.py          # synthetic MidiFileInfo / CameraFileInfo / Anchor builders
├── test_engine.py       # ~35 tests
├── test_service.py      # ~40 tests
└── test_persistence.py  # ~15 tests
```

### `test_engine.py` coverage

- Sign convention: positive shift corresponds to "MIDI ahead of camera" in every affected formula.
- Round-trip: `midi_unix → camera_frame → midi_seconds` lands within 1 frame of origin across a range of `(global_shift, capture_fps, duration)` combinations.
- `_exact` variant: chained through it, round-trip drift is zero.
- Out-of-range detection: before clip, after clip, exactly at frame 0, exactly at `total_frames - 1`, exactly at `total_frames`.
- `None` return paths: no active anchor, anchor referencing missing MIDI (via `get_effective_shift_for_camera`), negative frame, frame ≥ `total_frames`.
- `compute_global_shift_from_markers` sign.
- `out_of_range_delta` sign convention (positive = not started, negative = ended).

### `test_service.py` coverage

- `set_global_shift` with no anchors: state updated immediately, `anchors_to_clear == 0`.
- `set_global_shift` with anchors differing: state unchanged, result has `anchors_to_clear == N`; calling `confirm_global_shift(result)` clears and applies.
- `set_global_shift` with same value (within 1e-9 tolerance): no-op, no clearing.
- `add_anchor` appends to list, does not auto-activate.
- `add_anchor` with invalid frame / timestamp raises `InvalidAnchorError`.
- `add_anchor` with unknown MIDI filename raises `MissingMidiError`.
- `activate_anchor(idx)` sets `active_anchor_index`; `activate_anchor(None)` deactivates.
- `delete_anchor` at same index as active: deactivates.
- `delete_anchor` before active: decrements `active_anchor_index`.
- `delete_anchor` after active: no change.
- `delete_anchor` with invalid index raises `InvalidAnchorError`.
- Anchor-lock rule matrix: combinations of `{mode ∈ {independent, locked}, active_anchor ∈ {None, Some}, anchor_midi_resolvable ∈ {True, False}}`. Expected: `anchor_lock_target_midi == midi_idx` only when `mode == "locked"` AND `active_anchor` is set AND the referenced MIDI resolves.
- `markers_ready()` is `True` iff both markers set.

### `test_persistence.py` coverage

- v2 JSON round-trip preserves all fields exactly, including empty anchor lists and `None` `active_anchor_index`.
- Atomic write: a `monkeypatch`ed `json.dump` that raises mid-write leaves the target file untouched.
- Load with missing `participant_folder` raises `MediaNotFoundError` carrying the bad path.
- Load with anchor pointing to missing MIDI: anchor kept, `active_anchor_index` reset to `None` if it was pointing there, warning logged.
- Load with `schema_version != 2`: raises `SchemaVersionError`.

### Logging

All warnings raised during load (missing file basenames, diverging `total_frames`, auto-deactivated anchors) go through Python's `logging` module at `WARNING` level, under a logger named `alignment_tool.<module>`. `app.main()` configures a basic handler that writes to stderr. Log output is not surfaced in the UI in v2 — surfacing it is deferred.

### What is not tested

- Widgets, timeline drawing, scrubbing interactions, frame decoding, MIDI/camera adapter parsing of real files (these are covered by manual testing during rebuild + daily use).

## 12. Old code removal strategy

The writing-plans implementation plan sequences the cleanup such that v1 code is preserved until v2 runs end-to-end and tests pass:

1. New code is scaffolded under a new working directory layout (the structure in §4). The old `alignment_tool/` continues to exist alongside during scaffolding.
2. After v2 runs end-to-end against a real participant folder and all tests pass, a single cleanup commit removes: old `alignment_tool/*`, `docs/sections/`, `docs/index.md`, `docs/implementation_history_doc/` (if present), `scripts/`, `archives/`, stale `__pycache__/`.
3. The `docs/superpowers/` directory is preserved (contains this spec and the subsequent implementation plan).
4. A follow-up commit promotes or renames the scaffolded v2 package to `alignment_tool/`.

Exact branching / commit sequencing belongs in the implementation plan, not this design spec.

## 13. Open items for the implementation plan

The following concrete choices belong in the implementation plan, not here:

- Whether new code is built under a temporary package name and renamed at cleanup, or built directly into a new `alignment_tool/` subtree after old files are moved aside.
- Exact PySide6 version pin and any other dependency upgrades.
- Whether to add pre-commit tooling (ruff / black / mypy) during rebuild or defer.
- Any smoke-test participant folder to verify against during rebuild.
