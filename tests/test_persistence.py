from __future__ import annotations

import json
import os
from datetime import datetime
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
    pf = "/fake/P007"
    midi = make_midi_file(
        filename="t1.mid", unix_start=1000.0, duration=120.0,
        file_path=pf + "/disklavier/t1.mid",
    )
    anchor = make_anchor(
        midi_filename="t1.mid", midi_timestamp_seconds=5.5, camera_frame=1320, label="keypress A",
    )
    cam = make_camera_file(
        filename="C0001.MP4",
        anchors=[anchor],
        active_anchor_index=0,
        mp4_path=pf + "/overhead camera/C0001.MP4",
        xml_path=pf + "/overhead camera/C0001M01.XML",
    )
    state = make_state(
        participant_id="P007",
        participant_folder=pf,
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
    assert os.path.normpath(loaded.midi_files[0].file_path) == os.path.normpath(midi.file_path)
    assert loaded.midi_files[0].ticks_per_beat == midi.ticks_per_beat
    assert loaded.midi_files[0].tempo == midi.tempo
    assert len(loaded.camera_files) == 1
    assert os.path.normpath(loaded.camera_files[0].mp4_path) == os.path.normpath(cam.mp4_path)
    assert os.path.normpath(loaded.camera_files[0].xml_path) == os.path.normpath(cam.xml_path)
    assert loaded.camera_files[0].total_frames == cam.total_frames
    # active_anchor_index is session-only; always loads as None.
    assert loaded.camera_files[0].active_anchor_index is None
    assert loaded.camera_files[0].alignment_anchors[0].label == "keypress A"
    assert loaded.saved_at == state.saved_at


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


def test_active_anchor_index_is_not_persisted(tmp_path: Path):
    """active_anchor_index is session-only. Saving should omit the key entirely."""
    midi = make_midi_file(filename="t1.mid")
    anchor = make_anchor(midi_filename="t1.mid")
    cam = make_camera_file(anchors=[anchor], active_anchor_index=0)
    state = make_state(midi_files=[midi], camera_files=[cam])

    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    with open(filepath) as f:
        data = json.load(f)

    assert "active_anchor_index" not in data["camera_files"][0]


def test_load_ignores_legacy_active_anchor_index_key(tmp_path: Path):
    """Old JSONs with active_anchor_index set must load with active=None."""
    midi = make_midi_file(filename="t1.mid")
    anchor = make_anchor(midi_filename="t1.mid")
    cam = make_camera_file(anchors=[anchor], active_anchor_index=None)
    state = make_state(midi_files=[midi], camera_files=[cam])

    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))

    # Hand-inject the legacy key the way a pre-refactor save would have.
    with open(filepath) as f:
        data = json.load(f)
    data["camera_files"][0]["active_anchor_index"] = 0
    with open(filepath, "w") as f:
        json.dump(data, f)

    loaded = persistence.load_alignment(str(filepath))
    assert loaded.camera_files[0].active_anchor_index is None


# --- Validation tests ---


def test_save_rejects_nan_global_shift(tmp_path: Path):
    state = make_state(global_shift=float("nan"))
    with pytest.raises(ValueError):
        persistence.save_alignment(state, str(tmp_path / "x.json"))


def test_save_rejects_infinity_duration(tmp_path: Path):
    midi = make_midi_file(duration=float("inf"))
    state = make_state(midi_files=[midi])
    with pytest.raises(ValueError):
        persistence.save_alignment(state, str(tmp_path / "x.json"))


def _save_and_patch(tmp_path: Path, **overrides) -> Path:
    """Save a valid state, then patch the raw JSON with overrides."""
    midi = make_midi_file(filename="t1.mid")
    anchor = make_anchor(midi_filename="t1.mid")
    cam = make_camera_file(anchors=[anchor])
    state = make_state(midi_files=[midi], camera_files=[cam])
    filepath = tmp_path / "patched.json"
    persistence.save_alignment(state, str(filepath))
    with open(filepath) as f:
        data = json.load(f)
    _apply_patches(data, overrides)
    with open(filepath, "w") as f:
        json.dump(data, f, allow_nan=True)
    return filepath


