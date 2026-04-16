"""Single write boundary for AlignmentState. Qt-free."""
from __future__ import annotations

from dataclasses import dataclass

from alignment_tool.core import engine
from alignment_tool.core.errors import (
    AnchorsExistError, InvalidAnchorError, UnknownMidiFileError,
)
from alignment_tool.core.models import (
    AlignmentState, Anchor,
)


@dataclass(frozen=True)
class ShiftChangeResult:
    previous_shift: float
    cleared_anchor_count: int


class AlignmentService:
    def __init__(self, state: AlignmentState) -> None:
        self._state = state

    # --- global shift ---

    def set_global_shift(
        self, value: float, *, clear_anchors_if_needed: bool,
    ) -> ShiftChangeResult:
        existing = self._state.total_anchor_count()
        previous = self._state.global_shift_seconds

        if existing > 0 and not clear_anchors_if_needed:
            raise AnchorsExistError(count=existing)

        cleared = 0
        if existing > 0:
            for cf in self._state.camera_files:
                cleared += len(cf.alignment_anchors)
                cf.alignment_anchors.clear()
                cf.active_anchor_index = None

        self._state.global_shift_seconds = value
        return ShiftChangeResult(previous_shift=previous, cleared_anchor_count=cleared)

    # --- anchors ---

    def add_anchor(self, camera_index: int, anchor: Anchor) -> int:
        cf = self._get_camera(camera_index)
        if self._state.midi_file_by_name(anchor.midi_filename) is None:
            raise UnknownMidiFileError(anchor.midi_filename)
        cf.alignment_anchors.append(anchor)
        return len(cf.alignment_anchors) - 1

    def delete_anchor(self, camera_index: int, anchor_index: int) -> None:
        cf = self._get_camera(camera_index)
        if not (0 <= anchor_index < len(cf.alignment_anchors)):
            raise InvalidAnchorError(
                f"anchor_index {anchor_index} out of range for camera {camera_index}",
            )
        del cf.alignment_anchors[anchor_index]

        active = cf.active_anchor_index
        if active is None:
            return
        if active == anchor_index:
            cf.active_anchor_index = None
        elif active > anchor_index:
            cf.active_anchor_index = active - 1

    def set_active_anchor(
        self, camera_index: int, anchor_index: int | None,
    ) -> None:
        cf = self._get_camera(camera_index)
        if anchor_index is None:
            cf.active_anchor_index = None
            return
        if not (0 <= anchor_index < len(cf.alignment_anchors)):
            raise InvalidAnchorError(
                f"anchor_index {anchor_index} out of range",
            )
        cf.active_anchor_index = anchor_index

    def clear_active_anchor(self) -> None:
        """Clear active anchor on every camera clip. Session-only state."""
        for cf in self._state.camera_files:
            cf.active_anchor_index = None

    # --- pure reads ---

    def effective_shift_for(self, camera_index: int) -> float:
        cf = self._get_camera(camera_index)
        midi_map = {m.filename: m for m in self._state.midi_files}
        return engine.get_effective_shift_for_camera(
            cf, self._state.global_shift_seconds, midi_map,
        )

    def anchor_shift_for(
        self, camera_index: int, anchor_index: int,
    ) -> float | None:
        cf = self._get_camera(camera_index)
        if not (0 <= anchor_index < len(cf.alignment_anchors)):
            return None
        anchor = cf.alignment_anchors[anchor_index]
        midi = self._state.midi_file_by_name(anchor.midi_filename)
        if midi is None:
            return None
        return engine.compute_anchor_shift(
            anchor, cf, midi, self._state.global_shift_seconds,
        )

    # --- internal ---

    def _get_camera(self, camera_index: int):
        if not (0 <= camera_index < len(self._state.camera_files)):
            raise InvalidAnchorError(
                f"camera_index {camera_index} out of range",
            )
        return self._state.camera_files[camera_index]
