"""Overlap indicator — clickable dual-track navigation bar.

Shows MIDI (blue, top) and camera (orange, bottom) clip extents with
overlap highlighting. Each track is clickable/draggable to navigate
its respective panel. Two independent indicators track playhead positions.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QRectF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import QWidget

from alignment_tool.core.models import MidiFileInfo, CameraFileInfo

# Layout constants
MARGIN = 10
MIDI_TRACK_TOP = 0
MIDI_TRACK_BOTTOM = 14
CAMERA_TRACK_TOP = 16
CAMERA_TRACK_BOTTOM = 30
TRACK_SPLIT_Y = 15  # y < this = MIDI, y >= this = camera


class OverlapIndicatorWidget(QWidget):
    """Clickable dual-track navigation bar with MIDI and camera indicators."""

    midi_time_clicked = pyqtSignal(float)   # midi_seconds (seconds from MIDI file start)
    camera_frame_clicked = pyqtSignal(int)  # camera frame index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)

        self._midi_info: MidiFileInfo | None = None
        self._camera_info: CameraFileInfo | None = None
        self._effective_shift: float = 0.0

        # Dual playhead positions (unix time on shared axis), or None
        self._midi_playhead: float | None = None
        self._camera_playhead: float | None = None

        # Drag state
        self._dragging_track: str | None = None  # "midi" | "camera" | None

    # --- Public API ---

    def set_clips(self, midi: MidiFileInfo, camera: CameraFileInfo, effective_shift: float):
        self._midi_info = midi
        self._camera_info = camera
        self._effective_shift = effective_shift
        self.update()

    def set_midi_playhead(self, midi_unix_time: float):
        self._midi_playhead = midi_unix_time
        self.update()

    def set_camera_playhead(self, aligned_camera_unix_time: float):
        self._camera_playhead = aligned_camera_unix_time
        self.update()

    def set_effective_shift(self, shift: float):
        self._effective_shift = shift
        self.update()

    def clear(self) -> None:
        self._midi_info = None
        self._camera_info = None
        self._effective_shift = 0.0
        self._midi_playhead = None
        self._camera_playhead = None
        self.update()

    # --- Coordinate helpers ---

    def _compute_layout(self) -> tuple | None:
        """Return (t_min, t_max, t_range, bar_w) or None if not ready."""
        if self._midi_info is None or self._camera_info is None:
            return None
        eff = self._effective_shift
        aligned_cam_start = self._camera_info.raw_unix_start + eff
        aligned_cam_end = self._camera_info.raw_unix_end + eff
        t_min = min(self._midi_info.unix_start, aligned_cam_start)
        t_max = max(self._midi_info.unix_end, aligned_cam_end)
        t_range = t_max - t_min
        if t_range <= 0:
            return None
        bar_w = self.width() - 2 * MARGIN
        if bar_w <= 0:
            return None
        return t_min, t_max, t_range, bar_w

    def _x_to_t(self, x: float) -> float | None:
        """Convert pixel x to unix timestamp on the shared axis."""
        layout = self._compute_layout()
        if layout is None:
            return None
        t_min, t_max, t_range, bar_w = layout
        return t_min + (x - MARGIN) / bar_w * t_range

    def _t_to_x(self, t: float) -> float | None:
        """Convert unix timestamp to pixel x."""
        layout = self._compute_layout()
        if layout is None:
            return None
        t_min, t_max, t_range, bar_w = layout
        return MARGIN + (t - t_min) / t_range * bar_w

    # --- Mouse events ---

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        track = "midi" if event.pos().y() < TRACK_SPLIT_Y else "camera"
        self._dragging_track = track
        self._emit_click(track, event.pos().x())

    def mouseMoveEvent(self, event):
        if self._dragging_track is not None:
            self._emit_click(self._dragging_track, event.pos().x())

    def mouseReleaseEvent(self, event):
        self._dragging_track = None

    def _emit_click(self, track: str, x: float):
        """Convert click x to a navigation signal for the given track."""
        t = self._x_to_t(x)
        if t is None:
            return

        if track == "midi":
            if self._midi_info is None:
                return
            # Inverse of engine.midi_seconds_to_unix; clamped to the clip.
            midi_seconds = t - self._midi_info.unix_start
            midi_seconds = max(0.0, min(midi_seconds, self._midi_info.duration))
            self.midi_time_clicked.emit(midi_seconds)
        else:
            if self._camera_info is None:
                return
            # Inverse of engine.camera_frame_to_unix with effective_shift applied.
            # Cannot use engine.midi_unix_to_camera_frame here: it returns None for
            # OOR, but this widget must clamp to the valid frame range so the user
            # always lands on a legal frame when dragging past the clip edges.
            camera_unix = t - self._effective_shift
            frame_float = (camera_unix - self._camera_info.raw_unix_start) * self._camera_info.capture_fps
            frame = round(frame_float)
            frame = max(0, min(frame, self._camera_info.total_frames - 1))
            self.camera_frame_clicked.emit(frame)

    # --- Painting ---

    def paintEvent(self, event):
        if self._midi_info is None or self._camera_info is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(45, 45, 50))

        midi = self._midi_info
        cam = self._camera_info
        eff = self._effective_shift

        # Aligned camera times
        aligned_cam_start = cam.raw_unix_start + eff
        aligned_cam_end = cam.raw_unix_end + eff

        # Full time range
        t_min = min(midi.unix_start, aligned_cam_start)
        t_max = max(midi.unix_end, aligned_cam_end)
        t_range = t_max - t_min
        if t_range <= 0:
            painter.end()
            return

        bar_w = self.width() - 2 * MARGIN

        def t_to_x(t):
            return MARGIN + (t - t_min) / t_range * bar_w

        # MIDI bar (blue, top half)
        midi_x1 = t_to_x(midi.unix_start)
        midi_x2 = t_to_x(midi.unix_end)
        painter.setBrush(QBrush(QColor(31, 119, 180, 180)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(midi_x1, 2, midi_x2 - midi_x1, 12))

        # Camera bar (orange, bottom half)
        cam_x1 = t_to_x(aligned_cam_start)
        cam_x2 = t_to_x(aligned_cam_end)
        painter.setBrush(QBrush(QColor(255, 127, 14, 180)))
        painter.drawRect(QRectF(cam_x1, 16, cam_x2 - cam_x1, 12))

        # Overlap region (green highlight)
        overlap_start = max(midi.unix_start, aligned_cam_start)
        overlap_end = min(midi.unix_end, aligned_cam_end)
        if overlap_start < overlap_end:
            ox1 = t_to_x(overlap_start)
            ox2 = t_to_x(overlap_end)
            painter.setBrush(QBrush(QColor(0, 200, 80, 60)))
            painter.drawRect(QRectF(ox1, 2, ox2 - ox1, 26))

        # MIDI indicator (white line on top track)
        if self._midi_playhead is not None and t_min <= self._midi_playhead <= t_max:
            px = t_to_x(self._midi_playhead)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(int(px), MIDI_TRACK_TOP, int(px), MIDI_TRACK_BOTTOM)

        # Camera indicator (white line on bottom track)
        if self._camera_playhead is not None and t_min <= self._camera_playhead <= t_max:
            px = t_to_x(self._camera_playhead)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(int(px), CAMERA_TRACK_TOP, int(px), CAMERA_TRACK_BOTTOM)

        painter.end()
