# MIDI-Camera Alignment Tool v2 Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the existing PyQt5 alignment tool from scratch as a PySide6 app with a pure-Python core and thin Qt adapter, preserving feature-parity with v1 while fixing 15 audit-identified bugs.

**Architecture:** Two-tier. `core/` + `io/` are pure Python (no PySide6 import, fully unit-testable). `qt/` contains `AlignmentController(QObject)` + widgets + `FrameWorker`. Widgets talk only to the controller; the controller wraps `AlignmentService` + `AlignmentSession`.

**Tech Stack:** Python 3.11+, PySide6 ≥6.7, pretty_midi, mido, opencv-python, pytest. Windows only.

**Source of truth:** `docs/superpowers/specs/2026-04-13-midi-camera-alignment-rebuild-design.md`.

---

## File Structure

All new code goes under `alignment_tool/`. After Task 1 deletes v1, the final tree is:

```
alignment_tool/
├── __init__.py              # empty
├── __main__.py              # imports app.main, calls it
├── app.py                   # QApplication bootstrap + logging config
├── core/
│   ├── __init__.py          # empty
│   ├── errors.py            # 5 typed exceptions
│   ├── models.py            # Anchor, MidiFileInfo, CameraFileInfo, AlignmentState
│   ├── engine.py            # 10 pure math functions
│   ├── service.py           # AlignmentService + AlignmentSession + GlobalShiftResult
│   └── persistence.py       # save_alignment + load_alignment (schema v2)
├── io/
│   ├── __init__.py          # empty
│   ├── midi_adapter.py      # MidiAdapter — pretty_midi + mido wrapper
│   ├── camera_adapter.py    # CameraAdapter — cv2 + XML sidecar
│   ├── midi_cache.py        # MidiCache — per-path cache of parsed MIDI
│   └── participant_loader.py
└── qt/
    ├── __init__.py
    ├── controller.py        # AlignmentController(QObject) shim
    ├── main_window.py
    ├── level1/
    │   ├── __init__.py
    │   ├── widget.py
    │   └── timeline_canvas.py
    ├── level2/
    │   ├── __init__.py
    │   ├── view.py
    │   ├── midi_panel.py
    │   ├── camera_panel.py
    │   ├── anchor_table.py
    │   ├── overlap_indicator.py
    │   ├── marker_bar.py
    │   └── shortcut_router.py
    └── workers/
        ├── __init__.py
        └── frame_worker.py

tests/
├── __init__.py
├── conftest.py
├── fixtures.py
├── test_engine.py
├── test_service.py
└── test_persistence.py

requirements.txt
pytest.ini
```

---

## Phase A — Clean slate and scaffolding (Tasks 1–3)

### Task 1: Delete v1 files and preserve the spec/plan

**Files:**
- Delete: `alignment_tool/` (entire directory)
- Delete: `docs/sections/` (entire directory)
- Delete: `docs/index.md`
- Delete: `scripts/` (entire directory)
- Delete: `archives/` (entire directory)
- Delete: `__pycache__/` (root level)
- Keep: `docs/superpowers/` (spec + this plan)
- Keep: `CLAUDE.md`, `README.md`, `LICENSE`, `.gitignore`

- [ ] **Step 1: Verify which files/dirs exist**

Run: `ls`
Expected output includes: `alignment_tool`, `archives`, `docs`, `scripts`, `__pycache__` (plus keepers).

- [ ] **Step 2: Delete v1 directories**

```bash
rm -rf alignment_tool docs/sections docs/index.md scripts archives __pycache__
```

- [ ] **Step 3: Verify docs/superpowers/ survived**

Run: `ls docs/superpowers/specs/`
Expected: `2026-04-13-midi-camera-alignment-rebuild-design.md`

Run: `ls docs/superpowers/plans/`
Expected: `2026-04-13-midi-camera-alignment-rebuild.md`

- [ ] **Step 4: Commit the clean slate**

```bash
git add -A
git commit -m "$(cat <<'EOF'
Clean slate for v2 rebuild

Remove v1 PyQt5 source, v1 user docs, scripts, and archived examples.
Preserve docs/superpowers/ (spec + implementation plan) as the source
of truth for the rebuild.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Scaffold new package structure with empty files

**Files:**
- Create: all the directories and `__init__.py` files listed in the File Structure section.
- Create: `requirements.txt`, `pytest.ini`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p alignment_tool/core alignment_tool/io \
         alignment_tool/qt/level1 alignment_tool/qt/level2 alignment_tool/qt/workers \
         tests
```

- [ ] **Step 2: Create empty `__init__.py` files**

```bash
touch alignment_tool/__init__.py \
      alignment_tool/core/__init__.py \
      alignment_tool/io/__init__.py \
      alignment_tool/qt/__init__.py \
      alignment_tool/qt/level1/__init__.py \
      alignment_tool/qt/level2/__init__.py \
      alignment_tool/qt/workers/__init__.py \
      tests/__init__.py
```

- [ ] **Step 3: Write `requirements.txt`**

Create `requirements.txt`:
```
PySide6>=6.7,<7
pretty_midi>=0.2.10
mido>=1.3.0
opencv-python>=4.8
numpy>=1.24
pytest>=8.0
```

- [ ] **Step 4: Write `pytest.ini`**

Create `pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -ra --strict-markers
```

- [ ] **Step 5: Verify scaffolding**

Run: `find alignment_tool tests -type f | sort`
Expected: all `__init__.py` files listed, no other source yet.

- [ ] **Step 6: Commit**

```bash
git add alignment_tool tests requirements.txt pytest.ini
git commit -m "$(cat <<'EOF'
Scaffold v2 package structure

Add empty package skeleton for core/io/qt tiers, tests directory,
requirements.txt (PySide6, pretty_midi, mido, opencv-python, pytest),
and pytest.ini.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Install dependencies and verify Python environment

**Files:** none

- [ ] **Step 1: Check Python version**

Run: `python --version`
Expected: Python 3.11 or later.

- [ ] **Step 2: Install requirements**

Run: `pip install -r requirements.txt`
Expected: all packages resolve and install cleanly.

- [ ] **Step 3: Verify PySide6 is importable**

Run: `python -c "from PySide6.QtCore import QObject; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Verify pytest runs (zero tests collected is fine)**

Run: `pytest`
Expected: `collected 0 items` with exit code 5 (no tests — fine at this stage).

- [ ] **Step 5: No commit** (nothing to stage — environment only).

---

## Phase B — Pure-Python core (Tasks 4–14)

### Task 4: Typed exceptions (`core/errors.py`)

**Files:**
- Create: `alignment_tool/core/errors.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/core/errors.py`:
```python
"""Typed exceptions for the alignment tool core.

All exceptions raised by core/ and io/ inherit from AlignmentToolError.
The Qt controller catches these and translates to UI dialogs.
"""


class AlignmentToolError(Exception):
    """Base class for all tool exceptions."""


class InvalidStateError(AlignmentToolError):
    """Operation attempted before state is loaded, or on inconsistent state."""


class InvalidCameraError(AlignmentToolError):
    """Camera index out of range."""


class InvalidAnchorError(AlignmentToolError):
    """Anchor index out of range, or anchor values outside the clip/MIDI bounds."""


class MissingMidiError(AlignmentToolError):
    """Anchor references a MIDI filename that is not present in the state."""


class SchemaVersionError(AlignmentToolError):
    """JSON schema_version did not match the expected value."""


class MediaNotFoundError(AlignmentToolError):
    """participant_folder (or a required file within it) was not found."""

    def __init__(self, message: str, missing_path: str):
        super().__init__(message)
        self.missing_path = missing_path


class PersistenceError(AlignmentToolError):
    """Generic failure during save/load."""
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "from alignment_tool.core.errors import InvalidAnchorError, MediaNotFoundError; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/core/errors.py
git commit -m "$(cat <<'EOF'
Add typed exceptions for core tier

Defines AlignmentToolError base and specific subclasses for invalid
state/camera/anchor, missing MIDI, schema mismatch, media not found,
and generic persistence failures.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Data model (`core/models.py`)

**Files:**
- Create: `alignment_tool/core/models.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/core/models.py`:
```python
"""Pure-Python dataclasses for the alignment tool state.

No behavior beyond defaults. Mutations are performed by AlignmentService.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Anchor:
    """One (MIDI timestamp, camera frame) correspondence within a clip.

    Anchors are immutable — to change one, replace it in the clip's list.
    """
    midi_filename: str              # basename of the .mid (not a full path)
    midi_timestamp_seconds: float   # seconds from that MIDI file's first event
    camera_frame: int               # 0-indexed cv2 frame within the camera clip
    label: str = ""


@dataclass
class MidiFileInfo:
    """One MIDI file's metadata. file_path is reconstructed on load; not persisted."""
    filename: str
    file_path: Path
    unix_start: float
    unix_end: float
    duration: float
    sample_rate: float


@dataclass
class CameraFileInfo:
    """One camera clip's metadata plus its anchors and the active-anchor pointer."""
    filename: str
    file_path: Path
    xml_path: Path
    raw_unix_start: float
    raw_unix_end: float
    duration: float
    capture_fps: float
    total_frames: int
    alignment_anchors: list[Anchor] = field(default_factory=list)
    active_anchor_index: int | None = None


@dataclass
class AlignmentState:
    """Top-level container — persisted as schema v2."""
    participant_id: str
    participant_folder: Path
    global_shift_seconds: float = 0.0
    midi_files: list[MidiFileInfo] = field(default_factory=list)
    camera_files: list[CameraFileInfo] = field(default_factory=list)
    alignment_notes: str = ""
```

- [ ] **Step 2: Verify it imports**

Run: `python -c "from alignment_tool.core.models import AlignmentState, Anchor; a = Anchor('x.mid', 1.0, 100); print(a)"`
Expected: `Anchor(midi_filename='x.mid', midi_timestamp_seconds=1.0, camera_frame=100, label='')`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/core/models.py
git commit -m "$(cat <<'EOF'
Add dataclasses for alignment state

Anchor (frozen), MidiFileInfo, CameraFileInfo, AlignmentState. Paths
are pathlib.Path. total_frames and participant_folder are required
fields per schema v2.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Test fixtures (`tests/fixtures.py`)

**Files:**
- Create: `tests/fixtures.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the builders**

Create `tests/fixtures.py`:
```python
"""Synthetic builders for tests. No file I/O, no Qt."""
from __future__ import annotations

from pathlib import Path

from alignment_tool.core.models import (
    AlignmentState, Anchor, CameraFileInfo, MidiFileInfo,
)


def make_midi(
    filename: str = "trial.mid",
    unix_start: float = 1_000_000.0,
    duration: float = 60.0,
    sample_rate: float = 1920.0,
) -> MidiFileInfo:
    return MidiFileInfo(
        filename=filename,
        file_path=Path(f"/fake/{filename}"),
        unix_start=unix_start,
        unix_end=unix_start + duration,
        duration=duration,
        sample_rate=sample_rate,
    )


def make_camera(
    filename: str = "C0001.MP4",
    raw_unix_start: float = 1_000_005.0,
    capture_fps: float = 240.0,
    total_frames: int = 14400,
    anchors: list[Anchor] | None = None,
    active: int | None = None,
) -> CameraFileInfo:
    duration = total_frames / capture_fps
    return CameraFileInfo(
        filename=filename,
        file_path=Path(f"/fake/{filename}"),
        xml_path=Path(f"/fake/{filename.replace('.MP4', 'M01.XML')}"),
        raw_unix_start=raw_unix_start,
        raw_unix_end=raw_unix_start + duration,
        duration=duration,
        capture_fps=capture_fps,
        total_frames=total_frames,
        alignment_anchors=anchors or [],
        active_anchor_index=active,
    )


def make_anchor(
    midi_filename: str = "trial.mid",
    midi_timestamp_seconds: float = 5.0,
    camera_frame: int = 1200,
    label: str = "",
) -> Anchor:
    return Anchor(midi_filename, midi_timestamp_seconds, camera_frame, label)


def make_state(
    midis: list[MidiFileInfo] | None = None,
    cameras: list[CameraFileInfo] | None = None,
    global_shift: float = 0.0,
    participant_id: str = "P001",
) -> AlignmentState:
    return AlignmentState(
        participant_id=participant_id,
        participant_folder=Path("/fake/P001"),
        global_shift_seconds=global_shift,
        midi_files=midis if midis is not None else [make_midi()],
        camera_files=cameras if cameras is not None else [make_camera()],
    )
```

- [ ] **Step 2: Write conftest**

Create `tests/conftest.py`:
```python
"""Global pytest configuration."""
import sys
from pathlib import Path

# Ensure the project root is on sys.path so tests can import alignment_tool.
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 3: Sanity-check fixtures import**

Run: `python -c "from tests.fixtures import make_state; print(make_state())"`
Expected: prints an `AlignmentState(...)` representation.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures.py tests/conftest.py
git commit -m "$(cat <<'EOF'
Add synthetic test fixtures and conftest

make_midi/make_camera/make_anchor/make_state return dataclass
instances with sensible defaults. conftest prepends project root to
sys.path.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Engine — shift computations (TDD)

**Files:**
- Create: `tests/test_engine.py` (first batch of tests)
- Create: `alignment_tool/core/engine.py` (first batch of functions)

- [ ] **Step 1: Write failing tests for shift functions**

Create `tests/test_engine.py`:
```python
"""Tests for core/engine.py — pure-Python alignment math."""
import pytest

from alignment_tool.core import engine
from alignment_tool.core.models import AlignmentState
from tests.fixtures import make_anchor, make_camera, make_midi, make_state


class TestGlobalShiftFromMarkers:
    def test_positive_when_midi_ahead_of_camera(self):
        # MIDI at t=1000, camera at t=990 → MIDI ahead by 10 → positive shift.
        assert engine.compute_global_shift_from_markers(1000.0, 990.0) == 10.0

    def test_negative_when_camera_ahead(self):
        assert engine.compute_global_shift_from_markers(990.0, 1000.0) == -10.0

    def test_zero_when_equal(self):
        assert engine.compute_global_shift_from_markers(500.0, 500.0) == 0.0


class TestComputeAnchorShift:
    def test_zero_when_markers_consistent_with_global_shift(self):
        midi = make_midi(unix_start=1000.0, duration=60.0)
        camera = make_camera(raw_unix_start=990.0, capture_fps=240.0)
        # Anchor at MIDI t=5 (unix 1005) and camera frame 3600 (unix 990 + 15 = 1005).
        # global_shift = 0. anchor_shift should be +10 (MIDI unix ahead by 10).
        anchor = make_anchor(midi_timestamp_seconds=5.0, camera_frame=3600)
        shift = engine.compute_anchor_shift(anchor, camera, midi, global_shift=0.0)
        assert shift == pytest.approx(10.0)

    def test_residual_over_global_shift(self):
        midi = make_midi(unix_start=1000.0, duration=60.0)
        camera = make_camera(raw_unix_start=990.0, capture_fps=240.0)
        anchor = make_anchor(midi_timestamp_seconds=5.0, camera_frame=3600)
        # If global_shift already absorbs the 10s, anchor_shift should be 0.
        shift = engine.compute_anchor_shift(anchor, camera, midi, global_shift=10.0)
        assert shift == pytest.approx(0.0)


class TestComputeEffectiveShift:
    def test_sums_global_and_anchor(self):
        assert engine.compute_effective_shift(10.0, 0.5) == pytest.approx(10.5)

    def test_returns_global_when_anchor_zero(self):
        assert engine.compute_effective_shift(7.0, 0.0) == 7.0


class TestGetEffectiveShiftForCamera:
    def test_no_active_anchor_returns_global(self):
        state = make_state(global_shift=42.0)
        camera = state.camera_files[0]
        assert engine.get_effective_shift_for_camera(state, camera) == 42.0

    def test_active_anchor_returns_global_plus_anchor_shift(self):
        midi = make_midi(unix_start=1000.0, duration=60.0)
        anchor = make_anchor(midi_timestamp_seconds=5.0, camera_frame=3600)
        camera = make_camera(
            raw_unix_start=990.0, capture_fps=240.0,
            anchors=[anchor], active=0,
        )
        state = make_state(midis=[midi], cameras=[camera], global_shift=0.0)
        # anchor_shift = 10, global = 0 → effective = 10.
        assert engine.get_effective_shift_for_camera(state, camera) == pytest.approx(10.0)

    def test_active_anchor_missing_midi_falls_back_to_global(self):
        # Anchor references "ghost.mid" that isn't in state.midi_files.
        anchor = make_anchor(midi_filename="ghost.mid")
        camera = make_camera(anchors=[anchor], active=0)
        state = make_state(
            midis=[make_midi(filename="real.mid")],
            cameras=[camera],
            global_shift=99.0,
        )
        assert engine.get_effective_shift_for_camera(state, camera) == 99.0
```

- [ ] **Step 2: Run — expect failures**

Run: `pytest tests/test_engine.py -v`
Expected: all tests fail with `ModuleNotFoundError` or `AttributeError` — `engine` is empty.

- [ ] **Step 3: Implement the functions**

Create `alignment_tool/core/engine.py`:
```python
"""Pure-Python alignment math for MIDI/camera synchronization.

Sign convention: a positive shift means the MIDI clock is ahead of the
camera clock. That is, midi_unix = camera_unix + effective_shift.

All functions are pure — no I/O, no side effects. Return None in
documented out-of-range conditions so callers can distinguish from
numerical zero.
"""
from __future__ import annotations

from alignment_tool.core.models import (
    AlignmentState, Anchor, CameraFileInfo, MidiFileInfo,
)


def compute_global_shift_from_markers(
    midi_unix: float, camera_unix: float
) -> float:
    """Global shift that aligns a MIDI marker with a camera marker.

    Positive result means MIDI clock is ahead of camera clock at the markers.
    """
    return midi_unix - camera_unix


def compute_anchor_shift(
    anchor: Anchor,
    camera: CameraFileInfo,
    midi: MidiFileInfo,
    global_shift: float,
) -> float:
    """Per-anchor residual shift, on top of global_shift.

    If the anchor's MIDI and camera times already agree under global_shift,
    this returns 0.0.
    """
    midi_unix_at_anchor = midi.unix_start + anchor.midi_timestamp_seconds
    camera_unix_at_anchor = (
        camera.raw_unix_start + anchor.camera_frame / camera.capture_fps
    )
    return midi_unix_at_anchor - camera_unix_at_anchor - global_shift


