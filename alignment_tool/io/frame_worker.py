"""Background thread for cv2 video frame extraction."""
from __future__ import annotations

import logging
from collections import OrderedDict

import cv2
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage

logger = logging.getLogger(__name__)
MAX_CACHE = 32


class FrameWorker(QObject):
    frame_ready = pyqtSignal(int, object)   # (frame_index, QImage)
    open_failed = pyqtSignal(str)           # (error message)

    def __init__(self):
        super().__init__()
        self._capture: cv2.VideoCapture | None = None
        self._cache: OrderedDict[int, QImage] = OrderedDict()
        self._generation: int = 0

    @pyqtSlot(str)
    def open_video(self, mp4_path: str):
        self.close_video()
        self._generation += 1
        self._cache.clear()
        self._capture = cv2.VideoCapture(mp4_path)
        if not self._capture.isOpened():
            logger.warning("FrameWorker: cannot open %s", mp4_path)
            self._capture = None
            self.open_failed.emit(f"Could not open video: {mp4_path}")

    @pyqtSlot(int)
    def request_frame(self, frame_index: int):
        # Snapshot generation at dispatch; after a subsequent open_video,
        # this stale request simply becomes a no-op.
        requested_gen = self._generation
        if self._capture is None:
            return
        if frame_index in self._cache:
            self._cache.move_to_end(frame_index)
            if requested_gen == self._generation:
                self.frame_ready.emit(frame_index, self._cache[frame_index])
            return
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, bgr = self._capture.read()
        if not ret:
            return
        if requested_gen != self._generation:
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        self._cache[frame_index] = qimg
        if len(self._cache) > MAX_CACHE:
            self._cache.popitem(last=False)
        self.frame_ready.emit(frame_index, qimg)

    @pyqtSlot()
    def close_video(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._cache.clear()
