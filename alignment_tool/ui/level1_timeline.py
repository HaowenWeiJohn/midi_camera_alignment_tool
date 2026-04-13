"""Level 1: Timeline Overview — interactive bar chart with QPainter."""
from __future__ import annotations

from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QFontMetrics, QBrush
from PyQt5.QtWidgets import QWidget, QToolTip, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton

from alignment_tool.core.models import AlignmentState
from alignment_tool.core.engine import get_effective_shift_for_camera


# Colors
MIDI_COLOR = QColor(31, 119, 180)  # tab:blue
MIDI_SELECTED = QColor(15, 70, 110)
CAMERA_COLOR = QColor(255, 127, 14)  # tab:orange
CAMERA_SELECTED = QColor(180, 80, 0)
AXIS_COLOR = QColor(80, 80, 80)
GRID_COLOR = QColor(220, 220, 220)
BG_COLOR = QColor(255, 255, 255)

# Layout constants
MARGIN_LEFT = 100
MARGIN_RIGHT = 30
MARGIN_TOP = 30
MARGIN_BOTTOM = 50
BAR_HEIGHT = 30
ROW_GAP = 20
MIDI_ROW_Y = MARGIN_TOP
CAMERA_ROW_Y = MARGIN_TOP + BAR_HEIGHT + ROW_GAP


