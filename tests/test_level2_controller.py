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


def test_locked_mode_camera_before_midi_gives_oor_delta_positive():
    # Setup: MIDI starts at 1000, camera starts at 1030.
    # Camera frame 0 -> camera_unix=1030 -> midi_unix=1030 -> midi_seconds=30 -> in range.
    # Need a frame that maps to before midi_unix_start=1000.
    # effective_shift is derivable by the service, 0 with no anchors.
    # To get OOR, we'd need the camera frame to map to negative midi_seconds - but camera starts at 1030 which is 30s into MIDI.
    # Build a scenario where camera starts BEFORE MIDI.
    midi = make_midi_file(filename="m1.mid", unix_start=1050.0, duration=100.0)  # MIDI: 1050->1150
    cam = make_camera_file(raw_unix_start=1000.0, capture_fps=240.0, duration=60.0)  # Camera: 1000->1060
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)
    ctrl = Level2Controller(state, svc)
    ctrl.load_pair(midi_index=0, camera_index=0)
    ctrl.set_mode(Mode.LOCKED)

    # Frame 0 -> camera_unix=1000 -> midi_unix=1000 -> midi_seconds=-50 -> OOR, delta=+50.
    out = ctrl.on_camera_position_changed(camera_frame=0)
    assert out.new_midi_time is None
    assert out.out_of_range_delta == pytest.approx(50.0)


def test_locked_mode_camera_after_midi_gives_oor_delta_negative():
    # MIDI: 1000->1050 (short), Camera: 1000->1060 (longer).
    midi = make_midi_file(filename="m1.mid", unix_start=1000.0, duration=50.0)
    cam = make_camera_file(raw_unix_start=1000.0, capture_fps=240.0, duration=60.0)
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)
    ctrl = Level2Controller(state, svc)
    ctrl.load_pair(midi_index=0, camera_index=0)
    ctrl.set_mode(Mode.LOCKED)

    # Frame at 55s in -> camera_unix=1055 -> midi_unix=1055 -> midi_seconds=55 (MIDI duration 50) -> OOR, delta=-5.
    out = ctrl.on_camera_position_changed(camera_frame=240 * 55)
    assert out.new_midi_time is None
    assert out.out_of_range_delta == pytest.approx(-5.0)
