# 3. Data Sources and File Layout

## Participant Folder

Each participant has one folder. The operator picks it via `File → Open Participant…`.

```
<participant_folder>/
├── disklavier/              # MIDI files
│   └── *.mid
└── overhead camera/         # Video + metadata pairs
    ├── Cxxxx.MP4
    └── CxxxxM01.XML
```

The folder name is used as the `participant_id` (see `participant_loader.py:25`).

## MIDI Files (Disklavier)

### Format

- Standard MIDI file (`.mid`) produced by a Yamaha Disklavier.
- Contains note-on / note-off events with pitch (MIDI number 21–108, i.e., A0–C8), velocity, and timing, plus tempo and `set_tempo` meta messages, and frequently polytouch / aftertouch events.
- High temporal resolution: ticks-per-beat is typically in the hundreds or thousands.

### Reference Timestamp

The **end time** of a recording is encoded in the `track_name` meta message as `YYYYMMDD_HHMMSS` (naive local time). `MidiAdapter.get_recording_time_range` parses the first 15 characters of `track_name`, attaches the user-provided UTC offset, derives the **start** by subtracting the duration, and returns `(unix_start, unix_end, duration)`.

The duration itself is read via `pretty_midi.PrettyMIDI.get_end_time()`, which honors tempo maps.

```python
# alignment_tool/midi_adapter.py
end_dt = datetime.strptime(msg.name[:15], "%Y%m%d_%H%M%S")
end_dt = end_dt.replace(tzinfo=timezone(timedelta(hours=utc_offset)))
start_dt = end_dt - timedelta(seconds=self.duration)
```

If no `track_name` with a parseable timestamp is present, loading raises `ValueError`.

### Tempo Handling

`MidiAdapter._extract_tempo` collects all `set_tempo` messages. If there's exactly one, it is used. If there are multiple (a tempo map), the **first one encountered** is stored and `_has_tempo_changes` is flagged. `_ticks_to_seconds` uses this single tempo for computing `time_resolution = seconds_per_tick`.

For the piano-study dataset the tool is calibrated against, the MIDI sample rate is typically **1920 Hz** (i.e., ~0.521 ms per tick).

### Relevant MidiFileInfo Fields

From `alignment_tool/models.py`:

| Field | Source |
|---|---|
| `filename` | base name of the `.mid` file |
| `unix_start`, `unix_end`, `duration` | derived from `track_name` + `PrettyMIDI.get_end_time()` |
| `sample_rate` | `1.0 / time_resolution` |
| `ticks_per_beat` | from the MIDI header |
| `tempo` | microseconds per beat |
| `file_path` | absolute path (kept in memory for later reloading during Level 2) |

## Overhead Camera Files (Sony FX30)

### Format

- H.264 MP4 video, recorded by a Sony FX30 in high-frame-rate mode.
- An XML **sidecar** accompanies each `.MP4`. The filename convention is `<name>.MP4` → `<name>M01.XML`. The XML file uses the namespace `urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20` (see `NAMESPACE` in `camera_adapter.py`).

### XML Fields Parsed

`CameraAdapter._parse_xml`:

| XML node | What the tool extracts |
|---|---|
| `nrt:Duration[@value]` | `duration_frames` (integer frame count at capture rate) |
| `nrt:CreationDate[@value]` | `creation_date` (timezone-aware `datetime`, treated as the clip **start**) |
| `nrt:VideoFrame[@captureFps]` | `capture_fps` (~239.76) — the real-world rate at which the sensor captured |
| `nrt:VideoFrame[@formatFps]` | `format_fps` (~24) — the playback rate (slow-motion container rate) |

The `captureFps` and `formatFps` values sometimes end with a trailing `p` or `i` (progressive / interlaced marker); the code strips those via `rstrip('pi')`.

### MP4 Properties (via cv2)

`CameraAdapter._parse_mp4_properties` opens the MP4 just long enough to read:

- `mp4_fps` — container FPS (often equals `format_fps`, not `capture_fps`).
- `mp4_frame_count` — total number of frames stored in the container.
- `mp4_width`, `mp4_height`.

### Frame Indexing Convention

> The MP4 container stores **all** ~240fps capture frames (played back in slow motion at ~24fps). The cv2 frame index maps 1:1 to the capture frame index.

So when `cv2.VideoCapture.set(CAP_PROP_POS_FRAMES, N)` is called with `N`, it seeks to the N-th capture frame. `Anchor.camera_frame` is this cv2-compatible 0-indexed frame number (`models.py:10`).

### Wall-Clock Duration

`CameraAdapter.duration = duration_frames / capture_fps`. `raw_unix_end = creation_date.timestamp() + duration`.

### Relevant CameraFileInfo Fields

| Field | Source |
|---|---|
| `filename`, `xml_filename` | base names |
| `raw_unix_start`, `raw_unix_end` | `creation_date.timestamp()` and `+duration` |
| `duration` | `duration_frames / capture_fps` |
| `capture_fps` | from XML |
| `total_frames` | from cv2 (`CAP_PROP_FRAME_COUNT`) |
| `mp4_path`, `xml_path` | absolute paths (held in memory for Level 2 video access) |
| `alignment_anchors`, `active_anchor_index` | per-clip alignment state (mutated during a session) |

## Time Units Glossary

Keep these straight — they appear throughout the code:

| Name | Type | Meaning |
|---|---|---|
| **unix** | float seconds since epoch | absolute time shared between MIDI and camera |
| **midi_timestamp_seconds** | float | seconds from the start of one MIDI file |
| **camera_frame** | int | 0-indexed capture-rate frame number within one clip |
| **global_shift** | float seconds | single offset per participant; applied to every camera clip |
| **anchor_shift** | float seconds | derived per active anchor (not stored directly) |
| **effective_shift** | float seconds | `global_shift + anchor_shift` |

See [Alignment Concepts and Math](./04-alignment-concepts.md) for the formulas.

## Resolution Relationship

| Source | Rate | Step size |
|---|---|---|
| MIDI | 1920 Hz (dataset-specific) | ~0.521 ms |
| Overhead camera | 239.76 Hz | ~4.17 ms |

One camera frame spans approximately 8 MIDI ticks (1920 / 239.76 ≈ 8.01). Consequences:

- In locked mode, advancing one camera frame advances the MIDI cursor by ~8 ticks.
- In locked mode, advancing one MIDI tick usually does **not** move the displayed camera frame (it only moves when a frame boundary is crossed).
