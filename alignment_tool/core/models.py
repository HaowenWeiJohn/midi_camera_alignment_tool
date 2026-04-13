from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Anchor:
    midi_filename: str
    midi_timestamp_seconds: float  # seconds from MIDI file start
    camera_frame: int  # 0-indexed cv2 frame index
    label: str = ""


@dataclass
class CameraFileInfo:
    filename: str  # e.g. "C0001.MP4"
    xml_filename: str  # e.g. "C0001M01.XML"
    raw_unix_start: float
    raw_unix_end: float
    duration: float  # seconds (duration_frames / capture_fps)
    capture_fps: float  # ~239.76
    total_frames: int  # from cv2 frame count
    mp4_path: str = ""  # full path for video access
    xml_path: str = ""  # full path for XML
    alignment_anchors: list[Anchor] = field(default_factory=list)
    active_anchor_index: int | None = None

    def get_active_anchor(self) -> Anchor | None:
        if self.active_anchor_index is not None and 0 <= self.active_anchor_index < len(self.alignment_anchors):
            return self.alignment_anchors[self.active_anchor_index]
        return None


@dataclass
class MidiFileInfo:
    filename: str
    unix_start: float
    unix_end: float
    duration: float
    sample_rate: float  # 1 / time_resolution (~1920)
    ticks_per_beat: int = 0
    tempo: float = 500000.0  # microseconds per beat (default 120 BPM)
    file_path: str = ""  # full path for later re-loading


@dataclass
class AlignmentState:
    participant_id: str
    participant_folder: str
    global_shift_seconds: float = 0.0
    midi_files: list[MidiFileInfo] = field(default_factory=list)
    camera_files: list[CameraFileInfo] = field(default_factory=list)
    alignment_notes: str = ""

    def midi_file_by_name(self, filename: str) -> MidiFileInfo | None:
        for mf in self.midi_files:
            if mf.filename == filename:
                return mf
        return None

    def total_anchor_count(self) -> int:
        return sum(len(cf.alignment_anchors) for cf in self.camera_files)

    def clips_with_anchors_count(self) -> int:
        return sum(1 for cf in self.camera_files if cf.alignment_anchors)