def compute_effective_shift(global_shift: float, anchor_shift: float) -> float:
    """effective_shift = global_shift + anchor_shift."""
    return global_shift + anchor_shift


def get_effective_shift_for_camera(
    state: AlignmentState, camera: CameraFileInfo
) -> float:
    """Effective shift for one camera clip, falling back to global_shift.

    Falls back when: no active anchor, OR the active anchor references a
    MIDI filename not present in state.midi_files.
    """
    idx = camera.active_anchor_index
    if idx is None or idx < 0 or idx >= len(camera.alignment_anchors):
        return state.global_shift_seconds
    anchor = camera.alignment_anchors[idx]
    midi = _find_midi_by_filename(state, anchor.midi_filename)
    if midi is None:
        return state.global_shift_seconds
    anchor_shift = compute_anchor_shift(
        anchor, camera, midi, state.global_shift_seconds
    )
    return compute_effective_shift(state.global_shift_seconds, anchor_shift)


def _find_midi_by_filename(
    state: AlignmentState, filename: str
) -> MidiFileInfo | None:
    for m in state.midi_files:
        if m.filename == filename:
            return m
    return None
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_engine.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/engine.py tests/test_engine.py
git commit -m "$(cat <<'EOF'
Add engine shift computations with tests

compute_global_shift_from_markers, compute_anchor_shift,
compute_effective_shift, get_effective_shift_for_camera. Sign
convention: positive shift = MIDI ahead of camera. TDD round 1.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Engine — time conversions (TDD)

**Files:**
- Modify: `tests/test_engine.py` (append new test classes)
- Modify: `alignment_tool/core/engine.py` (append new functions)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_engine.py`:
```python
class TestUnixConversions:
    def test_midi_seconds_to_unix(self):
        midi = make_midi(unix_start=1000.0)
        assert engine.midi_seconds_to_unix(7.5, midi) == 1007.5

    def test_camera_frame_to_unix(self):
        camera = make_camera(raw_unix_start=2000.0, capture_fps=240.0)
        assert engine.camera_frame_to_unix(480, camera) == pytest.approx(2002.0)


class TestMidiUnixToCameraFrame:
    def test_in_range_returns_rounded_frame(self):
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        # midi_unix 1002, effective_shift 0 → camera_unix 1002 → frame = 480.
        assert engine.midi_unix_to_camera_frame(1002.0, 0.0, camera) == 480

    def test_before_clip_returns_none(self):
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        assert engine.midi_unix_to_camera_frame(999.0, 0.0, camera) is None

    def test_at_or_after_total_frames_returns_none(self):
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        # Frame index 24000 is out of range (valid range is [0, 24000)).
        # camera duration = 100s → midi_unix 1100 + 1/240 puts us at frame 24000.
        assert (
            engine.midi_unix_to_camera_frame(1100.0, 0.0, camera) is None
            or engine.midi_unix_to_camera_frame(1100.0 + 1 / 240, 0.0, camera)
            is None
        )

    def test_exact_helper_unrounded(self):
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        # midi_unix 1002.001, effective 0 → 480.24 exact.
        exact = engine.midi_unix_to_camera_frame_exact(1002.001, 0.0, camera)
        assert exact == pytest.approx(480.24)

    def test_exact_helper_returns_none_out_of_range(self):
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        assert engine.midi_unix_to_camera_frame_exact(999.0, 0.0, camera) is None
```

- [ ] **Step 2: Run — expect failures**

Run: `pytest tests/test_engine.py::TestUnixConversions tests/test_engine.py::TestMidiUnixToCameraFrame -v`
Expected: 6 failures (`AttributeError` — functions not defined yet).

- [ ] **Step 3: Append implementation**

Append to `alignment_tool/core/engine.py`:
```python
def midi_seconds_to_unix(seconds: float, midi: MidiFileInfo) -> float:
    """Convert seconds-from-midi-start to unix time."""
    return midi.unix_start + seconds


def camera_frame_to_unix(frame: int, camera: CameraFileInfo) -> float:
    """Convert 0-indexed camera frame to unix time."""
    return camera.raw_unix_start + frame / camera.capture_fps


def midi_unix_to_camera_frame(
    midi_unix: float, effective_shift: float, camera: CameraFileInfo
) -> int | None:
    """Map a MIDI unix time to a camera frame index (rounded).

    Returns None when the resulting frame is outside [0, camera.total_frames).
    """
    camera_unix = midi_unix - effective_shift
    frame_float = (camera_unix - camera.raw_unix_start) * camera.capture_fps
    frame = round(frame_float)
    if frame < 0 or frame >= camera.total_frames:
        return None
    return frame


def midi_unix_to_camera_frame_exact(
    midi_unix: float, effective_shift: float, camera: CameraFileInfo
) -> float | None:
    """Unrounded variant for internal chaining — avoids rounding drift."""
    camera_unix = midi_unix - effective_shift
    frame_float = (camera_unix - camera.raw_unix_start) * camera.capture_fps
    if frame_float < 0 or frame_float >= camera.total_frames:
        return None
    return frame_float
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_engine.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/engine.py tests/test_engine.py
git commit -m "$(cat <<'EOF'
Add engine time conversions

midi_seconds_to_unix, camera_frame_to_unix,
midi_unix_to_camera_frame (rounded + exact variants). Tests cover
in-range, before-clip, and at/after-end boundaries.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Engine — camera-to-midi + out-of-range delta (TDD)

**Files:**
- Modify: `tests/test_engine.py`
- Modify: `alignment_tool/core/engine.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_engine.py`:
```python
class TestCameraFrameToMidiSeconds:
    def test_in_range(self):
        midi = make_midi(unix_start=1000.0, duration=60.0)
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        # frame 2400 → camera_unix 1010 → midi_unix 1010 (shift 0) → midi_seconds 10.
        assert engine.camera_frame_to_midi_seconds(2400, 0.0, camera, midi) == \
            pytest.approx(10.0)

    def test_returns_none_before_midi_start(self):
        midi = make_midi(unix_start=1100.0, duration=60.0)
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        # frame 0 → camera_unix 1000 → midi_unix 1000 → midi_seconds -100 → None.
        assert engine.camera_frame_to_midi_seconds(0, 0.0, camera, midi) is None

    def test_returns_none_after_midi_end(self):
        midi = make_midi(unix_start=1000.0, duration=10.0)
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        # frame 3000 → camera_unix 1012.5 → midi_seconds 12.5 → None (duration 10).
        assert engine.camera_frame_to_midi_seconds(3000, 0.0, camera, midi) is None

    def test_at_exact_end_is_in_range(self):
        # midi_seconds == duration is allowed (inclusive upper bound).
        midi = make_midi(unix_start=1000.0, duration=10.0)
        camera = make_camera(
            raw_unix_start=1000.0, capture_fps=240.0, total_frames=24000,
        )
        # frame 2400 → midi_seconds 10.0 exactly.
        assert engine.camera_frame_to_midi_seconds(2400, 0.0, camera, midi) == \
            pytest.approx(10.0)


class TestOutOfRangeDelta:
    def test_in_range_returns_none(self):
        camera = make_camera(total_frames=1000, capture_fps=240.0)
        assert engine.out_of_range_delta(500, camera) is None

    def test_before_returns_positive_seconds(self):
        camera = make_camera(total_frames=1000, capture_fps=240.0)
        # frame -240 → 1s before start → +1.0.
        assert engine.out_of_range_delta(-240, camera) == pytest.approx(1.0)

    def test_after_returns_negative_seconds(self):
        camera = make_camera(total_frames=1000, capture_fps=240.0)
        # frame 1240 → 1s past end → -1.0.
        assert engine.out_of_range_delta(1240, camera) == pytest.approx(-1.0)


class TestRoundTrip:
    def test_midi_to_frame_to_midi_within_one_frame(self):
        midi = make_midi(unix_start=1000.0, duration=60.0)
        camera = make_camera(
            raw_unix_start=995.0, capture_fps=239.76, total_frames=24000,
        )
        for midi_seconds in [0.0, 1.234, 10.0, 30.123, 59.9]:
            midi_unix = engine.midi_seconds_to_unix(midi_seconds, midi)
            frame = engine.midi_unix_to_camera_frame(midi_unix, 0.0, camera)
            assert frame is not None
            back = engine.camera_frame_to_midi_seconds(frame, 0.0, camera, midi)
            assert back is not None
            # Within half a frame worth of seconds.
            assert abs(back - midi_seconds) < 1.0 / camera.capture_fps
```

- [ ] **Step 2: Run — expect failures**

Run: `pytest tests/test_engine.py::TestCameraFrameToMidiSeconds tests/test_engine.py::TestOutOfRangeDelta tests/test_engine.py::TestRoundTrip -v`
Expected: 8 failures.

- [ ] **Step 3: Append implementation**

Append to `alignment_tool/core/engine.py`:
```python
def camera_frame_to_midi_seconds(
    frame: int,
    effective_shift: float,
    camera: CameraFileInfo,
    midi: MidiFileInfo,
) -> float | None:
    """Map a camera frame to seconds-from-midi-start.

    Returns None when the resulting midi_seconds is < 0 or > midi.duration.
    Upper bound is inclusive (exactly duration is in range).
    """
    camera_unix = camera.raw_unix_start + frame / camera.capture_fps
    midi_unix = camera_unix + effective_shift
    midi_seconds = midi_unix - midi.unix_start
    if midi_seconds < 0 or midi_seconds > midi.duration:
        return None
    return midi_seconds


def out_of_range_delta(frame: int, camera: CameraFileInfo) -> float | None:
    """Signed seconds between a frame and the nearest clip boundary.

    Returns:
        None   when frame is in [0, total_frames),
        +value (seconds) when frame is before the clip (clip hasn't started),
        -value (seconds) when frame is past the clip (clip already ended).
    """
    if 0 <= frame < camera.total_frames:
        return None
    if frame < 0:
        return -frame / camera.capture_fps
    # frame >= total_frames
    return -(frame - (camera.total_frames - 1)) / camera.capture_fps
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_engine.py -v`
Expected: 23 passed.

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/engine.py tests/test_engine.py
git commit -m "$(cat <<'EOF'
Add engine camera-to-midi conversion and range delta

camera_frame_to_midi_seconds (None outside [0, duration]),
out_of_range_delta (signed seconds). Adds a round-trip test covering
float capture_fps (239.76) and multiple midi seconds points.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Service — GlobalShiftResult + load_state + set_global_shift (TDD)

**Files:**
- Create: `tests/test_service.py`
- Create: `alignment_tool/core/service.py`

- [ ] **Step 1: Write failing tests for load + global-shift flow**

Create `tests/test_service.py`:
```python
"""Tests for core/service.py — state mutations and session rules."""
import pytest

from alignment_tool.core.errors import InvalidStateError
from alignment_tool.core.service import AlignmentService, GlobalShiftResult
from tests.fixtures import make_anchor, make_camera, make_midi, make_state


class TestLoadState:
    def test_methods_error_before_load(self):
        service = AlignmentService()
        with pytest.raises(InvalidStateError):
            service.set_global_shift(1.0)

    def test_after_load_state_is_accessible(self):
        service = AlignmentService()
        state = make_state(global_shift=5.0)
        service.load_state(state)
        assert service.state is state
        assert service.total_anchor_count() == 0


class TestSetGlobalShiftNoAnchors:
    def test_applies_immediately_when_no_anchors(self):
        service = AlignmentService()
        service.load_state(make_state(global_shift=0.0))
        result = service.set_global_shift(12.5)
        assert result.anchors_to_clear == 0
        assert result.pending_token is None
        assert service.state.global_shift_seconds == pytest.approx(12.5)

    def test_noop_when_same_value_within_tolerance(self):
        service = AlignmentService()
        service.load_state(make_state(global_shift=3.0))
        result = service.set_global_shift(3.0 + 1e-12)
        assert result.anchors_to_clear == 0
        assert service.state.global_shift_seconds == pytest.approx(3.0)


class TestSetGlobalShiftWithAnchors:
    def _state_with_one_anchor(self):
        camera = make_camera(anchors=[make_anchor()], active=0)
        return make_state(cameras=[camera], global_shift=0.0)

    def test_pending_when_anchors_exist_and_value_changes(self):
        service = AlignmentService()
        service.load_state(self._state_with_one_anchor())
        result = service.set_global_shift(10.0)
        # State not mutated yet.
        assert service.state.global_shift_seconds == 0.0
        assert result.anchors_to_clear == 1
        assert result.clips_affected == 1
        assert result.pending_token is not None

    def test_confirm_commits_and_clears_all_anchors(self):
        service = AlignmentService()
        service.load_state(self._state_with_one_anchor())
        result = service.set_global_shift(10.0)
        service.confirm_global_shift(result)
        assert service.state.global_shift_seconds == 10.0
        cam = service.state.camera_files[0]
        assert cam.alignment_anchors == []
        assert cam.active_anchor_index is None

    def test_confirm_with_stale_token_raises(self):
        service = AlignmentService()
        service.load_state(self._state_with_one_anchor())
        r1 = service.set_global_shift(10.0)
        # Getting a second result invalidates r1's token.
        service.set_global_shift(20.0)
        with pytest.raises(InvalidStateError):
            service.confirm_global_shift(r1)
```

- [ ] **Step 2: Run — expect ImportError**

Run: `pytest tests/test_service.py -v`
Expected: `ModuleNotFoundError` for `alignment_tool.core.service`.

- [ ] **Step 3: Implement the service skeleton**

Create `alignment_tool/core/service.py`:
```python
"""Pure-Python service layer for the alignment tool.

AlignmentService owns the persistent AlignmentState and performs all
mutations. AlignmentSession owns UI/session state (markers, mode,
active panel).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from alignment_tool.core.engine import get_effective_shift_for_camera
from alignment_tool.core.errors import (
    InvalidAnchorError, InvalidCameraError, InvalidStateError,
    MissingMidiError,
)
from alignment_tool.core.models import (
    AlignmentState, Anchor, CameraFileInfo, MidiFileInfo,
)

_SHIFT_EPSILON = 1e-9


@dataclass
class GlobalShiftResult:
    new_shift: float
    anchors_to_clear: int
    clips_affected: int
    pending_token: object | None


class AlignmentService:
    def __init__(self) -> None:
        self._state: AlignmentState | None = None
        self._pending_token: object | None = None

    @property
    def state(self) -> AlignmentState:
        if self._state is None:
            raise InvalidStateError("No state loaded")
        return self._state

    def load_state(self, state: AlignmentState) -> None:
        self._state = state
        self._pending_token = None

    # --- queries -----------------------------------------------------

    def total_anchor_count(self) -> int:
        return sum(len(c.alignment_anchors) for c in self.state.camera_files)

    def effective_shift_for(self, camera_idx: int) -> float:
        camera = self._get_camera(camera_idx)
        return get_effective_shift_for_camera(self.state, camera)

    def active_anchor(self, camera_idx: int) -> Anchor | None:
        camera = self._get_camera(camera_idx)
        idx = camera.active_anchor_index
        if idx is None or idx < 0 or idx >= len(camera.alignment_anchors):
            return None
        return camera.alignment_anchors[idx]

    def midi_by_filename(
        self, name: str
    ) -> tuple[int, MidiFileInfo] | None:
        for i, m in enumerate(self.state.midi_files):
            if m.filename == name:
                return (i, m)
        return None

    # --- global shift ------------------------------------------------

    def set_global_shift(self, new_shift: float) -> GlobalShiftResult:
        state = self.state
        if abs(new_shift - state.global_shift_seconds) < _SHIFT_EPSILON:
            return GlobalShiftResult(
                new_shift=state.global_shift_seconds,
                anchors_to_clear=0,
                clips_affected=0,
                pending_token=None,
            )
        total_anchors = self.total_anchor_count()
        if total_anchors == 0:
            state.global_shift_seconds = new_shift
            return GlobalShiftResult(
                new_shift=new_shift,
                anchors_to_clear=0,
                clips_affected=0,
                pending_token=None,
            )
        clips_affected = sum(
            1 for c in state.camera_files if c.alignment_anchors
        )
        token = object()
        self._pending_token = token
        return GlobalShiftResult(
            new_shift=new_shift,
            anchors_to_clear=total_anchors,
            clips_affected=clips_affected,
            pending_token=token,
        )

    def confirm_global_shift(self, result: GlobalShiftResult) -> None:
        if (
            result.pending_token is None
            or result.pending_token is not self._pending_token
        ):
            raise InvalidStateError("Stale or invalid pending_token")
        state = self.state
        for c in state.camera_files:
            c.alignment_anchors.clear()
            c.active_anchor_index = None
        state.global_shift_seconds = result.new_shift
        self._pending_token = None

    # --- helpers -----------------------------------------------------

    def _get_camera(self, camera_idx: int) -> CameraFileInfo:
        cameras = self.state.camera_files
        if camera_idx < 0 or camera_idx >= len(cameras):
            raise InvalidCameraError(
                f"Camera index {camera_idx} out of range"
            )
        return cameras[camera_idx]
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_service.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/service.py tests/test_service.py
git commit -m "$(cat <<'EOF'
Add AlignmentService with load_state and global-shift flow

Two-step global shift: set_global_shift returns a GlobalShiftResult
with anchors_to_clear; if non-zero, caller must confirm_global_shift
with the same token. Epsilon-compare prevents spurious no-op clears.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Service — anchor mutations (TDD)

**Files:**
- Modify: `tests/test_service.py`
- Modify: `alignment_tool/core/service.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_service.py`:
```python
from alignment_tool.core.errors import (
    InvalidAnchorError, InvalidCameraError, MissingMidiError,
)


