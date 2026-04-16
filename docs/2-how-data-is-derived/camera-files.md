# Camera files

For each `.MP4 + .XML` pair the tool derives a `CameraFileInfo` record: filenames, frame count, capture FPS, duration, and wall-clock start/end. This page documents what comes from the XML sidecar, what comes from cv2, and how the timestamps are computed.

Source: `alignment_tool/io/camera_adapter.py`.

## The two inputs

The Sony FX30 writes two files for every clip:

1. **`C####.MP4`** — the video stream itself.
2. **`C####M01.XML`** — a sidecar describing the clip using the Sony "non-real-time metadata" schema (namespace `urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20`).

Both are required. If the XML sidecar is missing, the participant loader skips the MP4 with a warning (see [folder scanning](folder-scanning.md)).

## From the XML sidecar

`CameraAdapter._parse_xml` reads exactly two pieces of information:

- `nrt:Duration@value` → **`duration_frames`** (an integer count of frames in the clip).
- `nrt:VideoFrame@captureFps` → **`capture_fps`** (e.g. `239.76p` → `239.76`).
- `nrt:VideoFrame@formatFps` → **`format_fps`** (available but not used by alignment math).

Trailing progressive/interlaced flags (`p` or `i`) are stripped before parsing as a float.

!!! note "XML CreationDate is ignored"
    The XML file also contains a `CreationDate` element, but the tool **does not** read it. On many clips that field is missing, unreliable, or stored in a local-time format without a timezone. The camera's wall-clock timestamp comes from the MP4 mtime instead (see below).

## From cv2

`CameraAdapter._parse_mp4_properties` opens the MP4 briefly with `cv2.VideoCapture`, reads four properties, and releases the handle:

| Property | Field |
|---|---|
| `CAP_PROP_FRAME_COUNT` | `total_frames` |
| `CAP_PROP_FPS` | `mp4_fps` (informational only; `capture_fps` from XML is authoritative) |
| `CAP_PROP_FRAME_WIDTH` | `mp4_width` |
| `CAP_PROP_FRAME_HEIGHT` | `mp4_height` |

The XML's `capture_fps` is the value used everywhere in the alignment math. The cv2 `FPS` reading is only kept for debugging; on 4K-at-240fps clips the cv2 value can differ from the XML's true capture rate by up to a frame.

## Duration

```
duration = duration_frames / capture_fps
```

This is the wall-clock length of the clip in seconds. On a typical 240-fps capture a 5-second clip is 1200 frames.

## Wall-clock timestamps

Same mtime-based rule as for MIDI:

```
unix_end   = os.path.getmtime(mp4_path)
unix_start = unix_end − duration
```

The FX30 closes the MP4 when you press STOP, so the mtime reflects the camera's internal clock at end-of-recording. Because the camera and the Disklavier host maintain **independent** clocks, `unix_start` from this formula does not match `unix_start` for a simultaneously-recorded MIDI file — that gap is the whole reason this alignment tool exists. See [§1 Why alignment is needed](../1-motivation/why-alignment.md).

!!! warning "Preserve mtimes when copying files"
    Just as with MIDI files, copying an `.MP4` with a tool that updates the mtime will shift `unix_end` to the copy time and break the alignment. Use `cp --preserve=timestamps`, `rsync -a`, or `robocopy /DCOPY:T`, and verify with `stat` / `ls -l --full-time` before and after. You can always re-measure the offset by marking one keystroke pair and recomputing the global shift, but preserving mtimes is far less work.

## Fields on `CameraFileInfo`

The adapter produces a `CameraFileInfo` dataclass (see `alignment_tool/core/models.py:14-31`):

| Field | Meaning |
|---|---|
| `filename` | MP4 basename, e.g. `"C0001.MP4"` |
| `xml_filename` | XML basename, e.g. `"C0001M01.XML"` |
| `mp4_path`, `xml_path` | Absolute paths at runtime; relative in JSON |
| `raw_unix_start` | `unix_end − duration` — the clip's wall-clock start |
| `raw_unix_end` | `os.path.getmtime(mp4_path)` |
| `duration` | `duration_frames / capture_fps` |
| `capture_fps` | From XML (~239.76 on FX30 high-frame-rate captures) |
| `total_frames` | From cv2 `CAP_PROP_FRAME_COUNT` |
| `alignment_anchors` | Initially empty; filled in by the user |
| `active_anchor_index` | `None` at load; session-only |

The word **raw** in `raw_unix_start` is deliberate — it's the unmodified mtime-derived start time, before any `global_shift` or anchor correction has been applied. The "aligned" start that Level 1 plots uses `raw_unix_start + effective_shift` under the hood.
