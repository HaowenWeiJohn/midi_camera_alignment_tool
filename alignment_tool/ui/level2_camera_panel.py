"""Camera panel — displays video frames with frame-by-frame navigation."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout

from alignment_tool.core.models import CameraFileInfo
from alignment_tool.io.frame_worker import FrameWorker


class CameraPanelWidget(QWidget):
    """Video frame display panel for Level 2."""

    position_changed = pyqtSignal(int)  # emits current frame index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_info: CameraFileInfo | None = None
        self._current_frame: int = 0
        self._pending_frame: int = -1

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
        self._camera_info = camera_info
        self._current_frame = 0
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
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._frame_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._frame_label.setPixmap(scaled)

    def _update_counter(self):
        if self._camera_info is None:
            self._counter_label.setText("No video loaded")
            return
        total = self._camera_info.total_frames
        # Display is 1-indexed so the last frame reads "total / total" instead of
        # the confusing "total-1 / total". Internally, self._current_frame and
        # Anchor.camera_frame remain 0-indexed cv2 indices.
        frame_display = self._current_frame + 1
        time_s = self._current_frame / self._camera_info.capture_fps
        total_time_s = total / self._camera_info.capture_fps
        self._counter_label.setText(
            f"Frame: {frame_display} / {total}  |  "
            f"Time: {time_s:.3f}s / {total_time_s:.3f}s"
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

    def hideEvent(self, event):
        self.cleanup()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
