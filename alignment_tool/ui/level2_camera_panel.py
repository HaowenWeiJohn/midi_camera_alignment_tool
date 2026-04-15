"""Camera panel — displays video frames with frame-by-frame navigation."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QThread, QPointF
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QBrush, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout

from alignment_tool.core.models import CameraFileInfo
from alignment_tool.io.frame_worker import FrameWorker


class CameraPanelWidget(QWidget):
    """Video frame display panel for Level 2."""

    position_changed = pyqtSignal(int)  # emits current frame index
    user_interacted = pyqtSignal()      # emitted on direct user click; stays silent for programmatic updates
    dot_dropped = pyqtSignal(int, int, int)  # (source_x, source_y, center_frame)
    dot_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Plain QWidgets need WA_StyledBackground + an object-name selector
        # to reliably render stylesheet borders without cascading to children.
        self.setObjectName("cameraPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._camera_info: CameraFileInfo | None = None
        self._current_frame: int = 0
        self._pending_frame: int = -1

        # Source-frame dimensions cached from the first decoded frame; used to
        # translate right-click coords back to the original video's pixel grid.
        self._source_w: int = 0
        self._source_h: int = 0

        # Intensity-probe dot state. Single dot; replaced on each right-click.
        self._dot_source_xy: tuple[int, int] | None = None
        self._dot_center_frame: int | None = None

        # Frame display
        self._frame_label = QLabel()
        self._frame_label.setAlignment(Qt.AlignCenter)
        self._frame_label.setMinimumSize(320, 240)
        self._frame_label.setStyleSheet("background-color: #222;")

        # Frame counter
        self._counter_label = QLabel("No video loaded")
        self._counter_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._frame_label, stretch=1)
        layout.addWidget(self._counter_label)

        # Background worker
        self._worker_thread = QThread()
        self._worker = FrameWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker.open_failed.connect(self._on_worker_open_failed)
        self._worker_thread.start()

    def load_video(self, camera_info: CameraFileInfo):
        """Open a video for display."""
        # Drop any probe dot from the previous clip before swapping videos so
        # the stale pixel coordinate can't be applied to a different image.
        self._clear_dot(emit=True)
        self._camera_info = camera_info
        self._current_frame = 0
        self._source_w = 0
        self._source_h = 0
        self._worker.open_video(camera_info.mp4_path)
        self._request_frame(0)

    def set_frame(self, frame: int):
        """Navigate to a specific frame."""
        if self._camera_info is None:
            return
        frame = max(0, min(frame, self._camera_info.total_frames - 1))
        if frame == self._current_frame:
            return
        self._current_frame = frame
        self._request_frame(frame)
        self.position_changed.emit(frame)

    def step(self, delta: int):
        """Step by delta frames."""
        self.set_frame(self._current_frame + delta)

    @property
    def current_frame(self) -> int:
        return self._current_frame

    def _request_frame(self, frame: int):
        self._pending_frame = frame
        self._update_counter()
        self._worker.request_frame(frame)

    def _on_frame_ready(self, frame_index: int, qimg: QImage):
        # Only display if this is still the requested frame
        if frame_index != self._current_frame:
            return
        # Cache the source frame dimensions so contextMenuEvent can map a
        # click back to a pixel coordinate. CameraFileInfo does not store
        # width/height, so we learn them from the first decoded frame.
        self._source_w = qimg.width()
        self._source_h = qimg.height()
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._frame_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        if self._dot_source_xy is not None:
            self._paint_dot_on_pixmap(scaled)
        self._frame_label.setPixmap(scaled)

    def _paint_dot_on_pixmap(self, pixmap: QPixmap) -> None:
        """Overlay the probe dot at its scaled position on the given pixmap."""
        if self._dot_source_xy is None:
            return
        if self._source_w <= 0 or self._source_h <= 0:
            return
        sx, sy = self._dot_source_xy
        dw = pixmap.width()
        dh = pixmap.height()
        if dw <= 0 or dh <= 0:
            return
        dx = (sx + 0.5) / self._source_w * dw
        dy = (sy + 0.5) / self._source_h * dh
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QBrush(QColor(255, 60, 60, 220)))
        painter.drawEllipse(QPointF(dx, dy), 5.0, 5.0)
        painter.end()

    def contextMenuEvent(self, event):
        """Right-click drops the intensity-probe dot at the clicked pixel."""
        if self._camera_info is None or self._source_w <= 0 or self._source_h <= 0:
            event.ignore()
            return
        pm = self._frame_label.pixmap()
        if pm is None or pm.isNull():
            # QLabel is showing OOR text / placeholder, not a frame — skip.
            event.ignore()
            return
        label_pos = self._frame_label.mapFromParent(event.pos())
        lx, ly = label_pos.x(), label_pos.y()
        lw = self._frame_label.width()
        lh = self._frame_label.height()
        sw, sh = self._source_w, self._source_h
        if sw <= 0 or sh <= 0 or lw <= 0 or lh <= 0:
            event.ignore()
            return
        scale = min(lw / sw, lh / sh)
        if scale <= 0:
            event.ignore()
            return
        dw = sw * scale
        dh = sh * scale
        ox = (lw - dw) / 2.0
        oy = (lh - dh) / 2.0
        if lx < ox or ly < oy or lx > ox + dw or ly > oy + dh:
            # Click landed in the letterbox bands, not on the image.
            event.accept()
            return
        src_x = int((lx - ox) / scale)
        src_y = int((ly - oy) / scale)
        src_x = max(0, min(src_x, sw - 1))
        src_y = max(0, min(src_y, sh - 1))
        self._dot_source_xy = (src_x, src_y)
        self._dot_center_frame = self._current_frame
        self.dot_dropped.emit(src_x, src_y, self._current_frame)
        # Re-apply the current frame so the overlay paints without waiting for
        # the next scrub; cache hit makes this effectively instant.
        self._request_frame(self._current_frame)
        event.accept()

    def clear_dot(self) -> None:
        """Public hook so external callers can drop the current probe dot."""
        self._clear_dot(emit=True)

    def _clear_dot(self, *, emit: bool) -> None:
        if self._dot_source_xy is None and self._dot_center_frame is None:
            return
        self._dot_source_xy = None
        self._dot_center_frame = None
        if emit:
            self.dot_cleared.emit()
        if self._camera_info is not None:
            # Re-request the current frame so the overlay is repainted clean.
            self._request_frame(self._current_frame)

    def _update_counter(self):
        if self._camera_info is None:
            self._counter_label.setText("No video loaded")
            return
        total = self._camera_info.total_frames
        # Frame counter is 0-indexed with max shown as total_frames - 1, matching
        # the marker label ("Camera mark: frame N (T.TTTs)") and the anchor
        # table's Camera Frame column. Time is frame-centric too: the max time
        # is the time of the last frame, (total - 1) / fps, not the clip
        # wall-clock duration total / fps.
        max_index = max(0, total - 1)
        fps = self._camera_info.capture_fps
        time_s = self._current_frame / fps
        max_time_s = max_index / fps
        self._counter_label.setText(
            f"Frame: {self._current_frame} / {max_index}  |  "
            f"Time: {time_s:.3f}s / {max_time_s:.3f}s"
        )

    def show_out_of_range(self, message: str):
        """Show a gray panel with an out-of-range message."""
        self._frame_label.clear()
        self._frame_label.setText(message)
        self._frame_label.setStyleSheet("background-color: #555; color: white; font-size: 14px;")

    def show_normal(self):
        """Restore normal display mode."""
        self._frame_label.setStyleSheet("background-color: #222;")
        # Re-request current frame so that any OOR text placeholder is replaced
        # by a pixmap (QLabel holds text OR pixmap, not both). On a cache hit
        # this is effectively instant; on a cache miss the existing pixmap (if
        # any) remains visible during the async fetch, so there is no flicker
        # even on a Normal → Normal transition.
        if self._camera_info is not None:
            self._request_frame(self._current_frame)

    def _on_worker_open_failed(self, msg: str) -> None:
        self._frame_label.setStyleSheet("background: #7a1f1f; color: white;")
        self._frame_label.setText(f"Video unavailable:\n{msg}")

    def cleanup(self):
        """Release resources."""
        self._worker.close_video()
        self._worker_thread.quit()
        self._worker_thread.wait(2000)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.user_interacted.emit()
        super().mousePressEvent(event)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
