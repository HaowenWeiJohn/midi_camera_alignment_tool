"""Pixel-intensity probe plot — per-frame luma around a camera pixel.

Rendered below the Level 2 splitter. Populated when the user right-clicks the
camera panel to drop a dot; sampled once, then the plot is frozen while the
camera playhead moves across it. Left-clicking the plot seeks the camera.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PyQt5.QtWidgets import QWidget


PLOT_BG = QColor(25, 25, 30)
AXIS_COLOR = QColor(150, 150, 150)
GRID_COLOR = QColor(55, 55, 60)
LINE_COLOR = QColor(80, 180, 220)
POINT_COLOR = QColor(160, 210, 240)
PLAYHEAD_COLOR = QColor(255, 80, 80)
CENTER_COLOR = QColor(120, 120, 140)
PLACEHOLDER_COLOR = QColor(140, 140, 150)

MARGIN_LEFT = 44
MARGIN_RIGHT = 12
MARGIN_TOP = 10
MARGIN_BOTTOM = 20
FIXED_HEIGHT = 120

_NICE_STEPS = [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]


class IntensityPlotWidget(QWidget):
    """Fixed-height line-plot widget for the dropped-dot intensity window."""

    frame_seek_requested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(FIXED_HEIGHT)
        self.setMouseTracking(False)

        self._first_frame: int = 0
        self._last_frame: int = 0
        self._values: list[float | None] = []
        self._center_frame: int | None = None
        self._playhead_frame: int | None = None

        self._status_text: str | None = (
            "Right-click a pixel on the camera to probe its intensity across ±120 frames."
        )

        # Cached y-range for the current sample window
        self._y_min: float = 0.0
        self._y_max: float = 1.0

    # --- Public API ---

    def set_data(
        self,
        first_frame: int,
        last_frame: int,
        values: list,
        center_frame: int,
    ) -> None:
        self._first_frame = int(first_frame)
        self._last_frame = int(last_frame)
        self._values = list(values)
        self._center_frame = int(center_frame)
        self._status_text = None
        self._recompute_y_range()
        self.update()

    def set_playhead_frame(self, frame: int | None) -> None:
        self._playhead_frame = None if frame is None else int(frame)
        self.update()

    def clear(self) -> None:
        self._values = []
        self._center_frame = None
        self._playhead_frame = None
        self._status_text = (
            "Right-click a pixel on the camera to probe its intensity across ±120 frames."
        )
        self.update()

    def show_status(self, text: str) -> None:
        self._status_text = text
        self._values = []
        self._center_frame = None
        self.update()

    # --- Helpers ---

    def _has_data(self) -> bool:
        return bool(self._values) and self._last_frame > self._first_frame

    def _recompute_y_range(self) -> None:
        vals = [v for v in self._values if v is not None]
        if not vals:
            self._y_min, self._y_max = 0.0, 1.0
            return
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-6:
            # Flat trace — pad symmetrically so the line lands mid-plot.
            pad = 1.0 if hi == 0 else max(1.0, abs(hi) * 0.05)
            self._y_min = lo - pad
            self._y_max = hi + pad
        else:
            pad = (hi - lo) * 0.1
            self._y_min = lo - pad
            self._y_max = hi + pad

    def _plot_rect(self) -> tuple[int, int, int, int]:
        x0 = MARGIN_LEFT
        y0 = MARGIN_TOP
        x1 = self.width() - MARGIN_RIGHT
        y1 = self.height() - MARGIN_BOTTOM
        return x0, y0, x1, y1

    def _frame_to_x(self, frame: float) -> float | None:
        if not self._has_data():
            return None
        x0, _, x1, _ = self._plot_rect()
        span = self._last_frame - self._first_frame
        if span <= 0 or x1 <= x0:
            return None
        return x0 + (frame - self._first_frame) / span * (x1 - x0)

    def _x_to_frame(self, x: float) -> int | None:
        if not self._has_data():
            return None
        x0, _, x1, _ = self._plot_rect()
        span = self._last_frame - self._first_frame
        if span <= 0 or x1 <= x0:
            return None
        frac = (x - x0) / (x1 - x0)
        return self._first_frame + round(frac * span)

    def _value_to_y(self, v: float) -> float:
        _, y0, _, y1 = self._plot_rect()
        span = self._y_max - self._y_min
        if span <= 0:
            return (y0 + y1) / 2
        frac = (v - self._y_min) / span
        return y1 - frac * (y1 - y0)

    def _pick_tick_step(self, span: int, target: int = 8) -> int:
        if span <= 0:
            return 1
        raw = span / target
        for step in _NICE_STEPS:
            if step >= raw:
                return step
        return _NICE_STEPS[-1]

    # --- Mouse ---

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        if not self._has_data():
            return
        x0, _, x1, _ = self._plot_rect()
        x = event.pos().x()
        if x < x0 or x > x1:
            return
        frame = self._x_to_frame(x)
        if frame is None:
            return
        # Clamp to the sampled window; the receiver will clamp again to clip bounds.
        frame = max(self._first_frame, min(frame, self._last_frame))
        self.frame_seek_requested.emit(int(frame))

    # --- Painting ---

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), PLOT_BG)

        if not self._has_data():
            painter.setPen(PLACEHOLDER_COLOR)
            painter.setFont(QFont("sans-serif", 9))
            text = self._status_text or ""
            painter.drawText(self.rect(), Qt.AlignCenter, text)
            painter.end()
            return

        x0, y0, x1, y1 = self._plot_rect()

        # Plot frame
        painter.setPen(QPen(AXIS_COLOR, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(x0, y0, x1 - x0, y1 - y0)

        # X-axis ticks (frame numbers)
        span = self._last_frame - self._first_frame
        step = self._pick_tick_step(span)
        first_tick = (self._first_frame // step + 1) * step
        painter.setFont(QFont("monospace", 7))
        tick = first_tick
        painter.setPen(QPen(GRID_COLOR, 1, Qt.DashLine))
        tick_positions: list[tuple[float, int]] = []
        while tick <= self._last_frame:
            px = self._frame_to_x(tick)
            if px is not None:
                tick_positions.append((px, tick))
                painter.drawLine(int(px), y0, int(px), y1)
            tick += step
        painter.setPen(AXIS_COLOR)
        for px, tick_val in tick_positions:
            painter.drawText(int(px) - 15, y1 + 14, str(tick_val))

        # Y-axis ticks (min, mid, max luma)
        painter.setPen(QPen(GRID_COLOR, 1, Qt.DashLine))
        y_mid = (self._y_min + self._y_max) / 2
        for v in (self._y_min, y_mid, self._y_max):
            py = self._value_to_y(v)
            painter.drawLine(x0, int(py), x1, int(py))
        painter.setPen(AXIS_COLOR)
        for v in (self._y_min, y_mid, self._y_max):
            py = self._value_to_y(v)
            painter.drawText(4, int(py) + 3, f"{v:5.1f}")

        # Center marker (where the dot was dropped)
        if self._center_frame is not None:
            cx = self._frame_to_x(self._center_frame)
            if cx is not None:
                painter.setPen(QPen(CENTER_COLOR, 1, Qt.DotLine))
                painter.drawLine(int(cx), y0, int(cx), y1)

        # Intensity polyline — break the stroke at None gaps so missing samples
        # near the clip edges don't interpolate across the gap.
        painter.setPen(QPen(LINE_COLOR, 2))
        prev_pt: tuple[float, float] | None = None
        point_fill = QBrush(POINT_COLOR)
        for idx, value in enumerate(self._values):
            if value is None:
                prev_pt = None
                continue
            frame_idx = self._first_frame + idx
            px = self._frame_to_x(frame_idx)
            if px is None:
                prev_pt = None
                continue
            py = self._value_to_y(value)
            if prev_pt is not None:
                painter.drawLine(int(prev_pt[0]), int(prev_pt[1]), int(px), int(py))
            prev_pt = (px, py)

        # Small dots at each sample — helps at low-sample density (edges).
        painter.setPen(Qt.NoPen)
        painter.setBrush(point_fill)
        for idx, value in enumerate(self._values):
            if value is None:
                continue
            frame_idx = self._first_frame + idx
            px = self._frame_to_x(frame_idx)
            if px is None:
                continue
            py = self._value_to_y(value)
            painter.drawEllipse(int(px) - 1, int(py) - 1, 3, 3)

        # Playhead — red vertical line at current camera frame, only inside window.
        if (
            self._playhead_frame is not None
            and self._first_frame <= self._playhead_frame <= self._last_frame
        ):
            px = self._frame_to_x(self._playhead_frame)
            if px is not None:
                painter.setPen(QPen(PLAYHEAD_COLOR, 2))
                painter.drawLine(int(px), y0, int(px), y1)

        painter.end()
