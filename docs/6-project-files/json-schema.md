# JSON schema (v1)

The alignment save file is a single UTF-8 JSON document with `indent=2`, strict finite-number policy (`allow_nan=False`), and **schema_version == 1**. This page documents every field with types and validation rules.

## Example

```json
{
  "schema_version": 1,
  "participant_id": "participant_042",
  "participant_folder": "C:/data/study/participant_042",
  "global_shift_seconds": 412.3481,
  "alignment_notes": "",
  "midi_files": [
    {
      "filename": "trial_001.mid",
      "file_path": "disklavier/trial_001.mid",
      "unix_start": 1707345000.0,
      "unix_end": 1707345187.4,
      "duration": 187.4,
      "sample_rate": 1920.0,
      "ticks_per_beat": 480,
      "tempo": 500000.0
    }
  ],
  "camera_files": [
    {
      "filename": "C0001.MP4",
      "xml_filename": "C0001M01.XML",
      "mp4_path": "overhead camera/C0001.MP4",
      "xml_path": "overhead camera/C0001M01.XML",
      "raw_unix_start": 1707344587.0,
      "raw_unix_end": 1707345037.1,
      "duration": 450.1,
      "capture_fps": 239.76,
      "total_frames": 107928,
      "alignment_anchors": [
        {
          "midi_filename": "trial_001.mid",
          "midi_timestamp_seconds": 12.456,
          "camera_frame": 2987,
          "label": "phrase 1 opening"
        }
      ]
    }
  ]
}
```

## Top level

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Must equal `1`. Mismatch raises `UnsupportedSchemaVersionError`. |
| `participant_id` | string | Typically the last component of `participant_folder`. |
| `participant_folder` | string | Absolute path at save time; used as the base for relative `file_path`, `mp4_path`, `xml_path` values. |
| `global_shift_seconds` | float | Must be finite. Zero is legal. |
| `alignment_notes` | string | Optional (defaults to `""` on load if missing). Reserved for future use. |
| `midi_files` | array of MidiFile | May be empty. |
| `camera_files` | array of CameraFile | May be empty. |

## MidiFile

| Field | Type | Notes |
|---|---|---|
| `filename` | string | Basename, e.g. `"trial_001.mid"`. |
| `file_path` | string | Relative to `participant_folder` when possible; absolute or empty strings pass through unchanged. Resolved at load via `_resolve_path`. |
| `unix_start` | float | Must be finite. |
| `unix_end` | float | Must be finite. |
| `duration` | float | Must be finite **and** `> 0`. |
| `sample_rate` | float | Must be finite. Typically `1 / time_resolution` (~1920). |
| `ticks_per_beat` | int | No validation applied. |
| `tempo` | float | Microseconds per beat. No validation applied. `500000.0` is the 120-BPM default. |

## CameraFile

| Field | Type | Notes |
|---|---|---|
| `filename` | string | MP4 basename, e.g. `"C0001.MP4"`. |
| `xml_filename` | string | XML basename, e.g. `"C0001M01.XML"`. |
| `mp4_path` | string | Same resolution rule as `file_path`. |
| `xml_path` | string | Same resolution rule. |
| `raw_unix_start` | float | Must be finite. Unmodified mtime-derived start. |
| `raw_unix_end` | float | Must be finite. |
| `duration` | float | Not additionally validated at load. |
| `capture_fps` | float | Must be finite **and** `> 0`. Typically ~239.76. |
| `total_frames` | int | Must be `> 0`. |
| `alignment_anchors` | array of Anchor | May be empty. |

!!! note "active_anchor_index is not persisted"
    The runtime `CameraFileInfo` dataclass has an `active_anchor_index` field, but it is deliberately **not** part of the JSON schema. Every camera clip starts with `active_anchor_index = None` after a fresh load, by design.

## Anchor

| Field | Type | Notes |
|---|---|---|
| `midi_filename` | string | Must match the `filename` of some MIDI entry in the same file. |
| `midi_timestamp_seconds` | float | Must be finite. Seconds from the start of the referenced MIDI file. |
| `camera_frame` | int | Must be `>= 0`. 0-indexed cv2 frame. |
| `label` | string | Optional (defaults to `""` on load if missing). Free text. |

## Validation rules

After the JSON is parsed and rehydrated, `_validate_state` runs these checks. Any failure raises `CorruptAlignmentFileError` with a specific reason:

- `global_shift_seconds` is finite.
- For every MIDI file:
    - `unix_start`, `unix_end`, `duration`, `sample_rate` are finite.
    - `duration > 0`.
- For every camera file:
    - `raw_unix_start`, `raw_unix_end`, `capture_fps` are finite.
    - `capture_fps > 0`.
    - `total_frames > 0`.
- For every anchor:
    - `midi_filename` exists in the MIDI file set.
    - `midi_timestamp_seconds` is finite.
    - `camera_frame >= 0`.

The validation is strict and non-recoverable — if any check fails, the load aborts and the previous session is preserved.

## Path resolution

```
stored value                     →  runtime value (after load)
-------------------------------  -------------------------------
""                               →  "" (left as-is)
"disklavier/trial_001.mid"       →  {participant_folder}/disklavier/trial_001.mid
"C:/absolute/path/file.mid"      →  C:/absolute/path/file.mid (left as-is)
```

Saving does the inverse: absolute paths under `participant_folder` become relative, and paths outside that folder or empty strings are stored as-is.

This means:

- Moving a participant folder to a new location and running **Load Alignment…** will prompt to rebase paths once; afterward the session works unchanged (see [Moving participant folders](moving-participant-folders.md)).
- Absolute paths that were never under `participant_folder` survive saves and loads unchanged but won't be rebased.

## Editing the JSON by hand

Hand-editing is possible and supported — the schema is intentionally flat, with no hashes or signatures. The only rules are:

1. Keep `schema_version == 1`.
2. Keep every numeric field finite (no `NaN`, `Infinity`).
3. Keep `duration > 0`, `capture_fps > 0`, `total_frames > 0`.
4. Keep every `anchor.midi_filename` matching an existing MIDI entry.
5. Keep `anchor.camera_frame >= 0`.

If you break any of these, loading the file raises `CorruptAlignmentFileError` with a descriptive message.
