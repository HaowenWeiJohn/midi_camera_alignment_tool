"""MIDI panel — falling keys visualization with QPainter."""
from __future__ import annotations

import bisect

from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from alignment_tool.core.models import MidiFileInfo
from alignment_tool.io.midi_adapter import MidiAdapter, MIDI_TO_NOTE

# Piano keyboard constants
PIANO_HEIGHT = 40
MIN_PITCH = 21  # A0
MAX_PITCH = 108  # C8
NUM_KEYS = MAX_PITCH - MIN_PITCH + 1

# Colors
BG_COLOR = QColor(30, 30, 35)
PLAYHEAD_COLOR = QColor(255, 80, 80)
GRID_COLOR = QColor(60, 60, 65)
WHITE_KEY_COLOR = QColor(240, 240, 240)
BLACK_KEY_COLOR = QColor(40, 40, 40)
BLACK_KEY_PRESSED = QColor(80, 80, 80)

# Velocity colormap: soft=blue, medium=green, loud=red
VEL_COLORS = [
    (0, QColor(60, 100, 200)),    # soft: blue
    (64, QColor(60, 200, 100)),   # medium: green
    (100, QColor(255, 200, 50)),  # loud-ish: yellow
    (127, QColor(255, 60, 60)),   # loud: red
]


def _velocity_color(velocity: int) -> QColor:
    """Interpolate velocity to a color."""
    for i in range(len(VEL_COLORS) - 1):
        v0, c0 = VEL_COLORS[i]
        v1, c1 = VEL_COLORS[i + 1]
        if velocity <= v1:
            t = (velocity - v0) / max(1, v1 - v0)
            r = int(c0.red() + t * (c1.red() - c0.red()))
            g = int(c0.green() + t * (c1.green() - c0.green()))
            b = int(c0.blue() + t * (c1.blue() - c0.blue()))
            return QColor(r, g, b)
    return VEL_COLORS[-1][1]


def _is_black_key(pitch: int) -> bool:
    return (pitch % 12) in {1, 3, 6, 8, 10}


class NoteData:
    """Pre-processed note data for efficient rendering."""

    def __init__(self):
        self.starts: list[float] = []  # sorted by start time
        self.ends: list[float] = []
        self.pitches: list[int] = []
        self.velocities: list[int] = []

    def load_from_adapter(self, adapter: MidiAdapter):
        notes = adapter.notes
        # Sort by start time for binary search
        notes_sorted = sorted(notes, key=lambda n: n.start)
        self.starts = [n.start for n in notes_sorted]
        self.ends = [n.end for n in notes_sorted]
        self.pitches = [n.pitch for n in notes_sorted]
        self.velocities = [n.velocity for n in notes_sorted]

    def visible_range(self, t_min: float, t_max: float) -> range:
        """Return index range of notes that could be visible in [t_min, t_max]."""
        # Notes visible if: note.start < t_max AND note.end > t_min
        i_start = bisect.bisect_left(self.starts, t_min)
        # Go back to catch notes that started before t_min but end after it
        while i_start > 0 and self.ends[i_start - 1] > t_min:
            i_start -= 1
        i_end = bisect.bisect_right(self.starts, t_max)
        return range(i_start, i_end)


