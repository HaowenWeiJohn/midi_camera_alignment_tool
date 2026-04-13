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