class TimelineCanvas(QWidget):
    """Custom painted timeline bar chart."""

    pair_selected = pyqtSignal(int, int)  # (midi_index, camera_index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(CAMERA_ROW_Y + BAR_HEIGHT + MARGIN_BOTTOM)

        self._state: AlignmentState | None = None
        self._midi_rects: list[QRectF] = []
        self._camera_rects: list[QRectF] = []
        self._selected_midi: int | None = None
        self._selected_camera: int | None = None

        # View parameters
        self._t_start = 0.0  # visible time range start (seconds, relative to t0)
        self._t_end = 10000.0  # visible time range end
        self._t0 = 0.0  # reference time (first MIDI start)

        # Drag state
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_t = 0.0

    def set_state(self, state: AlignmentState):
        self._state = state
        self._selected_midi = None
        self._selected_camera = None
        self._fit_to_data()
        self.update()

    def refresh(self):
        """Recompute bar positions after state changes (e.g., global shift)."""
        self.update()

    def _fit_to_data(self):
        """Set view to show all data with some padding."""
        if self._state is None:
            return
        all_starts = []
        all_ends = []
        for mf in self._state.midi_files:
            all_starts.append(mf.unix_start)
            all_ends.append(mf.unix_end)

        midi_lookup = {mf.filename: mf for mf in self._state.midi_files}
        for cf in self._state.camera_files:
            eff = get_effective_shift_for_camera(cf, self._state.global_shift_seconds, midi_lookup)
            all_starts.append(cf.raw_unix_start + eff)
            all_ends.append(cf.raw_unix_end + eff)

        if not all_starts:
            return

        self._t0 = min(all_starts)
        t_min = 0.0
        t_max = max(all_ends) - self._t0
        padding = (t_max - t_min) * 0.05 or 100.0
        self._t_start = t_min - padding
        self._t_end = t_max + padding

    def _time_to_x(self, t_rel: float) -> float:
        """Convert relative time (seconds from t0) to pixel X."""
        plot_width = self.width() - MARGIN_LEFT - MARGIN_RIGHT
        if self._t_end <= self._t_start:
            return MARGIN_LEFT
        frac = (t_rel - self._t_start) / (self._t_end - self._t_start)
        return MARGIN_LEFT + frac * plot_width

    def _x_to_time(self, x: float) -> float:
        """Convert pixel X to relative time."""
        plot_width = self.width() - MARGIN_LEFT - MARGIN_RIGHT
        if plot_width <= 0:
            return self._t_start
        frac = (x - MARGIN_LEFT) / plot_width
        return self._t_start + frac * (self._t_end - self._t_start)

    def paintEvent(self, event):
        if self._state is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), BG_COLOR)

        midi_lookup = {mf.filename: mf for mf in self._state.midi_files}

        # Draw grid lines
        self._draw_grid(painter)

        # Draw MIDI bars
        self._midi_rects.clear()
        for i, mf in enumerate(self._state.midi_files):
            t_start_rel = mf.unix_start - self._t0
            x = self._time_to_x(t_start_rel)
            w = self._time_to_x(t_start_rel + mf.duration) - x
            rect = QRectF(x, MIDI_ROW_Y, max(w, 2), BAR_HEIGHT)
            self._midi_rects.append(rect)

            color = MIDI_SELECTED if i == self._selected_midi else MIDI_COLOR
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(130), 1))
            painter.drawRect(rect)

            # Label
            self._draw_bar_label(painter, rect, mf.filename, Qt.white)

        # Draw camera bars
        self._camera_rects.clear()
        for i, cf in enumerate(self._state.camera_files):
            eff = get_effective_shift_for_camera(cf, self._state.global_shift_seconds, midi_lookup)
            t_start_rel = cf.raw_unix_start + eff - self._t0
            x = self._time_to_x(t_start_rel)
            w = self._time_to_x(t_start_rel + cf.duration) - x
            rect = QRectF(x, CAMERA_ROW_Y, max(w, 2), BAR_HEIGHT)
            self._camera_rects.append(rect)

            color = CAMERA_SELECTED if i == self._selected_camera else CAMERA_COLOR
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(130), 1))
            painter.drawRect(rect)

            self._draw_bar_label(painter, rect, cf.filename, Qt.white)

        # Row labels
        painter.setPen(AXIS_COLOR)
        font = QFont("sans-serif", 9)
        painter.setFont(font)
        painter.drawText(5, MIDI_ROW_Y + BAR_HEIGHT // 2 + 5, "MIDI")
        painter.drawText(5, CAMERA_ROW_Y + BAR_HEIGHT // 2 + 5, "Camera")

        # Selection highlight
        if self._selected_midi is not None and self._selected_midi < len(self._midi_rects):
            self._draw_selection_border(painter, self._midi_rects[self._selected_midi])
        if self._selected_camera is not None and self._selected_camera < len(self._camera_rects):
            self._draw_selection_border(painter, self._camera_rects[self._selected_camera])

        painter.end()

    def _draw_grid(self, painter: QPainter):
        """Draw time axis with grid lines."""
        visible_duration = self._t_end - self._t_start
        if visible_duration <= 0:
            return

        # Choose tick interval
        target_ticks = 10
        raw_interval = visible_duration / target_ticks
        nice_intervals = [1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 1800, 3600]
        interval = nice_intervals[0]
        for ni in nice_intervals:
            if ni >= raw_interval:
                interval = ni
                break

        painter.setPen(QPen(GRID_COLOR, 1, Qt.DashLine))
        font = QFont("sans-serif", 8)
        painter.setFont(font)

        t = (int(self._t_start / interval) + 1) * interval
        y_bottom = CAMERA_ROW_Y + BAR_HEIGHT + 10
        while t < self._t_end:
            x = self._time_to_x(t)
            painter.setPen(QPen(GRID_COLOR, 1, Qt.DashLine))
            painter.drawLine(int(x), MARGIN_TOP, int(x), y_bottom)
            painter.setPen(AXIS_COLOR)
            label = self._format_time_label(t)
            painter.drawText(int(x) - 20, y_bottom + 15, label)
            t += interval

        # Axis label
        painter.drawText(
            self.width() // 2 - 30,
            y_bottom + 30,
            "Time (s)"
        )

    def _format_time_label(self, t: float) -> str:
        if abs(t) < 3600:
            return f"{t:.0f}"
        m, s = divmod(abs(t), 60)
        h, m = divmod(m, 60)
        sign = "-" if t < 0 else ""
        if h > 0:
            return f"{sign}{int(h)}:{int(m):02d}:{int(s):02d}"
        return f"{sign}{int(m)}:{int(s):02d}"

    def _draw_bar_label(self, painter: QPainter, rect: QRectF, text: str, color):
        """Draw filename label inside bar if it fits, otherwise skip."""
        font = QFont("sans-serif", 7)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text)
        if text_width < rect.width() - 4:
            painter.setPen(color)
            painter.drawText(
                int(rect.x() + 2),
                int(rect.y() + rect.height() / 2 + fm.ascent() / 2 - 1),
                text,
            )

    def _draw_selection_border(self, painter: QPainter, rect: QRectF):
        pen = QPen(Qt.yellow, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect.adjusted(-1, -1, 1, 1))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()

            # Check MIDI bars
            for i, rect in enumerate(self._midi_rects):
                if rect.contains(QPointF(pos)):
                    self._selected_midi = i if self._selected_midi != i else None
                    self.update()
                    return

            # Check camera bars
            for i, rect in enumerate(self._camera_rects):
                if rect.contains(QPointF(pos)):
                    self._selected_camera = i if self._selected_camera != i else None
                    self.update()
                    return

            # Click on empty space — start drag pan
            self._dragging = True
            self._drag_start_x = pos.x()
            self._drag_start_t = self._t_start

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def mouseMoveEvent(self, event):
        pos = event.pos()

        if self._dragging:
            dx = pos.x() - self._drag_start_x
            dt = dx / max(1, self.width() - MARGIN_LEFT - MARGIN_RIGHT) * (self._t_end - self._t_start)
            duration = self._t_end - self._t_start
            self._t_start = self._drag_start_t - dt
            self._t_end = self._t_start + duration
            self.update()
            return

        # Tooltips
        if self._state is None:
            return
        midi_lookup = {mf.filename: mf for mf in self._state.midi_files}

        for i, rect in enumerate(self._midi_rects):
            if rect.contains(QPointF(pos)):
                mf = self._state.midi_files[i]
                QToolTip.showText(event.globalPos(),
                    f"{mf.filename}\n"
                    f"Duration: {mf.duration:.1f}s\n"
                    f"Start: {mf.unix_start:.1f}\n"
                    f"End: {mf.unix_end:.1f}")
                return

        for i, rect in enumerate(self._camera_rects):
            if rect.contains(QPointF(pos)):
                cf = self._state.camera_files[i]
                eff = get_effective_shift_for_camera(cf, self._state.global_shift_seconds, midi_lookup)
                QToolTip.showText(event.globalPos(),
                    f"{cf.filename}\n"
                    f"Duration: {cf.duration:.1f}s\n"
                    f"Raw start: {cf.raw_unix_start:.1f}\n"
                    f"Aligned start: {cf.raw_unix_start + eff:.1f}\n"
                    f"Capture FPS: {cf.capture_fps}")
                return

        QToolTip.hideText()

    def mouseDoubleClickEvent(self, event):
        """Double-click with both selected = drill into Level 2."""
        if self._selected_midi is not None and self._selected_camera is not None:
            self.pair_selected.emit(self._selected_midi, self._selected_camera)

    def wheelEvent(self, event):
        """Scroll wheel zooms in/out around mouse position."""
        delta = event.angleDelta().y()
        if delta == 0:
            return

        mouse_t = self._x_to_time(event.pos().x())
        factor = 0.8 if delta > 0 else 1.25  # zoom in / out

        new_start = mouse_t + (self._t_start - mouse_t) * factor
        new_end = mouse_t + (self._t_end - mouse_t) * factor

        # Prevent extreme zoom
        if new_end - new_start < 1.0:
            return
        if new_end - new_start > 100000.0:
            return

        self._t_start = new_start
        self._t_end = new_end
        self.update()

    @property
    def selected_midi_index(self) -> int | None:
        return self._selected_midi

    @property
    def selected_camera_index(self) -> int | None:
        return self._selected_camera


class Level1Widget(QWidget):
    """Level 1 container: global shift controls + timeline canvas."""

    pair_selected = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Global shift controls
        shift_layout = QHBoxLayout()
        shift_layout.addWidget(QLabel("Global Shift (s):"))
        self._shift_spin = QDoubleSpinBox()
        self._shift_spin.setRange(-100000, 100000)
        self._shift_spin.setDecimals(3)
        self._shift_spin.setSingleStep(0.1)
        shift_layout.addWidget(self._shift_spin)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply_shift)
        shift_layout.addWidget(self._apply_btn)

        self._open_pair_btn = QPushButton("Open Selected Pair")
        self._open_pair_btn.clicked.connect(self._on_open_pair)
        shift_layout.addWidget(self._open_pair_btn)

        shift_layout.addStretch()
        layout.addLayout(shift_layout)

        # Timeline canvas
        self._canvas = TimelineCanvas()
        self._canvas.pair_selected.connect(self.pair_selected.emit)
        layout.addWidget(self._canvas, stretch=1)

        self._state: AlignmentState | None = None

    def set_state(self, state: AlignmentState):
        self._state = state
        self._shift_spin.setValue(state.global_shift_seconds)
        self._canvas.set_state(state)

    def refresh(self):
        if self._state is not None:
            self._shift_spin.setValue(self._state.global_shift_seconds)
        self._canvas.refresh()

    def _on_apply_shift(self):
        if self._state is None:
            return
        new_shift = self._shift_spin.value()
        if new_shift == self._state.global_shift_seconds:
            return

        # Check for existing anchors
        anchor_count = self._state.total_anchor_count()
        clip_count = self._state.clips_with_anchors_count()
        if anchor_count > 0:
            from PyQt5.QtWidgets import QMessageBox
            result = QMessageBox.warning(
                self, "Confirm Global Shift Change",
                f"Changing global shift will remove all {anchor_count} anchor(s) "
                f"across {clip_count} camera clip(s).\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result != QMessageBox.Yes:
                self._shift_spin.setValue(self._state.global_shift_seconds)
                return
            self._state.clear_all_anchors()

        self._state.global_shift_seconds = new_shift
        self._canvas.refresh()

    def _on_open_pair(self):
        mi = self._canvas.selected_midi_index
        ci = self._canvas.selected_camera_index
        if mi is not None and ci is not None:
            self.pair_selected.emit(mi, ci)