def _apply_patches(data: dict, patches: dict) -> None:
    for key, value in patches.items():
        if key == "global_shift_seconds":
            data["global_shift_seconds"] = value
        elif key.startswith("midi."):
            field = key.split(".", 1)[1]
            data["midi_files"][0][field] = value
        elif key.startswith("camera."):
            field = key.split(".", 1)[1]
            data["camera_files"][0][field] = value
        elif key.startswith("anchor."):
            field = key.split(".", 1)[1]
            data["camera_files"][0]["alignment_anchors"][0][field] = value


def test_load_rejects_zero_capture_fps(tmp_path: Path):
    filepath = _save_and_patch(tmp_path, **{"camera.capture_fps": 0})
    with pytest.raises(CorruptAlignmentFileError, match="capture_fps"):
        persistence.load_alignment(str(filepath))


def test_load_rejects_zero_total_frames(tmp_path: Path):
    filepath = _save_and_patch(tmp_path, **{"camera.total_frames": 0})
    with pytest.raises(CorruptAlignmentFileError, match="total_frames"):
        persistence.load_alignment(str(filepath))


def test_load_rejects_anchor_unknown_midi(tmp_path: Path):
    filepath = _save_and_patch(tmp_path, **{"anchor.midi_filename": "nonexistent.mid"})
    with pytest.raises(CorruptAlignmentFileError, match="unknown MIDI file"):
        persistence.load_alignment(str(filepath))


def test_load_rejects_nan_float_field(tmp_path: Path):
    filepath = _save_and_patch(tmp_path, global_shift_seconds=float("nan"))
    with pytest.raises(CorruptAlignmentFileError, match="finite"):
        persistence.load_alignment(str(filepath))


def test_load_rejects_negative_camera_frame(tmp_path: Path):
    filepath = _save_and_patch(tmp_path, **{"anchor.camera_frame": -5})
    with pytest.raises(CorruptAlignmentFileError, match="negative camera_frame"):
        persistence.load_alignment(str(filepath))


def test_load_rejects_negative_duration(tmp_path: Path):
    filepath = _save_and_patch(tmp_path, **{"midi.duration": -1.0})
    with pytest.raises(CorruptAlignmentFileError, match="duration"):
        persistence.load_alignment(str(filepath))


# --- Relative paths tests ---


def test_save_writes_relative_paths(tmp_path: Path):
    pf = "/fake/P042"
    midi = make_midi_file(file_path=pf + "/disklavier/trial_001.mid")
    cam = make_camera_file(
        mp4_path=pf + "/overhead camera/C0001.MP4",
        xml_path=pf + "/overhead camera/C0001M01.XML",
    )
    state = make_state(participant_folder=pf, midi_files=[midi], camera_files=[cam])
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    with open(filepath) as f:
        data = json.load(f)
    assert not os.path.isabs(data["midi_files"][0]["file_path"])
    assert not os.path.isabs(data["camera_files"][0]["mp4_path"])
    assert not os.path.isabs(data["camera_files"][0]["xml_path"])
    assert "disklavier" in data["midi_files"][0]["file_path"]
    assert "overhead camera" in data["camera_files"][0]["mp4_path"]


def test_load_resolves_relative_paths(tmp_path: Path):
    pf = "/fake/P042"
    midi = make_midi_file(file_path=pf + "/disklavier/trial_001.mid")
    cam = make_camera_file(
        mp4_path=pf + "/overhead camera/C0001.MP4",
        xml_path=pf + "/overhead camera/C0001M01.XML",
    )
    state = make_state(participant_folder=pf, midi_files=[midi], camera_files=[cam])
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    loaded = persistence.load_alignment(str(filepath))
    assert os.path.isabs(loaded.midi_files[0].file_path)
    assert os.path.isabs(loaded.camera_files[0].mp4_path)
    assert os.path.isabs(loaded.camera_files[0].xml_path)


