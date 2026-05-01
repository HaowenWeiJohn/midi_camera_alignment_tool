"""JSON save/load for AlignmentState. Schema v1: self-contained — Load alone produces a fully functional state.

Write is atomic (tempfile + os.replace). No legacy format compatibility.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from alignment_tool.core.errors import (
    CorruptAlignmentFileError, UnsupportedSchemaVersionError,
)
from alignment_tool.core.models import (
    AlignmentState, Anchor, CameraFileInfo, MidiFileInfo,
)

SCHEMA_VERSION = 1


def save_alignment(state: AlignmentState, filepath: str) -> None:
    """Serialize AlignmentState to JSON atomically. Updates state.saved_at to the wall-clock save time."""
    state.saved_at = datetime.now(timezone.utc).isoformat()
    data = _state_to_dict(state)
    target = Path(filepath)
    target_dir = target.parent if target.parent != Path("") else Path(".")

    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target_dir),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
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
        state = _dict_to_state(data)
    except (KeyError, TypeError, ValueError) as e:
        raise CorruptAlignmentFileError(filepath, f"missing/invalid field: {e}") from e
    _validate_state(state, filepath)
    return state


def rebase_paths(state: AlignmentState, new_folder: str) -> None:
    """Remap all media paths from the old participant_folder to a new one."""
    old_folder = state.participant_folder
    for mf in state.midi_files:
        mf.file_path = _rebase_one(mf.file_path, old_folder, new_folder)
    for cf in state.camera_files:
        cf.mp4_path = _rebase_one(cf.mp4_path, old_folder, new_folder)
        cf.xml_path = _rebase_one(cf.xml_path, old_folder, new_folder)
    state.participant_folder = new_folder


def _rebase_one(abs_path: str, old_folder: str, new_folder: str) -> str:
    if not abs_path:
        return abs_path
    rel = os.path.relpath(abs_path, old_folder)
    return os.path.normpath(os.path.join(new_folder, rel))


def _to_relative(abs_path: str, participant_folder: str) -> str:
    if not abs_path:
        return ""
    return os.path.relpath(abs_path, participant_folder)


def _resolve_path(stored_path: str, participant_folder: str) -> str:
    if not stored_path or os.path.isabs(stored_path):
        return stored_path
    return os.path.normpath(os.path.join(participant_folder, stored_path))


def _state_to_dict(state: AlignmentState) -> dict:
    pf = state.participant_folder
    return {
        "schema_version": SCHEMA_VERSION,
        "saved_at": state.saved_at,
        "participant_id": state.participant_id,
        "participant_folder": state.participant_folder,
        "global_shift_seconds": state.global_shift_seconds,
        "alignment_notes": state.alignment_notes,
        "midi_files": [_midi_to_dict(m, pf) for m in state.midi_files],
        "camera_files": [_camera_to_dict(c, pf) for c in state.camera_files],
    }


def _midi_to_dict(m: MidiFileInfo, participant_folder: str) -> dict:
    return {
        "filename": m.filename,
        "file_path": _to_relative(m.file_path, participant_folder),
        "unix_start": m.unix_start,
        "unix_end": m.unix_end,
        "duration": m.duration,
        "sample_rate": m.sample_rate,
        "ticks_per_beat": m.ticks_per_beat,
        "tempo": m.tempo,
    }


def _camera_to_dict(c: CameraFileInfo, participant_folder: str) -> dict:
    return {
        "filename": c.filename,
        "xml_filename": c.xml_filename,
        "mp4_path": _to_relative(c.mp4_path, participant_folder),
        "xml_path": _to_relative(c.xml_path, participant_folder),
        "raw_unix_start": c.raw_unix_start,
        "raw_unix_end": c.raw_unix_end,
        "duration": c.duration,
        "capture_fps": c.capture_fps,
        "total_frames": c.total_frames,
        "alignment_anchors": [_anchor_to_dict(a) for a in c.alignment_anchors],
    }


def _anchor_to_dict(a: Anchor) -> dict:
    return {
        "midi_filename": a.midi_filename,
        "midi_timestamp_seconds": a.midi_timestamp_seconds,
        "camera_frame": a.camera_frame,
        "label": a.label,
    }


def _dict_to_state(data: dict) -> AlignmentState:
    pf = data["participant_folder"]
    return AlignmentState(
        participant_id=data["participant_id"],
        participant_folder=pf,
        global_shift_seconds=data["global_shift_seconds"],
        alignment_notes=data.get("alignment_notes", ""),
        saved_at=data.get("saved_at"),
        midi_files=[_dict_to_midi(m, pf) for m in data["midi_files"]],
        camera_files=[_dict_to_camera(c, pf) for c in data["camera_files"]],
    )


def _dict_to_midi(d: dict, participant_folder: str) -> MidiFileInfo:
    return MidiFileInfo(
        filename=d["filename"],
        file_path=_resolve_path(d["file_path"], participant_folder),
        unix_start=d["unix_start"],
        unix_end=d["unix_end"],
        duration=d["duration"],
        sample_rate=d["sample_rate"],
        ticks_per_beat=d["ticks_per_beat"],
        tempo=d["tempo"],
    )


def _dict_to_camera(d: dict, participant_folder: str) -> CameraFileInfo:
    return CameraFileInfo(
        filename=d["filename"],
        xml_filename=d["xml_filename"],
        mp4_path=_resolve_path(d["mp4_path"], participant_folder),
        xml_path=_resolve_path(d["xml_path"], participant_folder),
        raw_unix_start=d["raw_unix_start"],
        raw_unix_end=d["raw_unix_end"],
        duration=d["duration"],
        capture_fps=d["capture_fps"],
        total_frames=d["total_frames"],
        alignment_anchors=[_dict_to_anchor(a) for a in d["alignment_anchors"]],
    )


def _dict_to_anchor(d: dict) -> Anchor:
    return Anchor(
        midi_filename=d["midi_filename"],
        midi_timestamp_seconds=d["midi_timestamp_seconds"],
        camera_frame=d["camera_frame"],
        label=d.get("label", ""),
    )


def _validate_state(state: AlignmentState, filepath: str) -> None:
    _check_finite(state.global_shift_seconds, "global_shift_seconds", filepath)
    midi_filenames = {mf.filename for mf in state.midi_files}

    for mf in state.midi_files:
        _check_finite(mf.unix_start, f"MIDI {mf.filename!r} unix_start", filepath)
        _check_finite(mf.unix_end, f"MIDI {mf.filename!r} unix_end", filepath)
        _check_finite(mf.duration, f"MIDI {mf.filename!r} duration", filepath)
        _check_finite(mf.sample_rate, f"MIDI {mf.filename!r} sample_rate", filepath)
        if mf.duration <= 0:
            raise CorruptAlignmentFileError(
                filepath, f"MIDI {mf.filename!r} has duration={mf.duration}")

    for cf in state.camera_files:
        _check_finite(cf.raw_unix_start, f"camera {cf.filename!r} raw_unix_start", filepath)
        _check_finite(cf.raw_unix_end, f"camera {cf.filename!r} raw_unix_end", filepath)
        _check_finite(cf.capture_fps, f"camera {cf.filename!r} capture_fps", filepath)
        if cf.capture_fps <= 0:
            raise CorruptAlignmentFileError(
                filepath, f"camera {cf.filename!r} has capture_fps={cf.capture_fps}")
        if cf.total_frames <= 0:
            raise CorruptAlignmentFileError(
                filepath, f"camera {cf.filename!r} has total_frames={cf.total_frames}")
        for j, anchor in enumerate(cf.alignment_anchors):
            if anchor.midi_filename not in midi_filenames:
                raise CorruptAlignmentFileError(
                    filepath,
                    f"anchor {j} on {cf.filename!r} references unknown MIDI file {anchor.midi_filename!r}")
            _check_finite(
                anchor.midi_timestamp_seconds,
                f"anchor {j} on {cf.filename!r} midi_timestamp_seconds", filepath)
            if anchor.camera_frame < 0:
                raise CorruptAlignmentFileError(
                    filepath,
                    f"anchor {j} on {cf.filename!r} has negative camera_frame={anchor.camera_frame}")


def _check_finite(value: float, field_name: str, filepath: str) -> None:
    if not math.isfinite(value):
        raise CorruptAlignmentFileError(
            filepath, f"{field_name} is {value!r} (expected finite number)")
