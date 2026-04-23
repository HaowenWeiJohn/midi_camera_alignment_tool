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


# --- set_anchor_label ---

def test_set_anchor_label_updates_label():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)

    svc.set_anchor_label(0, 1, "keypress A")

    assert state.camera_files[0].alignment_anchors[1].label == "keypress A"
    assert state.camera_files[0].alignment_anchors[0].label == ""


def test_set_anchor_label_accepts_empty_string():
    midi = make_midi_file(filename="m1.mid")
    anchor = make_anchor(midi_filename="m1.mid", label="old")
    cam = make_camera_file(anchors=[anchor])
    state = make_state(midi_files=[midi], camera_files=[cam])
    svc = AlignmentService(state)

    svc.set_anchor_label(0, 0, "")

    assert cam.alignment_anchors[0].label == ""


def test_set_anchor_label_bad_camera_index_raises():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)
    with pytest.raises(InvalidAnchorError):
        svc.set_anchor_label(99, 0, "x")


def test_set_anchor_label_bad_anchor_index_raises():
    state = _state_with_two_anchors()
    svc = AlignmentService(state)
    with pytest.raises(InvalidAnchorError):
        svc.set_anchor_label(0, 99, "x")


# --- effective_shift_for ---

def test_effective_shift_no_anchor_returns_global():
    state = make_state(global_shift=0.25)
    svc = AlignmentService(state)
    assert svc.effective_shift_for(0) == 0.25
