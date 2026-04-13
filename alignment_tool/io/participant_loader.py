"""Scans a participant folder to discover MIDI and camera files."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from alignment_tool.core.errors import MediaLoadError
from alignment_tool.core.models import AlignmentState
from alignment_tool.io.midi_adapter import MidiAdapter
from alignment_tool.io.camera_adapter import CameraAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParticipantLoadResult:
    state: AlignmentState
    warnings: list[str]


class ParticipantLoader:

    @staticmethod
    def load(folder: str) -> ParticipantLoadResult:
        """Load a participant from a folder.

        Expects subdirectories:
          - disklavier/   containing .mid files
          - overhead camera/   containing .MP4 and .XML files

        XML filenames are derived: C0001.MP4 -> C0001M01.XML
        """
        folder_path = Path(folder)
        participant_id = folder_path.name

        disklavier_dir = folder_path / "disklavier"
        camera_dir = folder_path / "overhead camera"

        warnings: list[str] = []

        # Discover MIDI files
        midi_files = []
        if disklavier_dir.is_dir():
            mid_filenames = sorted(
                f for f in os.listdir(disklavier_dir)
                if Path(f).suffix.lower() == ".mid"
            )
            for fname in mid_filenames:
                fpath = str(disklavier_dir / fname)
                try:
                    adapter = MidiAdapter(fpath)
                    midi_files.append(adapter.to_file_info())
                except MediaLoadError as exc:
                    warnings.append(f"{fname}: {exc.reason}")
                    logger.warning("Skipping MIDI file %s: %s", fname, exc.reason)
                    continue

        # Discover camera files
        camera_files = []
        if camera_dir.is_dir():
            mp4_filenames = sorted(
                f for f in os.listdir(camera_dir)
                if Path(f).suffix.lower() == ".mp4"
            )
            for mp4_name in mp4_filenames:
                mp4_stem = Path(mp4_name).stem
                xml_name = f"{mp4_stem}M01.XML"
                mp4_path = str(camera_dir / mp4_name)
                xml_path = str(camera_dir / xml_name)

                # Case-insensitive XML lookup: if the derived uppercase name
                # doesn't exist, scan the directory for a match.
                if not os.path.isfile(xml_path):
                    resolved = None
                    try:
                        for candidate in os.listdir(camera_dir):
                            cand_path = Path(candidate)
                            if (
                                cand_path.suffix.lower() == ".xml"
                                and cand_path.stem.lower() == f"{mp4_stem.lower()}m01"
                            ):
                                resolved = str(camera_dir / candidate)
                                break
                    except OSError:
                        resolved = None
                    if resolved is None:
                        logger.warning(
                            "XML sidecar not found for %s, skipping", mp4_name,
                        )
                        warnings.append(
                            f"{mp4_name}: XML sidecar not found"
                        )
                        continue
                    xml_path = resolved

                try:
                    adapter = CameraAdapter(xml_path, mp4_path)
                    camera_files.append(adapter.to_file_info())
                except MediaLoadError as exc:
                    warnings.append(f"{mp4_name}: {exc.reason}")
                    logger.warning("Skipping camera file %s: %s", mp4_name, exc.reason)
                    continue

        state = AlignmentState(
            participant_id=participant_id,
            participant_folder=folder,
            midi_files=midi_files,
            camera_files=camera_files,
        )
        return ParticipantLoadResult(state=state, warnings=warnings)