def test_load_handles_legacy_absolute_paths(tmp_path: Path):
    """Old JSON files with absolute paths should load correctly."""
    pf = "/fake/P042"
    midi = make_midi_file(filename="t1.mid", file_path=pf + "/disklavier/t1.mid")
    cam = make_camera_file(
        mp4_path=pf + "/overhead camera/C0001.MP4",
        xml_path=pf + "/overhead camera/C0001M01.XML",
    )
    state = make_state(participant_folder=pf, midi_files=[midi], camera_files=[cam])
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    # Overwrite with absolute paths to simulate old format
    with open(filepath) as f:
        data = json.load(f)
    data["midi_files"][0]["file_path"] = pf + "/disklavier/t1.mid"
    data["camera_files"][0]["mp4_path"] = pf + "/overhead camera/C0001.MP4"
    data["camera_files"][0]["xml_path"] = pf + "/overhead camera/C0001M01.XML"
    with open(filepath, "w") as f:
        json.dump(data, f)
    loaded = persistence.load_alignment(str(filepath))
    # Absolute paths pass through as-is
    assert loaded.midi_files[0].file_path == pf + "/disklavier/t1.mid"
    assert loaded.camera_files[0].mp4_path == pf + "/overhead camera/C0001.MP4"


def test_rebase_paths_updates_all_paths(tmp_path: Path):
    old_pf = "/old/P042"
    new_pf = "/new/location/P042"
    midi = make_midi_file(file_path=old_pf + "/disklavier/trial_001.mid")
    cam = make_camera_file(
        mp4_path=old_pf + "/overhead camera/C0001.MP4",
        xml_path=old_pf + "/overhead camera/C0001M01.XML",
    )
    state = make_state(participant_folder=old_pf, midi_files=[midi], camera_files=[cam])
    persistence.rebase_paths(state, new_pf)
    assert state.participant_folder == new_pf
    assert os.path.normpath(state.midi_files[0].file_path) == os.path.normpath(
        new_pf + "/disklavier/trial_001.mid"
    )
    assert os.path.normpath(state.camera_files[0].mp4_path) == os.path.normpath(
        new_pf + "/overhead camera/C0001.MP4"
    )
    assert os.path.normpath(state.camera_files[0].xml_path) == os.path.normpath(
        new_pf + "/overhead camera/C0001M01.XML"
    )


# --- saved_at timestamp tests ---


def test_save_writes_saved_at_field(tmp_path: Path):
    state = make_state()
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    with open(filepath) as f:
        data = json.load(f)
    assert isinstance(data["saved_at"], str)
    # Round-trips through datetime.fromisoformat without raising.
    datetime.fromisoformat(data["saved_at"])


def test_save_updates_state_saved_at_in_place(tmp_path: Path):
    state = make_state()
    assert state.saved_at is None
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    assert state.saved_at is not None
    with open(filepath) as f:
        data = json.load(f)
    assert data["saved_at"] == state.saved_at


def test_load_legacy_file_without_saved_at(tmp_path: Path):
    """Pre-existing v1 JSONs that predate saved_at must load with saved_at=None."""
    state = make_state()
    filepath = tmp_path / "legacy.json"
    persistence.save_alignment(state, str(filepath))

    # Strip the saved_at key the way a pre-feature save would have produced.
    with open(filepath) as f:
        data = json.load(f)
    data.pop("saved_at", None)
    with open(filepath, "w") as f:
        json.dump(data, f)

    loaded = persistence.load_alignment(str(filepath))
    assert loaded.saved_at is None
    assert loaded.participant_id == state.participant_id


def test_round_trip_preserves_saved_at(tmp_path: Path):
    state = make_state()
    filepath = tmp_path / "align.json"
    persistence.save_alignment(state, str(filepath))
    written = state.saved_at
    loaded = persistence.load_alignment(str(filepath))
    assert loaded.saved_at == written
