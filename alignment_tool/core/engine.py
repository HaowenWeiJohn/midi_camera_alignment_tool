"""Pure functions for all alignment time-math.

No Qt dependency — this module can be tested independently.
"""
from __future__ import annotations

from alignment_tool.core.errors import InvalidFpsError
from alignment_tool.core.models import Anchor, CameraFileInfo, MidiFileInfo


def _check_fps(camera: CameraFileInfo) -> None:
    if camera.capture_fps <= 0:
        raise InvalidFpsError(camera.capture_fps)


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
    _check_fps(camera)
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

    Returns a rounded frame index in ``[0, total_frames - 1]`` when the
    corresponding camera unix time lies within ``[raw_unix_start, raw_unix_end]``.
    Returns ``None`` only when truly out of range.

    Rounding can push ``frame_float`` to ``total_frames`` (e.g. when midi_unix
    is at the tail of the clip's last frame interval); we clamp rather than
    returning ``None`` so the user can actually reach the last frame when
    scrubbing MIDI near the end of the overlap. This also guards against the
    rare case where ``duration`` (XML-derived) and ``total_frames`` (cv2-derived)
    disagree by ±1 frame.
    """
    _check_fps(camera)
    camera_unix = midi_unix - effective_shift
    if camera_unix < camera.raw_unix_start or camera_unix > camera.raw_unix_end:
        return None
    frame_float = (camera_unix - camera.raw_unix_start) * camera.capture_fps
    frame = round(frame_float)
    return max(0, min(frame, camera.total_frames - 1))


def camera_frame_to_midi_seconds(
    frame: int,
    effective_shift: float,
    camera: CameraFileInfo,
    midi: MidiFileInfo,
) -> float | None:
    """Locked mode: camera drives MIDI.

    Returns seconds-from-MIDI-file-start, or None if out of range.
    """
    _check_fps(camera)
    camera_unix = camera.raw_unix_start + frame / camera.capture_fps
    midi_unix = camera_unix + effective_shift
    midi_seconds = midi_unix - midi.unix_start
    if midi_seconds < 0 or midi_seconds > midi.duration:
        return None
    return midi_seconds


def camera_frame_to_unix(frame: int, camera: CameraFileInfo) -> float:
    """Convert camera frame index to unix timestamp."""
    _check_fps(camera)
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


def midi_out_of_range_delta(
    frame: int,
    effective_shift: float,
    camera: CameraFileInfo,
    midi: MidiFileInfo,
) -> float | None:
    """If camera frame maps to a moment outside the MIDI file's range, return signed delta in seconds.

    Positive = MIDI file hasn't started yet (starts in X s).
    Negative = MIDI file already ended (ended X s ago).
    None = in range.
    """
    _check_fps(camera)
    camera_unix = camera.raw_unix_start + frame / camera.capture_fps
    midi_unix = camera_unix + effective_shift
    midi_seconds = midi_unix - midi.unix_start
    if midi_seconds < 0:
        return -midi_seconds
    if midi_seconds > midi.duration:
        return midi.duration - midi_seconds
    return None
