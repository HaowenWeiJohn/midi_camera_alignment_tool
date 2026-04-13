"""Lightweight MIDI file adapter for the alignment tool.

Adapts the essential logic from examples/midi.py, fixing known issues:
- Uses PrettyMIDI.get_end_time() for duration (avoids rounding error)
- Caches tempo extraction (avoids O(N) per call)
- Drops unused dependencies (pysampled, datanavigator)
- Uses file mtime as recording end time (some MIDI files lack the
  track_name timestamp the Disklavier normally embeds)
"""
from __future__ import annotations

import os
from datetime import datetime

import mido
import pretty_midi

from alignment_tool.core.models import MidiFileInfo

# Module-level constants
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MIDI_TO_NOTE = {
    pitch: f"{NOTE_NAMES[pitch % 12]}{(pitch // 12) - 1}"
    for pitch in range(21, 109)
}
NOTE_TO_MIDI = {note: midi for midi, note in MIDI_TO_NOTE.items()}


def _ticks_to_seconds(ticks: int, tempo: float, ticks_per_beat: int) -> float:
    """Convert MIDI ticks to seconds at a given tempo."""
    seconds_per_beat = tempo / 1_000_000
    return (ticks / ticks_per_beat) * seconds_per_beat


class MidiAdapter:
    """Wraps a MIDI file for the alignment tool's needs."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._mido = mido.MidiFile(filepath)
        self._pm = pretty_midi.PrettyMIDI(filepath)
        self._tempo = self._extract_tempo()

    def _extract_tempo(self) -> float:
        """Extract tempo in microseconds per beat.

        For constant-tempo files, returns the single tempo.
        For multi-tempo files, returns the first tempo encountered.
        """
        default_tempo = 500_000  # 120 BPM
        tempos = set()
        for track in self._mido.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    tempos.add(msg.tempo)
        if not tempos:
            return default_tempo
        if len(tempos) == 1:
            return tempos.pop()
        # Multiple tempos — return first encountered
        for track in self._mido.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    return msg.tempo
        return default_tempo

    @property
    def filepath(self) -> str:
        return self._filepath

    @property
    def ticks_per_beat(self) -> int:
        return self._mido.ticks_per_beat

    @property
    def tempo(self) -> float:
        return self._tempo

    @property
    def time_resolution(self) -> float:
        """Seconds per tick."""
        return _ticks_to_seconds(1, self._tempo, self._mido.ticks_per_beat)

    @property
    def sample_rate(self) -> float:
        """Ticks per second."""
        return 1.0 / self.time_resolution

    @property
    def duration(self) -> float:
        """Total duration in seconds (from PrettyMIDI, handles tempo maps)."""
        return self._pm.get_end_time()

    @property
    def notes(self) -> list:
        """PrettyMIDI note list from first instrument."""
        if self._pm.instruments:
            return self._pm.instruments[0].notes
        return []

    def get_recording_time_range(self, fmt: str = "unix"):
        """Return (start, end, duration) for this MIDI recording.

        End time comes from the file's mtime (os.path.getmtime), which is an
        absolute unix timestamp. Start time is end minus duration.
        """
        # mtime reflects the recording machine's clock at file-close; it will
        # be wrong if the file is later copied/touched without preserving times.
        end_unix = os.path.getmtime(self._filepath)
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

    def to_file_info(self) -> MidiFileInfo:
        """Build a MidiFileInfo from this adapter."""
        start, end, duration = self.get_recording_time_range("unix")
        return MidiFileInfo(
            filename=self._filepath.replace("\\", "/").split("/")[-1],
            unix_start=start,
            unix_end=end,
            duration=duration,
            sample_rate=self.sample_rate,
            ticks_per_beat=self.ticks_per_beat,
            tempo=self.tempo,
            file_path=self._filepath,
        )
