"""Overlap indicator — thin bar showing MIDI/camera temporal relationship."""
from __future__ import annotations

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import QWidget

from alignment_tool.models import MidiFileInfo, CameraFileInfo


class OverlapIndicatorWidget(QWidget):
    """Thin horizontal bar showing aligned clip overlap and playhead."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self._midi_info: MidiFileInfo | None = None
        self._camera_info: CameraFileInfo | None = None
        self._effective_shift: float = 0.0
        self._playhead_time: float = 0.0  # in MIDI-reference time

    def set_clips(self, midi: MidiFileInfo, camera: CameraFileInfo, effective_shift: float):
        self._midi_info = midi
        self._camera_info = camera
        self._effective_shift = effective_shift
        self.update()

    def set_playhead(self, midi_unix_time: float):
        self._playhead_time = midi_unix_time
        self.update()

    def set_effective_shift(self, shift: float):
        self._effective_shift = shift
        self.update()

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

        margin = 10
        bar_w = self.width() - 2 * margin

        def t_to_x(t):
            return margin + (t - t_min) / t_range * bar_w

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

        # Playhead
        if t_min <= self._playhead_time <= t_max:
            px = t_to_x(self._playhead_time)
            painter.setPen(QPen(QColor(255, 80, 80), 2))
            painter.drawLine(int(px), 0, int(px), self.height())

        painter.end()
