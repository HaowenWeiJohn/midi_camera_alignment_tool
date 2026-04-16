# MIDI files

For each `.mid` file the tool derives a `MidiFileInfo` record with a filename, duration, tempo metadata, and a pair of unix timestamps for "when did this recording start and end on the wall clock." This page documents exactly how each of those fields is computed.

Source: `alignment_tool/io/midi_adapter.py`.

## Parsing

Each `.mid` file is opened with two MIDI libraries:

- `mido.MidiFile` — used for its raw tempo messages (`set_tempo` meta events) and `ticks_per_beat`.
- `pretty_midi.PrettyMIDI` — used for duration and note lists.

Using both is a deliberate choice: `mido` gives fast, faithful access to the header tempo, and `pretty_midi` handles tempo maps correctly when computing the file's total duration. Neither library is consulted for absolute wall-clock time (see below).

## Tempo

`MidiAdapter._extract_tempo` walks every track and collects every `set_tempo` event. The resulting value is:

- the single tempo, if the file has exactly one tempo event;
- the **first** tempo encountered, if the file has multiple;
- **500 000 µs/beat (= 120 BPM)** when the file has no tempo event at all.

Tempo is stored as microseconds per beat. The tool also derives:

- `time_resolution = tempo / 1_000_000 / ticks_per_beat` — seconds per tick.
- `sample_rate = 1 / time_resolution` — ticks per second, typically about 1920.

The MIDI panel's arrow-key stepping uses `time_resolution` so a press always advances one tick, regardless of tempo.

## Duration

Duration is always read from `PrettyMIDI.get_end_time()`. This method walks tempo changes correctly and avoids the cumulative rounding drift you'd get from summing delta-ticks manually.

## Wall-clock timestamps

This is the delicate part. A MIDI file does not carry a reliable recording timestamp inside its header (the Disklavier's embedded track-name timestamp is missing or wrong on many takes). The tool therefore uses the **file's mtime** as the recording end time:

```
unix_end   = os.path.getmtime(filepath)
unix_start = unix_end − duration
```

This models the common case: the Disklavier closes (and flushes) the `.mid` file at the moment the performer stops. The file's mtime therefore reflects the Disklavier host's clock at end-of-recording.

!!! warning "Preserve mtimes when copying files"
    Copying or re-saving a `.mid` file without preserving its original modification time will move `unix_end` to the copy time and destroy the alignment. Always use tools that preserve timestamps:

    - `cp --preserve=timestamps` on Linux/macOS
    - `rsync -a` (archive mode, default preserves mtimes)
    - `robocopy /DCOPY:T` on Windows (copies directory timestamps)
    - Dragging files in most file managers preserves mtimes; zipping/unzipping generally does too, but verify with `stat` or `ls -l --full-time`.

## Fields on `MidiFileInfo`

The adapter produces a `MidiFileInfo` dataclass with the following fields (see `alignment_tool/core/models.py:35-43`):

| Field | Meaning |
|---|---|
| `filename` | Basename, e.g. `"trial_001.mid"` |
| `file_path` | Absolute path at runtime; stored relative to `participant_folder` in JSON |
| `unix_start` | `unix_end − duration` |
| `unix_end` | `os.path.getmtime(filepath)` |
| `duration` | Seconds, from `PrettyMIDI.get_end_time()` |
| `sample_rate` | `1 / time_resolution` (ticks per second) |
| `ticks_per_beat` | From `mido.MidiFile.ticks_per_beat` |
| `tempo` | Microseconds per beat (default 500 000 = 120 BPM) |

None of these fields are re-derived when you **load** a saved JSON — the stored values are trusted, which lets you re-open a session even if the source `.mid` files have since been moved to colder storage.
