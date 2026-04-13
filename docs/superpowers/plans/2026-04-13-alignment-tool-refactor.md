# MIDI-Camera Alignment Tool Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In-place refactor of `alignment_tool/` into `core`/`io`/`services`/`ui` sub-packages, extracting a Qt-free controller/service layer out of `Level2View`, centralizing all state mutations behind a single service, fixing the P0/P1/P2 bugs catalogued in the 2026-04-13 audit, and adding a Qt-free test suite.

**Architecture:** Strict one-way dependency: `ui → services → io → core`. `core` is pure (stdlib + dataclasses). `io` may use `QThread` / `pyqtSignal` but never `QWidget`. `services` is Qt-free (no `pyqtSignal` either) — UI calls service methods synchronously, service mutates state and returns results or raises typed exceptions. `ui` owns all widgets and catches exceptions into dialogs.

**Tech Stack:** Python 3.12, PyQt5, `mido`, `pretty_midi`, OpenCV (cv2), numpy, pytest.

**Linked spec:** `docs/superpowers/specs/2026-04-13-alignment-tool-refactor-design.md`

---

## Working Conventions

- **TDD** for every Qt-free change: failing test → minimal code → passing test → commit.
- **Commit after every task.** Each task ends in a green state where `python -m alignment_tool` still launches.
- **No legacy JSON compatibility.** Old saves are throwaway per the spec.
- **No mocks** of `core.engine` or `services` in tests — they're cheap to run for real.
- **Run tests with:** `pytest tests/ -v` from repo root.
- **Run the app with:** `python -m alignment_tool` from repo root.
- All new code uses `from __future__ import annotations` to match existing style.

---

## File Structure (end state)

```
alignment_tool/
├── __init__.py
├── __main__.py                        # unchanged
├── app.py                             # unchanged (QApplication boot)
│
├── core/
│   ├── __init__.py
│   ├── errors.py                      # NEW — exception hierarchy
│   ├── models.py                      # MOVED, trimmed (no mutation methods)
│   ├── engine.py                      # MOVED from alignment_engine.py, divide-by-zero fix
│   └── persistence.py                 # REWRITTEN — schema v1, atomic write, full fields
│
├── io/
│   ├── __init__.py
│   ├── midi_adapter.py                # MOVED, dead state removed
│   ├── camera_adapter.py              # MOVED, raises MediaLoadError + InvalidFpsError
│   ├── participant_loader.py          # MOVED, case-insensitive suffixes, returns ParticipantLoadResult
│   └── frame_worker.py                # MOVED, generation counter, open_failed signal
│
├── services/
│   ├── __init__.py
│   ├── alignment_service.py           # NEW — sole write boundary
│   └── level2_controller.py           # NEW — mode/sync/marker extraction
│
└── ui/
    ├── __init__.py
    ├── main_window.py                 # MOVED, wires service/controller, logging, warnings
    ├── level1_timeline.py             # MOVED, shift writes go through service
    ├── level2_view.py                 # MOVED, thinned (<250 LOC target)
    ├── level2_midi_panel.py           # MOVED from midi_panel.py, midi_info property
    ├── level2_camera_panel.py         # MOVED from camera_panel.py, hideEvent stop
    ├── level2_anchor_table.py         # MOVED, routes mutations through service
    └── level2_overlap_indicator.py    # MOVED, uses core.engine math

tests/
├── conftest.py                        # shared fixtures
├── fixtures.py                        # make_state, make_midi_file, make_camera_file, make_anchor
├── test_engine.py
├── test_persistence.py
├── test_alignment_service.py
├── test_level2_controller.py
├── test_errors.py
└── test_no_qt_in_core.py              # subprocess test
```

**Ordering rationale:** Tasks 1–3 are pure mechanical moves (each commit leaves behavior unchanged). Tasks 4–9 build the new Qt-free primitives in TDD. Tasks 10–15 rewire the UI to use those primitives and collapse the god-object. Tasks 16–17 add the cross-cutting import-direction test and ship docs.

---

## Task 1: Create `core/`, `io/`, `services/`, `ui/` package skeleton

**Files:**
- Create: `alignment_tool/core/__init__.py`
- Create: `alignment_tool/io/__init__.py`
- Create: `alignment_tool/services/__init__.py`
- Create: `alignment_tool/ui/__init__.py`
- Delete: `tests/__pycache__/` (stale pyc from deleted test suite per audit)

- [ ] **Step 1: Create the four empty sub-package markers.**

Each file contains a single line:

```python
"""alignment_tool.<subpkg> — see docs/superpowers/specs/2026-04-13-alignment-tool-refactor-design.md."""
```

- [ ] **Step 2: Delete stale pyc cache.**

Run: `rm -rf tests/__pycache__`

- [ ] **Step 3: Verify nothing broke.**

Run: `python -m alignment_tool`
Expected: App launches. Click File → exit. No import errors.

- [ ] **Step 4: Commit.**

```bash
git add alignment_tool/core/__init__.py alignment_tool/io/__init__.py alignment_tool/services/__init__.py alignment_tool/ui/__init__.py
git rm -r tests/__pycache__ 2>/dev/null || true
git commit -m "Scaffold core/io/services/ui sub-packages"
```

---

## Task 2: Move `models.py`, `alignment_engine.py`, `persistence.py` into `core/` (mechanical)

**Files:**
- Move: `alignment_tool/models.py` → `alignment_tool/core/models.py`
- Move: `alignment_tool/alignment_engine.py` → `alignment_tool/core/engine.py`
- Move: `alignment_tool/persistence.py` → `alignment_tool/core/persistence.py`
- Modify (import rewrites): every `.py` that imports these modules

This is a pure mechanical move. No behavior changes. `clear_all_anchors` on `AlignmentState` stays for now — we'll remove it once call sites are rewired in later tasks.

- [ ] **Step 1: Move the three files.**

```bash
git mv alignment_tool/models.py alignment_tool/core/models.py
git mv alignment_tool/alignment_engine.py alignment_tool/core/engine.py
git mv alignment_tool/persistence.py alignment_tool/core/persistence.py
```

- [ ] **Step 2: Rewrite imports in `core/engine.py`.**

Current line 7:

```python
from alignment_tool.models import Anchor, CameraFileInfo, MidiFileInfo
```

Becomes:

```python
from alignment_tool.core.models import Anchor, CameraFileInfo, MidiFileInfo
```

- [ ] **Step 3: Rewrite imports in `core/persistence.py`.**

Current lines 10-12:

```python
from alignment_tool.models import (
    AlignmentState, MidiFileInfo, CameraFileInfo, Anchor,
)
```

Becomes:

```python
from alignment_tool.core.models import (
    AlignmentState, MidiFileInfo, CameraFileInfo, Anchor,
)
```

- [ ] **Step 4: Rewrite imports everywhere else.**

Use Grep to find callers, then edit each:

```
alignment_tool/alignment_engine  →  alignment_tool.core.engine
alignment_tool.models            →  alignment_tool.core.models
alignment_tool.persistence       →  alignment_tool.core.persistence
alignment_tool import alignment_engine  →  alignment_tool.core import engine
alignment_tool import persistence        →  alignment_tool.core import persistence
```

Expected touched files (verify with Grep):
- `alignment_tool/main_window.py`
- `alignment_tool/level1_timeline.py`
- `alignment_tool/level2_view.py`
- `alignment_tool/midi_panel.py`
- `alignment_tool/camera_panel.py`
- `alignment_tool/anchor_table.py`
- `alignment_tool/overlap_indicator.py`
- `alignment_tool/midi_adapter.py`
- `alignment_tool/camera_adapter.py`
- `alignment_tool/participant_loader.py`

- [ ] **Step 5: Verify app still launches.**

Run: `python -m alignment_tool`
Expected: Window opens, no import errors in console.

- [ ] **Step 6: Commit.**

```bash
git add -A
git commit -m "Move models, engine, persistence into core/ sub-package"
```

---

## Task 3: Move adapters, loader, worker into `io/` (mechanical)

**Files:**
- Move: `alignment_tool/midi_adapter.py` → `alignment_tool/io/midi_adapter.py`
- Move: `alignment_tool/camera_adapter.py` → `alignment_tool/io/camera_adapter.py`
- Move: `alignment_tool/participant_loader.py` → `alignment_tool/io/participant_loader.py`
- Move: `alignment_tool/frame_worker.py` → `alignment_tool/io/frame_worker.py`
- Modify imports: all UI call sites + loader (which imports adapters)

Pure mechanical. No behavior changes.

- [ ] **Step 1: Move the four files.**

```bash
git mv alignment_tool/midi_adapter.py alignment_tool/io/midi_adapter.py
git mv alignment_tool/camera_adapter.py alignment_tool/io/camera_adapter.py
git mv alignment_tool/participant_loader.py alignment_tool/io/participant_loader.py
git mv alignment_tool/frame_worker.py alignment_tool/io/frame_worker.py
```

- [ ] **Step 2: Rewrite imports.**

Replace each of these across the repo:

```
alignment_tool.midi_adapter        →  alignment_tool.io.midi_adapter
alignment_tool.camera_adapter      →  alignment_tool.io.camera_adapter
alignment_tool.participant_loader  →  alignment_tool.io.participant_loader
alignment_tool.frame_worker        →  alignment_tool.io.frame_worker
```

And each adapter / loader internal import of `alignment_tool.core.models` stays as-is (already fixed in Task 2).

- [ ] **Step 3: Verify app launches and loads a participant.**

Run: `python -m alignment_tool`
Try File → Open Participant → pick a folder. Expected: Level 1 timeline populates. No console errors.

- [ ] **Step 4: Commit.**

```bash
git add -A
git commit -m "Move adapters, loader, worker into io/ sub-package"
```

---

## Task 4: Move UI widgets into `ui/` (mechanical, with rename)

**Files:**
- Move: `alignment_tool/main_window.py` → `alignment_tool/ui/main_window.py`
- Move: `alignment_tool/level1_timeline.py` → `alignment_tool/ui/level1_timeline.py`
- Move: `alignment_tool/level2_view.py` → `alignment_tool/ui/level2_view.py`
- Move & rename: `alignment_tool/midi_panel.py` → `alignment_tool/ui/level2_midi_panel.py`
- Move & rename: `alignment_tool/camera_panel.py` → `alignment_tool/ui/level2_camera_panel.py`
- Move & rename: `alignment_tool/anchor_table.py` → `alignment_tool/ui/level2_anchor_table.py`
- Move & rename: `alignment_tool/overlap_indicator.py` → `alignment_tool/ui/level2_overlap_indicator.py`
- Modify: `alignment_tool/app.py` (import path to `main_window`)

- [ ] **Step 1: Move and rename the UI files.**

```bash
git mv alignment_tool/main_window.py alignment_tool/ui/main_window.py
git mv alignment_tool/level1_timeline.py alignment_tool/ui/level1_timeline.py
git mv alignment_tool/level2_view.py alignment_tool/ui/level2_view.py
git mv alignment_tool/midi_panel.py alignment_tool/ui/level2_midi_panel.py
git mv alignment_tool/camera_panel.py alignment_tool/ui/level2_camera_panel.py
git mv alignment_tool/anchor_table.py alignment_tool/ui/level2_anchor_table.py
git mv alignment_tool/overlap_indicator.py alignment_tool/ui/level2_overlap_indicator.py
```

- [ ] **Step 2: Rewrite imports.**

Replace these across the repo:

```
alignment_tool.main_window          →  alignment_tool.ui.main_window
alignment_tool.level1_timeline      →  alignment_tool.ui.level1_timeline
alignment_tool.level2_view          →  alignment_tool.ui.level2_view
alignment_tool.midi_panel           →  alignment_tool.ui.level2_midi_panel
alignment_tool.camera_panel         →  alignment_tool.ui.level2_camera_panel
alignment_tool.anchor_table         →  alignment_tool.ui.level2_anchor_table
alignment_tool.overlap_indicator    →  alignment_tool.ui.level2_overlap_indicator
```

Class names (`MidiPanelWidget`, `CameraPanelWidget`, `AnchorTableWidget`, `OverlapIndicatorWidget`) remain unchanged — only the module paths change.

- [ ] **Step 3: Verify `app.py` imports.**

`alignment_tool/app.py` should now import `from alignment_tool.ui.main_window import MainWindow`.

- [ ] **Step 4: Verify app launches and full smoke test.**

Run: `python -m alignment_tool`
- Open a participant. Drill into Level 2. Scrub MIDI panel. Toggle mode. Back out. Save. Exit.
- Expected: All functional, no console errors.

- [ ] **Step 5: Commit.**

```bash
git add -A
git commit -m "Move UI widgets into ui/ sub-package"
```

---

## Task 5: Add `core/errors.py` with exception hierarchy + tests

**Files:**
- Create: `alignment_tool/core/errors.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py` (empty for now; will expand later)
- Create: `tests/test_errors.py`

- [ ] **Step 1: Write failing test.**

Create `tests/test_errors.py`:

```python
from alignment_tool.core.errors import (
    AlignmentToolError,
    MediaLoadError, MidiParseError, CameraXmlParseError, VideoOpenError,
    PersistenceError, UnsupportedSchemaVersionError, CorruptAlignmentFileError,
    InvariantError, AnchorsExistError, InvalidAnchorError,
    UnknownMidiFileError, InvalidFpsError, MarkersNotSetError,
)


def test_all_errors_inherit_from_base():
    for cls in (
        MediaLoadError, MidiParseError, CameraXmlParseError, VideoOpenError,
        PersistenceError, UnsupportedSchemaVersionError, CorruptAlignmentFileError,
        InvariantError, AnchorsExistError, InvalidAnchorError,
        UnknownMidiFileError, InvalidFpsError, MarkersNotSetError,
    ):
        assert issubclass(cls, AlignmentToolError), cls.__name__


def test_media_load_error_carries_path_and_reason():
    exc = MidiParseError(path="/x/y.mid", reason="corrupt header")
    assert exc.path == "/x/y.mid"
    assert exc.reason == "corrupt header"
    assert "/x/y.mid" in str(exc)
    assert "corrupt header" in str(exc)


def test_anchors_exist_error_carries_count():
    exc = AnchorsExistError(count=3)
    assert exc.count == 3
    assert "3" in str(exc)


def test_unsupported_schema_version_error_carries_found_and_supported():
    exc = UnsupportedSchemaVersionError(found=99, supported=1)
    assert exc.found == 99
    assert exc.supported == 1
```

Create empty `tests/__init__.py` and `tests/conftest.py` (both empty).

- [ ] **Step 2: Run to verify failure.**

Run: `pytest tests/test_errors.py -v`
Expected: ImportError — `alignment_tool.core.errors` doesn't exist.

- [ ] **Step 3: Implement `core/errors.py`.**

```python
"""Exception hierarchy for the alignment tool. All exceptions inherit from AlignmentToolError."""
from __future__ import annotations


class AlignmentToolError(Exception):
    """Base for every domain exception raised by the tool."""


class MediaLoadError(AlignmentToolError):
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


class MidiParseError(MediaLoadError):
    pass


class CameraXmlParseError(MediaLoadError):
    pass


class VideoOpenError(MediaLoadError):
    pass


class PersistenceError(AlignmentToolError):
    pass


class UnsupportedSchemaVersionError(PersistenceError):
    def __init__(self, found: int, supported: int):
        self.found = found
        self.supported = supported
        super().__init__(
            f"Alignment JSON schema_version={found} not supported (this build supports {supported})."
        )


class CorruptAlignmentFileError(PersistenceError):
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


class InvariantError(AlignmentToolError):
    """Raised by services when a requested mutation would break an invariant."""


class AnchorsExistError(InvariantError):
    def __init__(self, count: int):
        self.count = count
        super().__init__(
            f"Cannot change global shift while {count} anchor(s) exist; "
            "pass clear_anchors_if_needed=True to proceed."
        )


class InvalidAnchorError(InvariantError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class UnknownMidiFileError(InvariantError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Anchor references unknown MIDI file: {name!r}")


class InvalidFpsError(InvariantError):
    def __init__(self, fps: float):
        self.fps = fps
        super().__init__(f"capture_fps must be > 0, got {fps}")


class MarkersNotSetError(InvariantError):
    def __init__(self):
        super().__init__("Both MIDI and camera markers must be set first.")
```

- [ ] **Step 4: Run tests to verify pass.**

Run: `pytest tests/test_errors.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit.**

```bash
git add alignment_tool/core/errors.py tests/__init__.py tests/conftest.py tests/test_errors.py
git commit -m "Add core.errors exception hierarchy with tests"
```

---

## Task 6: Trim `core/models.py` (remove mutation methods, add test fixtures)

**Files:**
- Modify: `alignment_tool/core/models.py` — remove `clear_all_anchors` method (callers will be rewired in Tasks 12 & 13); keep `get_active_anchor`, `midi_file_by_name`, `total_anchor_count`, `clips_with_anchors_count` (pure reads).
- Create: `tests/fixtures.py` — `make_anchor`, `make_midi_file`, `make_camera_file`, `make_state`

**Note:** `clear_all_anchors` is used by `level1_timeline.py:413` and `level2_view.py:406`. We leave it in place for now — Tasks 12 and 13 will replace those call sites with `service.set_global_shift(..., clear_anchors_if_needed=True)`, and we'll delete the method after both rewirings land. This task only creates the fixtures library that later tests depend on.

- [ ] **Step 1: Create `tests/fixtures.py`.**

```python
"""Factory helpers for building test states. No disk I/O."""
from __future__ import annotations

from alignment_tool.core.models import (
    Anchor, MidiFileInfo, CameraFileInfo, AlignmentState,
)


def make_anchor(
    midi_filename: str = "trial_001.mid",
    midi_timestamp_seconds: float = 1.0,
    camera_frame: int = 240,
    label: str = "",
) -> Anchor:
    return Anchor(
        midi_filename=midi_filename,
        midi_timestamp_seconds=midi_timestamp_seconds,
        camera_frame=camera_frame,
        label=label,
    )


def make_midi_file(
    filename: str = "trial_001.mid",
    unix_start: float = 1_712_000_000.0,
    duration: float = 100.0,
    sample_rate: float = 1920.0,
    ticks_per_beat: int = 480,
    tempo: float = 500_000.0,
    file_path: str = "/fake/trial_001.mid",
) -> MidiFileInfo:
    return MidiFileInfo(
        filename=filename,
        unix_start=unix_start,
        unix_end=unix_start + duration,
        duration=duration,
        sample_rate=sample_rate,
        ticks_per_beat=ticks_per_beat,
        tempo=tempo,
        file_path=file_path,
    )


def make_camera_file(
    filename: str = "C0001.MP4",
    xml_filename: str = "C0001M01.XML",
    raw_unix_start: float = 1_712_000_030.0,
    duration: float = 90.0,
    capture_fps: float = 239.76,
    mp4_path: str = "/fake/C0001.MP4",
    xml_path: str = "/fake/C0001M01.XML",
    anchors: list[Anchor] | None = None,
    active_anchor_index: int | None = None,
) -> CameraFileInfo:
    total_frames = int(round(duration * capture_fps))
    return CameraFileInfo(
        filename=filename,
        xml_filename=xml_filename,
        raw_unix_start=raw_unix_start,
        raw_unix_end=raw_unix_start + duration,
        duration=duration,
        capture_fps=capture_fps,
        total_frames=total_frames,
        mp4_path=mp4_path,
        xml_path=xml_path,
        alignment_anchors=list(anchors) if anchors else [],
        active_anchor_index=active_anchor_index,
    )


def make_state(
    participant_id: str = "P042",
    participant_folder: str = "/fake/P042",
    global_shift: float = 0.0,
    midi_files: list[MidiFileInfo] | None = None,
    camera_files: list[CameraFileInfo] | None = None,
) -> AlignmentState:
    return AlignmentState(
        participant_id=participant_id,
        participant_folder=participant_folder,
        global_shift_seconds=global_shift,
        midi_files=midi_files if midi_files is not None else [make_midi_file()],
        camera_files=camera_files if camera_files is not None else [make_camera_file()],
    )
```

- [ ] **Step 2: Sanity-check that fixtures build.**

Create a one-off quick test at the end of `tests/test_errors.py`:

```python
def test_fixtures_build():
    from tests.fixtures import make_state
    s = make_state()
    assert s.participant_id == "P042"
    assert len(s.midi_files) == 1
    assert len(s.camera_files) == 1
```

Run: `pytest tests/test_errors.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit.**

```bash
git add tests/fixtures.py tests/test_errors.py
git commit -m "Add test fixtures for state, midi, camera, anchor"
```

---

## Task 7: Tests for `core/engine.py` + divide-by-zero fix

**Files:**
- Modify: `alignment_tool/core/engine.py` — raise `InvalidFpsError` in any function that divides by `capture_fps` when `capture_fps <= 0`. The `get_effective_shift_for_camera` / `midi_unix_to_camera_frame` / `camera_frame_to_midi_seconds` / `camera_frame_to_unix` / `out_of_range_delta` call chain all dereference `camera.capture_fps`; guard at the bottom primitives.
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests for existing behavior + fps guard.**