class MidiCanvasWidget(QWidget):
    """Custom-painted falling keys display."""

    position_changed = pyqtSignal(float)  # current time in seconds from file start
    user_interacted = pyqtSignal()        # direct user input (mouse/wheel); programmatic updates don't emit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)

        self._note_data = NoteData()
        self._midi_info: MidiFileInfo | None = None
        self._time_resolution: float = 1.0 / 1920  # seconds per tick

        # View state
        self._current_time: float = 0.0  # playhead position (seconds from file start)
        self._seconds_per_viewport: float = 5.0  # how many seconds visible in the viewport
        self._playhead_frac: float = 0.75  # playhead at 75% from top

        # Drag state
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_time = 0.0

    def load_midi(self, midi_info: MidiFileInfo, adapter: MidiAdapter):
        """Load MIDI data for display."""
        self._midi_info = midi_info
        self._time_resolution = adapter.time_resolution
        self._note_data = NoteData()
        self._note_data.load_from_adapter(adapter)
        self._current_time = 0.0
        self.update()

    def set_position(self, time_seconds: float):
        """Set playhead to a specific time."""
        if self._midi_info is None:
            return
        time_seconds = max(0.0, min(time_seconds, self._midi_info.duration))
        if time_seconds == self._current_time:
            return
        self._current_time = time_seconds
        self.update()
        self.position_changed.emit(time_seconds)

    def step_ticks(self, ticks: int):
        """Step by N ticks."""
        self.set_position(self._current_time + ticks * self._time_resolution)

    @property
    def current_time(self) -> float:
        return self._current_time

    @property
    def midi_info(self) -> MidiFileInfo | None:
        return self._midi_info

    def _pitch_to_x(self, pitch: int) -> tuple[float, float]:
        """Convert MIDI pitch to (x, width) in pixels."""
        plot_width = self.width()
        key_width = plot_width / NUM_KEYS
        idx = pitch - MIN_PITCH
        return idx * key_width, key_width

    def _time_to_y(self, t: float) -> float:
        """Convert time to Y pixel. Current time is at playhead_frac from top."""
        canvas_height = self.height() - PIANO_HEIGHT
        if canvas_height <= 0 or self._seconds_per_viewport <= 0:
            return 0
        playhead_y = canvas_height * self._playhead_frac
        dt = t - self._current_time
        pixels_per_second = canvas_height / self._seconds_per_viewport
        # Time increases downward (notes fall toward playhead)
        return playhead_y - dt * pixels_per_second

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), BG_COLOR)

        canvas_height = self.height() - PIANO_HEIGHT

        if self._midi_info is None or canvas_height <= 0:
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "No MIDI loaded")
            painter.end()
            return

        # Compute visible time range
        playhead_y = canvas_height * self._playhead_frac
        pps = canvas_height / self._seconds_per_viewport
        t_top = self._current_time + playhead_y / pps  # time at y=0 (future)
        t_bottom = self._current_time - (canvas_height - playhead_y) / pps  # time at y=canvas_height (past)

        # Draw horizontal grid lines (every 0.5s)
        grid_interval = 0.5
        if self._seconds_per_viewport > 20:
            grid_interval = 2.0
        elif self._seconds_per_viewport > 10:
            grid_interval = 1.0

        painter.setPen(QPen(GRID_COLOR, 1))
        t_grid = int(t_bottom / grid_interval) * grid_interval
        font = QFont("monospace", 7)
        painter.setFont(font)
        while t_grid <= t_top:
            y = self._time_to_y(t_grid)
            if 0 <= y <= canvas_height:
                painter.setPen(QPen(GRID_COLOR, 1))
                painter.drawLine(0, int(y), self.width(), int(y))
                painter.setPen(QColor(100, 100, 100))
                painter.drawText(2, int(y) - 2, f"{t_grid:.1f}s")
            t_grid += grid_interval

        # Draw vertical key separators
        painter.setPen(QPen(QColor(50, 50, 55), 1))
        for pitch in range(MIN_PITCH, MAX_PITCH + 1):
            if pitch % 12 == 0:  # C notes
                x, _ = self._pitch_to_x(pitch)
                painter.drawLine(int(x), 0, int(x), canvas_height)

        # Draw notes
        visible = self._note_data.visible_range(t_bottom, t_top)
        for i in visible:
            start = self._note_data.starts[i]
            end = self._note_data.ends[i]
            pitch = self._note_data.pitches[i]
            vel = self._note_data.velocities[i]

            if pitch < MIN_PITCH or pitch > MAX_PITCH:
                continue

            x, w = self._pitch_to_x(pitch)
            y_top = self._time_to_y(end)  # end is in the future relative to start
            y_bottom = self._time_to_y(start)

            color = _velocity_color(vel)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(130), 1))

            note_rect = QRectF(x + 1, min(y_top, y_bottom), w - 2, abs(y_bottom - y_top))
            note_rect = note_rect.intersected(QRectF(0, 0, self.width(), canvas_height))
            if note_rect.height() > 0:
                painter.drawRect(note_rect)

        # Draw playhead
        painter.setPen(QPen(PLAYHEAD_COLOR, 2))
        painter.drawLine(0, int(playhead_y), self.width(), int(playhead_y))

        # Draw piano keyboard at bottom
        self._draw_piano(painter, canvas_height)

        painter.end()

    def _draw_piano(self, painter: QPainter, y_offset: int):
        """Draw piano keyboard at the bottom."""
        # White keys first
        for pitch in range(MIN_PITCH, MAX_PITCH + 1):
            if _is_black_key(pitch):
                continue
            x, w = self._pitch_to_x(pitch)
            painter.setBrush(QBrush(WHITE_KEY_COLOR))
            painter.setPen(QPen(QColor(180, 180, 180), 1))
            painter.drawRect(QRectF(x, y_offset, w, PIANO_HEIGHT))

        # Black keys on top (narrower)
        for pitch in range(MIN_PITCH, MAX_PITCH + 1):
            if not _is_black_key(pitch):
                continue
            x, w = self._pitch_to_x(pitch)
            bw = w * 0.7
            bx = x + (w - bw) / 2
            painter.setBrush(QBrush(BLACK_KEY_COLOR))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(bx, y_offset, bw, PIANO_HEIGHT * 0.65))

        # C labels
        font = QFont("sans-serif", 6)
        painter.setFont(font)
        painter.setPen(QColor(120, 120, 120))
        for octave in range(1, 9):
            pitch = 12 * (octave + 1)  # C1=24, C2=36, ...
            if MIN_PITCH <= pitch <= MAX_PITCH:
                x, w = self._pitch_to_x(pitch)
                painter.drawText(int(x + 1), y_offset + PIANO_HEIGHT - 3, f"C{octave}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.user_interacted.emit()
            self._dragging = True
            self._drag_start_y = event.pos().y()
            self._drag_start_time = self._current_time

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def mouseMoveEvent(self, event):
        if self._dragging:
            canvas_height = self.height() - PIANO_HEIGHT
            if canvas_height <= 0:
                return
            dy = event.pos().y() - self._drag_start_y
            pps = canvas_height / self._seconds_per_viewport
            dt = dy / pps  # dragging down = moving forward in time
            self.set_position(self._drag_start_time + dt)

    def wheelEvent(self, event):
        """Scroll wheel zooms time axis."""
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.user_interacted.emit()
        factor = 0.8 if delta > 0 else 1.25
        new_spv = self._seconds_per_viewport * factor
        new_spv = max(0.5, min(60.0, new_spv))
        self._seconds_per_viewport = new_spv
        self.update()


class MidiPanelWidget(QWidget):
    """MIDI panel container with canvas + info label."""

    position_changed = pyqtSignal(float)  # seconds from file start
    user_interacted = pyqtSignal()        # relayed from canvas; see MidiCanvasWidget

    def __init__(self, parent=None):
        super().__init__(parent)
        # Plain QWidgets need WA_StyledBackground + an object-name selector
        # to reliably render stylesheet borders without cascading to children.
        self.setObjectName("midiPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._canvas = MidiCanvasWidget()
        self._canvas.position_changed.connect(self._on_canvas_position_changed)
        self._canvas.user_interacted.connect(self.user_interacted)

        self._info_label = QLabel("No MIDI loaded")
        self._info_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._canvas, stretch=1)
        layout.addWidget(self._info_label)

    def load_midi(self, midi_info: MidiFileInfo, adapter: MidiAdapter):
        self._canvas.load_midi(midi_info, adapter)
        self._update_info()

    def set_position(self, time_seconds: float):
        self._canvas.set_position(time_seconds)
        self._update_info()

    def step_ticks(self, ticks: int):
        self._canvas.step_ticks(ticks)
        self._update_info()

    @property
    def current_time(self) -> float:
        return self._canvas.current_time

    @property
    def canvas(self) -> MidiCanvasWidget:
        return self._canvas

    def _on_canvas_position_changed(self, time_seconds: float):
        """Handle canvas position changes (e.g. mouse drag) — update label and relay signal."""
        self._update_info()
        self.position_changed.emit(time_seconds)

    def _update_info(self):
        mi = self._canvas.midi_info
        if mi is None:
            self._info_label.setText("No MIDI loaded")
            return
        t = self._canvas.current_time
        dur = mi.duration
        sr = mi.sample_rate
        tick = int(t * sr)
        self._info_label.setText(
            f"Time: {t:.3f}s / {dur:.1f}s  |  Tick: {tick}"
        )

    def show_out_of_range(self, message: str):
        self._canvas.hide()
        self._info_label.setText(message)

    def show_normal(self):
        self._canvas.show()
        self._update_info()
