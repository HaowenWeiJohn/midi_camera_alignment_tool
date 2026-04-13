# MIDI-Camera Alignment Tool — Refactor Design

**Date:** 2026-04-13
**Scope:** In-place refactor of the `alignment_tool/` package on `main` — structural reorganization, controller extraction, bug fixes, test suite, minimal docs.
**Out of scope:** `archives/`, `scripts/`, new features, CI setup, migration of existing saved JSON files.

## Goals

1. Carve a Qt-free controller/service layer out of the current god-object `Level2View` so alignment logic is testable without a running Qt app.
2. Centralize all `AlignmentState` mutations behind a single service so invariants (notably "changing `global_shift_seconds` clears anchors") cannot be bypassed.
3. Fix the P0/P1/P2 bugs catalogued in the 2026-04-13 audit. Chief among them: Load currently produces a half-functional state because media paths and derived counts are not persisted.
4. Reorganize the flat `alignment_tool/` package into four sub-packages (`core`, `io`, `services`, `ui`) reflecting a strict one-way dependency direction.
5. Introduce a Qt-free test suite (~45 tests, <1s total) covering `core` and `services`.
6. Replace the untracked 11-section `docs/` tree with a single `docs/ARCHITECTURE.md` plus a meaningful `README.md`.

## Non-Goals

- No new user-facing features.
- No migration code for alignment JSON files written by earlier versions — existing saves are throwaway. Old files will error with a clear message instead of silently half-loading.
- No `pytest-qt` or integration tests against real MIDI/MP4 fixtures.
- No asynchronous participant loading (still synchronous; a few seconds is acceptable).
- No GitHub Actions / CI wiring.

## Target Package Layout

```
alignment_tool/
├── __init__.py
├── __main__.py
├── app.py                          # QApplication boot (unchanged behavior)
│
├── core/                           # Qt-free, pure
│   ├── __init__.py
│   ├── models.py                   # dataclasses only; no mutation methods
│   ├── engine.py                   # renamed from alignment_engine.py
│   ├── persistence.py              # save/load + schema_version; atomic write
│   └── errors.py                   # AlignmentToolError hierarchy
│
├── io/                             # external I/O; may use QThread but no QWidget
│   ├── __init__.py
│   ├── midi_adapter.py
│   ├── camera_adapter.py
│   ├── participant_loader.py
│   └── frame_worker.py
│
├── services/                       # Qt-free controllers; sole state-mutation site
│   ├── __init__.py
│   ├── alignment_service.py        # THE write boundary for AlignmentState
│   └── level2_controller.py        # sync/marker/mode logic extracted from Level2View
│
└── ui/                             # everything QWidget
    ├── __init__.py
    ├── main_window.py
    ├── level1_timeline.py          # container
    ├── level1_canvas.py            # split paint/hit-test out of level1_timeline
    ├── level2_view.py              # thin; delegates to Level2Controller
    ├── level2_midi_panel.py
    ├── level2_camera_panel.py
    ├── level2_anchor_table.py
    └── level2_overlap_indicator.py
```

**Dependency rule (strict, enforced by a test):**

```
ui → services → io → core
```

- `core` imports only stdlib + dataclasses.
- `io` imports `core` plus external libs (`mido`, `pretty_midi`, `cv2`); may use `QThread` / `pyqtSignal` but never `QWidget`.
- `services` imports `core` and `io`; uses no Qt at all — not even `pyqtSignal`. Callers pass state in and read results out synchronously.
- `ui` imports all three.

The `tests/test_no_qt_in_core.py` test runs a subprocess with `PyQt5` poisoned in `sys.modules`; importing `alignment_tool.core` and `alignment_tool.services` must succeed there.

## Components — New Services

### `services/alignment_service.py`

The single write boundary for `AlignmentState`. UI widgets never touch state fields directly after this refactor; they call service methods that validate invariants, mutate in place, and return result dataclasses or raise typed exceptions.

