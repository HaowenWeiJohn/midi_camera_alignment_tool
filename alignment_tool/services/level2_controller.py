"""Qt-free controller for Level 2 view: mode, markers, sync routing."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from alignment_tool.core import engine
from alignment_tool.core.errors import MarkersNotSetError
from alignment_tool.core.models import AlignmentState, Anchor
from alignment_tool.services.alignment_service import AlignmentService


class Mode(Enum):
    FREE = auto()
    LOCKED = auto()


@dataclass(frozen=True)
class SyncOutput:
    new_midi_time: float | None
    new_camera_frame: int | None
    out_of_range_delta: float | None


class Level2Controller:
    def __init__(self, state: AlignmentState, service: AlignmentService) -> None:
        self._state = state
        self._service = service
        self._midi_index = 0
        self._camera_index = 0
        self._mode = Mode.FREE
        self._midi_marker: float | None = None     # seconds-from-midi-start
        self._camera_marker: int | None = None     # frame index

    # --- pair / mode ---

    def load_pair(self, midi_index: int, camera_index: int) -> None:
        self._midi_index = midi_index
        self._camera_index = camera_index
        self.clear_markers()

    def set_mode(self, mode: Mode) -> None:
        self._mode = mode

    @property
    def mode(self) -> Mode:
        return self._mode

    # --- sync ---

    def on_midi_position_changed(self, midi_time: float) -> SyncOutput:
        if self._mode != Mode.LOCKED:
            return SyncOutput(None, None, None)
        cf = self._state.camera_files[self._camera_index]
        midi = self._state.midi_files[self._midi_index]
        eff = self._service.effective_shift_for(self._camera_index)
        midi_unix = midi.unix_start + midi_time
        frame = engine.midi_unix_to_camera_frame(midi_unix, eff, cf)
        oor = None if frame is not None else engine.out_of_range_delta(midi_unix, eff, cf)
        return SyncOutput(new_midi_time=None, new_camera_frame=frame, out_of_range_delta=oor)

    def on_camera_position_changed(self, camera_frame: int) -> SyncOutput:
        if self._mode != Mode.LOCKED:
            return SyncOutput(None, None, None)
        cf = self._state.camera_files[self._camera_index]
        midi = self._state.midi_files[self._midi_index]
        eff = self._service.effective_shift_for(self._camera_index)
        seconds = engine.camera_frame_to_midi_seconds(camera_frame, eff, cf, midi)
        oor = (None if seconds is not None
               else engine.midi_out_of_range_delta(camera_frame, eff, cf, midi))
        return SyncOutput(new_midi_time=seconds, new_camera_frame=None, out_of_range_delta=oor)

    # --- markers ---

    def mark_midi(self, midi_time: float) -> None:
        self._midi_marker = midi_time

    def mark_camera(self, camera_frame: int) -> None:
        self._camera_marker = camera_frame

    def clear_markers(self) -> None:
        self._midi_marker = None
        self._camera_marker = None

    @property
    def midi_marker(self) -> float | None:
        return self._midi_marker

    @property
    def camera_marker(self) -> int | None:
        return self._camera_marker

    def compute_shift_from_markers(self) -> float:
        self._require_markers()
        midi = self._state.midi_files[self._midi_index]
        cam = self._state.camera_files[self._camera_index]
        midi_unix = midi.unix_start + self._midi_marker  # type: ignore[arg-type]
        camera_unix = engine.camera_frame_to_unix(self._camera_marker, cam)  # type: ignore[arg-type]
        return engine.compute_global_shift_from_markers(midi_unix, camera_unix)

    def build_anchor_from_markers(self, label: str = "") -> Anchor:
        self._require_markers()
        midi = self._state.midi_files[self._midi_index]
        return Anchor(
            midi_filename=midi.filename,
            midi_timestamp_seconds=self._midi_marker,       # type: ignore[arg-type]
            camera_frame=self._camera_marker,               # type: ignore[arg-type]
            label=label,
        )

    def _require_markers(self) -> None:
        if self._midi_marker is None or self._camera_marker is None:
            raise MarkersNotSetError()