```python
from __future__ import annotations

import pytest

from alignment_tool.core import engine
from alignment_tool.core.errors import InvalidFpsError
from tests.fixtures import make_anchor, make_camera_file, make_midi_file


def test_compute_effective_shift_is_simple_sum():
    assert engine.compute_effective_shift(1.0, 0.25) == 1.25


def test_compute_anchor_shift_round_trips():
    midi = make_midi_file(unix_start=1000.0)
    cam = make_camera_file(raw_unix_start=1030.0, capture_fps=240.0)
    anchor = make_anchor(
        midi_filename=midi.filename,
        midi_timestamp_seconds=12.0,
        camera_frame=1200,  # = 5s into clip
    )

    shift = engine.compute_anchor_shift(anchor, cam, midi, global_shift=0.0)

    midi_unix = midi.unix_start + anchor.midi_timestamp_seconds        # 1012
    cam_unix = cam.raw_unix_start + anchor.camera_frame / cam.capture_fps  # 1035
    assert shift == pytest.approx(midi_unix - cam_unix)


def test_get_effective_shift_for_camera_no_anchor_returns_global():
    cam = make_camera_file()
    midi_map = {"trial_001.mid": make_midi_file()}

    assert engine.get_effective_shift_for_camera(cam, 0.5, midi_map) == 0.5


def test_get_effective_shift_for_camera_with_active_anchor_applies_it():
    midi = make_midi_file(unix_start=1000.0)
    cam = make_camera_file(
        raw_unix_start=1030.0,
        capture_fps=240.0,
        anchors=[make_anchor(midi_filename=midi.filename, midi_timestamp_seconds=5.0, camera_frame=0)],
        active_anchor_index=0,
    )

    eff = engine.get_effective_shift_for_camera(cam, 0.0, {midi.filename: midi})

    # anchor says MIDI t=5 aligns to camera frame 0 → shift = (1000+5) - (1030+0) = -25
    assert eff == pytest.approx(-25.0)


def test_midi_unix_to_camera_frame_in_range():
    cam = make_camera_file(raw_unix_start=1000.0, capture_fps=240.0, duration=10.0)
    frame = engine.midi_unix_to_camera_frame(midi_unix=1001.0, effective_shift=0.0, camera=cam)
    assert frame == 240


def test_midi_unix_to_camera_frame_before_start_returns_none():
    cam = make_camera_file(raw_unix_start=1000.0, capture_fps=240.0, duration=10.0)
    assert engine.midi_unix_to_camera_frame(midi_unix=999.0, effective_shift=0.0, camera=cam) is None


def test_midi_unix_to_camera_frame_after_end_returns_none():
    cam = make_camera_file(raw_unix_start=1000.0, capture_fps=240.0, duration=10.0)
    assert engine.midi_unix_to_camera_frame(midi_unix=1020.0, effective_shift=0.0, camera=cam) is None


def test_camera_frame_to_midi_seconds_round_trips_with_midi_unix_to_camera_frame():
    midi = make_midi_file(unix_start=1000.0, duration=100.0)
    cam = make_camera_file(raw_unix_start=1030.0, capture_fps=240.0, duration=60.0)

    seconds = engine.camera_frame_to_midi_seconds(
        frame=240, effective_shift=0.0, camera=cam, midi=midi,
    )
    assert seconds is not None
    # inverse:
    recovered_frame = engine.midi_unix_to_camera_frame(
        midi_unix=midi.unix_start + seconds, effective_shift=0.0, camera=cam,
    )
    assert recovered_frame == 240


def test_out_of_range_delta_before_start_is_positive():
    cam = make_camera_file(raw_unix_start=1000.0, duration=10.0)
    delta = engine.out_of_range_delta(midi_unix=998.0, effective_shift=0.0, camera=cam)
    assert delta == pytest.approx(2.0)


def test_out_of_range_delta_after_end_is_negative():
    cam = make_camera_file(raw_unix_start=1000.0, duration=10.0)
    delta = engine.out_of_range_delta(midi_unix=1015.0, effective_shift=0.0, camera=cam)
    assert delta == pytest.approx(-5.0)


def test_out_of_range_delta_in_range_is_none():
    cam = make_camera_file(raw_unix_start=1000.0, duration=10.0)
    assert engine.out_of_range_delta(midi_unix=1005.0, effective_shift=0.0, camera=cam) is None


def test_zero_fps_raises_invalid_fps_error():
    cam = make_camera_file(capture_fps=0.0)
    midi = make_midi_file()
    with pytest.raises(InvalidFpsError):
        engine.midi_unix_to_camera_frame(midi_unix=1000.0, effective_shift=0.0, camera=cam)
    with pytest.raises(InvalidFpsError):
        engine.camera_frame_to_midi_seconds(frame=0, effective_shift=0.0, camera=cam, midi=midi)
    with pytest.raises(InvalidFpsError):
        engine.camera_frame_to_unix(frame=0, camera=cam)
    with pytest.raises(InvalidFpsError):
        engine.compute_anchor_shift(
            make_anchor(), cam, midi, global_shift=0.0,
        )
```

- [ ] **Step 2: Run to verify failures.**

Run: `pytest tests/test_engine.py -v`
Expected: ~3 tests fail (the `InvalidFpsError` tests — `ZeroDivisionError` is raised instead).

- [ ] **Step 3: Add fps guard in `core/engine.py`.**

Edit `alignment_tool/core/engine.py` — add import and a private guard:

```python
from alignment_tool.core.errors import InvalidFpsError


def _check_fps(camera: CameraFileInfo) -> None:
    if camera.capture_fps <= 0:
        raise InvalidFpsError(camera.capture_fps)
```

Then at the top of each function that divides or multiplies by `camera.capture_fps`, call `_check_fps(camera)` as the first statement:

- `compute_anchor_shift`
- `midi_unix_to_camera_frame`
- `camera_frame_to_midi_seconds`
- `camera_frame_to_unix`

Note `out_of_range_delta` does not touch `capture_fps` directly, so no guard needed there.

- [ ] **Step 4: Run tests to verify pass.**

Run: `pytest tests/test_engine.py -v`
Expected: All pass (~13 tests).

- [ ] **Step 5: Commit.**

```bash
git add alignment_tool/core/engine.py tests/test_engine.py
git commit -m "Add engine tests; raise InvalidFpsError on capture_fps <= 0"
```

---

## Task 8: Rewrite `core/persistence.py` with schema v1 + atomic write

**Files:**
- Rewrite: `alignment_tool/core/persistence.py`
- Create: `tests/test_persistence.py`

The new schema persists every field needed for Level 2 to work after Load alone. `schema_version: 1` is required. No legacy migration.

- [ ] **Step 1: Write failing tests.**

```python
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from alignment_tool.core import persistence
from alignment_tool.core.errors import (
    UnsupportedSchemaVersionError, CorruptAlignmentFileError,
)
from tests.fixtures import (
    make_anchor, make_midi_file, make_camera_file, make_state,
)


def test_round_trip_preserves_all_fields(tmp_path: Path):
    midi = make_midi_file(filename="t1.mid", unix_start=1000.0, duration=120.0)
    anchor = make_anchor(
        midi_filename="t1.mid", midi_timestamp_seconds=5.5, camera_frame=1320, label="keypress A",
    )
    cam = make_camera_file(
        filename="C0001.MP4",
        anchors=[anchor],
        active_anchor_index=0,
    )
    state = make_state(
        participant_id="P007",
        global_shift=0.42,
        midi_files=[midi],
        camera_files=[cam],
    )
    state.alignment_notes = "session notes"

    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    loaded = persistence.load_alignment(str(filepath))

    assert loaded.participant_id == state.participant_id
    assert loaded.participant_folder == state.participant_folder
    assert loaded.global_shift_seconds == state.global_shift_seconds
    assert loaded.alignment_notes == state.alignment_notes
    assert len(loaded.midi_files) == 1
    assert loaded.midi_files[0].file_path == midi.file_path
    assert loaded.midi_files[0].ticks_per_beat == midi.ticks_per_beat
    assert loaded.midi_files[0].tempo == midi.tempo
    assert len(loaded.camera_files) == 1
    assert loaded.camera_files[0].mp4_path == cam.mp4_path
    assert loaded.camera_files[0].xml_path == cam.xml_path
    assert loaded.camera_files[0].total_frames == cam.total_frames
    assert loaded.camera_files[0].active_anchor_index == 0
    assert loaded.camera_files[0].alignment_anchors[0].label == "keypress A"


def test_saved_file_has_schema_version(tmp_path: Path):
    state = make_state()
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    with open(filepath) as f:
        data = json.load(f)
    assert data["schema_version"] == 1


def test_load_missing_schema_version_raises(tmp_path: Path):
    filepath = tmp_path / "old.json"
    filepath.write_text(json.dumps({"participant_id": "X"}))
    with pytest.raises(UnsupportedSchemaVersionError):
        persistence.load_alignment(str(filepath))


def test_load_higher_schema_version_raises(tmp_path: Path):
    filepath = tmp_path / "future.json"
    filepath.write_text(json.dumps({"schema_version": 99}))
    with pytest.raises(UnsupportedSchemaVersionError):
        persistence.load_alignment(str(filepath))


def test_load_unparseable_json_raises_corrupt(tmp_path: Path):
    filepath = tmp_path / "bad.json"
    filepath.write_text("{not json")
    with pytest.raises(CorruptAlignmentFileError):
        persistence.load_alignment(str(filepath))


def test_save_is_atomic_no_partial_file_on_crash(tmp_path: Path, monkeypatch):
    state = make_state()
    filepath = tmp_path / "align.json"

    # Pre-populate the target file with valid content.
    persistence.save_alignment(state, str(filepath))
    state2 = make_state(participant_id="P999")

    # Force os.replace to blow up; the temp file should not clobber the target.
    def boom(src, dst):
        raise OSError("disk full simulation")
    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError):
        persistence.save_alignment(state2, str(filepath))

    # Original file survives untouched.
    loaded = persistence.load_alignment(str(filepath))
    assert loaded.participant_id == state.participant_id


def test_unicode_filename_round_trip(tmp_path: Path):
    midi = make_midi_file(filename="trial_中文.mid")
    state = make_state(midi_files=[midi])
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    loaded = persistence.load_alignment(str(filepath))
    assert loaded.midi_files[0].filename == "trial_中文.mid"


def test_camera_file_with_zero_anchors(tmp_path: Path):
    cam = make_camera_file(anchors=[], active_anchor_index=None)
    state = make_state(camera_files=[cam])
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    loaded = persistence.load_alignment(str(filepath))
    assert loaded.camera_files[0].alignment_anchors == []
    assert loaded.camera_files[0].active_anchor_index is None
```

- [ ] **Step 2: Run tests to verify failures.**

Run: `pytest tests/test_persistence.py -v`
Expected: Most fail — schema_version missing, atomic write not implemented, etc.

- [ ] **Step 3: Rewrite `core/persistence.py`.**

