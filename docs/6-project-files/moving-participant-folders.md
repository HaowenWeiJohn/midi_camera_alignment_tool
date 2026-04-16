# Moving participant folders

Saved JSON files store media paths **relative to `participant_folder`** when possible, which makes them portable as long as the participant folder travels as a unit. This page covers what happens when the folder has moved between save and load, and how to recover.

## What the JSON stores

Recall from [JSON schema](json-schema.md) that the save file has:

```json
{
  "participant_folder": "C:/data/study/participant_042",
  "midi_files": [
    { "file_path": "disklavier/trial_001.mid", ... }
  ],
  "camera_files": [
    { "mp4_path": "overhead camera/C0001.MP4", ... }
  ]
}
```

`file_path`, `mp4_path`, and `xml_path` are stored relative to `participant_folder` at save time, so moving the whole folder together keeps those paths valid relative-wise.

## What load does

When you **File → Load Alignment…**, the tool:

1. Parses the JSON and validates every field.
2. Checks whether `participant_folder` still exists on disk (`os.path.isdir`).

If the folder exists, load proceeds normally. Relative paths are joined with `participant_folder` to produce absolute paths.

## Rebase prompt

If the stored `participant_folder` does **not** exist, a folder-picker dialog appears:

> Participant folder not found:
> `C:/data/study/participant_042`
>
> Select the new location:

### If you pick a new folder

The tool calls `persistence.rebase_paths(state, new_folder)`, which:

1. For every MIDI file: computes the old relative path via `os.path.relpath(file_path, old_participant_folder)`, then rejoins with the new folder.
2. Does the same for every camera clip's `mp4_path` and `xml_path`.
3. Updates `state.participant_folder = new_folder`.

The session is then adopted and the `_dirty` flag is set — the trailing `*` appears in the title. This is deliberate: the path fix-up is a real change that should be committed by saving the JSON once the new layout is confirmed.

### If you cancel the dialog

The load is aborted. The previous session (if any) stays active; nothing is mutated.

## Common scenarios

**"I copied the participant folder to a new disk."** Load the JSON, accept the folder-picker prompt with the new path. Save over the JSON (or save a new filename) to commit the rebased paths.

**"I renamed the folder."** Same as above — the new name is simply the new `participant_folder`.

**"I copied the JSON but the media is still at the original path."** Load the JSON on a machine that has the original path: no prompt appears, the load succeeds immediately.

**"I want to send the JSON to a collaborator."** Send just the JSON. They will need their own copy of the media (any layout with a `disklavier/` and `overhead camera/` subfolder works). On their first load, they'll get the rebase prompt; from then on their save points at their local path.

## What rebase does NOT do

- It does not verify that the referenced files actually exist at the new location — it only rewrites the strings. If the new folder is missing files, the parse errors surface later (when the MIDI panel tries to open a specific file, or when the camera panel tries to open a specific MP4).
- It does not touch paths that were stored as absolute (or empty). If you've manually edited a `file_path` to be an absolute path outside the participant folder, it will be left alone by the rebase.
- It does not migrate between schema versions. If the JSON is pre-v1, the load fails with `UnsupportedSchemaVersionError` before any rebase logic runs.

## Verifying after a rebase

A quick way to verify a rebase worked:

1. Drill into any MIDI + camera pair in Level 2.
2. Confirm the MIDI panel shows notes and the camera panel decodes frames.

If either panel is empty or shows *"Video unavailable: …"* or *"No MIDI loaded"*, some of the remapped paths still don't resolve. Re-check the folder layout against [§3.2 Data layout](../3-getting-started/data-layout.md) — the subdirectory names must be exactly `disklavier/` and `overhead camera/`.
