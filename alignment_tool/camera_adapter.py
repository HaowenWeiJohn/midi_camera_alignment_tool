"""Camera metadata adapter for the alignment tool.

Adapts examples/overhead_camera.py with fixes:
- Lazy MP4 opening for frame extraction
- get_frame() method for video frame access
- Uses MP4 mtime as recording end time; start derived as end - duration
  (XML CreationDate is no longer consulted — can be missing/unreliable)
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from alignment_tool.models import CameraFileInfo

NAMESPACE = {'nrt': 'urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20'}


class CameraAdapter:
    """Parses Sony FX30 XML sidecar + MP4 for the alignment tool."""

    def __init__(self, xml_path: str, mp4_path: str):
        self._xml_path = xml_path
        self._mp4_path = mp4_path
        self._capture: cv2.VideoCapture | None = None

        # Parse XML metadata
        tree = ET.parse(xml_path)
        root = tree.getroot()
        self._parse_xml(root)

        # Get basic MP4 properties (quick open/close)
        self._parse_mp4_properties()

    def _parse_xml(self, root: ET.Element):
        ns = NAMESPACE

        duration_elem = root.find('nrt:Duration', ns)
        self.duration_frames = int(duration_elem.get('value'))

        video_frame = root.find('.//nrt:VideoFrame', ns)
        self.capture_fps = float(video_frame.get('captureFps').rstrip('pi'))
        self.format_fps = float(video_frame.get('formatFps').rstrip('pi'))

    def _parse_mp4_properties(self):
        cap = cv2.VideoCapture(str(self._mp4_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {self._mp4_path}")
        self.mp4_fps = cap.get(cv2.CAP_PROP_FPS)
        self.mp4_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.mp4_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.mp4_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

    @property
    def duration(self) -> float:
        """Wall-clock duration in seconds (capture_fps based)."""
        return self.duration_frames / self.capture_fps

    def get_recording_time_range(self, fmt: str = "unix"):
        """Return (start, end, duration) for this MP4 recording.

        End time comes from the MP4's mtime (os.path.getmtime), which is an
        absolute unix timestamp. Start time is end minus duration.
        """
        # mtime reflects the camera's clock at file-close; it will be wrong if
        # the MP4 is later copied/touched without preserving times.
        end_unix = os.path.getmtime(self._mp4_path)
        start_unix = end_unix - self.duration

        if fmt == "unix":
            return start_unix, end_unix, self.duration
        elif fmt == "datetime":
            return (
                datetime.fromtimestamp(start_unix),
                datetime.fromtimestamp(end_unix),
                self.duration,
            )
        else:
            raise ValueError(f"Unknown format: {fmt!r}")

    def to_file_info(self) -> CameraFileInfo:
        """Build a CameraFileInfo from this adapter."""
        start, end, duration = self.get_recording_time_range("unix")
        mp4_name = Path(self._mp4_path).name
        xml_name = Path(self._xml_path).name
        return CameraFileInfo(
            filename=mp4_name,
            xml_filename=xml_name,
            raw_unix_start=start,
            raw_unix_end=end,
            duration=duration,
            capture_fps=self.capture_fps,
            total_frames=self.mp4_frame_count,
            mp4_path=self._mp4_path,
            xml_path=self._xml_path,
        )

    # --- Frame extraction for Level 2 ---

    def open(self):
        """Open a persistent cv2.VideoCapture for frame extraction."""
        if self._capture is None or not self._capture.isOpened():
            self._capture = cv2.VideoCapture(str(self._mp4_path))
            if not self._capture.isOpened():
                raise RuntimeError(f"Cannot open video: {self._mp4_path}")

    def close(self):
        """Release the cv2.VideoCapture."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def get_frame(self, frame_index: int) -> np.ndarray | None:
        """Extract a single frame by index (0-indexed). Returns RGB array or None."""
        self.open()
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, bgr = self._capture.read()
        if not ret:
            return None
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def __del__(self):
        self.close()