class TestAddAnchor:
    def test_appends_and_does_not_activate(self):
        service = AlignmentService()
        midi = make_midi()
        camera = make_camera()
        service.load_state(make_state(midis=[midi], cameras=[camera]))
        service.add_anchor(0, make_anchor())
        cam = service.state.camera_files[0]
        assert len(cam.alignment_anchors) == 1
        assert cam.active_anchor_index is None

    def test_invalid_frame_raises(self):
        service = AlignmentService()
        service.load_state(make_state())
        with pytest.raises(InvalidAnchorError):
            service.add_anchor(0, make_anchor(camera_frame=-1))

    def test_frame_at_total_frames_raises(self):
        service = AlignmentService()
        service.load_state(make_state(
            cameras=[make_camera(total_frames=1000)],
        ))
        with pytest.raises(InvalidAnchorError):
            service.add_anchor(0, make_anchor(camera_frame=1000))

    def test_timestamp_outside_duration_raises(self):
        service = AlignmentService()
        service.load_state(make_state(
            midis=[make_midi(duration=10.0)],
        ))
        with pytest.raises(InvalidAnchorError):
            service.add_anchor(0, make_anchor(midi_timestamp_seconds=10.01))

    def test_unknown_midi_raises(self):
        service = AlignmentService()
        service.load_state(make_state(
            midis=[make_midi(filename="real.mid")],
        ))
        with pytest.raises(MissingMidiError):
            service.add_anchor(0, make_anchor(midi_filename="ghost.mid"))

    def test_invalid_camera_raises(self):
        service = AlignmentService()
        service.load_state(make_state())
        with pytest.raises(InvalidCameraError):
            service.add_anchor(99, make_anchor())


class TestActivateAnchor:
    def _setup_with_two_anchors(self):
        anchors = [make_anchor(label="a"), make_anchor(label="b")]
        camera = make_camera(anchors=anchors)
        service = AlignmentService()
        service.load_state(make_state(cameras=[camera]))
        return service

    def test_activate_index_sets_active(self):
        service = self._setup_with_two_anchors()
        service.activate_anchor(0, 1)
        assert service.state.camera_files[0].active_anchor_index == 1

    def test_activate_none_deactivates(self):
        service = self._setup_with_two_anchors()
        service.activate_anchor(0, 0)
        service.activate_anchor(0, None)
        assert service.state.camera_files[0].active_anchor_index is None

    def test_activate_out_of_range_raises(self):
        service = self._setup_with_two_anchors()
        with pytest.raises(InvalidAnchorError):
            service.activate_anchor(0, 5)


class TestDeleteAnchor:
    def _setup(self, active: int | None):
        anchors = [
            make_anchor(label="a"),
            make_anchor(label="b"),
            make_anchor(label="c"),
        ]
        camera = make_camera(anchors=anchors, active=active)
        service = AlignmentService()
        service.load_state(make_state(cameras=[camera]))
        return service

    def test_delete_same_index_deactivates(self):
        service = self._setup(active=1)
        service.delete_anchor(0, 1)
        cam = service.state.camera_files[0]
        assert len(cam.alignment_anchors) == 2
        assert cam.active_anchor_index is None

    def test_delete_before_active_decrements(self):
        service = self._setup(active=2)
        service.delete_anchor(0, 0)
        cam = service.state.camera_files[0]
        assert cam.active_anchor_index == 1

    def test_delete_after_active_leaves_alone(self):
        service = self._setup(active=0)
        service.delete_anchor(0, 2)
        cam = service.state.camera_files[0]
        assert cam.active_anchor_index == 0

    def test_delete_invalid_index_raises(self):
        service = self._setup(active=None)
        with pytest.raises(InvalidAnchorError):
            service.delete_anchor(0, 99)
```

- [ ] **Step 2: Run — expect failures**

Run: `pytest tests/test_service.py::TestAddAnchor tests/test_service.py::TestActivateAnchor tests/test_service.py::TestDeleteAnchor -v`
Expected: 13 failures (methods not defined).

- [ ] **Step 3: Append implementation**

Append to `alignment_tool/core/service.py` (inside `AlignmentService`):
```python
    # --- anchor mutations -------------------------------------------

    def add_anchor(self, camera_idx: int, anchor: Anchor) -> None:
        camera = self._get_camera(camera_idx)
        if (
            anchor.camera_frame < 0
            or anchor.camera_frame >= camera.total_frames
        ):
            raise InvalidAnchorError(
                f"Camera frame {anchor.camera_frame} outside "
                f"[0, {camera.total_frames})"
            )
        midi_match = self.midi_by_filename(anchor.midi_filename)
        if midi_match is None:
            raise MissingMidiError(
                f"MIDI file {anchor.midi_filename!r} not found in state"
            )
        _, midi = midi_match
        if (
            anchor.midi_timestamp_seconds < 0
            or anchor.midi_timestamp_seconds > midi.duration
        ):
            raise InvalidAnchorError(
                f"MIDI timestamp {anchor.midi_timestamp_seconds} outside "
                f"[0, {midi.duration}]"
            )
        camera.alignment_anchors.append(anchor)

    def activate_anchor(
        self, camera_idx: int, anchor_idx: int | None
    ) -> None:
        camera = self._get_camera(camera_idx)
        if anchor_idx is None:
            camera.active_anchor_index = None
            return
        if anchor_idx < 0 or anchor_idx >= len(camera.alignment_anchors):
            raise InvalidAnchorError(
                f"Anchor index {anchor_idx} out of range"
            )
        camera.active_anchor_index = anchor_idx

    def delete_anchor(self, camera_idx: int, anchor_idx: int) -> None:
        camera = self._get_camera(camera_idx)
        if anchor_idx < 0 or anchor_idx >= len(camera.alignment_anchors):
            raise InvalidAnchorError(
                f"Anchor index {anchor_idx} out of range"
            )
        del camera.alignment_anchors[anchor_idx]
        active = camera.active_anchor_index
        if active is None:
            return
        if active == anchor_idx:
            camera.active_anchor_index = None
        elif active > anchor_idx:
            camera.active_anchor_index = active - 1

    def set_alignment_notes(self, text: str) -> None:
        self.state.alignment_notes = text
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_service.py -v`
Expected: 20 passed (7 prior + 13 new).

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/service.py tests/test_service.py
git commit -m "$(cat <<'EOF'
Add anchor mutations to AlignmentService

add_anchor validates frame, timestamp, and MIDI presence.
activate_anchor accepts None to deactivate. delete_anchor adjusts
active_anchor_index: deactivates on same-index, decrements on earlier,
leaves alone on later.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Session — anchor-lock rule (TDD)

**Files:**
- Modify: `tests/test_service.py`
- Modify: `alignment_tool/core/service.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_service.py`:
```python
from alignment_tool.core.service import AlignmentSession


class TestSessionBasics:
    def test_defaults(self):
        s = AlignmentSession()
        assert s.mode == "independent"
        assert s.active_panel == "camera"
        assert s.midi_marker is None
        assert s.camera_marker is None
        assert s.current_midi_index is None
        assert s.current_camera_index is None

    def test_markers_ready_requires_both(self):
        s = AlignmentSession()
        assert not s.markers_ready()
        s.set_marker_midi("trial.mid", 5.0)
        assert not s.markers_ready()
        s.set_marker_camera(100)
        assert s.markers_ready()

    def test_clear_markers_resets_both(self):
        s = AlignmentSession()
        s.set_marker_midi("trial.mid", 5.0)
        s.set_marker_camera(100)
        s.clear_markers()
        assert s.midi_marker is None
        assert s.camera_marker is None


class TestAnchorLockRule:
    def _setup(self, *, mode, active_idx, anchor_midi):
        anchor = make_anchor(midi_filename=anchor_midi)
        cameras = [make_camera(anchors=[anchor], active=active_idx)]
        midis = [
            make_midi(filename="real_a.mid"),
            make_midi(filename="real_b.mid"),
        ]
        service = AlignmentService()
        service.load_state(make_state(midis=midis, cameras=cameras))
        session = AlignmentSession()
        session.current_camera_index = 0
        session.mode = mode
        return service, session

    def test_independent_mode_target_is_none(self):
        service, session = self._setup(
            mode="independent", active_idx=0, anchor_midi="real_a.mid",
        )
        assert session.anchor_lock_target_midi(service) is None
        assert session.midi_combo_enabled(service) is True

    def test_locked_no_active_anchor_target_is_none(self):
        service, session = self._setup(
            mode="locked", active_idx=None, anchor_midi="real_a.mid",
        )
        assert session.anchor_lock_target_midi(service) is None
        assert session.midi_combo_enabled(service) is True

    def test_locked_active_with_known_midi_forces_target(self):
        service, session = self._setup(
            mode="locked", active_idx=0, anchor_midi="real_b.mid",
        )
        # real_b.mid is index 1 in midi_files.
        assert session.anchor_lock_target_midi(service) == 1
        assert session.midi_combo_enabled(service) is False

    def test_locked_active_with_unknown_midi_falls_through(self):
        service, session = self._setup(
            mode="locked", active_idx=0, anchor_midi="ghost.mid",
        )
        assert session.anchor_lock_target_midi(service) is None
        assert session.midi_combo_enabled(service) is True

    def test_no_camera_selected_target_is_none(self):
        service, session = self._setup(
            mode="locked", active_idx=0, anchor_midi="real_a.mid",
        )
        session.current_camera_index = None
        assert session.anchor_lock_target_midi(service) is None
```

- [ ] **Step 2: Run — expect failures**

Run: `pytest tests/test_service.py::TestSessionBasics tests/test_service.py::TestAnchorLockRule -v`
Expected: 8 failures.

- [ ] **Step 3: Append `AlignmentSession` to `service.py`**

Append to `alignment_tool/core/service.py`:
```python
class AlignmentSession:
    """UI/session state — not persisted. Holds markers, mode, and selections.

    Exposes the anchor-lock rule as a pure method so tests can verify it
    without Qt.
    """

    def __init__(self) -> None:
        self.current_midi_index: int | None = None
        self.current_camera_index: int | None = None
        self.mode: Literal["independent", "locked"] = "independent"
        self.active_panel: Literal["midi", "camera"] = "camera"
        self.midi_marker: tuple[str, float] | None = None
        self.camera_marker: int | None = None

    def set_mode(self, mode: Literal["independent", "locked"]) -> None:
        self.mode = mode

    def set_active_panel(self, panel: Literal["midi", "camera"]) -> None:
        self.active_panel = panel

    def set_midi_selection(self, idx: int | None) -> None:
        self.current_midi_index = idx

    def set_camera_selection(self, idx: int | None) -> None:
        self.current_camera_index = idx

    def set_marker_midi(self, filename: str, seconds: float) -> None:
        self.midi_marker = (filename, seconds)

    def set_marker_camera(self, frame: int) -> None:
        self.camera_marker = frame

    def clear_markers(self) -> None:
        self.midi_marker = None
        self.camera_marker = None

    def markers_ready(self) -> bool:
        return self.midi_marker is not None and self.camera_marker is not None

    def anchor_lock_target_midi(
        self, service: AlignmentService
    ) -> int | None:
        """MIDI index the combo must display, or None if unlocked."""
        if self.mode != "locked":
            return None
        if self.current_camera_index is None:
            return None
        try:
            anchor = service.active_anchor(self.current_camera_index)
        except (InvalidCameraError, InvalidStateError):
            return None
        if anchor is None:
            return None
        match = service.midi_by_filename(anchor.midi_filename)
        if match is None:
            return None
        midi_idx, _ = match
        return midi_idx

    def midi_combo_enabled(self, service: AlignmentService) -> bool:
        return self.anchor_lock_target_midi(service) is None
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_service.py -v`
Expected: 28 passed (20 prior + 8 new).

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/service.py tests/test_service.py
git commit -m "$(cat <<'EOF'
Add AlignmentSession with anchor-lock rule

Session owns mode, active panel, markers, and current MIDI/camera
selections. anchor_lock_target_midi is a pure function of (session,
service) — returns MIDI index only when mode is locked and the active
anchor's midi_filename resolves.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Persistence — save (atomic) (TDD)

**Files:**
- Create: `tests/test_persistence.py`
- Create: `alignment_tool/core/persistence.py`

- [ ] **Step 1: Write failing tests for save**

Create `tests/test_persistence.py`:
```python
"""Tests for core/persistence.py — JSON schema v2 save/load."""
import json
from pathlib import Path

import pytest

from alignment_tool.core import persistence
from alignment_tool.core.errors import PersistenceError
from tests.fixtures import make_anchor, make_camera, make_midi, make_state


class TestSave:
    def test_writes_schema_version_2(self, tmp_path: Path):
        state = make_state()
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["schema_version"] == 2

    def test_preserves_all_top_level_fields(self, tmp_path: Path):
        anchor = make_anchor(midi_filename="trial.mid", label="first C4")
        camera = make_camera(anchors=[anchor], active=0)
        state = make_state(
            midis=[make_midi(filename="trial.mid")],
            cameras=[camera],
            global_shift=-342.5,
        )
        state.alignment_notes = "hello"
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["participant_id"] == state.participant_id
        assert data["participant_folder"] == str(state.participant_folder)
        assert data["global_shift_seconds"] == pytest.approx(-342.5)
        assert data["alignment_notes"] == "hello"
        assert "saved_at_unix" in data

    def test_camera_entry_includes_total_frames(self, tmp_path: Path):
        state = make_state(
            cameras=[make_camera(total_frames=14385)],
        )
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["camera_files"][0]["total_frames"] == 14385

    def test_anchor_round_trips_in_json(self, tmp_path: Path):
        anchor = make_anchor(
            midi_filename="trial.mid",
            midi_timestamp_seconds=12.345,
            camera_frame=2880,
            label="first C4",
        )
        state = make_state(
            midis=[make_midi(filename="trial.mid")],
            cameras=[make_camera(anchors=[anchor], active=0)],
        )
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        a = data["camera_files"][0]["alignment_anchors"][0]
        assert a["midi_filename"] == "trial.mid"
        assert a["midi_timestamp_seconds"] == pytest.approx(12.345)
        assert a["camera_frame"] == 2880
        assert a["label"] == "first C4"

    def test_atomic_write_failure_leaves_existing_untouched(
        self, tmp_path: Path, monkeypatch
    ):
        out = tmp_path / "alignment.json"
        # Prior good save.
        state = make_state()
        persistence.save_alignment(state, out)
        original = out.read_text(encoding="utf-8")

        # Force json.dump to raise mid-write.
        import alignment_tool.core.persistence as p

        def boom(*a, **kw):
            raise RuntimeError("disk full")

        monkeypatch.setattr(p.json, "dump", boom)
        state2 = make_state(global_shift=999.0)
        with pytest.raises(PersistenceError):
            persistence.save_alignment(state2, out)
        # Original file untouched.
        assert out.read_text(encoding="utf-8") == original
        # No .tmp left around.
        assert not list(tmp_path.glob("*.tmp"))
