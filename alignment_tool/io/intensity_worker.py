"""Background worker that samples pixel intensity across a window of frames.

Runs on its own QThread with its own cv2.VideoCapture, independent of the
display FrameWorker. Avoids seek conflicts with the camera panel: display
scrubbing stays responsive while a window is being sampled.

Generation-counter pattern mirrors FrameWorker — a new open_video or a new
request_window bumps the counter so an in-flight walk can abort cleanly when
the user drops a new dot.
"""
from __future__ import annotations

import logging

import cv2
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


class IntensityWorker(QObject):
    # (center_frame, src_x, src_y, first_frame, last_frame, values)
    # values: list[float | None]; length == last_frame - first_frame + 1.
    intensity_ready = pyqtSignal(int, int, int, int, int, object)
    sample_failed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._capture: cv2.VideoCapture | None = None
        self._total_frames: int = 0
        self._generation: int = 0

    @pyqtSlot(str)
    def open_video(self, mp4_path: str) -> None:
        self.close_video()
        self._generation += 1
        self._capture = cv2.VideoCapture(mp4_path)
        if not self._capture.isOpened():
            logger.warning("IntensityWorker: cannot open %s", mp4_path)
            self._capture = None
            self._total_frames = 0
            self.sample_failed.emit(f"Could not open video: {mp4_path}")
            return
        self._total_frames = int(self._capture.get(cv2.CAP_PROP_FRAME_COUNT))

    @pyqtSlot()
    def close_video(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._total_frames = 0

    @pyqtSlot(int, int, int, int)
    def request_window(
        self, center_frame: int, src_x: int, src_y: int, half_width: int
    ) -> None:
        """Sample 3x3 luma around (src_x, src_y) for [center - half_width, center + half_width]."""
        self._generation += 1
        requested_gen = self._generation
        if self._capture is None or self._total_frames <= 0:
            self.sample_failed.emit("No video open for intensity sampling")
            return

        first_frame = center_frame - half_width
        last_frame = center_frame + half_width
        values: list[float | None] = [None] * (last_frame - first_frame + 1)

        # Clamp the actual decode range to [0, total - 1]; frames outside stay None.
        decode_start = max(0, first_frame)
        decode_end = min(self._total_frames - 1, last_frame)
        if decode_start > decode_end:
            # Entire window outside clip — emit all-None.
            self.intensity_ready.emit(
                center_frame, src_x, src_y, first_frame, last_frame, values
            )
            return

        # Single seek, then sequential reads — one GOP walk total instead of 101.
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, decode_start)

        for frame_idx in range(decode_start, decode_end + 1):
            if requested_gen != self._generation:
                return  # Cancelled: newer request or close_video.
            ret, bgr = self._capture.read()
            if not ret:
                continue
            luma = _patch_luma(bgr, src_x, src_y)
            if luma is None:
                continue
            values[frame_idx - first_frame] = luma

        if requested_gen != self._generation:
            return
        self.intensity_ready.emit(
            center_frame, src_x, src_y, first_frame, last_frame, values
        )


def _patch_luma(bgr, src_x: int, src_y: int) -> float | None:
    """Return Rec.601 luma averaged over the 3x3 patch centered at (src_x, src_y).

    Edge-clamped so clicks near the border still return a value. Returns None
    when the frame is empty or the click is outside the frame.
    """
    if bgr is None or bgr.size == 0:
        return None
    h, w = bgr.shape[:2]
    if src_x < 0 or src_y < 0 or src_x >= w or src_y >= h:
        return None
    x0 = max(0, src_x - 1)
    x1 = min(w, src_x + 2)
    y0 = max(0, src_y - 1)
    y1 = min(h, src_y + 2)
    patch = bgr[y0:y1, x0:x1]  # shape (dy, dx, 3), BGR order
    # Rec.601 luma on the averaged BGR.
    b = float(patch[:, :, 0].mean())
    g = float(patch[:, :, 1].mean())
    r = float(patch[:, :, 2].mean())
    return 0.299 * r + 0.587 * g + 0.114 * b