```python
"""JSON save/load for AlignmentState. Schema v1: self-contained — Load alone produces a fully functional state.

Write is atomic (tempfile + os.replace). No legacy format compatibility.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from alignment_tool.core.errors import (
    CorruptAlignmentFileError, UnsupportedSchemaVersionError,
)
from alignment_tool.core.models import (
    AlignmentState, Anchor, CameraFileInfo, MidiFileInfo,
)

SCHEMA_VERSION = 1


def save_alignment(state: AlignmentState, filepath: str) -> None:
    """Serialize AlignmentState to JSON atomically."""
    data = _state_to_dict(state)
    target = Path(filepath)
    target_dir = target.parent if target.parent != Path("") else Path(".")

    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target_dir),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(target))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_alignment(filepath: str) -> AlignmentState:
    """Deserialize AlignmentState from JSON. Requires schema_version == 1."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise CorruptAlignmentFileError(filepath, f"JSON decode error: {e}") from e
    except OSError as e:
        raise CorruptAlignmentFileError(filepath, str(e)) from e

    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(found=version or 0, supported=SCHEMA_VERSION)

    try:
        return _dict_to_state(data)
    except (KeyError, TypeError, ValueError) as e:
        raise CorruptAlignmentFileError(filepath, f"missing/invalid field: {e}") from e


def _state_to_dict(state: AlignmentState) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "participant_id": state.participant_id,
        "participant_folder": state.participant_folder,
        "global_shift_seconds": state.global_shift_seconds,
        "alignment_notes": state.alignment_notes,
        "midi_files": [_midi_to_dict(m) for m in state.midi_files],
        "camera_files": [_camera_to_dict(c) for c in state.camera_files],
    }


def _midi_to_dict(m: MidiFileInfo) -> dict:
    return {
        "filename": m.filename,
        "file_path": m.file_path,
        "unix_start": m.unix_start,
        "unix_end": m.unix_end,
        "duration": m.duration,
        "sample_rate": m.sample_rate,
        "ticks_per_beat": m.ticks_per_beat,
        "tempo": m.tempo,
    }


def _camera_to_dict(c: CameraFileInfo) -> dict:
    return {
        "filename": c.filename,
        "xml_filename": c.xml_filename,
        "mp4_path": c.mp4_path,
        "xml_path": c.xml_path,
        "raw_unix_start": c.raw_unix_start,
        "raw_unix_end": c.raw_unix_end,
        "duration": c.duration,
        "capture_fps": c.capture_fps,
        "total_frames": c.total_frames,
        "alignment_anchors": [_anchor_to_dict(a) for a in c.alignment_anchors],
        "active_anchor_index": c.active_anchor_index,
    }


def _anchor_to_dict(a: Anchor) -> dict:
    return {
        "midi_filename": a.midi_filename,
        "midi_timestamp_seconds": a.midi_timestamp_seconds,
        "camera_frame": a.camera_frame,
        "label": a.label,
    }


def _dict_to_state(data: dict) -> AlignmentState:
    return AlignmentState(
        participant_id=data["participant_id"],
        participant_folder=data["participant_folder"],
        global_shift_seconds=data["global_shift_seconds"],
        alignment_notes=data.get("alignment_notes", ""),
        midi_files=[_dict_to_midi(m) for m in data["midi_files"]],
        camera_files=[_dict_to_camera(c) for c in data["camera_files"]],
    )


def _dict_to_midi(d: dict) -> MidiFileInfo:
    return MidiFileInfo(
        filename=d["filename"],
        file_path=d["file_path"],
        unix_start=d["unix_start"],
        unix_end=d["unix_end"],
        duration=d["duration"],
        sample_rate=d["sample_rate"],
        ticks_per_beat=d["ticks_per_beat"],
        tempo=d["tempo"],
    )


def _dict_to_camera(d: dict) -> CameraFileInfo:
    return CameraFileInfo(
        filename=d["filename"],
        xml_filename=d["xml_filename"],
        mp4_path=d["mp4_path"],
        xml_path=d["xml_path"],
        raw_unix_start=d["raw_unix_start"],
        raw_unix_end=d["raw_unix_end"],
        duration=d["duration"],
        capture_fps=d["capture_fps"],
        total_frames=d["total_frames"],
        alignment_anchors=[_dict_to_anchor(a) for a in d["alignment_anchors"]],
        active_anchor_index=d["active_anchor_index"],
    )


def _dict_to_anchor(d: dict) -> Anchor:
    return Anchor(
        midi_filename=d["midi_filename"],
        midi_timestamp_seconds=d["midi_timestamp_seconds"],
        camera_frame=d["camera_frame"],
        label=d.get("label", ""),
    )
```

- [ ] **Step 4: Run tests to verify pass.**

Run: `pytest tests/test_persistence.py -v`
Expected: All pass (8 tests).

- [ ] **Step 5: Smoke-test the app.**

Run: `python -m alignment_tool`
- Open a participant, add an anchor, Save to a new file.
- Load the file back. Expected: all fields restored, Level 2 works (video frames show).

- [ ] **Step 6: Commit.**

```bash
git add alignment_tool/core/persistence.py tests/test_persistence.py
git commit -m "Rewrite persistence with schema_version=1 and atomic write"
```

---

## Task 9: Create `services/alignment_service.py` with tests

**Files:**
- Create: `alignment_tool/services/alignment_service.py`
- Create: `tests/test_alignment_service.py`

**Note:** `AlignmentState.clear_all_anchors()` still exists on the model; the service uses it internally. Task 15 removes the method from the model after UI call sites are rewired.

- [ ] **Step 1: Write failing tests.**

```python
from __future__ import annotations

import pytest

from alignment_tool.core.errors import (
    AnchorsExistError, InvalidAnchorError, UnknownMidiFileError,
)
from alignment_tool.services.alignment_service import (
    AlignmentService, ShiftChangeResult,
)
from tests.fixtures import (
    make_anchor, make_camera_file, make_midi_file, make_state,
)


def _state_with_two_anchors():
    midi = make_midi_file(filename="m1.mid")
    a1 = make_anchor(midi_filename="m1.mid", camera_frame=100)
    a2 = make_anchor(midi_filename="m1.mid", camera_frame=200)
    cam = make_camera_file(anchors=[a1, a2], active_anchor_index=0)
    return make_state(midi_files=[midi], camera_files=[cam])


# --- set_global_shift ---

def test_set_global_shift_no_anchors_updates_value():
    state = make_state()
    svc = AlignmentService(state)

    result = svc.set_global_shift(0.5, clear_anchors_if_needed=False)

    assert state.global_shift_seconds == 0.5
    assert result == ShiftChangeResult(previous_shift=0.0, cleared_anchor_count=0)


def test_set_global_shift_with_anchors_and_no_clear_raises():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)

    with pytest.raises(AnchorsExistError) as excinfo:
        svc.set_global_shift(0.5, clear_anchors_if_needed=False)

    assert excinfo.value.count == 2
    assert state.global_shift_seconds == 0.0  # unchanged
    assert state.total_anchor_count() == 2      # unchanged


def test_set_global_shift_with_anchors_and_clear_mutates():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)

    result = svc.set_global_shift(0.5, clear_anchors_if_needed=True)

    assert state.global_shift_seconds == 0.5
    assert state.total_anchor_count() == 0
    assert state.camera_files[0].active_anchor_index is None
    assert result.cleared_anchor_count == 2


# --- add_anchor ---

def test_add_anchor_appends_and_returns_index():
    midi = make_midi_file(filename="m1.mid")
    cam = make_camera_file(anchors=[])
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)

    idx = svc.add_anchor(0, make_anchor(midi_filename="m1.mid"))

    assert idx == 0
    assert len(cam.alignment_anchors) == 1


def test_add_anchor_with_unknown_midi_raises():
    midi = make_midi_file(filename="m1.mid")
    cam = make_camera_file(anchors=[])
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)

    with pytest.raises(UnknownMidiFileError):
        svc.add_anchor(0, make_anchor(midi_filename="does_not_exist.mid"))

    assert len(cam.alignment_anchors) == 0


def test_add_anchor_with_bad_camera_index_raises():
    state = make_state()
    svc = AlignmentService(state)
    with pytest.raises(InvalidAnchorError):
        svc.add_anchor(99, make_anchor())


# --- delete_anchor and active_index fixup ---

def test_delete_anchor_before_active_decrements_active_index():
    # 3 anchors, active=2; delete index 0 → active should become 1.
    midi = make_midi_file(filename="m1.mid")
    anchors = [make_anchor(midi_filename="m1.mid", camera_frame=i) for i in (10, 20, 30)]
    cam = make_camera_file(anchors=anchors, active_anchor_index=2)
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)

    svc.delete_anchor(0, 0)

    assert len(cam.alignment_anchors) == 2
    assert cam.active_anchor_index == 1


def test_delete_active_anchor_clears_active_index():
    midi = make_midi_file(filename="m1.mid")
    anchors = [make_anchor(midi_filename="m1.mid", camera_frame=i) for i in (10, 20)]
    cam = make_camera_file(anchors=anchors, active_anchor_index=0)
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)

    svc.delete_anchor(0, 0)

    assert cam.active_anchor_index is None


def test_delete_anchor_after_active_leaves_active_index():
    midi = make_midi_file(filename="m1.mid")
    anchors = [make_anchor(midi_filename="m1.mid", camera_frame=i) for i in (10, 20, 30)]
    cam = make_camera_file(anchors=anchors, active_anchor_index=0)
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)

    svc.delete_anchor(0, 2)

    assert cam.active_anchor_index == 0


def test_delete_last_anchor_with_none_active_is_noop_on_index():
    midi = make_midi_file(filename="m1.mid")
    cam = make_camera_file(
        anchors=[make_anchor(midi_filename="m1.mid")],
        active_anchor_index=None,
    )
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)

    svc.delete_anchor(0, 0)

    assert cam.alignment_anchors == []
    assert cam.active_anchor_index is None


def test_delete_anchor_bad_index_raises():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)
    with pytest.raises(InvalidAnchorError):
        svc.delete_anchor(0, 99)


# --- set_active_anchor ---

def test_set_active_anchor_updates_index():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)
    svc.set_active_anchor(0, 1)
    assert state.camera_files[0].active_anchor_index == 1


def test_set_active_anchor_to_none_clears():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)
    svc.set_active_anchor(0, None)
    assert state.camera_files[0].active_anchor_index is None


def test_set_active_anchor_bad_index_raises():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)
    with pytest.raises(InvalidAnchorError):
        svc.set_active_anchor(0, 99)


# --- effective_shift_for ---

def test_effective_shift_no_anchor_returns_global():
    state = make_state(global_shift=0.25)
    svc = AlignmentService(state)
    assert svc.effective_shift_for(0) == 0.25
```

- [ ] **Step 2: Run tests to verify failure.**

Run: `pytest tests/test_alignment_service.py -v`
Expected: ImportError — service module doesn't exist.

- [ ] **Step 3: Implement `services/alignment_service.py`.**

```python
"""Single write boundary for AlignmentState. Qt-free."""
from __future__ import annotations

from dataclasses import dataclass

from alignment_tool.core import engine
from alignment_tool.core.errors import (
    AnchorsExistError, InvalidAnchorError, UnknownMidiFileError,
)
from alignment_tool.core.models import (
    AlignmentState, Anchor,
)


@dataclass(frozen=True)
class ShiftChangeResult:
    previous_shift: float
    cleared_anchor_count: int


class AlignmentService:
    def __init__(self, state: AlignmentState) -> None:
        self._state = state

    # --- global shift ---

    def set_global_shift(
        self, value: float, *, clear_anchors_if_needed: bool,
    ) -> ShiftChangeResult:
        existing = self._state.total_anchor_count()
        previous = self._state.global_shift_seconds

        if existing > 0 and not clear_anchors_if_needed:
            raise AnchorsExistError(count=existing)

        cleared = 0
        if existing > 0:
            for cf in self._state.camera_files:
                cleared += len(cf.alignment_anchors)
                cf.alignment_anchors.clear()
                cf.active_anchor_index = None

        self._state.global_shift_seconds = value
        return ShiftChangeResult(previous_shift=previous, cleared_anchor_count=cleared)

    # --- anchors ---

    def add_anchor(self, camera_index: int, anchor: Anchor) -> int:
        cf = self._get_camera(camera_index)
        if self._state.midi_file_by_name(anchor.midi_filename) is None:
            raise UnknownMidiFileError(anchor.midi_filename)
        cf.alignment_anchors.append(anchor)
        return len(cf.alignment_anchors) - 1

    def delete_anchor(self, camera_index: int, anchor_index: int) -> None:
        cf = self._get_camera(camera_index)
        if not (0 <= anchor_index < len(cf.alignment_anchors)):
            raise InvalidAnchorError(
                f"anchor_index {anchor_index} out of range for camera {camera_index}",
            )
        del cf.alignment_anchors[anchor_index]

        active = cf.active_anchor_index
        if active is None:
            return
        if active == anchor_index:
            cf.active_anchor_index = None
        elif active > anchor_index:
            cf.active_anchor_index = active - 1

    def set_active_anchor(
        self, camera_index: int, anchor_index: int | None,
    ) -> None:
        cf = self._get_camera(camera_index)
        if anchor_index is None:
            cf.active_anchor_index = None
            return
        if not (0 <= anchor_index < len(cf.alignment_anchors)):
            raise InvalidAnchorError(
                f"anchor_index {anchor_index} out of range",
            )
        cf.active_anchor_index = anchor_index

    # --- pure reads ---

    def effective_shift_for(self, camera_index: int) -> float:
        cf = self._get_camera(camera_index)
        midi_map = {m.filename: m for m in self._state.midi_files}
        return engine.get_effective_shift_for_camera(
            cf, self._state.global_shift_seconds, midi_map,
        )

    def anchor_shift_for(
        self, camera_index: int, anchor_index: int,
    ) -> float | None:
        cf = self._get_camera(camera_index)
        if not (0 <= anchor_index < len(cf.alignment_anchors)):
            return None
        anchor = cf.alignment_anchors[anchor_index]
        midi = self._state.midi_file_by_name(anchor.midi_filename)
        if midi is None:
            return None
        return engine.compute_anchor_shift(
            anchor, cf, midi, self._state.global_shift_seconds,
        )

    # --- internal ---

    def _get_camera(self, camera_index: int):
        if not (0 <= camera_index < len(self._state.camera_files)):
            raise InvalidAnchorError(
                f"camera_index {camera_index} out of range",
            )
        return self._state.camera_files[camera_index]
```

