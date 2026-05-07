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
    probe_x: int | None = None,
    probe_y: int | None = None,
) -> Anchor:
    return Anchor(
        midi_filename=midi_filename,
        midi_timestamp_seconds=midi_timestamp_seconds,
        camera_frame=camera_frame,
        label=label,
        probe_x=probe_x,
        probe_y=probe_y,
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
