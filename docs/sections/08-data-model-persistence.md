# 8. Data Model and Persistence

## 8.1 Dataclasses (`alignment_tool/models.py`)

All runtime state is held in four plain `@dataclass` types. There is no ORM, no observer pattern — widgets mutate the same object graph.

### `Anchor`

```python
@dataclass
class Anchor:
    midi_filename: str                 # which MIDI file the timestamp is relative to
    midi_timestamp_seconds: float      # seconds from that MIDI file's start
    camera_frame: int                  # 0-indexed cv2 frame within a camera clip
    label: str = ""                    # optional operator note
```

Derived values (`anchor_shift`, aligned unix positions) are **not** stored on the anchor — they are recomputed by `alignment_engine` each time.

### `CameraFileInfo`

```python
@dataclass
class CameraFileInfo:
    filename: str                      # e.g. "C0001.MP4"
    xml_filename: str                  # e.g. "C0001M01.XML"
    raw_unix_start: float              # raw_unix_end - duration
    raw_unix_end: float                # from MP4 mtime (os.path.getmtime)
    duration: float                    # duration_frames / capture_fps
    capture_fps: float                 # e.g. 239.76
    total_frames: int                  # from cv2 CAP_PROP_FRAME_COUNT
    mp4_path: str = ""                 # in-memory only; not persisted
    xml_path: str = ""                 # in-memory only; not persisted
    alignment_anchors: list[Anchor] = []
    active_anchor_index: int | None = None

    def get_active_anchor(self) -> Anchor | None: ...
```

### `MidiFileInfo`

```python
@dataclass
class MidiFileInfo:
    filename: str
    unix_start: float                  # unix_end - duration
    unix_end: float                    # from .mid file mtime (os.path.getmtime)
    duration: float                    # from PrettyMIDI.get_end_time()
    sample_rate: float                 # 1 / time_resolution (~1920 Hz)
    ticks_per_beat: int = 0            # in-memory only; not persisted
    tempo: float = 500000.0            # microseconds/beat; in-memory only
    file_path: str = ""                # in-memory only; not persisted
```

### `AlignmentState`

```python
@dataclass
class AlignmentState:
    participant_id: str
    participant_folder: str            # in-memory only; not persisted
    global_shift_seconds: float = 0.0
    midi_files: list[MidiFileInfo] = []
    camera_files: list[CameraFileInfo] = []
    alignment_notes: str = ""

    def midi_file_by_name(self, filename: str) -> MidiFileInfo | None: ...
    def total_anchor_count(self) -> int: ...
    def clips_with_anchors_count(self) -> int: ...
    def clear_all_anchors(self): ...
```

`clear_all_anchors` is called when the operator confirms a global-shift change that would invalidate anchors.

## 8.2 Stored vs Derived

The tool is deliberate about what it stores and what it recomputes. The stored items are the **raw evidence** of an alignment decision; everything else is a view.

| Stored | Derived |
|---|---|
| `Anchor(midi_filename, midi_timestamp_seconds, camera_frame, label)` | `anchor_shift` |
| `global_shift_seconds` | `effective_shift` for any clip |
| `active_anchor_index` per clip | `aligned_unix_start`, `aligned_unix_end` |
| File metadata (start, duration, fps, sample rate) | Bar positions, playhead positions, overlap region |

This matters for load semantics: after reloading a JSON, the tool can redraw the Level 1 timeline with correct positions without needing to re-scan any of the media.

## 8.3 JSON Schema

`alignment_tool/persistence.py` implements the schema. A concrete example:

```json
{
  "participant_id": "009",
  "global_shift_seconds": -342.5,
  "midi_files": [
    {
      "filename": "20250815_144525_pia02_s009_001.mid",
      "unix_start": 1723740325.0,
      "unix_end": 1723740625.0,
      "duration": 300.0,
      "sample_rate": 1920.0
    }
  ],
  "camera_files": [
    {
      "filename": "C0001.MP4",
      "xml_filename": "C0001M01.XML",
      "raw_unix_start": 1723741025.0,
      "raw_unix_end": 1723741325.0,
      "duration": 300.0,
      "capture_fps": 239.76,
      "alignment_anchors": [
        {
          "midi_filename": "20250815_144525_pia02_s009_001.mid",
          "midi_timestamp_seconds": 45.123,
          "camera_frame": 5678,
          "label": "C4 onset near start"
        }
      ],
      "active_anchor_index": 0
    }
  ],
  "alignment_notes": ""
}
```

### Field-by-field

| Path | Required | Meaning |
|---|---|---|
| `participant_id` | yes | copy of folder name |
| `global_shift_seconds` | yes | applies to **every** camera clip |
| `midi_files[].filename` | yes | matches the base name in `disklavier/` |
| `midi_files[].unix_start/unix_end/duration/sample_rate` | yes | cached metadata so Level 1 can redraw without re-parsing `.mid` files |
| `camera_files[].filename / xml_filename` | yes | base names |
| `camera_files[].raw_unix_start/raw_unix_end/duration/capture_fps` | yes | cached metadata |
| `camera_files[].alignment_anchors` | yes (possibly empty) | list of anchor pairs |
| `camera_files[].active_anchor_index` | yes (may be `null`) | which anchor is currently active |
| `alignment_notes` | optional on load (defaults to `""`) | free-text notes |

### What is *not* in the JSON

- `participant_folder` — operator picks the folder at load time; the absolute path is not portable.
- `mp4_path`, `xml_path`, `file_path` — regenerated from the folder.
- `total_frames`, `ticks_per_beat`, `tempo` — reread from media.

On load, `CameraFileInfo.total_frames` is initialized to `0`. Level 2 will not seek correctly with that value, so the current implementation requires re-opening the participant folder (via `File → Open Participant…`) to edit a previously-saved alignment in Level 2. Level 1 works purely from the JSON.

### Save implementation (`persistence.save_alignment`)

Pretty-printed with `indent=2`. No atomic-write / tempfile swap — if the process is killed mid-write, the file may be partial.

### Load implementation (`persistence.load_alignment`)

Straight JSON → dataclass construction. Missing `alignment_notes` defaults to `""` (`data.get("alignment_notes", "")`). Missing `label` on an anchor defaults to `""` (`a.get("label", "")`). All other fields are required and will raise `KeyError` on malformed input.

Older JSON files may contain a `utc_offset_hours` field — it is ignored on load (the field has been removed from the data model).

## 8.4 Mutations at a Glance

| Operation | Mutation |
|---|---|
| Open participant | Builds a fresh `AlignmentState` from disk. |
| Change global shift (Apply) | Sets `state.global_shift_seconds`; may call `state.clear_all_anchors()`. |
| Add anchor | Appends to `camera_files[i].alignment_anchors`. |
| Activate anchor | Sets `camera_files[i].active_anchor_index = index`. |
| Deactivate anchor | Sets `camera_files[i].active_anchor_index = None`. |
| Delete anchor | Pops from `camera_files[i].alignment_anchors`; adjusts `active_anchor_index`. |
| Save | Writes JSON; no mutation. |
| Load | Replaces `state` entirely. |
