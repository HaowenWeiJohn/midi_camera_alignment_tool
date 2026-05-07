"""Camera panel — displays video frames with zoom, pan, and frame-by-frame navigation."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QThread, QPointF, QRectF, QPoint
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QBrush, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

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

        # Full-resolution decoded frame for on-demand rendering.
        self._source_image: QImage | None = None

        # Zoom/pan state. zoom=1.0 means fit-to-label. pan is in source pixels.
        self._zoom: float = 1.0
        self._pan: QPointF = QPointF(0.0, 0.0)
        self._dragging: bool = False
        self._drag_start: QPoint | None = None
        self._drag_pan_start: QPointF | None = None

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

    # --- Public API ---

    def load_video(self, camera_info: CameraFileInfo):
        """Open a video for display."""
        self._clear_dot(emit=True)
        self._camera_info = camera_info
        self._current_frame = 0
        self._source_w = 0
        self._source_h = 0
        self._source_image = None
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
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

    def close_video(self) -> None:
        """Release the video capture without opening a new one."""
        self._worker.close_video()
        self._camera_info = None
        self._current_frame = 0
        self._source_w = 0
        self._source_h = 0
        self._source_image = None
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._dot_source_xy = None
        self._dot_center_frame = None
        self._frame_label.clear()
        self._counter_label.setText("No video loaded")

    def clear_dot(self) -> None:
        """Public hook so external callers can drop the current probe dot."""
        self._clear_dot(emit=True)

    def drop_dot(self, src_x: int, src_y: int) -> None:
        """Drop a probe dot at the given source-pixel coords on the current frame.

        Mirrors the right-click pathway: clamps to the source image bounds, sets
        the dot, emits ``dot_dropped`` so the intensity worker re-samples around
        the current frame. No-op until a frame has been decoded (we need
        _source_w/_source_h to clamp meaningfully).
        """
        if self._camera_info is None or self._source_w <= 0 or self._source_h <= 0:
            return
        if self._source_image is None:
            return
        clamped_x = max(0, min(int(src_x), self._source_w - 1))
        clamped_y = max(0, min(int(src_y), self._source_h - 1))
        self._drop_dot(clamped_x, clamped_y)

    @property
    def current_dot_xy(self) -> tuple[int, int] | None:
        """Source-pixel coords of the active probe dot, or None."""
        return self._dot_source_xy

    def show_out_of_range(self, message: str):
        """Show a gray panel with an out-of-range message."""
        self._frame_label.clear()
        self._frame_label.setText(message)
        self._frame_label.setStyleSheet("background-color: #555; color: white; font-size: 14px;")

    def show_normal(self):
        """Restore normal display mode."""
        self._frame_label.setStyleSheet("background-color: #222;")
        if self._source_image is not None:
            self._render_frame()
        elif self._camera_info is not None:
            self._request_frame(self._current_frame)

    def cleanup(self):
        """Release resources."""
        self._worker.close_video()
        self._worker_thread.quit()
        self._worker_thread.wait(2000)

    # --- Rendering ---

    def _request_frame(self, frame: int):
        self._pending_frame = frame
        self._update_counter()
        self._worker.request_frame(frame)

    def _on_frame_ready(self, frame_index: int, qimg: QImage):
        if frame_index != self._current_frame:
            return
        self._source_w = qimg.width()
        self._source_h = qimg.height()
        self._source_image = qimg
        self._render_frame()

    def _render_frame(self) -> None:
        """Scale and paint the current source image with zoom/pan and probe dot."""
        if self._source_image is None:
            return
        label_w = self._frame_label.width()
        label_h = self._frame_label.height()
        if label_w <= 0 or label_h <= 0:
            return
        sw, sh = self._source_w, self._source_h
        if sw <= 0 or sh <= 0:
            return

        fit_scale = min(label_w / sw, label_h / sh)
        eff_scale = fit_scale * self._zoom

        # Position of the full image in label coords (top-left corner).
        img_w = sw * eff_scale
        img_h = sh * eff_scale
        img_x = (label_w - img_w) / 2.0 - self._pan.x() * eff_scale
        img_y = (label_h - img_h) / 2.0 - self._pan.y() * eff_scale

        pixmap = QPixmap(label_w, label_h)
        pixmap.fill(QColor("#222"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        target = QRectF(img_x, img_y, img_w, img_h)
        source = QRectF(0, 0, sw, sh)
        painter.drawImage(target, self._source_image, source)

        if self._dot_source_xy is not None:
            self._paint_dot(painter, img_x, img_y, eff_scale)

        painter.end()
        self._frame_label.setPixmap(pixmap)

    def _paint_dot(self, painter: QPainter, img_x: float, img_y: float, eff_scale: float) -> None:
        if self._dot_source_xy is None or self._source_w <= 0:
            return
        sx, sy = self._dot_source_xy
        dx = img_x + (sx + 0.5) * eff_scale
        dy = img_y + (sy + 0.5) * eff_scale
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QBrush(QColor(255, 60, 60, 220)))
        painter.drawEllipse(QPointF(dx, dy), 5.0, 5.0)

    # --- Coordinate mapping ---

    def _label_to_source(self, lx: float, ly: float) -> tuple[int, int] | None:
        """Convert label pixel coords to source pixel coords. None if outside image."""
        if self._source_w <= 0 or self._source_h <= 0:
            return None
        label_w = self._frame_label.width()
        label_h = self._frame_label.height()
        if label_w <= 0 or label_h <= 0:
            return None
        fit_scale = min(label_w / self._source_w, label_h / self._source_h)
        eff_scale = fit_scale * self._zoom
        if eff_scale <= 0:
            return None

        sx = (lx - label_w / 2.0) / eff_scale + self._source_w / 2.0 + self._pan.x()
        sy = (ly - label_h / 2.0) / eff_scale + self._source_h / 2.0 + self._pan.y()

        if sx < 0 or sx >= self._source_w or sy < 0 or sy >= self._source_h:
            return None
        return (max(0, min(int(sx), self._source_w - 1)),
                max(0, min(int(sy), self._source_h - 1)))

    def _clamp_pan(self) -> None:
        if self._source_w <= 0 or self._source_h <= 0:
            return
        label_w = self._frame_label.width()
        label_h = self._frame_label.height()
        if label_w <= 0 or label_h <= 0:
            return
        fit_scale = min(label_w / self._source_w, label_h / self._source_h)
        eff_scale = fit_scale * self._zoom
        img_w = self._source_w * eff_scale
        img_h = self._source_h * eff_scale

        max_pan_x = max(0.0, (img_w - label_w) / (2.0 * eff_scale))
        max_pan_y = max(0.0, (img_h - label_h) / (2.0 * eff_scale))

        px = max(-max_pan_x, min(max_pan_x, self._pan.x()))
        py = max(-max_pan_y, min(max_pan_y, self._pan.y()))
        self._pan = QPointF(px, py)

    # --- Counter ---

    def _update_counter(self):
        if self._camera_info is None:
            self._counter_label.setText("No video loaded")
            return
        total = self._camera_info.total_frames
        max_index = max(0, total - 1)
        fps = self._camera_info.capture_fps
        time_s = self._current_frame / fps
        max_time_s = max_index / fps
        zoom_str = f"  |  Zoom: {self._zoom:.1f}x" if self._zoom > 1.0 else ""
        self._counter_label.setText(
            f"Frame: {self._current_frame} / {max_index}  |  "
            f"Time: {time_s:.3f}s / {max_time_s:.3f}s{zoom_str}"
        )

    # --- Dot management ---

    def _clear_dot(self, *, emit: bool) -> None:
        if self._dot_source_xy is None and self._dot_center_frame is None:
            return
        self._dot_source_xy = None
        self._dot_center_frame = None
        if emit:
            self.dot_cleared.emit()
        if self._source_image is not None:
            self._render_frame()
        elif self._camera_info is not None:
            self._request_frame(self._current_frame)

    # --- Events ---

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._source_image is not None:
            self._clamp_pan()
            self._render_frame()

    def wheelEvent(self, event):
        """Scroll-wheel zoom centered on the cursor."""
        if self._source_image is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.user_interacted.emit()

        label_pos = self._frame_label.mapFromParent(event.pos())
        mx, my = label_pos.x(), label_pos.y()
        label_w = self._frame_label.width()
        label_h = self._frame_label.height()

        old_zoom = self._zoom
        fit_scale = min(label_w / self._source_w, label_h / self._source_h)
        old_eff = fit_scale * old_zoom

        factor = 1.25 if delta > 0 else 0.8
        new_zoom = max(1.0, min(20.0, old_zoom * factor))
        if new_zoom == old_zoom:
            return
        self._zoom = new_zoom
        new_eff = fit_scale * new_zoom

        # Adjust pan so the pixel under the cursor stays fixed.
        if old_eff > 0 and new_eff > 0:
            self._pan = QPointF(
                self._pan.x() + (mx - label_w / 2.0) * (1.0 / old_eff - 1.0 / new_eff),
                self._pan.y() + (my - label_h / 2.0) * (1.0 / old_eff - 1.0 / new_eff),
            )

        if self._zoom == 1.0:
            self._pan = QPointF(0.0, 0.0)
        self._clamp_pan()
        self._update_counter()
        self._render_frame()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.user_interacted.emit()
            if self._zoom > 1.0 and self._source_image is not None:
                self._dragging = True
                self._drag_start = event.pos()
                self._drag_pan_start = QPointF(self._pan)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_start is not None and self._drag_pan_start is not None:
            label_w = self._frame_label.width()
            label_h = self._frame_label.height()
            if label_w > 0 and label_h > 0 and self._source_w > 0:
                fit_scale = min(label_w / self._source_w, label_h / self._source_h)
                eff_scale = fit_scale * self._zoom
                if eff_scale > 0:
                    dx = event.pos().x() - self._drag_start.x()
                    dy = event.pos().y() - self._drag_start.y()
                    self._pan = QPointF(
                        self._drag_pan_start.x() - dx / eff_scale,
                        self._drag_pan_start.y() - dy / eff_scale,
                    )
                    self._clamp_pan()
                    self._render_frame()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._drag_start = None
            self._drag_pan_start = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click resets zoom to fit-to-label."""
        if event.button() == Qt.LeftButton and self._zoom != 1.0:
            self._zoom = 1.0
            self._pan = QPointF(0.0, 0.0)
            self._update_counter()
            self._render_frame()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """Right-click drops the intensity-probe dot at the clicked pixel."""
        if self._camera_info is None or self._source_w <= 0 or self._source_h <= 0:
            event.ignore()
            return
        if self._source_image is None:
            event.ignore()
            return
        label_pos = self._frame_label.mapFromParent(event.pos())
        result = self._label_to_source(label_pos.x(), label_pos.y())
        if result is None:
            event.accept()
            return
        src_x, src_y = result
        self._drop_dot(src_x, src_y)
        event.accept()

    def _drop_dot(self, src_x: int, src_y: int) -> None:
        """Place the probe dot and notify listeners. Caller has clamped to bounds."""
        self._dot_source_xy = (src_x, src_y)
        self._dot_center_frame = self._current_frame
        self.dot_dropped.emit(src_x, src_y, self._current_frame)
        self._render_frame()

    def _on_worker_open_failed(self, msg: str) -> None:
        self._frame_label.setStyleSheet("background: #7a1f1f; color: white;")
        self._frame_label.setText(f"Video unavailable:\n{msg}")

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
