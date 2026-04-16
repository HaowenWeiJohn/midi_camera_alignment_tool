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
    )


def _dict_to_anchor(d: dict) -> Anchor:
    return Anchor(
        midi_filename=d["midi_filename"],
        midi_timestamp_seconds=d["midi_timestamp_seconds"],
        camera_frame=d["camera_frame"],
        label=d.get("label", ""),
    )
