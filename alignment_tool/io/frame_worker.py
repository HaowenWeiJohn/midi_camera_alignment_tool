"""Background thread for cv2 video frame extraction."""
from __future__ import annotations

from collections import OrderedDict

import cv2
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage


MAX_CACHE = 32


class FrameWorker(QObject):
    """Extracts video frames on a background thread.

    Owns the cv2.VideoCapture handle — all access is serialized through Qt signals.
    """

    frame_ready = pyqtSignal(int, object)  # (frame_index, QImage)

    def __init__(self):
        super().__init__()
        self._capture: cv2.VideoCapture | None = None
        self._cache: OrderedDict[int, QImage] = OrderedDict()

    @pyqtSlot(str)
    def open_video(self, mp4_path: str):
        self.close_video()
        self._cache.clear()
        self._capture = cv2.VideoCapture(mp4_path)
        if not self._capture.isOpened():
            print(f"FrameWorker: cannot open {mp4_path}")
            self._capture = None

    @pyqtSlot(int)
    def request_frame(self, frame_index: int):
        if self._capture is None:
            return

        # Check cache
        if frame_index in self._cache:
            self._cache.move_to_end(frame_index)
            self.frame_ready.emit(frame_index, self._cache[frame_index])
            return

        # Seek and read
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, bgr = self._capture.read()
        if not ret:
            return

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        # .copy() is critical — the numpy buffer is reused by cv2
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()

        # Cache
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
