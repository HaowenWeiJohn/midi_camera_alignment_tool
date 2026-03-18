"""Camera metadata adapter for the alignment tool.

Adapts examples/overhead_camera.py with fixes:
- Local format_time_range (no cross-module import)
- Lazy MP4 opening for frame extraction
- get_frame() method for video frame access
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from alignment_tool.models import CameraFileInfo

NAMESPACE = {'nrt': 'urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20'}


def _format_time_range(start_dt: datetime, duration_seconds: float, fmt: str = "unix"):
    end_dt = start_dt + timedelta(seconds=duration_seconds)
    if fmt == "datetime":
        return start_dt, end_dt, duration_seconds
    elif fmt == "unix":
        return start_dt.timestamp(), end_dt.timestamp(), duration_seconds
    else:
        raise ValueError(f"Unknown format: {fmt!r}")


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

        creation_elem = root.find('nrt:CreationDate', ns)
        self.creation_date = datetime.fromisoformat(creation_elem.get('value'))

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
        return _format_time_range(self.creation_date, self.duration, fmt)

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