- [ ] **Step 4: Run tests to verify pass.**

Run: `pytest tests/test_alignment_service.py -v`
Expected: All pass (~15 tests).

- [ ] **Step 5: Commit.**

```bash
git add alignment_tool/services/alignment_service.py tests/test_alignment_service.py
git commit -m "Add AlignmentService as sole write boundary for AlignmentState"
```

---

## Task 10: Create `services/level2_controller.py` with tests

**Files:**
- Create: `alignment_tool/services/level2_controller.py`
- Create: `tests/test_level2_controller.py`

- [ ] **Step 1: Write failing tests.**

```python
from __future__ import annotations

import pytest

from alignment_tool.core.errors import MarkersNotSetError
from alignment_tool.services.alignment_service import AlignmentService
from alignment_tool.services.level2_controller import (
    Level2Controller, Mode, SyncOutput,
)
from tests.fixtures import (
    make_anchor, make_camera_file, make_midi_file, make_state,
)


def _setup():
    midi = make_midi_file(filename="m1.mid", unix_start=1000.0, duration=100.0)
    cam = make_camera_file(raw_unix_start=1030.0, capture_fps=240.0, duration=60.0)
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)
    ctrl = Level2Controller(state, svc)
    ctrl.load_pair(midi_index=0, camera_index=0)
    return state, svc, ctrl


def test_initial_mode_is_free():
    _, _, ctrl = _setup()
    assert ctrl.mode == Mode.FREE


def test_free_mode_midi_change_returns_null_sync():
    _, _, ctrl = _setup()
    out = ctrl.on_midi_position_changed(midi_time=5.0)
    assert out == SyncOutput(new_midi_time=None, new_camera_frame=None, out_of_range_delta=None)


def test_free_mode_camera_change_returns_null_sync():
    _, _, ctrl = _setup()
    out = ctrl.on_camera_position_changed(camera_frame=100)
    assert out == SyncOutput(new_midi_time=None, new_camera_frame=None, out_of_range_delta=None)


def test_locked_mode_midi_change_returns_expected_frame():
    _, _, ctrl = _setup()
    ctrl.set_mode(Mode.LOCKED)
    # global_shift=0, no anchors: camera_unix = midi_unix - 0.
    # midi_time=1 → midi_unix=1001 → camera_unix=1001 → 1001-1030=-29s → before clip start
    # Need a time that's inside the clip. Clip starts at 1030, so midi_time=30 → midi_unix=1030.
    out = ctrl.on_midi_position_changed(midi_time=30.0)
    assert out.new_camera_frame == 0
    assert out.out_of_range_delta is None


def test_locked_mode_midi_before_clip_gives_oor_delta_positive():
    _, _, ctrl = _setup()
    ctrl.set_mode(Mode.LOCKED)
    out = ctrl.on_midi_position_changed(midi_time=0.0)   # midi_unix = 1000, clip starts 1030
    assert out.new_camera_frame is None
    assert out.out_of_range_delta == pytest.approx(30.0)


def test_locked_mode_midi_after_clip_gives_oor_delta_negative():
    _, _, ctrl = _setup()
    ctrl.set_mode(Mode.LOCKED)
    # clip ends at 1030+60 = 1090. midi_unix=1100 → 10s past end.
    out = ctrl.on_midi_position_changed(midi_time=100.0)
    assert out.new_camera_frame is None
    assert out.out_of_range_delta == pytest.approx(-10.0)


def test_locked_mode_camera_change_returns_midi_time():
    _, _, ctrl = _setup()
    ctrl.set_mode(Mode.LOCKED)
    # frame 240 at 240fps = 1s into clip → camera_unix=1031 → midi_seconds = 31
    out = ctrl.on_camera_position_changed(camera_frame=240)
    assert out.new_midi_time == pytest.approx(31.0)


# --- markers ---

def test_mark_midi_and_camera_then_compute_shift():
    _, _, ctrl = _setup()
    ctrl.mark_midi(10.0)      # midi_unix = 1010
    ctrl.mark_camera(2400)    # camera_unix = 1030 + 2400/240 = 1040
    shift = ctrl.compute_shift_from_markers()
    assert shift == pytest.approx(1010.0 - 1040.0)  # -30


def test_compute_shift_without_markers_raises():
    _, _, ctrl = _setup()
    with pytest.raises(MarkersNotSetError):
        ctrl.compute_shift_from_markers()


def test_clear_markers_resets():
    _, _, ctrl = _setup()
    ctrl.mark_midi(1.0)
    ctrl.mark_camera(10)
    ctrl.clear_markers()
    with pytest.raises(MarkersNotSetError):
        ctrl.compute_shift_from_markers()


def test_build_anchor_from_markers_returns_anchor_for_current_pair():
    state, _, ctrl = _setup()
    ctrl.mark_midi(5.5)
    ctrl.mark_camera(1320)
    anchor = ctrl.build_anchor_from_markers(label="A")
    assert anchor.midi_filename == "m1.mid"
    assert anchor.midi_timestamp_seconds == 5.5
    assert anchor.camera_frame == 1320
    assert anchor.label == "A"


def test_build_anchor_from_markers_without_markers_raises():
    _, _, ctrl = _setup()
    with pytest.raises(MarkersNotSetError):
        ctrl.build_anchor_from_markers()
```

- [ ] **Step 2: Run tests to verify failure.**

Run: `pytest tests/test_level2_controller.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `services/level2_controller.py`.**

```python
"""Qt-free controller for Level 2 view: mode, markers, sync routing."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from alignment_tool.core import engine
from alignment_tool.core.errors import MarkersNotSetError
from alignment_tool.core.models import AlignmentState, Anchor
from alignment_tool.services.alignment_service import AlignmentService


class Mode(Enum):
    FREE = auto()
    LOCKED = auto()


@dataclass(frozen=True)
class SyncOutput:
    new_midi_time: float | None
    new_camera_frame: int | None
    out_of_range_delta: float | None


class Level2Controller:
    def __init__(self, state: AlignmentState, service: AlignmentService) -> None:
        self._state = state
        self._service = service
        self._midi_index = 0
        self._camera_index = 0
        self._mode = Mode.FREE
        self._midi_marker: float | None = None     # seconds-from-midi-start
        self._camera_marker: int | None = None     # frame index

    # --- pair / mode ---

    def load_pair(self, midi_index: int, camera_index: int) -> None:
        self._midi_index = midi_index
        self._camera_index = camera_index
        self.clear_markers()

    def set_mode(self, mode: Mode) -> None:
        self._mode = mode

    @property
    def mode(self) -> Mode:
        return self._mode

    # --- sync ---

    def on_midi_position_changed(self, midi_time: float) -> SyncOutput:
        if self._mode != Mode.LOCKED:
            return SyncOutput(None, None, None)
        cf = self._state.camera_files[self._camera_index]
        midi = self._state.midi_files[self._midi_index]
        eff = self._service.effective_shift_for(self._camera_index)
        midi_unix = midi.unix_start + midi_time
        frame = engine.midi_unix_to_camera_frame(midi_unix, eff, cf)
        oor = None if frame is not None else engine.out_of_range_delta(midi_unix, eff, cf)
        return SyncOutput(new_midi_time=None, new_camera_frame=frame, out_of_range_delta=oor)

    def on_camera_position_changed(self, camera_frame: int) -> SyncOutput:
        if self._mode != Mode.LOCKED:
            return SyncOutput(None, None, None)
        cf = self._state.camera_files[self._camera_index]
        midi = self._state.midi_files[self._midi_index]
        eff = self._service.effective_shift_for(self._camera_index)
        seconds = engine.camera_frame_to_midi_seconds(camera_frame, eff, cf, midi)
        return SyncOutput(new_midi_time=seconds, new_camera_frame=None, out_of_range_delta=None)

    # --- markers ---

    def mark_midi(self, midi_time: float) -> None:
        self._midi_marker = midi_time

    def mark_camera(self, camera_frame: int) -> None:
        self._camera_marker = camera_frame

    def clear_markers(self) -> None:
        self._midi_marker = None
        self._camera_marker = None

    @property
    def midi_marker(self) -> float | None:
        return self._midi_marker

    @property
    def camera_marker(self) -> int | None:
        return self._camera_marker

    def compute_shift_from_markers(self) -> float:
        self._require_markers()
        midi = self._state.midi_files[self._midi_index]
        cam = self._state.camera_files[self._camera_index]
        midi_unix = midi.unix_start + self._midi_marker  # type: ignore[arg-type]
        camera_unix = engine.camera_frame_to_unix(self._camera_marker, cam)  # type: ignore[arg-type]
        return engine.compute_global_shift_from_markers(midi_unix, camera_unix)

    def build_anchor_from_markers(self, label: str = "") -> Anchor:
        self._require_markers()
        midi = self._state.midi_files[self._midi_index]
        return Anchor(
            midi_filename=midi.filename,
            midi_timestamp_seconds=self._midi_marker,       # type: ignore[arg-type]
            camera_frame=self._camera_marker,               # type: ignore[arg-type]
            label=label,
        )

    def _require_markers(self) -> None:
        if self._midi_marker is None or self._camera_marker is None:
            raise MarkersNotSetError()
```

- [ ] **Step 4: Run tests to verify pass.**

Run: `pytest tests/test_level2_controller.py -v`
Expected: All pass (~12 tests).

- [ ] **Step 5: Commit.**

```bash
git add alignment_tool/services/level2_controller.py tests/test_level2_controller.py
git commit -m "Add Level2Controller (Qt-free) for mode, markers, sync routing"
```

---

## Task 11: Wire `MainWindow` to service + surface load warnings + `ParticipantLoadResult`

**Files:**
- Modify: `alignment_tool/io/participant_loader.py` — return `ParticipantLoadResult(state, warnings)`, case-insensitive suffix, raise `MediaLoadError` on per-file failure
- Modify: `alignment_tool/ui/main_window.py` — build `AlignmentService` and `Level2Controller`, pass into child widgets, surface warnings as non-modal list, use `_show_exception` helper, replace `print` with `logging`
- Create (helper): a small `_show_exception(self, exc)` method on `MainWindow`

**Note on `_show_exception`:** Lives inside `MainWindow` (not a standalone module). It branches on exception type:
- `MediaLoadError` / `PersistenceError` → `QMessageBox.critical`
- `InvariantError` → `QMessageBox.warning`
- Anything else → re-raise

- [ ] **Step 1: Update `io/participant_loader.py`.**

Read the existing file, then:

- Return a `ParticipantLoadResult` dataclass with `state: AlignmentState` and `warnings: list[str]`.
- Use case-insensitive suffix matching: `if p.suffix.lower() == ".mid":` and `".mp4"`.
- Wrap each per-file adapter construction in a try/except. On `MediaLoadError`, append a warning string and skip the file; do not abort the whole load.
- Remove `print` statements; use `logging.getLogger(__name__)` for anything preserved.

Sketch of the new top:

```python
"""Scan a participant folder into an AlignmentState. Collects per-file warnings."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from alignment_tool.core.errors import MediaLoadError
from alignment_tool.core.models import AlignmentState
from alignment_tool.io.camera_adapter import CameraAdapter
from alignment_tool.io.midi_adapter import MidiAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParticipantLoadResult:
    state: AlignmentState
    warnings: list[str]


