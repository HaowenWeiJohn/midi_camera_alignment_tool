"""Pure functions for all alignment time-math.

No Qt dependency — this module can be tested independently.
"""
from __future__ import annotations

from alignment_tool.models import Anchor, CameraFileInfo, MidiFileInfo


def compute_anchor_shift(
    anchor: Anchor,
    camera: CameraFileInfo,
    midi: MidiFileInfo,
    global_shift: float,
) -> float:
    """Derive anchor_shift from an anchor pair.

    anchor_shift = (midi_unix_start + midi_timestamp_seconds)
                 - (raw_camera_unix_start + camera_frame / capture_fps)
                 - global_shift
    """
    midi_unix_at_anchor = midi.unix_start + anchor.midi_timestamp_seconds
    camera_unix_at_anchor = camera.raw_unix_start + anchor.camera_frame / camera.capture_fps
    return midi_unix_at_anchor - camera_unix_at_anchor - global_shift


def compute_effective_shift(global_shift: float, anchor_shift: float) -> float:
    """effective_shift = global_shift + anchor_shift"""
    return global_shift + anchor_shift


def get_effective_shift_for_camera(
    camera: CameraFileInfo,
    global_shift: float,
    midi_files: dict[str, MidiFileInfo],
) -> float:
    """Get the total effective shift for a camera file, considering its active anchor."""
    anchor = camera.get_active_anchor()
    if anchor is None:
        return global_shift
    midi = midi_files.get(anchor.midi_filename)
    if midi is None:
        return global_shift
    a_shift = compute_anchor_shift(anchor, camera, midi, global_shift)
    return compute_effective_shift(global_shift, a_shift)


def midi_unix_to_camera_frame(
    midi_unix: float,
    effective_shift: float,
    camera: CameraFileInfo,
) -> int | None:
    """Locked mode: MIDI drives camera.

    Returns frame index (rounded to nearest int), or None if out of range.
    """
    camera_unix = midi_unix - effective_shift
    frame_float = (camera_unix - camera.raw_unix_start) * camera.capture_fps
    frame = round(frame_float)
    if frame < 0 or frame >= camera.total_frames:
        return None
    return frame


def camera_frame_to_midi_seconds(
    frame: int,
    effective_shift: float,
    camera: CameraFileInfo,
    midi: MidiFileInfo,
) -> float | None:
    """Locked mode: camera drives MIDI.

    Returns seconds-from-MIDI-file-start, or None if out of range.
    """
    camera_unix = camera.raw_unix_start + frame / camera.capture_fps
    midi_unix = camera_unix + effective_shift
    midi_seconds = midi_unix - midi.unix_start
    if midi_seconds < 0 or midi_seconds > midi.duration:
        return None
    return midi_seconds


def camera_frame_to_unix(frame: int, camera: CameraFileInfo) -> float:
    """Convert camera frame index to unix timestamp."""
    return camera.raw_unix_start + frame / camera.capture_fps


def midi_seconds_to_unix(seconds_from_start: float, midi: MidiFileInfo) -> float:
    """Convert MIDI-file-relative seconds to unix timestamp."""
    return midi.unix_start + seconds_from_start


def compute_global_shift_from_markers(midi_unix: float, camera_unix: float) -> float:
    """global_shift = midi_unix - camera_unix"""
    return midi_unix - camera_unix


def out_of_range_delta(
    midi_unix: float,
    effective_shift: float,
    camera: CameraFileInfo,
) -> float | None:
    """If camera frame would be out of range, return signed delta in seconds.

    Positive = camera clip hasn't started yet (starts in X s).
    Negative = camera clip already ended (ended X s ago).
    None = in range.
    """
    camera_unix = midi_unix - effective_shift
    if camera_unix < camera.raw_unix_start:
        return camera.raw_unix_start - camera_unix  # positive: starts in X s
    if camera_unix > camera.raw_unix_end:
        return camera.raw_unix_end - camera_unix  # negative: ended X s ago
    return None