```

- [ ] **Step 2: Run — expect ImportError**

Run: `pytest tests/test_persistence.py -v`
Expected: module not found.

- [ ] **Step 3: Implement `save_alignment` with atomic write**

Create `alignment_tool/core/persistence.py`:
```python
"""JSON schema v2 serialize/deserialize for AlignmentState.

Save writes to a temp file and atomically renames into place.
Load validates schema_version and resolves media relative to the
stored participant_folder (or to an overriding one passed by the caller).
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from alignment_tool.core.errors import (
    InvalidAnchorError, MediaNotFoundError, PersistenceError,
    SchemaVersionError,
)
from alignment_tool.core.models import (
    AlignmentState, Anchor, CameraFileInfo, MidiFileInfo,
)

SCHEMA_VERSION = 2
_log = logging.getLogger(__name__)


def save_alignment(state: AlignmentState, filepath: Path) -> None:
    """Atomically write the state as JSON schema v2 to `filepath`.

    Uses a sibling .tmp file and os.replace so that a crash mid-write
    cannot truncate the existing target.
    """
    payload = _state_to_dict(state)
    filepath = Path(filepath)
    tmp = filepath.with_suffix(filepath.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, filepath)
    except Exception as e:
        # Clean up tmp if it exists.
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise PersistenceError(f"Failed to save alignment: {e}") from e


def _state_to_dict(state: AlignmentState) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "participant_id": state.participant_id,
        "participant_folder": str(state.participant_folder),
        "global_shift_seconds": state.global_shift_seconds,
        "alignment_notes": state.alignment_notes,
        "saved_at_unix": time.time(),
        "midi_files": [_midi_to_dict(m) for m in state.midi_files],
        "camera_files": [_camera_to_dict(c) for c in state.camera_files],
    }


def _midi_to_dict(m: MidiFileInfo) -> dict:
    return {
        "filename": m.filename,
        "unix_start": m.unix_start,
        "unix_end": m.unix_end,
        "duration": m.duration,
        "sample_rate": m.sample_rate,
    }


def _camera_to_dict(c: CameraFileInfo) -> dict:
    return {
        "filename": c.filename,
        "xml_filename": c.xml_path.name,
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
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_persistence.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/persistence.py tests/test_persistence.py
git commit -m "$(cat <<'EOF'
Add persistence.save_alignment (schema v2, atomic)

save_alignment writes JSON to <file>.tmp then os.replace. On any
exception the tmp is removed and PersistenceError is raised, leaving
the existing target untouched. Schema v2 includes schema_version,
participant_folder, total_frames, saved_at_unix.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Persistence — load with validation (TDD)

**Files:**
- Modify: `tests/test_persistence.py`
- Modify: `alignment_tool/core/persistence.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_persistence.py`:
```python
from alignment_tool.core.errors import (
    MediaNotFoundError, SchemaVersionError,
)


def _scaffold_participant(tmp_path: Path) -> Path:
    """Create a minimal on-disk participant folder with empty files."""
    folder = tmp_path / "P042"
    (folder / "disklavier").mkdir(parents=True)
    (folder / "overhead camera").mkdir(parents=True)
    (folder / "disklavier" / "trial.mid").write_bytes(b"")
    (folder / "overhead camera" / "C0001.MP4").write_bytes(b"")
    (folder / "overhead camera" / "C0001M01.XML").write_bytes(b"")
    return folder


class TestLoad:
    def test_round_trip_preserves_fields(self, tmp_path: Path):
        folder = _scaffold_participant(tmp_path)
        midi = make_midi(filename="trial.mid")
        camera = make_camera(filename="C0001.MP4")
        state = make_state(midis=[midi], cameras=[camera])
        state.participant_folder = folder
        state.participant_id = "P042"
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)

        loaded = persistence.load_alignment(out)
        assert loaded.participant_id == "P042"
        assert loaded.participant_folder == folder
        assert len(loaded.midi_files) == 1
        assert loaded.midi_files[0].filename == "trial.mid"
        # file_path is reconstructed on load.
        assert loaded.midi_files[0].file_path == folder / "disklavier" / "trial.mid"
        assert len(loaded.camera_files) == 1
        cam = loaded.camera_files[0]
        assert cam.filename == "C0001.MP4"
        assert cam.file_path == folder / "overhead camera" / "C0001.MP4"
        assert cam.xml_path == folder / "overhead camera" / "C0001M01.XML"
        assert cam.total_frames == 14400

    def test_schema_version_mismatch_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
        with pytest.raises(SchemaVersionError):
            persistence.load_alignment(bad)

    def test_missing_participant_folder_raises(self, tmp_path: Path):
        state = make_state()
        state.participant_folder = tmp_path / "does_not_exist"
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        with pytest.raises(MediaNotFoundError) as exc:
            persistence.load_alignment(out)
        assert str(tmp_path / "does_not_exist") in exc.value.missing_path

    def test_relocate_participant_folder_argument(self, tmp_path: Path):
        """Caller can pass an override folder when the stored one is gone."""
        folder = _scaffold_participant(tmp_path)
        state = make_state(
            midis=[make_midi(filename="trial.mid")],
            cameras=[make_camera(filename="C0001.MP4")],
        )
        state.participant_folder = tmp_path / "ghost"
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        loaded = persistence.load_alignment(out, override_folder=folder)
        assert loaded.participant_folder == folder

    def test_anchor_with_missing_midi_clears_active(self, tmp_path: Path):
        folder = _scaffold_participant(tmp_path)
        # Anchor points to "ghost.mid" — not present on disk.
        anchor = make_anchor(midi_filename="ghost.mid")
        camera = make_camera(
            filename="C0001.MP4", anchors=[anchor], active=0,
        )
        # State includes only "trial.mid", but the anchor references "ghost.mid".
        state = make_state(
            midis=[make_midi(filename="trial.mid")],
            cameras=[camera],
        )
        state.participant_folder = folder
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        loaded = persistence.load_alignment(out)
        cam = loaded.camera_files[0]
        # Anchor kept.
        assert len(cam.alignment_anchors) == 1
        # Active cleared because it pointed to the dangling anchor.
        assert cam.active_anchor_index is None

    def test_anchor_frame_out_of_bounds_raises(self, tmp_path: Path):
        folder = _scaffold_participant(tmp_path)
        bad_anchor = make_anchor(
            midi_filename="trial.mid", camera_frame=999999,
        )
        camera = make_camera(
            filename="C0001.MP4", anchors=[bad_anchor], total_frames=14400,
        )
        state = make_state(
            midis=[make_midi(filename="trial.mid")],
            cameras=[camera],
        )
        state.participant_folder = folder
        out = tmp_path / "alignment.json"
        persistence.save_alignment(state, out)
        with pytest.raises(InvalidAnchorError):
            persistence.load_alignment(out)
```

- [ ] **Step 2: Run — expect failures**

Run: `pytest tests/test_persistence.py::TestLoad -v`
Expected: 6 failures (`load_alignment` not defined).

- [ ] **Step 3: Append `load_alignment` to `persistence.py`**

Append to `alignment_tool/core/persistence.py`:
```python
def load_alignment(
    filepath: Path, override_folder: Path | None = None
) -> AlignmentState:
    """Load and validate a schema-v2 JSON into an AlignmentState.

    - Checks schema_version == 2.
    - Uses override_folder if given; else the stored participant_folder.
      If neither exists on disk, raises MediaNotFoundError.
    - Reconstructs file_path/xml_path from the resolved folder.
    - Auto-deactivates clips whose active anchor points at a missing MIDI.
    - Raises InvalidAnchorError for anchors whose frame/timestamp are out
      of bounds given the stored total_frames/duration.
    """
    filepath = Path(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Expected schema_version={SCHEMA_VERSION}, got {version!r}"
        )

    stored_folder = Path(data["participant_folder"])
    folder = override_folder if override_folder is not None else stored_folder
    folder = Path(folder)
    if not folder.is_dir():
        raise MediaNotFoundError(
            f"Participant folder not found: {folder}",
            missing_path=str(folder),
        )

    midi_files = [
        _dict_to_midi(m, folder) for m in data.get("midi_files", [])
    ]
    midi_names = {m.filename for m in midi_files}

    camera_files = []
    for c in data.get("camera_files", []):
        cam = _dict_to_camera(c, folder, midi_files)
        # Auto-deactivate if the active anchor's midi is dangling.
        active = cam.active_anchor_index
        if (
            active is not None
            and 0 <= active < len(cam.alignment_anchors)
            and cam.alignment_anchors[active].midi_filename not in midi_names
        ):
            _log.warning(
                "Auto-deactivating anchor in clip %s: MIDI %r missing",
                cam.filename,
                cam.alignment_anchors[active].midi_filename,
            )
            cam.active_anchor_index = None
        camera_files.append(cam)

    state = AlignmentState(
        participant_id=data["participant_id"],
        participant_folder=folder,
        global_shift_seconds=data.get("global_shift_seconds", 0.0),
        midi_files=midi_files,
        camera_files=camera_files,
        alignment_notes=data.get("alignment_notes", ""),
    )
    return state


def _dict_to_midi(d: dict, folder: Path) -> MidiFileInfo:
    filename = d["filename"]
    return MidiFileInfo(
        filename=filename,
        file_path=folder / "disklavier" / filename,
        unix_start=d["unix_start"],
        unix_end=d["unix_end"],
        duration=d["duration"],
        sample_rate=d.get("sample_rate", 1920.0),
    )


def _dict_to_camera(
    d: dict, folder: Path, midi_files: list[MidiFileInfo]
) -> CameraFileInfo:
    filename = d["filename"]
    xml_filename = d["xml_filename"]
    total_frames = d["total_frames"]
    duration = d["duration"]
    anchors: list[Anchor] = []
    midi_by_name = {m.filename: m for m in midi_files}
    for a in d.get("alignment_anchors", []):
        frame = a["camera_frame"]
        ts = a["midi_timestamp_seconds"]
        if frame < 0 or frame >= total_frames:
            raise InvalidAnchorError(
                f"Anchor camera_frame {frame} outside [0, {total_frames}) "
                f"in clip {filename}"
            )
        midi = midi_by_name.get(a["midi_filename"])
        if midi is not None:
            if ts < 0 or ts > midi.duration:
                raise InvalidAnchorError(
                    f"Anchor midi_timestamp {ts} outside [0, {midi.duration}] "
                    f"for {a['midi_filename']}"
                )
        anchors.append(Anchor(
            midi_filename=a["midi_filename"],
            midi_timestamp_seconds=ts,
            camera_frame=frame,
            label=a.get("label", ""),
        ))
    active = d.get("active_anchor_index")
    if active is not None and (active < 0 or active >= len(anchors)):
        _log.warning(
            "Clamping invalid active_anchor_index %s to None in %s",
            active,
            filename,
        )
        active = None
    return CameraFileInfo(
        filename=filename,
        file_path=folder / "overhead camera" / filename,
        xml_path=folder / "overhead camera" / xml_filename,
        raw_unix_start=d["raw_unix_start"],
        raw_unix_end=d["raw_unix_end"],
        duration=duration,
        capture_fps=d["capture_fps"],
        total_frames=total_frames,
        alignment_anchors=anchors,
        active_anchor_index=active,
    )
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_persistence.py -v`
Expected: 11 passed (5 prior + 6 new).

- [ ] **Step 5: Commit**

```bash
git add alignment_tool/core/persistence.py tests/test_persistence.py
git commit -m "$(cat <<'EOF'
Add persistence.load_alignment with validation

Enforces schema_version == 2. Accepts override_folder for relocation.
Reconstructs file_path/xml_path from folder. Auto-deactivates anchors
that reference missing MIDI files; raises InvalidAnchorError on frames
or timestamps out of bounds.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase C — IO adapters (Tasks 15–18)

### Task 15: MIDI adapter (`io/midi_adapter.py`)

**Files:**
- Create: `alignment_tool/io/midi_adapter.py`

- [ ] **Step 1: Write the adapter**

Create `alignment_tool/io/midi_adapter.py`:
```python
"""MIDI file reader. Produces MidiFileInfo + note list.

Uses mido for tick/tempo metadata and pretty_midi for duration + note
timing (it resolves tempo changes to wall-clock seconds).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import mido
import pretty_midi

from alignment_tool.core.models import MidiFileInfo

_log = logging.getLogger(__name__)


@dataclass
class MidiNote:
    pitch: int           # 0..127
    start: float         # seconds from file start
    end: float
    velocity: int


class MidiAdapter:
    """Reads one .mid file. Instantiate, query properties, done.

    The file is parsed eagerly in __init__; repeated parsing is prevented
    by the MidiCache higher up the call chain.
    """

    def __init__(self, filepath: Path | str) -> None:
        self._filepath = Path(filepath)
        self._mido = mido.MidiFile(str(self._filepath))
        self._pm = pretty_midi.PrettyMIDI(str(self._filepath))
        self._ticks_per_beat = self._mido.ticks_per_beat
        self._tempo = self._extract_first_tempo(self._mido)
        self._duration = float(self._pm.get_end_time())
        self._unix_end = os.path.getmtime(self._filepath)
        self._unix_start = self._unix_end - self._duration

    @staticmethod
    def _extract_first_tempo(mf: mido.MidiFile) -> int:
        for track in mf.tracks:
            for msg in track:
                if msg.type == "set_tempo":
                    return msg.tempo
        return 500000  # 120 BPM default

    @property
    def filepath(self) -> Path:
        return self._filepath

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def ticks_per_beat(self) -> int:
        return self._ticks_per_beat

    @property
    def tempo(self) -> int:
        return self._tempo

    @property
    def sample_rate(self) -> float:
        """Ticks per second (informational)."""
        return 1_000_000.0 * self._ticks_per_beat / self._tempo

    @property
    def notes(self) -> list[MidiNote]:
        """All notes across all instruments, sorted by start time.

        Fixes audit item 17 — v1 only returned instruments[0].notes.
        """
        out: list[MidiNote] = []
        for inst in self._pm.instruments:
            for n in inst.notes:
                out.append(MidiNote(
                    pitch=int(n.pitch),
                    start=float(n.start),
                    end=float(n.end),
                    velocity=int(n.velocity),
                ))
        out.sort(key=lambda n: n.start)
        return out

    def to_file_info(self) -> MidiFileInfo:
        return MidiFileInfo(
            filename=self._filepath.name,
            file_path=self._filepath,
            unix_start=self._unix_start,
            unix_end=self._unix_end,
            duration=self._duration,
            sample_rate=self.sample_rate,
        )
```

- [ ] **Step 2: Sanity-check import**

Run: `python -c "from alignment_tool.io.midi_adapter import MidiAdapter; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/io/midi_adapter.py
git commit -m "$(cat <<'EOF'
Add MidiAdapter (pretty_midi + mido)

One-shot parse on construction. Exposes duration, ticks_per_beat,
tempo, sample_rate, notes (aggregated across all instruments — fixes
audit item 17), and to_file_info. unix_end from mtime; unix_start
derived as unix_end - duration.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Camera adapter (`io/camera_adapter.py`)

**Files:**
- Create: `alignment_tool/io/camera_adapter.py`

- [ ] **Step 1: Write the adapter**

Create `alignment_tool/io/camera_adapter.py`:
```python
"""Sony FX30 camera clip reader. Probes MP4 metadata via cv2 and parses
the XML sidecar for captureFps / durationFrames.
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2

from alignment_tool.core.models import CameraFileInfo

_log = logging.getLogger(__name__)

_NRT_NS = "{urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20}"


class CameraAdapter:
    """One camera clip = one .MP4 + one M01.XML sidecar.

    Use as a context manager OR call close() explicitly. Avoid relying
    on __del__ because interpreter shutdown ordering is unpredictable
    (audit item 21).
    """

    def __init__(self, xml_path: Path | str, mp4_path: Path | str) -> None:
        self._xml_path = Path(xml_path)
        self._mp4_path = Path(mp4_path)
        self._capture_fps, self._duration_frames = self._parse_xml(
            self._xml_path
        )
        self._cap: cv2.VideoCapture | None = cv2.VideoCapture(
            str(self._mp4_path)
        )
        if not self._cap.isOpened():
            self._cap.release()
            self._cap = None
            raise IOError(f"cannot open video: {self._mp4_path}")
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._unix_end = os.path.getmtime(self._mp4_path)
        self._unix_start = self._unix_end - self.duration

    @staticmethod
    def _parse_xml(xml_path: Path) -> tuple[float, int]:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        dur_el = root.find(f".//{_NRT_NS}Duration")
        vf_el = root.find(f".//{_NRT_NS}VideoFrame")
        if dur_el is None or vf_el is None:
            raise ValueError(
                f"XML missing Duration or VideoFrame: {xml_path}"
            )
        duration_frames = int(dur_el.attrib["value"])
        fps_raw = vf_el.attrib["captureFps"]
        capture_fps = float(fps_raw.rstrip("pi"))
        return capture_fps, duration_frames

    @property
    def duration(self) -> float:
        return self._duration_frames / self._capture_fps

    @property
    def capture_fps(self) -> float:
        return self._capture_fps

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "CameraAdapter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def to_file_info(self) -> CameraFileInfo:
        return CameraFileInfo(
            filename=self._mp4_path.name,
            file_path=self._mp4_path,
            xml_path=self._xml_path,
            raw_unix_start=self._unix_start,
            raw_unix_end=self._unix_end,
            duration=self.duration,
            capture_fps=self._capture_fps,
            total_frames=self._total_frames,
        )
```

- [ ] **Step 2: Sanity-check import**

Run: `python -c "from alignment_tool.io.camera_adapter import CameraAdapter; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/io/camera_adapter.py
git commit -m "$(cat <<'EOF'
Add CameraAdapter (cv2 + XML sidecar)

Parses XML for captureFps + durationFrames, probes MP4 via cv2 for
total_frames/width/height. Context-manager + explicit close (avoids
fragile __del__ — fixes audit item 21). raw_unix_end from mtime;
raw_unix_start derived.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: MIDI cache (`io/midi_cache.py`)

**Files:**
- Create: `alignment_tool/io/midi_cache.py`

- [ ] **Step 1: Write the cache**

Create `alignment_tool/io/midi_cache.py`:
```python
"""Cache of parsed MidiAdapter instances, keyed by absolute file path.

Level2View previously re-parsed the selected MIDI every time the combo
changed. A single MidiCache instance is constructed in app.main() and
passed to Level2View; repeated selections hit the cache.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alignment_tool.io.midi_adapter import MidiAdapter

_log = logging.getLogger(__name__)


class MidiCache:
    def __init__(self) -> None:
        self._store: dict[Path, MidiAdapter] = {}

    def get(self, file_path: Path) -> MidiAdapter:
        key = Path(file_path).resolve()
        if key not in self._store:
            _log.debug("MidiCache miss: %s", key)
            self._store[key] = MidiAdapter(key)
        return self._store[key]

    def clear(self) -> None:
        self._store.clear()
```

- [ ] **Step 2: Sanity-check import**

Run: `python -c "from alignment_tool.io.midi_cache import MidiCache; print(MidiCache())"`
Expected: prints the repr.

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/io/midi_cache.py
git commit -m "$(cat <<'EOF'
Add MidiCache — one parse per file

Keyed by resolved absolute path. Eliminates the v1 behavior of
re-parsing the MIDI file on every combo change in Level2View.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: Participant loader (`io/participant_loader.py`)

**Files:**
- Create: `alignment_tool/io/participant_loader.py`

- [ ] **Step 1: Write the loader**

Create `alignment_tool/io/participant_loader.py`:
```python
"""Scan a participant folder and build an AlignmentState from scratch.

