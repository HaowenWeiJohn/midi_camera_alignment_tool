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

    # anchor says MIDI t=5 aligns to camera frame 0 -> shift = (1000+5) - (1030+0) = -25
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