```python
class AlignmentService:
    def __init__(self, state: AlignmentState) -> None: ...

    # --- global shift ---
    def set_global_shift(
        self, value: float, *, clear_anchors_if_needed: bool
    ) -> ShiftChangeResult:
        """
        If anchors exist and clear_anchors_if_needed is False → AnchorsExistError.
        If anchors exist and clear_anchors_if_needed is True  → clears all anchors, sets shift.
        If no anchors → sets shift.
        Returns ShiftChangeResult(previous_shift, cleared_anchor_count).
        """

    # --- anchors ---
    def add_anchor(self, camera_index: int, anchor: Anchor) -> int: ...
    def delete_anchor(self, camera_index: int, anchor_index: int) -> None: ...
    def set_active_anchor(
        self, camera_index: int, anchor_index: Optional[int]
    ) -> None: ...

    # --- pure reads (thin wrappers over core.engine) ---
    def effective_shift_for(self, camera_index: int) -> float: ...
    def anchor_shift_for(self, camera_index: int, anchor_index: int) -> Optional[float]: ...
```

**Invariants enforced here:**

- `set_global_shift` is the only code path that writes `state.global_shift_seconds`. The rule "clear anchors when shift changes" lives here, not at two UI call sites as today.
- `add_anchor` validates that `anchor.midi_filename` exists in `state.midi_files`; otherwise `UnknownMidiFileError`.
- `delete_anchor` fixes up `active_anchor_index` for the three cases (deleted index before / at / after active).

### `services/level2_controller.py`

Qt-free extraction of the logic currently embedded in `Level2View` (sync routing, mode state, marker state, shift-from-markers computation).

```python
@dataclass
class SyncOutput:
    new_midi_time:        Optional[float]  # None → no change
    new_camera_frame:     Optional[int]
    out_of_range_delta:   Optional[float]  # None → in range

class Mode(Enum):
    FREE = auto()
    LOCKED = auto()

class Level2Controller:
    def __init__(self, state: AlignmentState, service: AlignmentService) -> None: ...

    def load_pair(self, midi_index: int, camera_index: int) -> None: ...
    def set_mode(self, mode: Mode) -> None: ...

    def on_midi_position_changed(self, midi_time: float) -> SyncOutput: ...
    def on_camera_position_changed(self, camera_frame: int) -> SyncOutput: ...

    # markers
    def mark_midi(self, midi_time: float) -> None: ...
    def mark_camera(self, camera_frame: int) -> None: ...
    def clear_markers(self) -> None: ...
    def compute_shift_from_markers(self) -> float:      # → MarkersNotSetError if unset
        ...
    def build_anchor_from_markers(self, label: str = "") -> Anchor: ...
```

`Level2View` shrinks to widget construction, signal wiring (widget-signal → controller-method), and rendering `SyncOutput` back onto the panels. Target: <250 LOC, down from 574.

### Bug fixes by location

| Audit ref | Fix location |
|---|---|
| P0 — Lossy persistence on Load | `core/persistence.py` — schema v1 adds `participant_folder`, `mp4_path`, `xml_path`, `file_path`, `total_frames`, `ticks_per_beat`, `tempo`, `duration_seconds` |
| P0 — Invariant bypass on `global_shift` | `services/alignment_service.set_global_shift` — sole write path |
| P0 — Fragile mutation-order in `anchor_table` | Mutation moves to `service.set_active_anchor`; view calls service then emits signal |
| P1 — Divide-by-zero if `capture_fps == 0` | `core/engine.py` raises `InvalidFpsError`; `io/camera_adapter.py` refuses to build `CameraFileInfo` with `capture_fps <= 0` |
| P1 — Overlap drag feedback-loop risk | `ui/level2_overlap_indicator.py` wraps internal updates in `QSignalBlocker` |
| P1 — Camera worker lifetime on Level-2 hide | `ui/level2_camera_panel.py` stops worker in `hideEvent` as well as `closeEvent` |
| P1 — Stale frame after `open_video` | `io/frame_worker.py` adds a monotonic `generation` counter; stale frames discarded |
| P1 — `MidiAdapter` dead `_has_tempo_changes` | Removed |
| P1 — Case-sensitive `.mid`/`.MP4` filter | `io/participant_loader.py` — case-insensitive suffix match |
| P1 — Inline `QMessageBox` import | Hoisted to module top |
| P2 — Math duplicated in overlap indicator and `level2_view.py:506` | Both call `core.engine` |
| P2 — `notes[0]` assumption | Replaced with `min(n.start for n in notes)` |
| P2 — `MidiPanelWidget` reaches into `_canvas._midi_info` | Canvas exposes `midi_info` property |
| P2 — `models.clear_all_anchors` living on the model | Removed; the service owns this |