class ParticipantLoader:
    @staticmethod
    def load(folder: str) -> ParticipantLoadResult:
        ...
```

The internal scan logic (finding `disklavier/` and `overhead camera/` etc.) stays; only the filtering, error handling, and return shape change.

- [ ] **Step 2: Update `MainWindow` to use `AlignmentService` + `Level2Controller`.**

Key changes to `alignment_tool/ui/main_window.py`:

- In `__init__`, add fields `self._service: AlignmentService | None = None`, `self._controller: Level2Controller | None = None`. Do NOT build them yet; do it in `_set_state`.

- `_set_state(state)` becomes:

```python
def _set_state(self, state: AlignmentState, warnings: list[str] | None = None):
    self._state = state
    self._service = AlignmentService(state)
    self._controller = Level2Controller(state, self._service)
    self._save_action.setEnabled(True)
    self.setWindowTitle(f"MIDI-Camera Alignment Tool — Participant {state.participant_id}")
    self._update_status()
    self._level1.set_state(state, self._service)
    self._level2.attach(state, self._service, self._controller)
    self._stack.setCurrentWidget(self._level1)
    if warnings:
        self._show_warnings(warnings)
    self.state_changed.emit()
```

- Replace `_on_open_participant`:

```python
def _on_open_participant(self):
    folder = QFileDialog.getExistingDirectory(self, "Select Participant Folder")
    if not folder:
        return
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        result = ParticipantLoader.load(folder)
    except AlignmentToolError as e:
        QApplication.restoreOverrideCursor()
        self._show_exception(e)
        return
    except Exception as e:
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(self, "Error Loading Participant", str(e))
        return
    QApplication.restoreOverrideCursor()

    if not result.state.midi_files and not result.state.camera_files:
        QMessageBox.warning(
            self, "No Files Found",
            f"No .mid or .MP4 files found in:\n{folder}\n\n"
            "Expected subdirectories: disklavier/ and overhead camera/"
        )
        return
    self._set_state(result.state, warnings=result.warnings)
```

- Update `_on_load` similarly, catching `AlignmentToolError`.

- Add helpers:

```python
def _show_exception(self, exc: AlignmentToolError) -> None:
    from alignment_tool.core.errors import (
        MediaLoadError, PersistenceError, InvariantError,
    )
    if isinstance(exc, (MediaLoadError, PersistenceError)):
        QMessageBox.critical(self, type(exc).__name__, str(exc))
    elif isinstance(exc, InvariantError):
        QMessageBox.warning(self, type(exc).__name__, str(exc))
    else:
        QMessageBox.critical(self, "Error", str(exc))

def _show_warnings(self, warnings: list[str]) -> None:
    if not warnings:
        return
    msg = "\n".join(f"• {w}" for w in warnings)
    QMessageBox.warning(
        self, "Some files could not be loaded",
        f"{len(warnings)} file(s) were skipped:\n\n{msg}",
    )
```

- Update `Level1Widget.set_state(state, service)` and `Level2View.attach(state, service, controller)` signatures.  (The child widgets will be updated in Tasks 12 & 13 to accept these; until then, use placeholder extra args that are ignored.)

- [ ] **Step 3: Update `Level1Widget.set_state` signature placeholder.**

Temporarily update `alignment_tool/ui/level1_timeline.py:Level1Widget.set_state`:

```python
def set_state(self, state: AlignmentState, service: AlignmentService | None = None):
    # service param will be used in Task 12
    self._state = state
    ...   # existing body
```

Same for `Level2View.load_pair` which gets replaced by `attach`: for now add a forwarding shim:

```python
def attach(self, state, service, controller):
    self._service_placeholder = service
    self._controller_placeholder = controller
    # keep existing API for now
    ...

def load_pair(self, state, midi_index, camera_index):
    # existing body unchanged
    ...
```

This keeps the app runnable while Tasks 12–13 do the real extraction.

- [ ] **Step 4: Smoke-test.**

Run: `python -m alignment_tool`
- Open a participant. Drill in. Exit.
- Expected: still functional. Warning dialog appears if some files were malformed (likely none for a clean folder).

- [ ] **Step 5: Commit.**

```bash
git add -A
git commit -m "Wire MainWindow to AlignmentService/Level2Controller; surface load warnings"
```

---

## Task 12: Route `Level1Widget` shift changes through `AlignmentService`

**Files:**
- Modify: `alignment_tool/ui/level1_timeline.py:_on_apply_shift`

Today this method directly calls `state.clear_all_anchors()` and writes `state.global_shift_seconds`. Replace with a service call that raises `AnchorsExistError` when confirmation is required.

- [ ] **Step 1: Update `Level1Widget.set_state` to actually store the service.**

```python
def set_state(self, state: AlignmentState, service: AlignmentService):
    self._state = state
    self._service = service
    # existing body
