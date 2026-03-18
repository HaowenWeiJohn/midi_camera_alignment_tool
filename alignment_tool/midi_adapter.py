"""Lightweight MIDI file adapter for the alignment tool.

Adapts the essential logic from examples/midi.py, fixing known issues:
- Uses PrettyMIDI.get_end_time() for duration (avoids rounding error)
- Caches tempo extraction (avoids O(N) per call)
- Drops unused dependencies (pysampled, datanavigator)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import mido
import pretty_midi

from alignment_tool.models import MidiFileInfo

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
        self._tempo, self._has_tempo_changes = self._extract_tempo()

    def _extract_tempo(self) -> tuple[float, bool]:
        """Extract tempo, returning (tempo_usec, has_changes).

        For constant-tempo files, returns the single tempo.
        For multi-tempo files, returns the first tempo and flags it.
        """
        default_tempo = 500_000  # 120 BPM
        tempos = set()
        for track in self._mido.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    tempos.add(msg.tempo)
        if not tempos:
            return default_tempo, False
        if len(tempos) == 1:
            return tempos.pop(), False
        # Multiple tempos — return first encountered, flag it
        for track in self._mido.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    return msg.tempo, True
        return default_tempo, False

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

    def get_recording_time_range(self, fmt: str = "unix", utc_offset: float | None = None):
        """Return (start, end, duration) for this MIDI recording.

        The track_name meta message encodes the END time as YYYYMMDD_HHMMSS.
        Start time is derived by subtracting duration.
        """
        end_dt = None
        for track in self._mido.tracks:
            for msg in track:
                if msg.type == 'track_name' and msg.name:
                    try:
                        end_dt = datetime.strptime(msg.name[:15], "%Y%m%d_%H%M%S")
                    except (ValueError, IndexError):
                        pass
                    break
            if end_dt is not None:
                break

        if end_dt is None:
            raise ValueError(f"Cannot determine recording time for {self._filepath}")

        if utc_offset is not None:
            tz = timezone(timedelta(hours=utc_offset))
            end_dt = end_dt.replace(tzinfo=tz)

        start_dt = end_dt - timedelta(seconds=self.duration)
        end_dt_final = start_dt + timedelta(seconds=self.duration)

        if fmt == "unix":
            return start_dt.timestamp(), end_dt_final.timestamp(), self.duration
        elif fmt == "datetime":
            return start_dt, end_dt_final, self.duration
        else:
            raise ValueError(f"Unknown format: {fmt!r}")

    def to_file_info(self, utc_offset: float) -> MidiFileInfo:
        """Build a MidiFileInfo from this adapter."""
        start, end, duration = self.get_recording_time_range("unix", utc_offset)
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