## Control & Data Flow

### State ownership

One `AlignmentState` lives on `MainWindow`. `AlignmentService` and `Level2Controller` hold references (not copies). Widgets never cache anything derivable from state.

### Write path (sole pattern)

```
widget signal
   │
   ▼
ui/*  →  service.method(...)
                 │
                 ▼
         alignment_service:
            - validates invariants
            - raises typed exception on violation
            - mutates AlignmentState in place
            - returns result dataclass
                 │
                 ▼
ui/* either catches exception → QMessageBox
     or reads result → refreshes affected widgets
```

Only two entry points for state mutation exist in the whole codebase:

1. `services/alignment_service.py` — runtime mutations.
2. `core/persistence.load_alignment()` — bulk replacement on File → Load.

Any other module that writes to `AlignmentState` fields is a review flag.

### Level-2 sync flow (FREE vs LOCKED)

```
MidiCanvas.position_changed(t) ──► Level2View._on_midi_position_changed(t)
                                        │
                                        ▼
                              Level2Controller.on_midi_position_changed(t)
                                        │
                              ┌─────────┴─────────┐
                            FREE                LOCKED
                              │                   │
                        SyncOutput(            SyncOutput(
                         mid=None,              mid=None,
                         cam=None,              cam=f,
                         oor=None               oor=δ or None
                        )                      )
                                        │
                                        ▼
                         Level2View renders the output:
                           - QSignalBlocker on camera_panel
                           - camera_panel.set_frame(f) if not None
                           - update OOR label with δ
                           - unblock
```

Feedback-loop prevention is now explicit (`QSignalBlocker`) rather than relying on accidental float-equality early-outs.

### Startup / Load sequence

```
python -m alignment_tool
    ↓
app.py: QApplication + MainWindow()
    ↓
MainWindow.__init__:
    - self._state = None
    - self._service = None
    - self._controller = None
    - build menus + empty QStackedWidget
    ↓
File → Open Participant:
    - participant_loader.load(path) → AlignmentState
    - build AlignmentService and Level2Controller from the new state
    - level1_widget.set_state(state)
    - level2_view.attach(state, service, controller)
    ↓
File → Save Alignment:
    - core.persistence.save_alignment(state, path)    (atomic)
    ↓
File → Load Alignment:
    - state = core.persistence.load_alignment(path)
    - same assignment path as Open Participant
    - no split-brain: media paths come from the JSON
```

### Threading

One `QThread` for `FrameWorker` — shape unchanged. Guarantees tightened:

- Monotonic `generation` counter on the worker; frames from a prior `open_video` are discarded by generation mismatch.
- `CameraPanelWidget.hideEvent` stops the worker, matching `closeEvent`. Fixes the cv2 handle leak on Level-2 ↔ Level-1 drill-back.
- All cross-thread slots are decorated `@pyqtSlot`.

`participant_loader` remains synchronous. Async loading is a deliberate non-goal for this pass.

### Error surfaces