```

- [ ] **Step 2: Rewrite `_on_apply_shift`.**

Current body (roughly): reads spinbox value; if anchors exist, asks for confirmation; calls `clear_all_anchors`; sets `global_shift_seconds`.

New body:

```python
def _on_apply_shift(self):
    if self._state is None or self._service is None:
        return
    value = self._shift_spinbox.value()
    try:
        self._service.set_global_shift(value, clear_anchors_if_needed=False)
    except AnchorsExistError as exc:
        reply = QMessageBox.question(
            self, "Anchors exist",
            f"{exc.count} anchor(s) exist. Applying a new global shift will "
            "clear all anchors across all clips. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            self._shift_spinbox.setValue(self._state.global_shift_seconds)
            return
        self._service.set_global_shift(value, clear_anchors_if_needed=True)

    self.refresh()
    self.state_modified.emit()
```

Hoist any `from PyQt5.QtWidgets import QMessageBox` out of the method body to the module top.

Add import: `from alignment_tool.core.errors import AnchorsExistError` and `from alignment_tool.services.alignment_service import AlignmentService`.

- [ ] **Step 3: Smoke-test invariant.**

Run: `python -m alignment_tool`
- Open a participant with no anchors, change shift → applies.
- Add an anchor in Level 2, back out to Level 1, change shift → confirmation dialog appears; if "Yes", anchors cleared and shift applied; if "No", shift reverts.

- [ ] **Step 4: Commit.**

```bash
git add alignment_tool/ui/level1_timeline.py
git commit -m "Route Level1 shift changes through AlignmentService"
```

---

## Task 13: Thin `Level2View`; route sync, markers, mutations through controller + service

**Files:**
- Modify: `alignment_tool/ui/level2_view.py` — remove `_locked`, `_midi_marker`, `_camera_marker` fields; delegate to `Level2Controller`. Remove inline engine-math duplication (spec bug P2 — line ~506 in the old file). Add `QSignalBlocker` around mirrored `set_*` calls.
- Modify: `alignment_tool/ui/level2_anchor_table.py` — mutation calls go through `AlignmentService` (not direct writes to `CameraFileInfo`)

This is the largest single task. The approach: **do not rewrite the view from scratch.** Edit it incrementally — replace each `_on_*` handler with a `self._controller.<method>()` call and render the returned `SyncOutput`. Leave UI construction (`_build_ui`) untouched.

- [ ] **Step 1: Replace the internal state fields with controller/service references.**

In `Level2View.__init__`:

```python
def __init__(self, parent=None):
    super().__init__(parent)
    self._state: AlignmentState | None = None
    self._service: AlignmentService | None = None
    self._controller: Level2Controller | None = None
    self._midi_index: int = 0
    self._camera_index: int = 0
    self._midi_adapter: MidiAdapter | None = None
    self._active_panel: str = "camera"   # still view-local: which panel last had focus
    self._build_ui()
```

Delete `self._locked`, `self._midi_marker`, `self._camera_marker`. Every read moves to the controller.

Add imports:

```python
from alignment_tool.services.alignment_service import AlignmentService
from alignment_tool.services.level2_controller import (
    Level2Controller, Mode, SyncOutput,
)
from alignment_tool.core.errors import (
    MarkersNotSetError, AnchorsExistError, UnknownMidiFileError,
)
```

- [ ] **Step 2: Replace `load_pair` with `attach` + `load_pair`.**

```python
def attach(
    self, state: AlignmentState,
    service: AlignmentService,
    controller: Level2Controller,
) -> None:
    self._state = state
    self._service = service
    self._controller = controller
    self._populate_combos()

def load_pair(self, midi_index: int, camera_index: int) -> None:
    if self._controller is None:
        return
    self._midi_index = midi_index
    self._camera_index = camera_index
    self._controller.load_pair(midi_index, camera_index)
    self._load_midi_file(midi_index)
    self._load_camera_file(camera_index)
    self._refresh_all()
```

`MainWindow._on_pair_selected` must now call `self._level2.load_pair(midi_index, camera_index)` with two args (no state).

- [ ] **Step 3: Rewrite the sync handlers.**

Replace `_on_midi_position_changed` and `_on_camera_position_changed` bodies:

```python
def _on_midi_position_changed(self, midi_time: float) -> None:
    if self._controller is None:
        return
    out = self._controller.on_midi_position_changed(midi_time)
    self._apply_sync_output(out, driver="midi")

def _on_camera_position_changed(self, camera_frame: int) -> None:
    if self._controller is None:
        return
    out = self._controller.on_camera_position_changed(camera_frame)
    self._apply_sync_output(out, driver="camera")

def _apply_sync_output(self, out: SyncOutput, driver: str) -> None:
    # Feedback-loop safe via QSignalBlocker.
    if out.new_camera_frame is not None:
        with QSignalBlocker(self._camera_panel):
            self._camera_panel.set_frame(out.new_camera_frame)
    if out.new_midi_time is not None:
        with QSignalBlocker(self._midi_panel):
            self._midi_panel.set_position(out.new_midi_time)
    if out.out_of_range_delta is not None:
        self._show_oor(out.out_of_range_delta)
    else:
        self._clear_oor()
```

Add import at the top of the file:

```python
from PyQt5.QtCore import QSignalBlocker
```

Remove any inline `round((camera_unix - cf.raw_unix_start) * cf.capture_fps)` — that duplication lived in the old sync handlers; it's now inside the engine/controller.

- [ ] **Step 4: Rewrite the mode toggle.**

```python
def _toggle_mode(self) -> None:
    if self._controller is None:
        return
    new_mode = Mode.LOCKED if self._mode_btn.isChecked() else Mode.FREE
    self._controller.set_mode(new_mode)
    self._mode_btn.setText(f"Mode: {'Locked' if new_mode == Mode.LOCKED else 'Independent'}")
    self._update_status_line()
```

- [ ] **Step 5: Rewrite marker actions.**

Marker actions currently live in `_mark_midi`, `_mark_camera`, `_on_compute_shift`, `_on_add_anchor`. Replace:

```python
def _mark_midi(self) -> None:
    if self._controller is None:
        return
    self._controller.mark_midi(self._midi_panel.current_position)
    self._update_marker_ui()

def _mark_camera(self) -> None:
    if self._controller is None:
        return
    self._controller.mark_camera(self._camera_panel.current_frame)
    self._update_marker_ui()

def _on_compute_shift(self) -> None:
    if self._controller is None or self._service is None:
        return
    try:
        new_shift = self._controller.compute_shift_from_markers()
    except MarkersNotSetError as exc:
        QMessageBox.warning(self, "Markers not set", str(exc))
        return
    reply = QMessageBox.question(
        self, "Apply global shift?",
        f"Apply {new_shift:.3f}s as the global shift for all camera clips?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
    )
    if reply != QMessageBox.Yes:
        return
    try:
        self._service.set_global_shift(new_shift, clear_anchors_if_needed=False)
    except AnchorsExistError as exc:
        reply = QMessageBox.question(
            self, "Anchors exist",
            f"{exc.count} anchor(s) exist and will be cleared. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._service.set_global_shift(new_shift, clear_anchors_if_needed=True)
    self._controller.clear_markers()
    self._update_marker_ui()
    self.state_modified.emit()

def _on_add_anchor(self) -> None:
    if self._controller is None or self._service is None:
        return
    label, ok = QInputDialog.getText(self, "Anchor label", "Label (optional):")
    if not ok:
        return
    try:
        anchor = self._controller.build_anchor_from_markers(label=label)
    except MarkersNotSetError as exc:
        QMessageBox.warning(self, "Markers not set", str(exc))
        return
    try:
        idx = self._service.add_anchor(self._camera_index, anchor)
    except UnknownMidiFileError as exc:
        QMessageBox.warning(self, "Unknown MIDI file", str(exc))
        return
    self._anchor_table.refresh()
    self._service.set_active_anchor(self._camera_index, idx)
    self._controller.clear_markers()
    self._update_marker_ui()
    self.state_modified.emit()
```

- [ ] **Step 6: Update `_update_marker_ui` to read from controller.**

```python
def _update_marker_ui(self) -> None:
    if self._controller is None or self._state is None:
        return
    midi_m = self._controller.midi_marker
    cam_m = self._controller.camera_marker
    self._midi_marker_label.setText(f"MIDI marker: {midi_m:.3f}s" if midi_m is not None else "MIDI marker: —")
    self._camera_marker_label.setText(f"Camera marker: frame {cam_m}" if cam_m is not None else "Camera marker: —")
    both = midi_m is not None and cam_m is not None
    self._compute_shift_btn.setEnabled(both)
    self._add_anchor_btn.setEnabled(both)
```

- [ ] **Step 7: Remove now-dead code.**

- Delete `self._locked`, `self._midi_marker`, `self._camera_marker` fields (already done in Step 1).
- Delete any inline math that recomputes `round((camera_unix - cf.raw_unix_start) * cf.capture_fps)`.
- Delete the `load_pair(state, midi_index, camera_index)` three-arg overload — there's only the two-arg `load_pair` now.

- [ ] **Step 8: Update `AnchorTableWidget` mutations to go through the service.**

Read the current `_on_cell_clicked` and `_on_delete` methods. Rewrite:

```python
# In AnchorTableWidget.__init__, accept a service.
def set_context(self, state, service, camera_index):
    self._state = state
    self._service = service
    self._camera_index = camera_index

def _on_cell_clicked(self, row, column):
    if self._service is None:
        return
    self._service.set_active_anchor(self._camera_index, row)
    self.anchor_activated.emit(row)
    self.refresh()

def _on_delete(self, row):
    if self._service is None:
        return
    self._service.delete_anchor(self._camera_index, row)
    self.anchor_deleted.emit(row)
    self.refresh()
```

`Level2View._load_camera_file` calls `self._anchor_table.set_context(self._state, self._service, self._camera_index)` after populating.

- [ ] **Step 9: Smoke-test.**

Run: `python -m alignment_tool`
- Full Level 2 workflow: load participant, drill in, mark MIDI, mark camera, Add Anchor, toggle Lock mode, scrub both panels, observe OOR label, delete an anchor, activate another.
- Expected: every action works; no console errors.

- [ ] **Step 10: Commit.**

```bash
git add -A
git commit -m "Thin Level2View: delegate to Level2Controller + AlignmentService; add QSignalBlocker"
```

---

## Task 14: Remove `clear_all_anchors` from the model, collapse math duplication in `OverlapIndicator`

**Files:**
- Modify: `alignment_tool/core/models.py` — remove `clear_all_anchors` method
- Modify: `alignment_tool/ui/level2_overlap_indicator.py` — replace inline `round((camera_unix - cf.raw_unix_start) * cf.capture_fps)` and `camera.raw_unix_start + frame / camera.capture_fps` with calls to `core.engine.camera_frame_to_unix` / `midi_unix_to_camera_frame`
- Modify: `alignment_tool/ui/level2_midi_panel.py` — add public `midi_info` property, replace `canvas._midi_info` reach-ins

- [ ] **Step 1: Delete `AlignmentState.clear_all_anchors`.**

Edit `alignment_tool/core/models.py`: delete lines for `clear_all_anchors`. Verify nothing references it anymore with Grep:

Run: `rg "clear_all_anchors" alignment_tool/`
Expected: no matches. (The service no longer calls the method — it clears in place.)

- [ ] **Step 2: Wait — double-check the service still works.**

The service's `set_global_shift` clears anchors via an explicit `for cf in ...: cf.alignment_anchors.clear()` loop (see Task 9, Step 3). It does NOT call `state.clear_all_anchors()`. Good.

Run: `pytest tests/ -v`
Expected: all pass.

- [ ] **Step 3: Collapse math duplication in overlap indicator.**

Read `alignment_tool/ui/level2_overlap_indicator.py` — lines around 68-83, 132-134, 152-167, 183-189 (per audit). Replace each inline formula with the engine call.

Add import at top:

```python
from alignment_tool.core import engine
```

Example pattern:

```python
# Before:
camera_unix = camera.raw_unix_start + frame / camera.capture_fps
# After:
camera_unix = engine.camera_frame_to_unix(frame, camera)
```

And for the "where does this camera frame land in MIDI time":

```python
# Before:
frame = round((midi_unix - effective_shift - camera.raw_unix_start) * camera.capture_fps)
# After:
frame = engine.midi_unix_to_camera_frame(midi_unix, effective_shift, camera)  # may be None
```

Handle `None` by skipping the draw for out-of-range frames (match existing behavior — clip bars already handle OOR by drawing outside the visible range, which just gets clipped by Qt).

- [ ] **Step 4: Add `midi_info` property to MidiCanvas; stop reaching into `_midi_info`.**

In `alignment_tool/ui/level2_midi_panel.py` (the canvas class inside the file):

```python
@property
def midi_info(self) -> dict | None:   # or whatever its type is
    return self._midi_info
```

In `MidiPanelWidget._update_info`, replace `self._canvas._midi_info` with `self._canvas.midi_info`.

- [ ] **Step 5: Fix `notes[0]` earliest-note assumption.**

Per the audit, `alignment_tool/ui/level2_view.py` has an inline comment around line 170 that documents a brittle `notes[0]` lookup (which assumes `notes` is ordered by `start` — not guaranteed across `pretty_midi` versions). Grep for it and replace:

Run: `rg "notes\[0\]" alignment_tool/`

Wherever the code does something like `notes[0].start` to find the earliest onset, replace with `min(n.start for n in notes)`. Delete the 5–7 line NOTE comment block that was there to explain the assumption.

If there are no hits (the comment may have already been cleaned up during Task 13's gutting of `level2_view.py`), skip.

- [ ] **Step 6: Smoke-test.**

Run: `python -m alignment_tool`
- Load a participant with anchors. Enter Level 2. Scrub the overlap indicator.
- Expected: playhead tracking matches previous behavior exactly.

- [ ] **Step 7: Commit.**

```bash
git add alignment_tool/core/models.py alignment_tool/ui/level2_overlap_indicator.py alignment_tool/ui/level2_midi_panel.py alignment_tool/ui/level2_view.py
git commit -m "Remove model clear_all_anchors; collapse math duplication via core.engine; fix notes[0] assumption"
```

---

## Task 15: `FrameWorker` generation counter + `open_failed` signal; camera panel `hideEvent`; case-insensitive suffix; adapter cleanups

**Files:**
- Modify: `alignment_tool/io/frame_worker.py` — add `_generation` counter, bump in `open_video`, tag each `request_frame` with generation, drop stale frames; add `open_failed = pyqtSignal(str)`.
- Modify: `alignment_tool/ui/level2_camera_panel.py` — listen for `open_failed`, render a red overlay; add `hideEvent` that calls `cleanup()`.
- Modify: `alignment_tool/io/midi_adapter.py` — remove unused `_has_tempo_changes` bool; remove unused `MIDI_TO_NOTE` import if present.
- Modify: `alignment_tool/io/camera_adapter.py` — raise `InvalidFpsError` if `capture_fps <= 0`; raise `VideoOpenError`/`CameraXmlParseError` instead of returning silently on failure.

- [ ] **Step 1: Update `FrameWorker`.**

```python
"""Background thread for cv2 video frame extraction."""
from __future__ import annotations

import logging
from collections import OrderedDict

import cv2
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage

logger = logging.getLogger(__name__)
MAX_CACHE = 32


class FrameWorker(QObject):
    frame_ready = pyqtSignal(int, object)   # (frame_index, QImage)
    open_failed = pyqtSignal(str)           # (error message)

    def __init__(self):
        super().__init__()
        self._capture: cv2.VideoCapture | None = None
        self._cache: OrderedDict[int, QImage] = OrderedDict()
        self._generation: int = 0

    @pyqtSlot(str)
    def open_video(self, mp4_path: str):
        self.close_video()
        self._generation += 1
        self._cache.clear()
        self._capture = cv2.VideoCapture(mp4_path)
        if not self._capture.isOpened():
            logger.warning("FrameWorker: cannot open %s", mp4_path)
            self._capture = None
            self.open_failed.emit(f"Could not open video: {mp4_path}")

    @pyqtSlot(int)
    def request_frame(self, frame_index: int):
        # Snapshot generation at dispatch; after a subsequent open_video,
        # this stale request simply becomes a no-op.
        requested_gen = self._generation
        if self._capture is None:
            return
        if frame_index in self._cache:
            self._cache.move_to_end(frame_index)
            if requested_gen == self._generation:
                self.frame_ready.emit(frame_index, self._cache[frame_index])
            return
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, bgr = self._capture.read()
        if not ret:
            return
        if requested_gen != self._generation:
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        self._cache[frame_index] = qimg
        if len(self._cache) > MAX_CACHE:
            self._cache.popitem(last=False)
        self.frame_ready.emit(frame_index, qimg)

    @pyqtSlot()
    def close_video(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._cache.clear()
```

- [ ] **Step 2: Update `CameraPanelWidget` to listen to `open_failed` and stop in `hideEvent`.**

In `alignment_tool/ui/level2_camera_panel.py`:

- Connect `self._worker.open_failed.connect(self._on_worker_open_failed)` after worker creation.
- Add:

```python
def _on_worker_open_failed(self, msg: str) -> None:
    self._frame_label.setStyleSheet("background: #7a1f1f; color: white;")
    self._frame_label.setText(f"Video unavailable:\n{msg}")

def hideEvent(self, event):
    self.cleanup()
    super().hideEvent(event)
```

- [ ] **Step 3: Adapter dead-state cleanup.**

In `alignment_tool/io/midi_adapter.py`:
- Remove `self._has_tempo_changes` if still present (it's computed but never read).
- Remove `from alignment_tool.... import MIDI_TO_NOTE` if unused.

(Case-insensitive suffix in `participant_loader.py` is already handled in Task 11 Step 1.)

In `alignment_tool/io/camera_adapter.py`:
- In the constructor (`CameraAdapter.__init__`), wrap XML parsing in try/except → raise `CameraXmlParseError(path, reason)`.
- Wrap `cv2.VideoCapture(mp4_path)` + `isOpened()` check → raise `VideoOpenError(path, reason)` if open fails.
- In `to_file_info()`, after reading `capture_fps`, `if capture_fps <= 0: raise InvalidFpsError(capture_fps)`.

- [ ] **Step 4: Smoke-test.**

Run: `python -m alignment_tool`
- Load a participant (case-insensitive filenames if any). Drill into Level 2. Drill back out. Drill into a different pair. Exit.
- Expected: no handle leaks (observable via a repeat of drill-in/out 10x — no gradual slowdown). No console errors.

- [ ] **Step 5: Commit.**

```bash
git add -A
git commit -m "FrameWorker generation + open_failed; camera hideEvent cleanup; adapter error hygiene"
```

---

## Task 16: Add `test_no_qt_in_core.py` subprocess import guard

**Files:**
- Create: `tests/test_no_qt_in_core.py`

- [ ] **Step 1: Write the test.**

```python
"""Subprocess test: importing core and services must NOT import PyQt5.

This enforces the one-way dependency rule from the refactor spec.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap


def test_core_and_services_do_not_import_pyqt5():
    code = textwrap.dedent("""
        import importlib, sys
        # Poison: if anything tries to `import PyQt5`, it fails loudly.
        class _Poison:
            def __getattr__(self, name):
                raise AssertionError(f"PyQt5.{name} accessed from Qt-free code")
        sys.modules["PyQt5"] = _Poison()

        importlib.import_module("alignment_tool.core")
        importlib.import_module("alignment_tool.core.errors")
        importlib.import_module("alignment_tool.core.models")
        importlib.import_module("alignment_tool.core.engine")
        importlib.import_module("alignment_tool.core.persistence")
        importlib.import_module("alignment_tool.services")
        importlib.import_module("alignment_tool.services.alignment_service")
        importlib.import_module("alignment_tool.services.level2_controller")

        assert "PyQt5.QtCore" not in sys.modules, "PyQt5.QtCore leaked"
        assert "PyQt5.QtWidgets" not in sys.modules, "PyQt5.QtWidgets leaked"
    """)
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Qt-free import check failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
```

- [ ] **Step 2: Run the test.**

Run: `pytest tests/test_no_qt_in_core.py -v`
Expected: pass. If it fails, `stderr` will identify which module imported PyQt5 — fix by moving that import into a function body or into `ui/`.

- [ ] **Step 3: Run the full suite.**

Run: `pytest tests/ -v`
Expected: ~45 tests passing, <1s total.

- [ ] **Step 4: Commit.**

```bash
git add tests/test_no_qt_in_core.py
git commit -m "Enforce ui→services→io→core import direction via subprocess test"
```

---

## Task 17: Write `docs/ARCHITECTURE.md`, update `README.md`, delete the untracked `docs/sections/`

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Rewrite: `README.md`
- Delete: `docs/index.md`, `docs/sections/` (currently untracked — not in git — so just `rm -rf`)

- [ ] **Step 1: Verify `docs/sections/` is untracked.**

Run: `git status`
Expected: `docs/` listed under "Untracked files". (Confirmed at the start of this refactor.)

- [ ] **Step 2: Delete the untracked docs tree (keep `docs/superpowers/`).**

Run: `rm -rf docs/index.md docs/sections`

- [ ] **Step 3: Write `docs/ARCHITECTURE.md`.**

```markdown
# Architecture

> Living overview of the `alignment_tool` package. For the history of how we got here, see `docs/superpowers/specs/2026-04-13-alignment-tool-refactor-design.md`.

## Package Layering

```
ui → services → io → core
```

- **`core/`** — pure Python. Dataclasses (`models`), time math (`engine`), JSON persistence (`persistence`), exception hierarchy (`errors`). No Qt, no external I/O.
- **`io/`** — filesystem and hardware surfaces: MIDI parsing (`midi_adapter`), Sony FX30 XML + cv2 wrapping (`camera_adapter`), folder scan (`participant_loader`), background video decode (`frame_worker`). May use `QThread` / `pyqtSignal`; never `QWidget`.
- **`services/`** — Qt-free controllers. `AlignmentService` is the *only* code path that mutates `AlignmentState` at runtime (persistence load does bulk replacement). `Level2Controller` extracts mode, marker, and sync logic out of the Level 2 view.
- **`ui/`** — every PyQt widget.

The import direction is enforced by `tests/test_no_qt_in_core.py`, which imports `core` and `services` in a subprocess where `PyQt5` is poisoned in `sys.modules`.

## Two-Phase Alignment

The tool reconciles two unsynchronized clocks:

1. **Global offset** — one scalar `global_shift_seconds` on `AlignmentState` absorbs the 1–20 minute clock offset for a whole participant. Applied uniformly to every camera clip.
2. **Per-clip anchor refinement** — each `CameraFileInfo` may hold `Anchor` pairs (`midi_timestamp_seconds`, `camera_frame`). The `active_anchor_index` selects which anchor derives the clip's `anchor_shift`; the effective shift is `global_shift + anchor_shift`.

**Invariant:** changing `global_shift_seconds` invalidates every anchor. This is enforced inside `AlignmentService.set_global_shift` — no other code path writes the field. Callers either pass `clear_anchors_if_needed=True` (and get a `ShiftChangeResult.cleared_anchor_count`) or catch `AnchorsExistError` and prompt the user.

## Data Flow

- **State ownership** — one `AlignmentState` lives on `MainWindow`. `AlignmentService` and `Level2Controller` hold references (not copies).
- **Write path** — widget signal → `ui/*` handler → `service.method(...)` → mutation or typed exception → UI refreshes.
- **Read path** — widgets query `service.effective_shift_for(camera_index)` and friends; they never recompute the formulas themselves.
- **Level-2 sync (FREE vs LOCKED)** — `Level2Controller.on_midi_position_changed` / `on_camera_position_changed` return a `SyncOutput(new_midi_time, new_camera_frame, out_of_range_delta)`. The view renders this output through `QSignalBlocker`-guarded `set_*` calls.

## Persistence

Schema v1, JSON, atomic write via `tempfile` + `os.replace`. Every field needed for Level 2 to function is persisted (media paths, `total_frames`, `ticks_per_beat`, etc.), so a fresh `File → Load Alignment` yields a fully operational state without also re-opening the source folder.

Missing or mismatched `schema_version` → `UnsupportedSchemaVersionError`. Unparseable JSON → `CorruptAlignmentFileError`.

## Threading

One `QThread` owns a `FrameWorker`. The worker keeps a monotonic `_generation` counter; frames dispatched before the last `open_video` are discarded. `CameraPanelWidget.hideEvent` stops the worker so cv2 handles don't leak across Level-1 ↔ Level-2 transitions.

## Testing

Qt-free suite under `tests/`: `core` and `services` tested without a running `QApplication`. `pytest-qt` is intentionally not used; UI is verified manually.
```

- [ ] **Step 4: Rewrite `README.md`.**

```markdown
# midi_camera_alignment_tool

A PyQt5 desktop tool for temporally aligning overhead camera recordings (Sony FX30, ~240 fps) to Disklavier MIDI files across a multi-participant piano study. The two recording systems run on unsynchronized clocks with a 1–20 minute constant offset per participant; the tool provides a manual two-phase workflow (global offset → per-clip anchor refinement) and persists the result as JSON.

## Install

```bash
python -m pip install -r requirements.txt    # or install PyQt5, mido, pretty_midi, opencv-python, numpy
```

## Run

```bash
python -m alignment_tool
```

## Expected participant folder layout

```
participant_042/
  disklavier/
    trial_001.mid
    trial_002.mid
    ...
  overhead camera/
    C0001.MP4
    C0001M01.XML
    C0002.MP4
    C0002M01.XML
    ...
```

## Workflow

1. **File → Open Participant** — select the participant folder.
2. **Level 1 — Timeline** — rough bar chart of every MIDI and camera clip by unix timestamp. Enter a "global shift" in seconds and click Apply to move every camera clip until the two tracks roughly line up. Double-click a MIDI/camera pair to drill into Level 2.
3. **Level 2 — Detail View** — side-by-side falling-keys MIDI piano roll + video frame. Mark one MIDI keypress (`M`), mark the same keypress in the video (`C`), then either "Compute Shift" (set the global shift from these two markers) or "Add Anchor" (record a per-clip refinement).
4. **Mode: Locked** — when engaged, scrubbing either panel drives the other using the current effective shift. Use this to spot-check alignment quality.
5. **File → Save Alignment** — writes everything to JSON. **File → Load Alignment** — restores a saved session with no need to re-open the folder.

## Architecture

See `docs/ARCHITECTURE.md`.

## Tests

```bash
pytest tests/ -v
```

All ~45 tests are Qt-free and run in well under a second.
```

- [ ] **Step 5: Verify docs render, app still runs, tests still pass.**

Run: `pytest tests/ -v`
Expected: all pass.

Run: `python -m alignment_tool`
Expected: launches, full workflow works.

- [ ] **Step 6: Commit.**

```bash
git add README.md docs/ARCHITECTURE.md
git commit -m "Add docs/ARCHITECTURE.md; rewrite README; drop stale docs/sections"
```

---

## Final Validation Checklist

After Task 17:

- [ ] `pytest tests/ -v` → all ~45 tests pass, runtime <1s
- [ ] `python -m alignment_tool` launches cleanly
- [ ] Full manual smoke: Open participant → Level 1 shift → Drill into Level 2 → Mark MIDI + camera → Compute Shift → Add Anchor → Lock mode scrub → Back to Level 1 → Save → Load → re-enter Level 2 and video still renders
- [ ] `git log --oneline` shows one commit per completed task, each green
- [ ] `grep -r "clear_all_anchors" alignment_tool/` → no matches
- [ ] `grep -r "alignment_tool.alignment_engine\|alignment_tool.models\|alignment_tool.persistence\|alignment_tool.midi_adapter\|alignment_tool.camera_adapter\|alignment_tool.frame_worker\|alignment_tool.participant_loader\|alignment_tool.main_window\|alignment_tool.level1_timeline\|alignment_tool.level2_view\|alignment_tool.midi_panel\|alignment_tool.camera_panel\|alignment_tool.anchor_table\|alignment_tool.overlap_indicator" alignment_tool/ tests/` → no matches (every import uses the new sub-package path)

If all boxes tick, the refactor is complete.
