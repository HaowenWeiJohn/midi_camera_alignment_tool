# Saving and loading

The alignment session is persisted as a single **JSON file** (Schema v1). Saving and loading go through `alignment_tool.core.persistence`, which is intentionally free of UI code so it can be round-tripped in tests and in downstream scripts.

## Save (++ctrl+s++)

**File → Save Alignment…** shows a standard file picker for `*.json`. After you choose a path:

1. The full `AlignmentState` is serialized (see [JSON schema](json-schema.md) for the exact layout).
2. A temp file is created next to the target (`{target}.{random}.tmp`), the JSON is written with `indent=2`, UTF-8, `ensure_ascii=False`, `allow_nan=False`.
3. `os.replace(temp, target)` renames the temp to the final path — an **atomic** replacement on all supported platforms. Either the old file is intact or the new file is intact; there is no partial-write window.
4. On success, the `_dirty` flag is cleared, the trailing `*` drops from the window title, and the status bar briefly shows `Saved: /path/to/alignment.json`.

If the write fails for any reason, the temp file is removed (best-effort) and the exception propagates through the standard error dialog router. Common failure modes:

- `PermissionError` — the target folder is not writable.
- `json.JSONDecodeError` / `ValueError` via `allow_nan=False` — should never happen with a valid `AlignmentState`; indicates a bug.

## Load (++ctrl+l++)

**File → Load Alignment…** shows a file picker for `*.json`. The file is read in one shot and validated before any state is swapped in:

1. UTF-8 decode and `json.load` — a `json.JSONDecodeError` bubbles up as `CorruptAlignmentFileError`.
2. `schema_version` is checked against `SCHEMA_VERSION = 1`. A mismatch raises `UnsupportedSchemaVersionError` with both the found and expected version.
3. The dict is converted to dataclasses; missing or type-wrong fields raise `CorruptAlignmentFileError`.
4. `_validate_state` runs post-rehydration — see [JSON schema: validation](json-schema.md#validation-rules). Any failure here raises `CorruptAlignmentFileError`.
5. **Path resolution**: every file path stored in the JSON is joined with the saved `participant_folder` if relative, or passed through if absolute/empty. See [Moving participant folders](moving-participant-folders.md) for what happens when the folder no longer exists.

If the load succeeds, the new `AlignmentState` replaces the current session entirely (`MainWindow._set_state`), Level 1 renders its timeline, Level 2 is reset, and Save is enabled.

## Schema v1 is self-contained

A Schema v1 file alone is enough to rehydrate a fully-functional session — you do not need to re-open the participant folder first. Every field the app needs at runtime is stored: MIDI tempos, ticks-per-beat, camera FPS, frame counts, unix timestamps, anchor pairs. The source media files are only re-read when you actively scrub a camera clip (via the cv2 frame worker) or inspect a MIDI file (via `MidiAdapter`).

This means:

- You can inspect a saved JSON on a machine without the source media and confirm what the session *says* happened.
- You can share the JSON with collaborators who have their own copy of the media at a different path — they'll hit the rebase dialog once on load (see [Moving participant folders](moving-participant-folders.md)).
- You **cannot** load a pre-v1 file; there is no migration layer. If you have an older save format, the tool raises `UnsupportedSchemaVersionError` immediately.

## Unsaved-changes protection

Three actions check `_dirty` and prompt Save/Discard/Cancel before proceeding if you have unsaved changes:

- **Open Participant…** — would replace the session.
- **Load Alignment…** — same.
- **Exit** / close window — would lose the session.

See [Main window: Unsaved-changes prompt](../5-reference/main-window.md#unsaved-changes-prompt) for the dialog's behaviour.

## What the save captures

- `participant_id`, `participant_folder`
- `global_shift_seconds`
- `alignment_notes` (reserved; currently always `""`)
- All MIDI file descriptors with their timing metadata
- All camera file descriptors with their timing metadata and frame counts
- Every anchor on every camera clip

## What the save does NOT capture

- `active_anchor_index` — session-only (cleared on every load).
- Level 2 marker state (`midi_marker`, `camera_marker`) — session-only, not in any model.
- UI state — zoom levels, pan offsets, selected bars, active panel, probe dot, mode (Independent vs Locked).
- Any decoded frames, note lists, or cached tempo tables — those are recomputed from the source files when needed.

Re-loading a session is deliberately a clean slate for UI state, with the alignment itself fully restored.