- `print(…)` is removed from the runtime path. Short lifecycle logs go through Python `logging`.
- `io/frame_worker.py` emits an `open_failed(str)` signal; `CameraPanelWidget` shows a red overlay instead of a blank frame.
- `io/midi_adapter.py` and `io/camera_adapter.py` raise `MediaLoadError(path, reason)` in constructors.
- `participant_loader.load` catches per-file `MediaLoadError` and returns `ParticipantLoadResult(state, warnings: list[str])`; `MainWindow` surfaces warnings in a non-modal dialog.
- `services/*` raises `InvariantError` subclasses; UI maps each to the appropriate dialog via a single `_show_exception(exc)` helper.

## Persistence Schema (v1)

```json
{
  "schema_version": 1,
  "participant_folder": "C:/.../participant_042",
  "global_shift_seconds": 0.42,
  "alignment_notes": "",
  "midi_files": [
    {
      "filename": "trial_003.mid",
      "file_path": "C:/.../trial_003.mid",
      "start_unix": 1712000000.0,
      "end_unix":   1712000182.5,
      "duration_seconds": 182.5,
      "ticks_per_beat": 480,
      "tempo": 500000
    }
  ],
  "camera_files": [
    {
      "filename": "C0001.MP4",
      "mp4_path": "C:/.../C0001.MP4",
      "xml_path": "C:/.../C0001M01.XML",
      "raw_unix_start": 1712000030.0,
      "duration_seconds": 90.0,
      "capture_fps": 239.76,
      "total_frames": 21578,
      "active_anchor_index": 0,
      "alignment_anchors": [
        {
          "label": "",
          "midi_filename": "trial_003.mid",
          "midi_timestamp_seconds": 12.347,
          "camera_frame": 1420
        }
      ]
    }
  ]
}
```

**Changes from the pre-refactor format:**

- `schema_version: 1` is required. Missing or higher → `UnsupportedSchemaVersionError`. Makes future bumps cheap.
- All fields previously dropped on save (`participant_folder`, `file_path`, `mp4_path`, `xml_path`, `total_frames`, `ticks_per_beat`, `tempo`, `duration_seconds`) are now required. Load alone becomes sufficient for Level 2 to function.
- No legacy compatibility code. Old files error out cleanly.

**Write safety:** `tempfile.NamedTemporaryFile` in the same directory + `os.replace`. No half-written JSON on crash.

**Load behavior when media is missing:** state still loads; affected `MidiFileInfo` / `CameraFileInfo` are flagged with a runtime-only `_missing: True` (not persisted); timeline draws them greyed out; user gets a non-modal warning list.

## Exception Hierarchy

```
alignment_tool.core.errors
├── AlignmentToolError                 # base — every dialog path catches this
│
├── MediaLoadError(path, reason)
│   ├── MidiParseError
│   ├── CameraXmlParseError
│   └── VideoOpenError
│
├── PersistenceError
│   ├── UnsupportedSchemaVersionError(found, supported)
│   └── CorruptAlignmentFileError(path, reason)
│
└── InvariantError
    ├── AnchorsExistError(count)
    ├── InvalidAnchorError(reason)
    ├── UnknownMidiFileError(name)
    ├── InvalidFpsError
    └── MarkersNotSetError
```

UI has one helper, `_show_exception(exc)`, mapping each type to critical / warning / info dialogs. No uncaught exceptions reach the Qt event loop.

## Testing Strategy

**Target:** ~45 tests, all Qt-free, <1s total runtime.

```
tests/
├── conftest.py                     # shared fixtures
├── fixtures.py                     # make_state(), make_midi_file(), make_camera_file(), make_anchor()
├── test_no_qt_in_core.py           # subprocess test — PyQt5 forbidden
├── test_engine.py                  # ~10 tests: pure math
├── test_persistence.py             # ~8 tests: round-trip + schema + atomic write
├── test_alignment_service.py       # ~15 tests: invariants + mutations
├── test_level2_controller.py       # ~12 tests: sync/markers/modes
└── test_errors.py                  # ~3 tests: exception wiring
```