Layout expected:
    <folder>/disklavier/*.mid
    <folder>/overhead camera/*.MP4 + *M01.XML

MP4 extension match is case-insensitive (fixes audit item 24).
"""
from __future__ import annotations

import logging
from pathlib import Path

from alignment_tool.core.models import AlignmentState
from alignment_tool.io.camera_adapter import CameraAdapter
from alignment_tool.io.midi_adapter import MidiAdapter

_log = logging.getLogger(__name__)


def load_participant(folder: Path | str) -> AlignmentState:
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")

    midi_dir = folder / "disklavier"
    cam_dir = folder / "overhead camera"

    midi_files = []
    if midi_dir.is_dir():
        for p in sorted(midi_dir.iterdir()):
            if p.suffix.lower() == ".mid" and p.is_file():
                try:
                    midi_files.append(MidiAdapter(p).to_file_info())
                except Exception as e:
                    _log.warning("Skipping MIDI %s: %s", p.name, e)

    camera_files = []
    if cam_dir.is_dir():
        for p in sorted(cam_dir.iterdir()):
            if p.suffix.lower() == ".mp4" and p.is_file():
                xml_sibling = p.with_name(p.stem + "M01.XML")
                if not xml_sibling.is_file():
                    # Also try the exact case used by Sony (M01.XML) if
                    # the filesystem is case-sensitive despite Windows.
                    xml_sibling = p.with_name(p.stem + "M01.XML")
                    if not xml_sibling.is_file():
                        _log.warning(
                            "Skipping %s — no sidecar XML at %s",
                            p.name,
                            xml_sibling.name,
                        )
                        continue
                try:
                    with CameraAdapter(xml_sibling, p) as ca:
                        camera_files.append(ca.to_file_info())
                except Exception as e:
                    _log.warning("Skipping camera %s: %s", p.name, e)

    return AlignmentState(
        participant_id=folder.name,
        participant_folder=folder,
        midi_files=midi_files,
        camera_files=camera_files,
    )
```

- [ ] **Step 2: Sanity-check import**

Run: `python -c "from alignment_tool.io.participant_loader import load_participant; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Boundary check — nothing in core/ or io/ imports PySide6**

Run (Windows bash):
```bash
grep -r "PySide6" alignment_tool/core alignment_tool/io || echo "CLEAN"
```
Expected: `CLEAN`.

- [ ] **Step 4: Commit**

```bash
git add alignment_tool/io/participant_loader.py
git commit -m "$(cat <<'EOF'
Add load_participant scanner

Walks <folder>/disklavier for .mid (case-insensitive) and
<folder>/overhead camera for .MP4/.mp4 pairs with M01.XML sidecars
(fixes audit item 24). Malformed files are logged and skipped.
Returns an AlignmentState with participant_folder set.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase D — Qt controller and frame worker (Tasks 19–20)

### Task 19: `qt/controller.py` — AlignmentController(QObject)

**Files:**
- Create: `alignment_tool/qt/controller.py`

- [ ] **Step 1: Write the controller**

Create `alignment_tool/qt/controller.py`:
```python
"""Thin Qt shim over AlignmentService + AlignmentSession.

Facade methods call into the service, catch typed exceptions, and emit
fine-grained Qt signals. Widgets subscribe to signals and never mutate
the state directly.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from alignment_tool.core.errors import (
    AlignmentToolError,
)
from alignment_tool.core.models import Anchor, AlignmentState
from alignment_tool.core.service import (
    AlignmentService, AlignmentSession, GlobalShiftResult,
)


class AlignmentController(QObject):
    # State changes --------------------------------------------------
    state_loaded = Signal()
    global_shift_changed = Signal(float)
    anchors_changed = Signal(int)          # camera_idx
    active_anchor_changed = Signal(int)    # camera_idx
    notes_changed = Signal()

    # Session changes ------------------------------------------------
    mode_changed = Signal(str)             # "independent" | "locked"
    active_panel_changed = Signal(str)     # "midi" | "camera"
    marker_changed = Signal()
    selection_changed = Signal()           # current midi/camera indices

    # Errors ---------------------------------------------------------
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = AlignmentService()
        self._session = AlignmentSession()

    # --- accessors ---------------------------------------------------

    @property
    def service(self) -> AlignmentService:
        return self._service

    @property
    def session(self) -> AlignmentSession:
        return self._session

    def has_state(self) -> bool:
        try:
            _ = self._service.state
            return True
        except AlignmentToolError:
            return False

    # --- state lifecycle --------------------------------------------

    def load_state(self, state: AlignmentState) -> None:
        self._service.load_state(state)
        self._session = AlignmentSession()
        self.state_loaded.emit()

    # --- global shift flow ------------------------------------------

    def request_global_shift(self, new_shift: float) -> GlobalShiftResult:
        """Inspect-and-maybe-apply. Returns the result; if
        anchors_to_clear > 0 the caller MUST call confirm_global_shift.
        """
        try:
            result = self._service.set_global_shift(new_shift)
        except AlignmentToolError as e:
            self.error_occurred.emit(str(e))
            return GlobalShiftResult(
                new_shift=new_shift,
                anchors_to_clear=0,
                clips_affected=0,
                pending_token=None,
            )
        if result.anchors_to_clear == 0:
            self.global_shift_changed.emit(result.new_shift)
        return result

    def confirm_global_shift(self, result: GlobalShiftResult) -> None:
        try:
            self._service.confirm_global_shift(result)
        except AlignmentToolError as e:
            self.error_occurred.emit(str(e))
            return
        self.global_shift_changed.emit(result.new_shift)
        for i in range(len(self._service.state.camera_files)):
            self.anchors_changed.emit(i)
            self.active_anchor_changed.emit(i)

    # --- anchor mutations -------------------------------------------

    def add_anchor(self, camera_idx: int, anchor: Anchor) -> None:
        try:
            self._service.add_anchor(camera_idx, anchor)
        except AlignmentToolError as e:
            self.error_occurred.emit(str(e))
            return
        self.anchors_changed.emit(camera_idx)

    def activate_anchor(
        self, camera_idx: int, anchor_idx: int | None
    ) -> None:
        try:
            self._service.activate_anchor(camera_idx, anchor_idx)
        except AlignmentToolError as e:
            self.error_occurred.emit(str(e))
            return
        self.active_anchor_changed.emit(camera_idx)

    def delete_anchor(self, camera_idx: int, anchor_idx: int) -> None:
        try:
            self._service.delete_anchor(camera_idx, anchor_idx)
        except AlignmentToolError as e:
            self.error_occurred.emit(str(e))
            return
        self.anchors_changed.emit(camera_idx)
        self.active_anchor_changed.emit(camera_idx)

    def set_alignment_notes(self, text: str) -> None:
        try:
            self._service.set_alignment_notes(text)
        except AlignmentToolError as e:
            self.error_occurred.emit(str(e))
            return
        self.notes_changed.emit()

    # --- session passthrough ----------------------------------------

    def set_mode(self, mode: str) -> None:
        self._session.set_mode(mode)  # type: ignore[arg-type]
        self.mode_changed.emit(mode)

    def set_active_panel(self, panel: str) -> None:
        self._session.set_active_panel(panel)  # type: ignore[arg-type]
        self.active_panel_changed.emit(panel)

    def set_midi_selection(self, idx: int | None) -> None:
        self._session.set_midi_selection(idx)
        self.selection_changed.emit()

    def set_camera_selection(self, idx: int | None) -> None:
        self._session.set_camera_selection(idx)
        self.selection_changed.emit()

    def set_marker_midi(self, filename: str, seconds: float) -> None:
        self._session.set_marker_midi(filename, seconds)
        self.marker_changed.emit()

    def set_marker_camera(self, frame: int) -> None:
        self._session.set_marker_camera(frame)
        self.marker_changed.emit()

    def clear_markers(self) -> None:
        self._session.clear_markers()
        self.marker_changed.emit()
```

- [ ] **Step 2: Import sanity check**

Run: `python -c "from alignment_tool.qt.controller import AlignmentController; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/controller.py
git commit -m "$(cat <<'EOF'
Add AlignmentController (Qt shim over service/session)

Facade methods catch AlignmentToolError and emit error_occurred.
Fine-grained change signals let widgets subscribe narrowly.
request_global_shift returns the GlobalShiftResult for caller-owned
confirmation dialogs.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Frame worker (`qt/workers/frame_worker.py`)

**Files:**
- Create: `alignment_tool/qt/workers/frame_worker.py`

- [ ] **Step 1: Write the worker**

Create `alignment_tool/qt/workers/frame_worker.py`:
```python
"""Background frame decoder. Lives on a QThread; all invocation is via
queued signals (fixes audit item 1).
"""
from __future__ import annotations

import logging
from collections import OrderedDict

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImage

_log = logging.getLogger(__name__)
_CACHE_SIZE = 32


class FrameWorker(QObject):
    frame_ready = Signal(int, object)  # (frame_index, QImage)

    def __init__(self) -> None:
        super().__init__()
        self._capture: cv2.VideoCapture | None = None
        self._cache: OrderedDict[int, QImage] = OrderedDict()

    @Slot(str)
    def open_video(self, path: str) -> None:
        self.close_video()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            _log.warning("FrameWorker cannot open: %s", path)
            cap.release()
            return
        self._capture = cap
        self._cache.clear()

    @Slot()
    def close_video(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._cache.clear()

    @Slot(int)
    def request_frame(self, frame: int) -> None:
        if self._capture is None:
            return
        cached = self._cache.get(frame)
        if cached is not None:
            self._cache.move_to_end(frame)
            self.frame_ready.emit(frame, cached)
            return
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, bgr = self._capture.read()
        if not ok or bgr is None:
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        # Copy so the ndarray buffer outliving the QImage is irrelevant.
        buf = np.ascontiguousarray(rgb).tobytes()
        img = QImage(buf, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self._cache[frame] = img
        if len(self._cache) > _CACHE_SIZE:
            self._cache.popitem(last=False)
        self.frame_ready.emit(frame, img)
```

- [ ] **Step 2: Sanity-check import**

Run: `python -c "from alignment_tool.qt.workers.frame_worker import FrameWorker; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/workers/frame_worker.py
git commit -m "$(cat <<'EOF'
Add FrameWorker for background frame decoding

@Slot-decorated methods are invoked via queued signal connections from
CameraPanelWidget (built in the next task). 32-entry LRU cache of
QImages. Buffer-lifetime safety: tobytes() copy plus QImage.copy()
before emit.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase E — Widgets (Tasks 21–31)

> **Implementation note on widgets.** All tasks in this phase use PySide6 scoped enums (`Qt.ShortcutContext.WidgetWithChildrenShortcut`, `Qt.AlignmentFlag.AlignCenter`, `QImage.Format.Format_RGB888`). Use `Signal`/`Slot` (not `pyqtSignal`/`pyqtSlot`). `QKeySequence("Shift+Left")` instead of `Qt.SHIFT + Qt.Key_Left`.

### Task 21: Midi panel (`qt/level2/midi_panel.py`)

**Files:**
- Create: `alignment_tool/qt/level2/midi_panel.py`

Scope: falling-keys piano-roll view with playhead at 75% canvas height, 88-key piano at bottom, mouse drag to scrub, mouse wheel to zoom vertical time range, info label below showing current time/duration/tick.

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level2/midi_panel.py`:
```python
"""Falling-keys MIDI display with scrubbing + zoom."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from alignment_tool.io.midi_adapter import MidiAdapter, MidiNote

_PIANO_KEYS = 88
_LOWEST_PITCH = 21   # A0
_HIGHEST_PITCH = 108  # C8
_PIANO_HEIGHT_FRAC = 0.18
_PLAYHEAD_FRAC = 0.75


@dataclass
class _Viewport:
    seconds: float = 10.0
    min_seconds: float = 0.5
    max_seconds: float = 60.0


class MidiCanvasWidget(QWidget):
    position_changed = Signal(float)  # seconds from midi start
    focus_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self._adapter: MidiAdapter | None = None
        self._notes: list[MidiNote] = []
        self._position: float = 0.0
        self._vp = _Viewport()
        self._drag_last_y: int | None = None

    def load_midi(self, adapter: MidiAdapter) -> None:
        self._adapter = adapter
        self._notes = adapter.notes
        self._position = 0.0
        self.update()

    def unload(self) -> None:
        self._adapter = None
        self._notes = []
        self.update()

    @property
    def current_time(self) -> float:
        return self._position

    def set_position(self, seconds: float) -> None:
        if self._adapter is None:
            return
        seconds = max(0.0, min(seconds, self._adapter.duration))
        if seconds == self._position:
            return
        self._position = seconds
        self.update()
        self.position_changed.emit(seconds)

    def step_ticks(self, ticks: int) -> None:
        if self._adapter is None:
            return
        secs = ticks / self._adapter.sample_rate
        self.set_position(self._position + secs)

    # --- painting ---------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w = self.width()
        h = self.height()
        piano_h = int(h * _PIANO_HEIGHT_FRAC)
        roll_h = h - piano_h
        # background
        p.fillRect(0, 0, w, h, QColor(20, 20, 28))
        if self._adapter is None:
            p.setPen(QColor(120, 120, 120))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No MIDI loaded",
            )
            return
        # time window: position at 75% of roll; notes fall from top.
        playhead_y = int(roll_h * _PLAYHEAD_FRAC)
        t_lookahead = self._vp.seconds * _PLAYHEAD_FRAC
        t_lookback = self._vp.seconds * (1 - _PLAYHEAD_FRAC)
        t_min = self._position - t_lookahead
        t_max = self._position + t_lookback
        pitch_px = w / _PIANO_KEYS
        for n in self._notes:
            if n.end < t_min or n.start > t_max:
                continue
            pitch_idx = n.pitch - _LOWEST_PITCH
            if pitch_idx < 0 or pitch_idx >= _PIANO_KEYS:
                continue
            x = int(pitch_idx * pitch_px)
            y_top = int(
                (n.start - t_min) / (t_max - t_min) * roll_h
            )
            y_bot = int(
                (n.end - t_min) / (t_max - t_min) * roll_h
            )
            # Note rect: y_top is higher in world time, which should be higher in window.
            # We want later notes at top, so invert.
            # World: small time = top; large time = bottom. Playhead at 75%.
            # Flip: later notes appear lower as position advances.
            # Simpler: draw time increasing downward from t_min→t_max.
            velocity_alpha = max(60, min(255, int(n.velocity * 2)))
            color = QColor(90, 200, 255, velocity_alpha)
            p.fillRect(
                int(x + 1), min(y_top, y_bot),
                max(1, int(pitch_px - 2)), max(1, abs(y_bot - y_top)),
                color,
            )
        # playhead
        p.setPen(QPen(QColor(255, 80, 80), 2))
        p.drawLine(0, playhead_y, w, playhead_y)
        # piano (simple)
        p.fillRect(0, roll_h, w, piano_h, QColor(40, 40, 48))
        p.setPen(QColor(70, 70, 70))
        for i in range(_PIANO_KEYS + 1):
            x = int(i * pitch_px)
            p.drawLine(x, roll_h, x, h)

    # --- interaction ------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_last_y = int(event.position().y())
            self.focus_requested.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_last_y is None or self._adapter is None:
            return
        y = int(event.position().y())
        dy = y - self._drag_last_y
        self._drag_last_y = y
        # Dragging down scrolls forward in time.
        seconds_per_pixel = self._vp.seconds / max(1, self.height())
        self.set_position(self._position + dy * seconds_per_pixel)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._drag_last_y = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        angle = event.angleDelta().y()
        factor = 0.8 if angle > 0 else 1.25
        new = max(self._vp.min_seconds, min(self._vp.max_seconds, self._vp.seconds * factor))
        self._vp.seconds = new
        self.update()


class MidiPanelWidget(QWidget):
    position_changed = Signal(float)
    focus_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = MidiCanvasWidget(self)
        self._info = QLabel("No MIDI loaded", self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._info)
        self._canvas.position_changed.connect(self._on_position)
        self._canvas.focus_requested.connect(self.focus_requested.emit)
        self._oor = False

    def load_midi(self, adapter: MidiAdapter) -> None:
        self._canvas.load_midi(adapter)
        self._oor = False
        self._update_info()

    def unload(self) -> None:
        self._canvas.unload()
        self._info.setText("No MIDI loaded")

    def set_position(self, seconds: float) -> None:
        self._canvas.set_position(seconds)

    def step_ticks(self, ticks: int) -> None:
        self._canvas.step_ticks(ticks)

    def show_out_of_range(self, message: str) -> None:
        self._oor = True
        self._canvas.hide()
        self._info.setText(message)

    def show_normal(self) -> None:
        if self._oor:
            self._oor = False
            self._canvas.show()
            self._update_info()

    @property
    def current_time(self) -> float:
        return self._canvas.current_time

    def _on_position(self, seconds: float) -> None:
        self._update_info()
        self.position_changed.emit(seconds)

    def _update_info(self) -> None:
        adapter = self._canvas._adapter
        if adapter is None:
            self._info.setText("No MIDI loaded")
            return
        t = self._canvas.current_time
        ticks = int(t * adapter.sample_rate)
        self._info.setText(
            f"Time: {t:.3f} s / {adapter.duration:.1f} | Tick: {ticks}"
        )
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level2.midi_panel import MidiPanelWidget; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level2/midi_panel.py
git commit -m "$(cat <<'EOF'
Add MidiPanelWidget (falling-keys canvas + info label)

Drag-to-scrub, wheel-to-zoom vertical time range, playhead at 75%.
focus_requested emitted on mouse press so Level2View can set active
panel (fixes audit item 22). Supports out-of-range overlay for locked
mode.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 22: Camera panel (`qt/level2/camera_panel.py`) — proper threading

**Files:**
- Create: `alignment_tool/qt/level2/camera_panel.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level2/camera_panel.py`:
```python
"""Camera frame viewer. Decodes off the GUI thread via queued signals
to FrameWorker (fixes audit items 1 and 2).
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from alignment_tool.qt.workers.frame_worker import FrameWorker

_log = logging.getLogger(__name__)


class CameraPanelWidget(QWidget):
    position_changed = Signal(int)
    focus_requested = Signal()

    # Emitted to the worker via queued connections.
    _frame_requested = Signal(int)
    _video_open_requested = Signal(str)
    _video_close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(320, 180)
        self._image_label.setStyleSheet("background: #111;")
        self._counter = QLabel("Frame: 0 / 0 | Time: 0.000 s", self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._image_label, 1)
        layout.addWidget(self._counter)

        self._total_frames = 0
        self._capture_fps = 0.0
        self._current_frame = -1
        self._oor = False

        self._worker = FrameWorker()
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._frame_requested.connect(self._worker.request_frame)
        self._video_open_requested.connect(self._worker.open_video)
        self._video_close_requested.connect(self._worker.close_video)
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._thread.start()

    def load_video(
        self, mp4_path: str, total_frames: int, capture_fps: float
    ) -> None:
        self._total_frames = total_frames
        self._capture_fps = capture_fps
        self._current_frame = 0
        self._video_open_requested.emit(mp4_path)
        self._frame_requested.emit(0)
        self._update_counter()

    def unload(self) -> None:
        self._video_close_requested.emit()
        self._total_frames = 0
        self._capture_fps = 0.0
        self._current_frame = -1
        self._image_label.clear()
        self._update_counter()

    def set_frame(self, frame: int) -> None:
        if self._total_frames == 0:
            return
        frame = max(0, min(frame, self._total_frames - 1))
        if frame == self._current_frame:
            return
        self._current_frame = frame
        self._update_counter()
        self._frame_requested.emit(frame)
        self.position_changed.emit(frame)

    def step(self, frames: int) -> None:
        self.set_frame(self._current_frame + frames)

    def show_out_of_range(self, message: str) -> None:
        self._oor = True
        self._image_label.setText(message)
        self._image_label.setStyleSheet("background: #333; color: white;")

    def show_normal(self) -> None:
        if self._oor:
            self._oor = False
            self._image_label.setStyleSheet("background: #111;")
            if self._current_frame >= 0:
                self._frame_requested.emit(self._current_frame)

    @property
    def current_frame(self) -> int:
        return self._current_frame

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.focus_requested.emit()
        super().mousePressEvent(event)

    def cleanup(self) -> None:
        """Must be called before destruction (MainWindow.closeEvent)."""
        self._video_close_requested.emit()
        self._thread.quit()
        self._thread.wait(2000)

    def _on_frame_ready(self, frame: int, image: QImage) -> None:
        if frame != self._current_frame or self._oor:
            return
        pix = QPixmap.fromImage(image).scaled(
            self._image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(pix)

    def _update_counter(self) -> None:
        t = (
            self._current_frame / self._capture_fps
            if self._capture_fps > 0
            else 0.0
        )
        self._counter.setText(
            f"Frame: {max(0, self._current_frame)} / {self._total_frames} | "
            f"Time: {t:.3f} s"
        )
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level2.camera_panel import CameraPanelWidget; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level2/camera_panel.py
git commit -m "$(cat <<'EOF'
Add CameraPanelWidget with queued FrameWorker dispatch

All calls to FrameWorker go via _frame_requested /
_video_open_requested / _video_close_requested signals, which Qt
routes across threads with queued connections. cleanup() quits and
waits the worker thread (fixes audit items 1 and 2).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 23: Anchor table (`qt/level2/anchor_table.py`)

**Files:**
- Create: `alignment_tool/qt/level2/anchor_table.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level2/anchor_table.py`:
```python
"""Anchor list for the currently-selected camera clip.

Shows #, MIDI File, MIDI Time, Camera Frame, Derived Shift, Label, Active.
Clicking the Active cell toggles activation. Delete button removes the
selected row. Talks to AlignmentController; never mutates state directly.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from alignment_tool.core import engine
from alignment_tool.core.models import CameraFileInfo
from alignment_tool.qt.controller import AlignmentController

_COLS = [
    "#", "MIDI File", "MIDI Time (s)", "Camera Frame",
    "Derived Shift (s)", "Label", "Active",
]


class AnchorTableWidget(QWidget):
    def __init__(
        self,
        controller: AlignmentController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._camera_idx: int | None = None

        self._table = QTableWidget(self)
        self._table.setColumnCount(len(_COLS))
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setMaximumHeight(200)
        self._table.cellClicked.connect(self._on_cell_clicked)

        self._delete_btn = QPushButton("Delete Selected", self)
        self._delete_btn.clicked.connect(self._on_delete)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._table)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self._delete_btn)
        layout.addLayout(btn_row)

        controller.anchors_changed.connect(self._on_anchors_changed)
        controller.active_anchor_changed.connect(self._on_anchors_changed)
        controller.global_shift_changed.connect(self._refresh_if_loaded)

    def set_camera(self, camera_idx: int | None) -> None:
        self._camera_idx = camera_idx
        self._refresh_if_loaded(0.0)

    def _on_anchors_changed(self, camera_idx: int) -> None:
        if camera_idx == self._camera_idx:
            self._refresh_if_loaded(0.0)

    def _refresh_if_loaded(self, _unused: float) -> None:
        self._table.setRowCount(0)
        if self._camera_idx is None or not self._controller.has_state():
            return
        state = self._controller.service.state
        if self._camera_idx >= len(state.camera_files):
            return
        camera = state.camera_files[self._camera_idx]
        self._populate(camera)

    def _populate(self, camera: CameraFileInfo) -> None:
        self._table.setRowCount(len(camera.alignment_anchors))
        gs = self._controller.service.state.global_shift_seconds
        for row, a in enumerate(camera.alignment_anchors):
            self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self._table.setItem(row, 1, QTableWidgetItem(a.midi_filename))
            self._table.setItem(
                row, 2, QTableWidgetItem(f"{a.midi_timestamp_seconds:.3f}"),
            )
            self._table.setItem(row, 3, QTableWidgetItem(str(a.camera_frame)))
            # Derived shift (N/A if midi missing).
            state = self._controller.service.state
            match = self._controller.service.midi_by_filename(a.midi_filename)
            if match is None:
                shift_str = "N/A"
            else:
                _, midi = match
                shift = engine.compute_anchor_shift(a, camera, midi, gs)
                shift_str = f"{shift:.4f}"
            self._table.setItem(row, 4, QTableWidgetItem(shift_str))
            self._table.setItem(row, 5, QTableWidgetItem(a.label))
            active_item = QTableWidgetItem(
                "*" if camera.active_anchor_index == row else ""
            )
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if camera.active_anchor_index == row:
                active_item.setBackground(QBrush(QColor(40, 120, 40)))
            self._table.setItem(row, 6, active_item)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if self._camera_idx is None:
            return
        if col == 6:
            # Toggle activation.
            state = self._controller.service.state
            camera = state.camera_files[self._camera_idx]
            if camera.active_anchor_index == row:
                self._controller.activate_anchor(self._camera_idx, None)
            else:
                self._controller.activate_anchor(self._camera_idx, row)

    def _on_delete(self) -> None:
        if self._camera_idx is None:
            return
        row = self._table.currentRow()
        if row < 0:
            return
        self._controller.delete_anchor(self._camera_idx, row)
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level2.anchor_table import AnchorTableWidget; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level2/anchor_table.py
git commit -m "$(cat <<'EOF'
Add AnchorTableWidget

Seven-column anchor table with * on dark-green background for the
active row. Click Active cell to toggle; Delete button removes selected
row. All mutations flow through AlignmentController — no direct state
writes.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 24: Overlap indicator (`qt/level2/overlap_indicator.py`)

**Files:**
- Create: `alignment_tool/qt/level2/overlap_indicator.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level2/overlap_indicator.py`:
```python
"""Dual-track navigation bar showing aligned MIDI + camera extents."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from alignment_tool.core.models import CameraFileInfo, MidiFileInfo

_TRACK_HEIGHT = 30


class OverlapIndicatorWidget(QWidget):
    midi_time_clicked = Signal(float)     # seconds from midi start
    camera_frame_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_TRACK_HEIGHT)
        self._midi: MidiFileInfo | None = None
        self._camera: CameraFileInfo | None = None
        self._eff_shift: float = 0.0
        self._midi_playhead_unix: float | None = None
        self._camera_playhead_unix: float | None = None

    def set_clips(
        self,
        midi: MidiFileInfo | None,
        camera: CameraFileInfo | None,
    ) -> None:
        self._midi = midi
        self._camera = camera
        self.update()

    def set_effective_shift(self, shift: float) -> None:
        self._eff_shift = shift
        self.update()

    def set_midi_playhead(self, unix: float | None) -> None:
        self._midi_playhead_unix = unix
        self.update()

    def set_camera_playhead(self, unix: float | None) -> None:
        self._camera_playhead_unix = unix
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(25, 25, 32))
        if self._midi is None or self._camera is None:
            return
        t_min, t_max = self._time_range()
        if t_max - t_min <= 0:
            return
        mid_y = self.height() // 2
        # MIDI extent (blue, top half).
        x1 = self._t_to_x(self._midi.unix_start, t_min, t_max)
        x2 = self._t_to_x(self._midi.unix_end, t_min, t_max)
        p.fillRect(x1, 0, max(1, x2 - x1), mid_y, QColor(31, 119, 180))
        # Camera extent (orange, bottom half).
        cam_start = self._camera.raw_unix_start + self._eff_shift
        cam_end = self._camera.raw_unix_end + self._eff_shift
        x1c = self._t_to_x(cam_start, t_min, t_max)
        x2c = self._t_to_x(cam_end, t_min, t_max)
        p.fillRect(x1c, mid_y, max(1, x2c - x1c), mid_y, QColor(255, 127, 14))
        # Overlap (green).
        ov_start = max(self._midi.unix_start, cam_start)
        ov_end = min(self._midi.unix_end, cam_end)
        if ov_end > ov_start:
            xo1 = self._t_to_x(ov_start, t_min, t_max)
            xo2 = self._t_to_x(ov_end, t_min, t_max)
            p.fillRect(
                xo1, 0, max(1, xo2 - xo1), self.height(),
                QColor(60, 160, 90, 120),
            )
        # Playheads.
        pen = QPen(QColor(255, 255, 255), 1)
        p.setPen(pen)
        if self._midi_playhead_unix is not None:
            xm = self._t_to_x(self._midi_playhead_unix, t_min, t_max)
            p.drawLine(xm, 0, xm, mid_y)
        if self._camera_playhead_unix is not None:
            xc = self._t_to_x(self._camera_playhead_unix, t_min, t_max)
            p.drawLine(xc, mid_y, xc, self.height())

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._emit_clicked(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._emit_clicked(event)

    def _emit_clicked(self, event: QMouseEvent) -> None:
        if self._midi is None or self._camera is None:
            return
        y = int(event.position().y())
        x = int(event.position().x())
        t_min, t_max = self._time_range()
        t = t_min + (x / max(1, self.width())) * (t_max - t_min)
        mid_y = self.height() // 2
        if y < mid_y:
            seconds = t - self._midi.unix_start
            seconds = max(0.0, min(seconds, self._midi.duration))
            self.midi_time_clicked.emit(seconds)
        else:
            cam_unix = t - self._eff_shift
            frame = round(
                (cam_unix - self._camera.raw_unix_start)
                * self._camera.capture_fps
            )
            frame = max(0, min(frame, self._camera.total_frames - 1))
            self.camera_frame_clicked.emit(frame)

    def _time_range(self) -> tuple[float, float]:
        assert self._midi is not None and self._camera is not None
        cam_start = self._camera.raw_unix_start + self._eff_shift
        cam_end = self._camera.raw_unix_end + self._eff_shift
        t_min = min(self._midi.unix_start, cam_start)
        t_max = max(self._midi.unix_end, cam_end)
        # pad 2% on each side
        pad = (t_max - t_min) * 0.02
        return t_min - pad, t_max + pad

    def _t_to_x(self, t: float, t_min: float, t_max: float) -> int:
        return int((t - t_min) / (t_max - t_min) * self.width())
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level2.overlap_indicator import OverlapIndicatorWidget; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level2/overlap_indicator.py
git commit -m "$(cat <<'EOF'
Add OverlapIndicatorWidget

Blue MIDI extent top-half, orange camera extent (shifted by effective
shift) bottom-half, green overlap overlay, two white playheads. Click
top half emits midi_time_clicked (seconds), bottom half emits
camera_frame_clicked.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 25: Marker bar (`qt/level2/marker_bar.py`)

**Files:**
- Create: `alignment_tool/qt/level2/marker_bar.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level2/marker_bar.py`:
```python
"""Marker labels + Compute Shift + Add Anchor buttons."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QWidget,
)


class MarkerBar(QWidget):
    compute_shift_clicked = Signal()
    add_anchor_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._midi_label = QLabel("MIDI mark: (none)", self)
        self._camera_label = QLabel("Camera mark: (none)", self)
        self._compute_btn = QPushButton("Compute Global Shift", self)
        self._add_btn = QPushButton("Add Anchor (A)", self)
        self._compute_btn.setEnabled(False)
        self._add_btn.setEnabled(False)
        tip = "Set markers first: press M on MIDI panel, C on camera panel"
        self._compute_btn.setToolTip(tip)
        self._add_btn.setToolTip(tip)
        self._compute_btn.clicked.connect(self.compute_shift_clicked.emit)
        self._add_btn.clicked.connect(self.add_anchor_clicked.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._midi_label)
        layout.addWidget(self._camera_label)
        layout.addStretch(1)
        layout.addWidget(self._compute_btn)
        layout.addWidget(self._add_btn)

    def set_midi_marker(
        self, midi_filename: str | None, seconds: float | None
    ) -> None:
        if midi_filename is None:
            self._midi_label.setText("MIDI mark: (none)")
        else:
            self._midi_label.setText(
                f"MIDI mark: {midi_filename} @ {seconds:.3f}s"
            )
            self._flash(self._midi_label)

    def set_camera_marker(self, frame: int | None) -> None:
        if frame is None:
            self._camera_label.setText("Camera mark: (none)")
        else:
            self._camera_label.setText(f"Camera mark: frame {frame}")
            self._flash(self._camera_label)

    def set_buttons_enabled(self, enabled: bool) -> None:
        self._compute_btn.setEnabled(enabled)
        self._add_btn.setEnabled(enabled)
        self._compute_btn.setToolTip(
            "" if enabled else
            "Set markers first: press M on MIDI panel, C on camera panel"
        )
        self._add_btn.setToolTip(
            "" if enabled else
            "Set markers first: press M on MIDI panel, C on camera panel"
        )

    def _flash(self, label: QLabel) -> None:
        original = label.styleSheet()
        label.setStyleSheet("background: #446;")
        QTimer.singleShot(400, lambda: label.setStyleSheet(original))
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level2.marker_bar import MarkerBar; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level2/marker_bar.py
git commit -m "$(cat <<'EOF'
Add MarkerBar (marker labels + buttons)

Shows MIDI and camera marker values, flashes #446 background for
400ms when updated. Emits compute_shift_clicked and add_anchor_clicked
so Level2View can handle them. Buttons disabled until markers ready.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 26: Shortcut router (`qt/level2/shortcut_router.py`)

**Files:**
- Create: `alignment_tool/qt/level2/shortcut_router.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level2/shortcut_router.py`:
```python
"""Level 2 keyboard shortcuts routed through QShortcut."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


class ShortcutRouter:
    """Owns QShortcut objects and wires keys to callables."""

    def __init__(self, host: QWidget) -> None:
        self._host = host
        self._shortcuts: list[QShortcut] = []

    def bind(self, key: str, callback: Callable[[], None]) -> None:
        sc = QShortcut(QKeySequence(key), self._host)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(callback)
        self._shortcuts.append(sc)

    def clear(self) -> None:
        for sc in self._shortcuts:
            sc.setParent(None)
        self._shortcuts.clear()
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level2.shortcut_router import ShortcutRouter; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level2/shortcut_router.py
git commit -m "$(cat <<'EOF'
Add ShortcutRouter

Thin wrapper around QShortcut with WidgetWithChildrenShortcut context.
Level2View.bind_shortcuts() will call router.bind(key, callback) for
each shortcut; keeps key-handling out of the view layout code.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 27: Level 2 composite view (`qt/level2/view.py`)

**Files:**
- Create: `alignment_tool/qt/level2/view.py`

Scope: compose all Level-2 subwidgets, wire them to the controller, enforce anchor-lock rule on the MIDI combo, handle locked-mode synchronization between MIDI and camera panels, wire shortcuts.

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level2/view.py`:
```python
"""Level 2 detail view. Thin composition over subwidgets and controller."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from alignment_tool.core import engine
from alignment_tool.core.models import Anchor
from alignment_tool.io.midi_cache import MidiCache
from alignment_tool.qt.controller import AlignmentController
from alignment_tool.qt.level2.anchor_table import AnchorTableWidget
from alignment_tool.qt.level2.camera_panel import CameraPanelWidget
from alignment_tool.qt.level2.marker_bar import MarkerBar
from alignment_tool.qt.level2.midi_panel import MidiPanelWidget
from alignment_tool.qt.level2.overlap_indicator import OverlapIndicatorWidget
from alignment_tool.qt.level2.shortcut_router import ShortcutRouter

_log = logging.getLogger(__name__)
_HINT = (
    "{mode} Mode | Active: {panel} (Tab to switch) | Arrows: navigate | "
    "L: toggle mode | M: mark MIDI | C: mark camera | A: add anchor | "
    "O: jump to overlap"
)


class Level2View(QWidget):
    back_requested = Signal()

    def __init__(
        self,
        controller: AlignmentController,
        midi_cache: MidiCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._midi_cache = midi_cache

        # Top bar.
        self._back_btn = QPushButton("< Back", self)
        self._midi_combo = QComboBox(self)
        self._camera_combo = QComboBox(self)
        self._mode_btn = QPushButton("Mode: Independent", self)
        self._mode_btn.setCheckable(True)
        top = QHBoxLayout()
        top.addWidget(self._back_btn)
        top.addWidget(QLabel("MIDI:", self))
        top.addWidget(self._midi_combo, 1)
        top.addWidget(QLabel("Camera:", self))
        top.addWidget(self._camera_combo, 1)
        top.addWidget(self._mode_btn)

        # Hint line.
        self._hint_line = QLabel("", self)
        self._hint_line.setStyleSheet("color: #888;")

        # Overlap.
        self._overlap = OverlapIndicatorWidget(self)

        # Panels.
        self._midi_panel = MidiPanelWidget(self)
        self._camera_panel = CameraPanelWidget(self)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._midi_panel)
        splitter.addWidget(self._camera_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        self._marker_bar = MarkerBar(self)
        self._anchor_table = AnchorTableWidget(controller, self)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._hint_line)
        layout.addWidget(self._overlap)
        layout.addWidget(splitter, 1)
        layout.addWidget(self._marker_bar)
        layout.addWidget(self._anchor_table)

        self._router = ShortcutRouter(self)
        self._wire_signals()
        self._bind_shortcuts()

    # --- lifecycle ---------------------------------------------------

    def populate_from_state(self) -> None:
        """Called after state is loaded or changed."""
        self._midi_combo.blockSignals(True)
        self._camera_combo.blockSignals(True)
        self._midi_combo.clear()
        self._camera_combo.clear()
        if not self._controller.has_state():
            self._midi_combo.blockSignals(False)
            self._camera_combo.blockSignals(False)
            return
        state = self._controller.service.state
        for m in state.midi_files:
            self._midi_combo.addItem(m.filename)
        for c in state.camera_files:
            self._camera_combo.addItem(c.filename)
        self._midi_combo.blockSignals(False)
        self._camera_combo.blockSignals(False)

    def open_pair(self, midi_idx: int, camera_idx: int) -> None:
        self._controller.set_midi_selection(midi_idx)
        self._controller.set_camera_selection(camera_idx)
        self._midi_combo.setCurrentIndex(midi_idx)
        self._camera_combo.setCurrentIndex(camera_idx)
        self._load_midi(midi_idx)
        self._load_camera(camera_idx)
        self._anchor_table.set_camera(camera_idx)
        self._update_overlap()
        self._update_hint()

    def cleanup(self) -> None:
        self._camera_panel.cleanup()
        self._midi_panel.unload()

    # --- wiring ------------------------------------------------------

    def _wire_signals(self) -> None:
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._mode_btn.toggled.connect(self._on_mode_toggled)
        self._midi_combo.currentIndexChanged.connect(self._on_midi_selected)
        self._camera_combo.currentIndexChanged.connect(
            self._on_camera_selected
        )
        self._midi_panel.position_changed.connect(
            self._on_midi_position_changed
        )
        self._camera_panel.position_changed.connect(
            self._on_camera_position_changed
        )
        self._midi_panel.focus_requested.connect(
            lambda: self._controller.set_active_panel("midi")
        )
        self._camera_panel.focus_requested.connect(
            lambda: self._controller.set_active_panel("camera")
        )
        self._overlap.midi_time_clicked.connect(self._midi_panel.set_position)
        self._overlap.camera_frame_clicked.connect(
            self._camera_panel.set_frame
        )
        self._marker_bar.compute_shift_clicked.connect(self._on_compute_shift)
        self._marker_bar.add_anchor_clicked.connect(self._on_add_anchor)
        self._controller.active_anchor_changed.connect(
            lambda _: self._apply_anchor_lock_rule()
        )
        self._controller.global_shift_changed.connect(
            lambda _: self._update_overlap()
        )
        self._controller.marker_changed.connect(self._on_markers_changed)
        self._controller.active_panel_changed.connect(
            lambda _: self._update_hint()
        )

    def _bind_shortcuts(self) -> None:
        self._router.bind("M", self._mark_midi)
        self._router.bind("C", self._mark_camera)
        self._router.bind("L", lambda: self._mode_btn.toggle())
        self._router.bind("A", self._on_add_anchor)
        self._router.bind("O", self._jump_to_overlap)
        self._router.bind("Tab", self._toggle_active_panel)
        self._router.bind("Right", lambda: self._step_active(+1, False))
        self._router.bind("Left", lambda: self._step_active(-1, False))
        self._router.bind("Shift+Right", lambda: self._step_active(+1, True))
        self._router.bind("Shift+Left", lambda: self._step_active(-1, True))
        self._router.bind("Escape", self.back_requested.emit)

    # --- handlers ----------------------------------------------------

    def _on_midi_selected(self, idx: int) -> None:
        self._controller.set_midi_selection(idx)
        self._load_midi(idx)
        self._update_overlap()

    def _on_camera_selected(self, idx: int) -> None:
        self._controller.set_camera_selection(idx)
        self._load_camera(idx)
        self._anchor_table.set_camera(idx)
        self._update_overlap()
        self._apply_anchor_lock_rule()

    def _on_mode_toggled(self, checked: bool) -> None:
        mode = "locked" if checked else "independent"
        self._mode_btn.setText(
            "Mode: Locked" if checked else "Mode: Independent"
        )
        self._controller.set_mode(mode)
        self._apply_anchor_lock_rule()
        self._update_hint()
        if not checked:
            self._midi_panel.show_normal()
            self._camera_panel.show_normal()

    def _on_midi_position_changed(self, seconds: float) -> None:
        state = self._controller.service.state if self._controller.has_state() else None
        if state is None:
            return
        midi_idx = self._controller.session.current_midi_index
        cam_idx = self._controller.session.current_camera_index
        if midi_idx is None or cam_idx is None:
            return
        midi = state.midi_files[midi_idx]
        self._overlap.set_midi_playhead(midi.unix_start + seconds)
        if self._controller.session.mode != "locked":
            return
        camera = state.camera_files[cam_idx]
        eff = engine.get_effective_shift_for_camera(state, camera)
        frame = engine.midi_unix_to_camera_frame(
            midi.unix_start + seconds, eff, camera,
        )
        if frame is None:
            cam_unix = (midi.unix_start + seconds) - eff
            approx_frame = round(
                (cam_unix - camera.raw_unix_start) * camera.capture_fps
            )
            delta = engine.out_of_range_delta(approx_frame, camera)
            if delta is not None and delta > 0:
                msg = f"Camera clip starts in {delta:.2f} s"
            elif delta is not None:
                msg = f"Camera clip ended {-delta:.2f} s ago"
            else:
                msg = "Camera out of range"
            self._camera_panel.show_out_of_range(msg)
        else:
            self._camera_panel.show_normal()
            self._camera_panel.set_frame(frame)

    def _on_camera_position_changed(self, frame: int) -> None:
        state = self._controller.service.state if self._controller.has_state() else None
        if state is None:
            return
        midi_idx = self._controller.session.current_midi_index
        cam_idx = self._controller.session.current_camera_index
        if midi_idx is None or cam_idx is None:
            return
        camera = state.camera_files[cam_idx]
        self._overlap.set_camera_playhead(
            camera.raw_unix_start + frame / camera.capture_fps
        )
        if self._controller.session.mode != "locked":
            return
        midi = state.midi_files[midi_idx]
        eff = engine.get_effective_shift_for_camera(state, camera)
        midi_seconds = engine.camera_frame_to_midi_seconds(
            frame, eff, camera, midi,
        )
        if midi_seconds is None:
            self._midi_panel.show_out_of_range("MIDI out of range")
        else:
            self._midi_panel.show_normal()
            self._midi_panel.set_position(midi_seconds)

    def _on_markers_changed(self) -> None:
        session = self._controller.session
        if session.midi_marker is None:
            self._marker_bar.set_midi_marker(None, None)
        else:
            self._marker_bar.set_midi_marker(*session.midi_marker)
        if session.camera_marker is None:
            self._marker_bar.set_camera_marker(None)
        else:
            self._marker_bar.set_camera_marker(session.camera_marker)
        self._marker_bar.set_buttons_enabled(session.markers_ready())

    def _on_compute_shift(self) -> None:
        state = self._controller.service.state if self._controller.has_state() else None
        if state is None or not self._controller.session.markers_ready():
            return
        mfn, secs = self._controller.session.midi_marker  # type: ignore[misc]
        frame = self._controller.session.camera_marker  # type: ignore[assignment]
        mm = self._controller.service.midi_by_filename(mfn)
        if mm is None:
            return
        _, midi = mm
        cam_idx = self._controller.session.current_camera_index
        if cam_idx is None:
            return
        camera = state.camera_files[cam_idx]
        midi_unix = midi.unix_start + secs
        cam_unix = camera.raw_unix_start + frame / camera.capture_fps
        shift = engine.compute_global_shift_from_markers(midi_unix, cam_unix)
        reply = QMessageBox.question(
            self, "Apply Global Shift?",
            f"Computed global shift: {shift:.4f} s. Apply?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        result = self._controller.request_global_shift(shift)
        if result.anchors_to_clear > 0:
            warn = QMessageBox.warning(
                self, "Clear anchors?",
                f"This will remove all {result.anchors_to_clear} anchor(s). Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if warn != QMessageBox.StandardButton.Yes:
                return
            self._controller.confirm_global_shift(result)

    def _on_add_anchor(self) -> None:
        session = self._controller.session
        if not session.markers_ready():
            return
        cam_idx = session.current_camera_index
        if cam_idx is None:
            return
        mfn, secs = session.midi_marker  # type: ignore[misc]
        frame = session.camera_marker  # type: ignore[assignment]
        label, ok = QInputDialog.getText(
            self, "Anchor Label", "Optional label:",
        )
        if not ok:
            return
        self._controller.add_anchor(
            cam_idx,
            Anchor(
                midi_filename=mfn,
                midi_timestamp_seconds=secs,
                camera_frame=frame,
                label=label,
            ),
        )
        self._controller.clear_markers()

    # --- helpers -----------------------------------------------------

    def _load_midi(self, idx: int) -> None:
        state = self._controller.service.state
        if idx < 0 or idx >= len(state.midi_files):
            self._midi_panel.unload()
            return
        mi = state.midi_files[idx]
        adapter = self._midi_cache.get(mi.file_path)
        self._midi_panel.load_midi(adapter)

    def _load_camera(self, idx: int) -> None:
        state = self._controller.service.state
        if idx < 0 or idx >= len(state.camera_files):
            self._camera_panel.unload()
            return
        ci = state.camera_files[idx]
        self._camera_panel.load_video(
            str(ci.file_path), ci.total_frames, ci.capture_fps,
        )

    def _apply_anchor_lock_rule(self) -> None:
        session = self._controller.session
        if not self._controller.has_state():
            return
        target = session.anchor_lock_target_midi(self._controller.service)
        enabled = session.midi_combo_enabled(self._controller.service)
        self._midi_combo.setEnabled(enabled)
        if target is not None and target != self._midi_combo.currentIndex():
            self._midi_combo.setCurrentIndex(target)

    def _update_overlap(self) -> None:
        session = self._controller.session
        if not self._controller.has_state():
            self._overlap.set_clips(None, None)
            return
        state = self._controller.service.state
        midi = (
            state.midi_files[session.current_midi_index]
            if session.current_midi_index is not None
            and 0 <= session.current_midi_index < len(state.midi_files)
            else None
        )
        camera = (
            state.camera_files[session.current_camera_index]
            if session.current_camera_index is not None
            and 0 <= session.current_camera_index < len(state.camera_files)
            else None
        )
        self._overlap.set_clips(midi, camera)
        if camera is not None:
            eff = engine.get_effective_shift_for_camera(state, camera)
            self._overlap.set_effective_shift(eff)

    def _update_hint(self) -> None:
        session = self._controller.session
        self._hint_line.setText(_HINT.format(
            mode=session.mode.capitalize(), panel=session.active_panel.upper(),
        ))

    def _mark_midi(self) -> None:
        session = self._controller.session
        if session.current_midi_index is None:
            return
        state = self._controller.service.state
        midi = state.midi_files[session.current_midi_index]
        self._controller.set_marker_midi(
            midi.filename, self._midi_panel.current_time,
        )

    def _mark_camera(self) -> None:
        session = self._controller.session
        if session.current_camera_index is None:
            return
        frame = self._camera_panel.current_frame
        if frame < 0:
            return
        self._controller.set_marker_camera(frame)

    def _toggle_active_panel(self) -> None:
        current = self._controller.session.active_panel
        self._controller.set_active_panel(
            "midi" if current == "camera" else "camera"
        )

    def _step_active(self, sign: int, large: bool) -> None:
        if self._controller.session.active_panel == "midi":
            self._midi_panel.step_ticks(sign * (100 if large else 1))
        else:
            self._camera_panel.step(sign * (10 if large else 1))

    def _jump_to_overlap(self) -> None:
        state = self._controller.service.state if self._controller.has_state() else None
        if state is None:
            return
        session = self._controller.session
        if session.current_midi_index is None or session.current_camera_index is None:
            return
        midi = state.midi_files[session.current_midi_index]
        camera = state.camera_files[session.current_camera_index]
        eff = engine.get_effective_shift_for_camera(state, camera)
        cam_start = camera.raw_unix_start + eff
        cam_end = camera.raw_unix_end + eff
        ov_start = max(midi.unix_start, cam_start)
        ov_end = min(midi.unix_end, cam_end)
        if ov_start >= ov_end:
            QMessageBox.information(
                self, "No Overlap",
                "The MIDI and camera clips don't overlap under the current "
                "shift. Review the global shift.",
            )
            return
        self._midi_panel.set_position(ov_start - midi.unix_start)
        frame = engine.midi_unix_to_camera_frame(ov_start, eff, camera)
        if frame is not None:
            self._camera_panel.set_frame(frame)
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level2.view import Level2View; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level2/view.py
git commit -m "$(cat <<'EOF'
Add Level2View composite

Wires TopBar, hint line, OverlapIndicator, MIDI/Camera panels, marker
bar, and anchor table. Handles locked-mode sync via engine functions,
anchor-lock rule via session.anchor_lock_target_midi, shortcuts via
ShortcutRouter. All mutation goes through AlignmentController.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 28: Level 1 timeline canvas (`qt/level1/timeline_canvas.py`)

**Files:**
- Create: `alignment_tool/qt/level1/timeline_canvas.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level1/timeline_canvas.py`:
```python
"""Level 1 timeline — MIDI row + camera row + click/hover selection."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import (
    QColor, QMouseEvent, QPainter, QPen, QWheelEvent,
)
from PySide6.QtWidgets import QToolTip, QWidget

from alignment_tool.core import engine
from alignment_tool.core.models import AlignmentState, CameraFileInfo, MidiFileInfo

_TICK_CANDIDATES = [1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 1800, 3600]
_MIDI_COLOR = QColor(31, 119, 180)
_CAM_COLOR = QColor(255, 127, 14)
_SELECT_COLOR = QColor(255, 255, 0)
_LABEL_LEFT_MARGIN = 60
_ROW_HEIGHT = 40


class TimelineCanvas(QWidget):
    pair_selected = Signal(int, int)  # (midi_idx, camera_idx)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMouseTracking(True)
        self._state: AlignmentState | None = None
        self._t_start: float = 0.0
        self._t_end: float = 1.0
        self.selected_midi_index: int | None = None
        self.selected_camera_index: int | None = None
        self._drag_last_x: int | None = None

    def set_state(self, state: AlignmentState | None) -> None:
        self._state = state
        self.selected_midi_index = None
        self.selected_camera_index = None
        self._fit_to_data()
        self.update()

    def refresh(self) -> None:
        self.update()

    def _fit_to_data(self) -> None:
        if self._state is None:
            self._t_start = 0.0
            self._t_end = 1.0
            return
        mins = []
        maxs = []
        for m in self._state.midi_files:
            mins.append(m.unix_start)
            maxs.append(m.unix_end)
        gs = self._state.global_shift_seconds
        for c in self._state.camera_files:
            eff = engine.get_effective_shift_for_camera(self._state, c)
            mins.append(c.raw_unix_start + eff)
            maxs.append(c.raw_unix_end + eff)
        if not mins:
            self._t_start = 0.0
            self._t_end = 60.0
            return
        t0 = min(mins)
        t1 = max(maxs)
        pad = max(1.0, (t1 - t0) * 0.05)
        self._t_start = t0 - pad
        self._t_end = t1 + pad

    # --- painting ---------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(20, 20, 28))
        if self._state is None:
            return
        w = self.width()
        h = self.height()
        midi_y = h // 2 - _ROW_HEIGHT - 5
        cam_y = h // 2 + 5
        # Row labels.
        p.setPen(QColor(200, 200, 200))
        p.drawText(4, midi_y + _ROW_HEIGHT // 2 + 5, "MIDI")
        p.drawText(4, cam_y + _ROW_HEIGHT // 2 + 5, "Camera")
        # Gridlines.
        self._draw_grid(p, w, h)
        # MIDI bars.
        for i, m in enumerate(self._state.midi_files):
            self._draw_bar(
                p, m.unix_start, m.unix_end, midi_y, _ROW_HEIGHT,
                _MIDI_COLOR, m.filename,
                selected=(i == self.selected_midi_index),
            )
        # Camera bars.
        for i, c in enumerate(self._state.camera_files):
            eff = engine.get_effective_shift_for_camera(self._state, c)
            self._draw_bar(
                p, c.raw_unix_start + eff, c.raw_unix_end + eff,
                cam_y, _ROW_HEIGHT, _CAM_COLOR, c.filename,
                selected=(i == self.selected_camera_index),
            )
        # Axis label.
        p.setPen(QColor(160, 160, 160))
        p.drawText(w // 2 - 40, h - 4, "Time (s)")

    def _draw_grid(self, p: QPainter, w: int, h: int) -> None:
        span = self._t_end - self._t_start
        if span <= 0:
            return
        target_ticks = 10
        ideal = span / target_ticks
        tick = _TICK_CANDIDATES[0]
        for t in _TICK_CANDIDATES:
            tick = t
            if t >= ideal:
                break
        first = int(self._t_start / tick) * tick
        p.setPen(QPen(QColor(60, 60, 70), 1, Qt.PenStyle.DashLine))
        t = float(first)
        while t < self._t_end:
            x = self._t_to_x(t)
            p.drawLine(x, 20, x, h - 20)
            p.setPen(QColor(140, 140, 140))
            p.drawText(x + 2, h - 20, self._fmt_time(t - self._t_start))
            p.setPen(QPen(QColor(60, 60, 70), 1, Qt.PenStyle.DashLine))
            t += tick

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        s = int(seconds)
        if s >= 3600:
            return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
        return f"{s // 60}:{s % 60:02d}"

    def _draw_bar(
        self, p: QPainter, t0: float, t1: float,
        y: int, h: int, color: QColor, label: str, selected: bool,
    ) -> None:
        x0 = max(_LABEL_LEFT_MARGIN, self._t_to_x(t0))
        x1 = self._t_to_x(t1)
        if x1 <= x0:
            return
        p.fillRect(x0, y, x1 - x0, h, color)
        if selected:
            p.setPen(QPen(_SELECT_COLOR, 2))
            p.drawRect(x0, y, x1 - x0, h)
        p.setPen(QColor(255, 255, 255))
        if x1 - x0 > 60:
            p.drawText(
                x0 + 4, y + h // 2 + 5,
                label if len(label) < 40 else label[:37] + "...",
            )

    def _t_to_x(self, t: float) -> int:
        span = max(1e-9, self._t_end - self._t_start)
        w = self.width() - _LABEL_LEFT_MARGIN
        return _LABEL_LEFT_MARGIN + int((t - self._t_start) / span * w)

    # --- interaction ------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test(event.position().x(), event.position().y())
            if hit is None:
                self._drag_last_x = int(event.position().x())
                return
            kind, idx = hit
            if kind == "midi":
                if self.selected_midi_index == idx:
                    self.selected_midi_index = None
                else:
                    self.selected_midi_index = idx
            else:
                if self.selected_camera_index == idx:
                    self.selected_camera_index = None
                else:
                    self.selected_camera_index = idx
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if (
            self.selected_midi_index is not None
            and self.selected_camera_index is not None
        ):
            self.pair_selected.emit(
                self.selected_midi_index, self.selected_camera_index,
            )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        x = int(event.position().x())
        if self._drag_last_x is not None and event.buttons() & Qt.MouseButton.LeftButton:
            span = self._t_end - self._t_start
            w = self.width() - _LABEL_LEFT_MARGIN
            dx = x - self._drag_last_x
            self._drag_last_x = x
            self._t_start -= dx * span / max(1, w)
            self._t_end -= dx * span / max(1, w)
            self.update()
            return
        # Tooltip.
        hit = self._hit_test(event.position().x(), event.position().y())
        if hit is not None and self._state is not None:
            kind, idx = hit
            if kind == "midi":
                m = self._state.midi_files[idx]
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{m.filename}\nduration {m.duration:.2f}s\n"
                    f"unix {m.unix_start:.1f} → {m.unix_end:.1f}",
                )
            else:
                c = self._state.camera_files[idx]
                eff = engine.get_effective_shift_for_camera(self._state, c)
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{c.filename}\nduration {c.duration:.2f}s\n"
                    f"raw {c.raw_unix_start:.1f}\n"
                    f"aligned {c.raw_unix_start + eff:.1f}\n"
                    f"fps {c.capture_fps:.2f}",
                )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._drag_last_x = None

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        x = int(event.position().x())
        span = self._t_end - self._t_start
        anchor_t = self._t_start + (x - _LABEL_LEFT_MARGIN) / max(
            1, self.width() - _LABEL_LEFT_MARGIN
        ) * span
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        new_span = max(1.0, min(100_000.0, span * factor))
        frac = (anchor_t - self._t_start) / max(1e-9, span)
        self._t_start = anchor_t - frac * new_span
        self._t_end = self._t_start + new_span
        self.update()

    def _hit_test(self, x: float, y: float) -> tuple[str, int] | None:
        if self._state is None:
            return None
        h = self.height()
        midi_y = h // 2 - _ROW_HEIGHT - 5
        cam_y = h // 2 + 5
        if midi_y <= y <= midi_y + _ROW_HEIGHT:
            for i, m in enumerate(self._state.midi_files):
                x0 = self._t_to_x(m.unix_start)
                x1 = self._t_to_x(m.unix_end)
                if x0 <= x <= x1:
                    return ("midi", i)
        if cam_y <= y <= cam_y + _ROW_HEIGHT:
            for i, c in enumerate(self._state.camera_files):
                eff = engine.get_effective_shift_for_camera(self._state, c)
                x0 = self._t_to_x(c.raw_unix_start + eff)
                x1 = self._t_to_x(c.raw_unix_end + eff)
                if x0 <= x <= x1:
                    return ("camera", i)
        return None
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level1.timeline_canvas import TimelineCanvas; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level1/timeline_canvas.py
git commit -m "$(cat <<'EOF'
Add TimelineCanvas

MIDI (blue) + camera (orange, aligned by effective_shift) rows with
dashed gridlines, tooltips, click-select, double-click to open pair,
drag-pan, wheel-zoom anchored at cursor.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 29: Level 1 widget (`qt/level1/widget.py`)

**Files:**
- Create: `alignment_tool/qt/level1/widget.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/level1/widget.py`:
```python
"""Level 1 container: shift spinner header + TimelineCanvas."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from alignment_tool.qt.controller import AlignmentController
from alignment_tool.qt.level1.timeline_canvas import TimelineCanvas


class Level1Widget(QWidget):
    pair_selected = Signal(int, int)

    def __init__(
        self,
        controller: AlignmentController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._shift_spin = QDoubleSpinBox(self)
        self._shift_spin.setRange(-100000.0, 100000.0)
        self._shift_spin.setDecimals(3)
        self._shift_spin.setSingleStep(0.1)
        self._apply_btn = QPushButton("Apply", self)
        self._open_btn = QPushButton("Open Selected Pair", self)
        self._canvas = TimelineCanvas(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Global Shift (s):", self))
        header.addWidget(self._shift_spin)
        header.addWidget(self._apply_btn)
        header.addStretch(1)
        header.addWidget(self._open_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self._canvas, 1)

        self._apply_btn.clicked.connect(self._on_apply)
        self._open_btn.clicked.connect(self._on_open_selected)
        self._canvas.pair_selected.connect(self.pair_selected.emit)
        controller.state_loaded.connect(self._refresh_from_controller)
        controller.global_shift_changed.connect(self._on_shift_changed)
        controller.anchors_changed.connect(lambda _: self._canvas.refresh())
        controller.active_anchor_changed.connect(
            lambda _: self._canvas.refresh()
        )

    def _refresh_from_controller(self) -> None:
        if not self._controller.has_state():
            self._canvas.set_state(None)
            self._shift_spin.setValue(0.0)
            return
        state = self._controller.service.state
        self._shift_spin.blockSignals(True)
        self._shift_spin.setValue(state.global_shift_seconds)
        self._shift_spin.blockSignals(False)
        self._canvas.set_state(state)

    def _on_shift_changed(self, new_shift: float) -> None:
        self._shift_spin.blockSignals(True)
        self._shift_spin.setValue(new_shift)
        self._shift_spin.blockSignals(False)
        self._canvas.refresh()

    def _on_apply(self) -> None:
        if not self._controller.has_state():
            return
        new_shift = self._shift_spin.value()
        current = self._controller.service.state.global_shift_seconds
        if abs(new_shift - current) < 1e-9:
            return
        result = self._controller.request_global_shift(new_shift)
        if result.anchors_to_clear == 0:
            return
        warn = QMessageBox.warning(
            self, "Clear anchors?",
            f"Changing global shift will remove all "
            f"{result.anchors_to_clear} anchor(s) across "
            f"{result.clips_affected} camera clip(s). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if warn != QMessageBox.StandardButton.Yes:
            # Revert spinner.
            self._shift_spin.blockSignals(True)
            self._shift_spin.setValue(current)
            self._shift_spin.blockSignals(False)
            return
        self._controller.confirm_global_shift(result)

    def _on_open_selected(self) -> None:
        mi = self._canvas.selected_midi_index
        ci = self._canvas.selected_camera_index
        if mi is None or ci is None:
            return
        self.pair_selected.emit(mi, ci)
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.level1.widget import Level1Widget; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/level1/widget.py
git commit -m "$(cat <<'EOF'
Add Level1Widget

Shift spinner + Apply button with anchor-clear confirmation. Open
Selected Pair button emits pair_selected. Subscribes to controller
state_loaded/global_shift_changed/anchors_changed so the canvas stays
in sync.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 30: Main window (`qt/main_window.py`)

**Files:**
- Create: `alignment_tool/qt/main_window.py`

- [ ] **Step 1: Write the module**

Create `alignment_tool/qt/main_window.py`:
```python
"""Main application window. Shell with stacked Level 1 / Level 2 views."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QStackedWidget, QWidget,
)

from alignment_tool.core import persistence
from alignment_tool.core.errors import (
    AlignmentToolError, MediaNotFoundError,
)
from alignment_tool.io.midi_cache import MidiCache
from alignment_tool.io.participant_loader import load_participant
from alignment_tool.qt.controller import AlignmentController
from alignment_tool.qt.level1.widget import Level1Widget
from alignment_tool.qt.level2.view import Level2View

_log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MIDI-Camera Alignment Tool v2")
        self.resize(1400, 900)

        self._controller = AlignmentController(self)
        self._midi_cache = MidiCache()

        self._stack = QStackedWidget(self)
        self._placeholder = QLabel(
            "Open a participant folder (File → Open Participant)", self,
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._level1 = Level1Widget(self._controller, self)
        self._level2 = Level2View(self._controller, self._midi_cache, self)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._level1)
        self._stack.addWidget(self._level2)
        self.setCentralWidget(self._stack)

        self._status = QLabel("No participant loaded", self)
        self.statusBar().addWidget(self._status, 1)

        self._build_menu()
        self._wire()

    # --- menu/wiring -------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self._open_action = QAction("Open Participant…", self)
        self._open_action.setShortcut(QKeySequence("Ctrl+O"))
        self._save_action = QAction("Save Alignment…", self)
        self._save_action.setShortcut(QKeySequence("Ctrl+S"))
        self._save_action.setEnabled(False)
        self._load_action = QAction("Load Alignment…", self)
        self._load_action.setShortcut(QKeySequence("Ctrl+L"))
        self._exit_action = QAction("Exit", self)
        self._exit_action.setShortcut(QKeySequence("Ctrl+Q"))

        file_menu.addAction(self._open_action)
        file_menu.addAction(self._save_action)
        file_menu.addAction(self._load_action)
        file_menu.addSeparator()
        file_menu.addAction(self._exit_action)

        self._open_action.triggered.connect(self._on_open_participant)
        self._save_action.triggered.connect(self._on_save)
        self._load_action.triggered.connect(self._on_load)
        self._exit_action.triggered.connect(self.close)

    def _wire(self) -> None:
        self._level1.pair_selected.connect(self._on_pair_selected)
        self._level2.back_requested.connect(self._on_back)
        self._controller.state_loaded.connect(self._on_state_loaded)
        self._controller.error_occurred.connect(self._on_error)
        self._controller.global_shift_changed.connect(
            lambda _: self._refresh_status()
        )
        self._controller.anchors_changed.connect(
            lambda _: self._refresh_status()
        )

    # --- menu handlers ----------------------------------------------

    def _on_open_participant(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select participant folder", "",
        )
        if not folder:
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            state = load_participant(folder)
        except Exception as e:
            self.unsetCursor()
            QMessageBox.critical(self, "Error Loading Participant", str(e))
            return
        self.unsetCursor()
        if not state.midi_files and not state.camera_files:
            QMessageBox.warning(
                self, "No Files Found",
                "Expected 'disklavier/' and 'overhead camera/' subfolders "
                "with .mid and .MP4 files.",
            )
            return
        self._controller.load_state(state)
        # Level1Widget auto-refreshes via the state_loaded signal.

    def _on_save(self) -> None:
        if not self._controller.has_state():
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save alignment JSON", "", "JSON Files (*.json)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if not path.suffix:
            path = path.with_suffix(".json")
        try:
            persistence.save_alignment(self._controller.service.state, path)
        except AlignmentToolError as e:
            QMessageBox.critical(self, "Error Saving", str(e))
            return
        self._status.setText(f"Saved: {path}")

    def _on_load(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Load alignment JSON", "", "JSON Files (*.json)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            state = persistence.load_alignment(path)
        except MediaNotFoundError as e:
            relocate = QFileDialog.getExistingDirectory(
                self,
                f"Participant folder not found ({e.missing_path}). "
                f"Locate it:",
                "",
            )
            if not relocate:
                return
            try:
                state = persistence.load_alignment(
                    path, override_folder=Path(relocate),
                )
            except AlignmentToolError as e2:
                QMessageBox.critical(self, "Error Loading", str(e2))
                return
        except AlignmentToolError as e:
            QMessageBox.critical(self, "Error Loading", str(e))
            return
        self._controller.load_state(state)

    # --- state transitions ------------------------------------------

    def _on_state_loaded(self) -> None:
        self._save_action.setEnabled(True)
        self._stack.setCurrentWidget(self._level1)
        self._level2.populate_from_state()
        state = self._controller.service.state
        self.setWindowTitle(
            f"MIDI-Camera Alignment Tool v2 — {state.participant_id}"
        )
        self._refresh_status()

    def _on_pair_selected(self, midi_idx: int, camera_idx: int) -> None:
        self._level2.open_pair(midi_idx, camera_idx)
        self._stack.setCurrentWidget(self._level2)
        state = self._controller.service.state
        self._status.setText(
            f"Level 2: {state.midi_files[midi_idx].filename} + "
            f"{state.camera_files[camera_idx].filename}"
        )

    def _on_back(self) -> None:
        self._stack.setCurrentWidget(self._level1)
        self._refresh_status()

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Operation failed", message)

    def _refresh_status(self) -> None:
        if not self._controller.has_state():
            self._status.setText("No participant loaded")
            return
        state = self._controller.service.state
        anchors = self._controller.service.total_anchor_count()
        self._status.setText(
            f"Participant {state.participant_id} | "
            f"{len(state.midi_files)} MIDI | "
            f"{len(state.camera_files)} camera | "
            f"Global shift: {state.global_shift_seconds:.3f}s | "
            f"Anchors: {anchors}"
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._level2.cleanup()
        super().closeEvent(event)
```

- [ ] **Step 2: Sanity check**

Run: `python -c "from alignment_tool.qt.main_window import MainWindow; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add alignment_tool/qt/main_window.py
git commit -m "$(cat <<'EOF'
Add MainWindow

QStackedWidget with placeholder / Level1 / Level2. File menu: Open
(Ctrl+O), Save (Ctrl+S, disabled until load), Load (Ctrl+L), Exit
(Ctrl+Q). Load handles MediaNotFoundError with a relocation dialog.
closeEvent calls Level2View.cleanup() to quit the frame worker thread.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 31: App entry (`app.py`, `__main__.py`)

**Files:**
- Create: `alignment_tool/app.py`
- Create: `alignment_tool/__main__.py`

- [ ] **Step 1: Write `app.py`**

Create `alignment_tool/app.py`:
```python
"""QApplication bootstrap + logging config."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from alignment_tool.qt.main_window import MainWindow


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
```

- [ ] **Step 2: Write `__main__.py`**

Create `alignment_tool/__main__.py`:
```python
"""Entry for `python -m alignment_tool`."""
import sys

from alignment_tool.app import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Sanity check — package imports**

Run: `python -c "import alignment_tool; from alignment_tool import app; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add alignment_tool/app.py alignment_tool/__main__.py
git commit -m "$(cat <<'EOF'
Add app.main and __main__ entry

Configures root logger to WARNING at stderr, constructs QApplication
and MainWindow. python -m alignment_tool now works end-to-end.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase F — Verification, smoke test, polish (Tasks 32–34)

### Task 32: Boundary check — core/io must not import PySide6

**Files:** none (grep check + optional pre-commit hook).

- [ ] **Step 1: Run the check**

Run: `grep -r "PySide6" alignment_tool/core alignment_tool/io && echo FAIL || echo CLEAN`
Expected: `CLEAN`

If `FAIL`: remove the offending import; the logic it uses must move into `qt/`.

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass — ~23 engine, ~28 service, ~11 persistence.

- [ ] **Step 3: Run the boundary check as a committed script**

Create `tests/test_boundary.py`:
```python
"""Enforces: no PySide6 imports under core/ or io/."""
from pathlib import Path


def test_no_pyside_in_core_or_io():
    root = Path(__file__).parent.parent / "alignment_tool"
    offenders: list[str] = []
    for sub in ("core", "io"):
        for path in (root / sub).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "PySide6" in text:
                offenders.append(str(path))
    assert not offenders, (
        f"PySide6 imported under core/ or io/: {offenders}"
    )
```

- [ ] **Step 4: Run it**

Run: `pytest tests/test_boundary.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_boundary.py
git commit -m "$(cat <<'EOF'
Add boundary test: no PySide6 under core/ or io/

Fails the suite if any file under alignment_tool/core or
alignment_tool/io imports PySide6. Protects the pure-Python contract
that keeps the core testable without Qt.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 33: Smoke test with a real participant folder

**Files:** none (manual verification).

- [ ] **Step 1: Launch the app**

Run: `python -m alignment_tool`
Expected: window titled "MIDI-Camera Alignment Tool v2" opens with the placeholder message.

- [ ] **Step 2: Open a participant folder (File → Open Participant)**

Use a known-good participant folder containing `disklavier/*.mid` and `overhead camera/*.MP4` + XML sidecars.
Expected: Level 1 timeline shows both MIDI (blue) and camera (orange) bars. Status bar shows file counts + global shift 0.000s + 0 anchors.

- [ ] **Step 3: Drill into a pair**

Select a MIDI bar and a camera bar, double-click (or use "Open Selected Pair").
Expected: Level 2 view opens. MIDI falling-keys panel plays a note pattern. Camera panel shows frame 0. Overlap indicator shows both extents with green overlap region.

- [ ] **Step 4: Test markers + Compute Shift**

Scrub MIDI to a visible keypress, press `M`. Scrub camera to the matching keypress, press `C`. The marker bar labels update and the "Compute Global Shift" button enables. Click it.
Expected: confirmation dialog shows a computed shift; accepting updates `global_shift_seconds` (check status bar) and the camera bar in Level 1 visibly shifts.

- [ ] **Step 5: Test anchor creation + locked mode**

With markers set, press `A`, accept a label. Anchor appears in the table.
Click the `*` cell to activate it. Toggle Mode (`L`). In locked mode, scrub MIDI → camera follows; scrub camera → MIDI follows.

- [ ] **Step 6: Test Save / Load round-trip**

File → Save (`Ctrl+S`), pick a path. Close the app (`Ctrl+Q`). Relaunch. File → Load (`Ctrl+L`), pick the JSON.
Expected: Level 1 shows the same state, anchors preserved, Level 2 works immediately (no "re-open participant folder" required).

- [ ] **Step 7: Test JSON load with missing participant folder**

Rename the participant folder on disk, re-launch and Load. A relocation dialog should appear; select the renamed folder.
Expected: state loads successfully against the new path.

- [ ] **Step 8: Test close-during-video**

Open Level 2, scrub the camera panel rapidly for a few seconds, then close the window.
Expected: no "QThread destroyed while thread is still running" warning in stderr.

- [ ] **Step 9: Commit a smoke-test log**

No code change — just note in commit message that manual smoke passed. If no code changes, skip this step.

---

### Task 34: README update + final polish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README**

Run: inspect `README.md` contents.

- [ ] **Step 2: Replace with v2 contents**

Overwrite `README.md` with:
```markdown
# midi_camera_alignment_tool

PySide6 desktop tool for aligning overhead camera (Sony FX30) recordings to Disklavier MIDI files in a multi-participant piano study.

## Install

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```
python -m alignment_tool
```

## Test

```
pytest
```

## Layout

- `alignment_tool/core/` — pure-Python math, state, service, persistence.
- `alignment_tool/io/` — file adapters (MIDI, camera, participant scanner).
- `alignment_tool/qt/` — PySide6 widgets and the controller shim.
- `tests/` — unit tests for core/ and io/. No Qt.

## Design

See `docs/superpowers/specs/2026-04-13-midi-camera-alignment-rebuild-design.md`.
```

- [ ] **Step 3: Run the full test suite one more time**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Update README for v2

Install / run / test instructions, module layout overview, and a
pointer to the design spec.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Appendix — Bug-fix cross-reference

Every audit fix from §10 of the spec lands in one of the tasks above:

| Audit item | Fixed in |
|---|---|
| 1 (FrameWorker cross-thread) | Task 20 + 22 |
| 2 (QThread shutdown leak) | Task 22 + 30 |
| 4 (participant_folder not persisted) | Tasks 5 + 13 + 14 |
| 5 (total_frames=0 after load) | Tasks 5 + 14 |
| 7 (anchor on missing MIDI silent) | Task 14 |
| 11 (path parsing) | Tasks 15, 16, 18 |
| 17 (notes only [0]) | Task 15 |
| 18 (scoped enums) | All Phase D/E tasks |
| 19 (Signal/Slot) | All Phase D/E tasks |
| 21 (__del__) | Task 16 |
| 22 (panel focus) | Tasks 21, 22, 27 |
| 23 (float creep) | Tasks 8 + 27 |
| 24 (.mp4 case) | Task 18 |
| 26 (atomic save) | Task 13 |
| 27 (float ==) | Tasks 10 + 29 |

---

## Open Questions / Risks

- **Smoke-test fidelity (Task 33)** depends on the user supplying a real participant folder. If none is available, the test reduces to launching the app and verifying the placeholder + menu behavior.
- **FPS edge cases.** The math assumes constant `capture_fps` within a clip. Variable-frame-rate MP4s will drift; out of scope per §1.
- **PySide6 painting defaults differ slightly from PyQt5** (antialiasing, text baseline). Visual tweaks during Task 33 may be needed; fix inline.
