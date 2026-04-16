# Error messages

The tool surfaces all errors through modal `QMessageBox` dialogs — critical (red icon) for unrecoverable problems, warning (triangle icon) for user-correctable invariant violations. Every dialog's title is the Python exception class name; the body is the exception message.

This page explains each exception class the user might see, what caused it, and how to recover.

## Media loading errors (critical)

Raised when a `.mid`, `.MP4`, or XML file can't be parsed. The participant loader catches these per-file and aggregates them into a single warning list instead of a hard failure — but if they reach the top-level handler, one of these dialogs appears.

| Class | Cause | Remedy |
|---|---|---|
| `MidiParseError` | `mido` or `pretty_midi` couldn't parse a `.mid` file. Usually a truncated file or a format variant (SMF 2) the libraries don't handle. | Verify the file with an external MIDI tool. Most often it's a short recording that never finalized its end-of-track meta event. |
| `CameraXmlParseError` | The Sony XML sidecar is missing, malformed, or from a newer schema. | Check the `.XML` file alongside the `.MP4`. Expected namespace is `urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20`; required elements are `nrt:Duration@value` and `nrt:VideoFrame@captureFps`. |
| `VideoOpenError` | `cv2.VideoCapture` refused to open the `.MP4`. | Verify the file plays in another tool. OpenCV's Windows backend can reject files with unusual codec variants — converting with ffmpeg typically fixes it. |

## Persistence errors (critical)

Raised by load paths only.

| Class | Cause | Remedy |
|---|---|---|
| `UnsupportedSchemaVersionError` | The JSON's `schema_version` is not `1`. | There is no migration layer. Either re-create the session using the current tool, or manually update the JSON to Schema v1 (see [JSON schema](../6-project-files/json-schema.md)). |
| `CorruptAlignmentFileError` | JSON syntactically invalid, missing required keys, non-finite numbers, `duration <= 0`, `capture_fps <= 0`, `total_frames <= 0`, anchor referencing an unknown MIDI filename, or `camera_frame < 0`. The dialog body contains the specific reason. | Read the reason in the dialog. Fix the field in the JSON with a text editor, or re-create the session. |

## Invariant errors (warning)

Raised when a user action would violate an internal invariant. These are corrected at the call site (typically by showing a confirm dialog), so most users never see them directly.

| Class | Cause | Remedy |
|---|---|---|
| `AnchorsExistError` | Attempted to change `global_shift_seconds` while anchors exist and `clear_anchors_if_needed=False`. In the UI this is intercepted and turned into a *"…will remove all N anchor(s). Continue?"* prompt. | Click **Yes** on the prompt if you're okay clearing anchors; click **No** to keep the current shift. |
| `InvalidAnchorError` | An anchor index is out of range or a `camera_index` is out of range. Indicates a bug in the UI layer; users shouldn't see this. | File an issue with the steps to reproduce. |
| `UnknownMidiFileError` | Adding an anchor whose `midi_filename` doesn't exist in the session. Should be unreachable in the UI (the anchor is built from a marker against a loaded MIDI). | Indicates a bug — file an issue. |
| `InvalidFpsError` | A camera file has `capture_fps <= 0`. Caught at camera load, not usually user-visible. | Check the `.XML` sidecar's `captureFps` value. |
| `MarkersNotSetError` | Pressing **Compute Global Shift** or **Add Anchor** when one of the two markers isn't set. | Set both markers: ++m++ on the MIDI panel, ++c++ on the camera panel, then retry. |

## Non-error dialogs

Informational pop-ups that aren't exceptions but look similar:

| Title | When | What to do |
|---|---|---|
| *"No Files Found"* | Opening a participant folder that has no `.mid` or `.MP4` files | Verify the folder layout matches [§3.2 Data layout](../3-getting-started/data-layout.md). |
| *"Some files could not be loaded"* | Some individual files were skipped during participant load | The dialog lists each skipped file and the reason. The successfully-loaded files are still available. |
| *"No Overlap"* | Pressing ++o++ in Level 2 when the MIDI and camera clips don't overlap at the current shift | Adjust the global shift first, or use the overlap indicator to see the gap visually. |
| *"Participant folder not found"* | Loading a JSON whose `participant_folder` doesn't exist | Pick the new location or cancel. See [Moving participant folders](../6-project-files/moving-participant-folders.md). |
| *"Unsaved Changes"* | Closing / opening / loading while dirty | Choose Save / Discard / Cancel as appropriate. |

## Unexpected errors

Anything not covered by the classes above surfaces as a generic `QMessageBox.critical` with the title *"Error"* and the exception's string representation as the body. These are bugs — please file an issue with the message text and repro steps if you encounter one.
