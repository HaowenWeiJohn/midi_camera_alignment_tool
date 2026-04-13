"""JSON save/load for alignment state.

Follows the JSON schema specified in ALIGNMENT_TOOL_SPEC.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from alignment_tool.models import (
    AlignmentState, MidiFileInfo, CameraFileInfo, Anchor,
)


def save_alignment(state: AlignmentState, filepath: str) -> None:
    """Serialize AlignmentState to JSON."""
    data = {
        "participant_id": state.participant_id,
        "global_shift_seconds": state.global_shift_seconds,
        "midi_files": [
            {
                "filename": mf.filename,
                "unix_start": mf.unix_start,
                "unix_end": mf.unix_end,
                "duration": mf.duration,
                "sample_rate": mf.sample_rate,
            }
            for mf in state.midi_files
        ],
        "camera_files": [
            {
                "filename": cf.filename,
                "xml_filename": cf.xml_filename,
                "raw_unix_start": cf.raw_unix_start,
                "raw_unix_end": cf.raw_unix_end,
                "duration": cf.duration,
                "capture_fps": cf.capture_fps,
                "alignment_anchors": [
                    {
                        "midi_filename": a.midi_filename,
                        "midi_timestamp_seconds": a.midi_timestamp_seconds,
                        "camera_frame": a.camera_frame,
                        "label": a.label,
                    }
                    for a in cf.alignment_anchors
                ],
                "active_anchor_index": cf.active_anchor_index,
            }
            for cf in state.camera_files
        ],
        "alignment_notes": state.alignment_notes,
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_alignment(filepath: str) -> AlignmentState:
    """Deserialize AlignmentState from JSON.

    Note: file_path, mp4_path, xml_path, total_frames, ticks_per_beat, tempo
    are NOT in the JSON — they must be repopulated by re-scanning the
    participant folder if needed for Level 2 functionality.
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    midi_files = [
        MidiFileInfo(
            filename=mf["filename"],
            unix_start=mf["unix_start"],
            unix_end=mf["unix_end"],
            duration=mf["duration"],
            sample_rate=mf["sample_rate"],
        )
        for mf in data["midi_files"]
    ]

    camera_files = [
        CameraFileInfo(
            filename=cf["filename"],
            xml_filename=cf["xml_filename"],
            raw_unix_start=cf["raw_unix_start"],
            raw_unix_end=cf["raw_unix_end"],
            duration=cf["duration"],
            capture_fps=cf["capture_fps"],
            total_frames=0,  # needs re-scan for Level 2
            alignment_anchors=[
                Anchor(
                    midi_filename=a["midi_filename"],
                    midi_timestamp_seconds=a["midi_timestamp_seconds"],
                    camera_frame=a["camera_frame"],
                    label=a.get("label", ""),
                )
                for a in cf["alignment_anchors"]
            ],
            active_anchor_index=cf["active_anchor_index"],
        )
        for cf in data["camera_files"]
    ]

    return AlignmentState(
        participant_id=data["participant_id"],
        participant_folder="",  # not stored in JSON
        global_shift_seconds=data["global_shift_seconds"],
        midi_files=midi_files,
        camera_files=camera_files,
        alignment_notes=data.get("alignment_notes", ""),
    )
