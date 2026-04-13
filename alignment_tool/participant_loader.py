"""Scans a participant folder to discover MIDI and camera files."""
from __future__ import annotations

import os
from pathlib import Path

from alignment_tool.core.models import AlignmentState
from alignment_tool.midi_adapter import MidiAdapter
from alignment_tool.camera_adapter import CameraAdapter


class ParticipantLoader:

    @staticmethod
    def load(folder: str) -> AlignmentState:
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

        # Discover MIDI files
        midi_files = []
        if disklavier_dir.is_dir():
            mid_filenames = sorted(
                f for f in os.listdir(disklavier_dir) if f.endswith(".mid")
            )
            for fname in mid_filenames:
                fpath = str(disklavier_dir / fname)
                adapter = MidiAdapter(fpath)
                midi_files.append(adapter.to_file_info())

        # Discover camera files
        camera_files = []
        if camera_dir.is_dir():
            mp4_filenames = sorted(
                f for f in os.listdir(camera_dir) if f.endswith(".MP4")
            )
            for mp4_name in mp4_filenames:
                xml_name = mp4_name.replace(".MP4", "M01.XML")
                mp4_path = str(camera_dir / mp4_name)
                xml_path = str(camera_dir / xml_name)

                if not os.path.isfile(xml_path):
                    print(f"Warning: XML sidecar not found for {mp4_name}, skipping")
                    continue

                adapter = CameraAdapter(xml_path, mp4_path)
                camera_files.append(adapter.to_file_info())

        return AlignmentState(
            participant_id=participant_id,
            participant_folder=folder,
            midi_files=midi_files,
            camera_files=camera_files,
        )
