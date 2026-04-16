# FAQ

## Why do file modification times matter so much?

The tool does not trust timestamps embedded inside the `.mid` or `.XML` files — those have proven unreliable on the Disklavier and FX30 workflows. Instead, the *end* of each recording is taken from the file's mtime, and the start is computed as `end − duration`. If an mtime has been bumped by a careless copy, the resulting `unix_start` / `unix_end` are wrong by however long ago the recording really happened, which makes the initial global shift much further from zero and (in extreme cases) can make a clip's entire time range fall outside the MIDI session's range.

See [MIDI files](../2-how-data-is-derived/midi-files.md) and [Camera files](../2-how-data-is-derived/camera-files.md) for the exact derivation.

## What's the safe way to copy participant data?

| Platform | Command |
|---|---|
| Linux / macOS | `cp --preserve=timestamps src dst` or `rsync -a src/ dst/` |
| Windows PowerShell | `robocopy src dst /E /COPY:DAT /DCOPY:T` |
| Archives | `tar`, `zip`, `7z` preserve mtimes by default; verify with `stat` after extraction |

## What if the Disklavier clock drifts mid-session?

In practice it doesn't — within a one-hour recording session the offset between the Disklavier and the FX30 host clocks is effectively constant. If you observe drift *within* a participant, it is usually per-clip rather than continuous (for example, the camera was stopped and restarted and that clip's mtime is a little off). In that case, add an **anchor** on the affected clip; see [Refining with anchors](../4-tutorials/refining-with-anchors.md).

## Why does changing the global shift wipe all my anchors?

Because an anchor's `anchor_shift` is defined relative to the current `global_shift`. Changing `global_shift` would silently change what each anchor means, which is worse than just asking you to re-mark them. The confirmation dialog is the tool's way of requiring that you acknowledge this trade-off.

## Can I edit the JSON by hand?

Yes. The schema is flat and documented in [JSON schema](../6-project-files/json-schema.md). The validator is strict — any field failing the finite / positive / reference checks will cause the load to fail with a `CorruptAlignmentFileError` that names the field. This is safer than silently fixing bad values, because a bad value usually means a subtle bug that should be investigated.

## Does the tool play audio?

No. The tool has no audio playback at all. The MIDI panel is a visual piano roll; the camera panel is a visual video frame viewer. Both panels scrub silently.

## Does the tool export aligned data?

No. The JSON save file **is** the export. Downstream scripts load the JSON, read `global_shift_seconds` and each camera clip's `alignment_anchors + active_anchor_index`, and use the formulas in [two-phase approach](../1-motivation/two-phase-approach.md) to map MIDI seconds ↔ camera frames. The tool ships with tested time-math helpers in `alignment_tool/core/engine.py` that downstream code can import directly.

## Can I use the tool with a different camera or MIDI source?

The metadata extraction is specific to:

- **MIDI**: any standard `.mid` file that `mido` and `pretty_midi` can parse. Non-Disklavier MIDI sources work as long as you accept that the mtime-based timestamp still defines when the recording was made.
- **Camera**: the FX30's Sony non-real-time XML sidecar is currently the only supported metadata format. Other cameras would need a new adapter module — the abstraction point is `alignment_tool/io/camera_adapter.py`.

## Can I align a MIDI file against two different camera clips simultaneously?

Yes — open the pair, switch the **Camera:** combo to the other clip, add a separate set of anchors to the new clip. Anchors are per-camera-clip, not per-pair, so a single MIDI can supply keystrokes for many clips.

## Is there an undo / redo?

No. The only protection against accidental changes is the dirty-flag prompt when opening, loading, or exiting. Save often.

## Why is the MIDI panel scrolling backwards when I drag up?

Because notes fall from top (future) to bottom (past). Dragging up moves the page of notes up, which means looking further into the past — which reduces the current time. This is consistent with most falling-keys visualizations. If you prefer the opposite, drag the other direction.

## Why did a file get skipped at load with "XML sidecar not found"?

The MP4 was found but its matching `.XML` file wasn't. The expected name is `{stem}M01.XML` (case-insensitive). Check:

- Both files were copied over, not just the MP4.
- The naming follows `C####.MP4 + C####M01.XML`.
- The `.XML` extension is intact (not `.xml` + `.XML` duplicate, etc.).

## How accurate is the alignment?

After a computed global shift alone, alignment is usually within a few frames across a participant's whole session. After refining with per-clip anchors, it's typically within 1 frame of the keystroke's onset — limited by how precisely you can identify the onset frame in the video (which the intensity probe helps with; see [using the intensity probe](../4-tutorials/using-intensity-probe.md)).