### Coverage per file

- **`test_engine.py`** — `compute_effective_shift`, `compute_anchor_shift`, `midi_seconds_to_camera_frame` round-trip, `out_of_range_delta` boundaries (before / at-edge / after / zero), `InvalidFpsError` guard.
- **`test_persistence.py`** — round-trip equality on a fully-populated state; missing `schema_version` → error; higher `schema_version` → error; atomic write leaves no partial file under injected failure; Unicode filenames; zero-anchor camera files.
- **`test_alignment_service.py`** — `set_global_shift` with / without anchors; with anchors + `clear=False` → raises; with anchors + `clear=True` → clears; `add_anchor` with unknown MIDI → raises; `delete_anchor` fixes up `active_anchor_index` (before / at / after active); `set_active_anchor(None)` clears lock derivation; `effective_shift_for` falls back to global with no anchors.
- **`test_level2_controller.py`** — mode toggle produces the correct `SyncOutput` shape; `on_midi_position_changed` in FREE mode → null delta; in LOCKED mode → correct frame; OOR boundaries (before clip start / after end / exactly at edge); `mark_* → compute_shift_from_markers → build_anchor_from_markers` round-trip.
- **`test_no_qt_in_core.py`** — subprocess imports `alignment_tool.core` and `alignment_tool.services` with `sys.modules["PyQt5"]` poisoned; passes iff no Qt leaks in.
- **`test_errors.py`** — each `InvariantError` subclass carries the documented attributes (e.g. `AnchorsExistError(count=3).count == 3`).

### Explicitly not tested

- `io/` adapters (would require fixture MP4/MIDI binaries).
- `ui/` widgets (would require `pytest-qt`).
- End-to-end Open → Save → Load via real files on disk.

### Conventions

- Each test ≤20 lines, arrange-act-assert with blank-line separators, one behavior per test.
- Fixtures construct state via `fixtures.make_state(...)`, never by reading disk.
- No mocks of `core.engine` or `services` — they're cheap to run for real.

## Documentation Strategy

Discard the untracked `docs/sections/` (11 files). Replace with:

- `docs/ARCHITECTURE.md` — ~1 page covering the `core/io/services/ui` layering, dependency direction, the two-phase alignment invariant, and the persistence schema. Written so a collaborator can onboard without reading every module.
- `README.md` — updated from its current one-line state: install, run, data layout expected, two-phase workflow summary, pointer to `docs/ARCHITECTURE.md`.

No module-by-module reference doc. Module docstrings + type hints carry that weight.

## Implementation Order (sketch for the plan)

The follow-on plan (created via `writing-plans`) will break this into review-checkpointable steps. The natural order:

1. Introduce `core/errors.py` and the new schema v1 in `core/persistence.py`. Tests: `test_persistence`, `test_errors`.
2. Move dataclasses into `core/models.py`; strip mutation methods. Rename `alignment_engine.py` → `core/engine.py`. Fix divide-by-zero. Tests: `test_engine`.
3. Introduce `services/alignment_service.py`. Tests: `test_alignment_service`. Adjust existing UI call sites to route mutations through the service.
4. Introduce `services/level2_controller.py`, extracting logic out of `level2_view.py`. Tests: `test_level2_controller`.
5. Move `io/` modules into their folder; apply P1 fixes (`frame_worker` generation counter, `hideEvent` stop, case-insensitive suffix).
6. Move `ui/` modules into their folder; thin `level2_view.py`; collapse math duplication into `core.engine` calls.
7. Add `test_no_qt_in_core.py`.
8. Write `docs/ARCHITECTURE.md` and update `README.md`. Delete the untracked `docs/sections/` tree.

Each step leaves the app runnable on `python -m alignment_tool`.
