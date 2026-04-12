# 7. Workflows

The tool is designed around two sequential phases. Both assume a participant has been loaded via `File → Open Participant…`.

## 7.1 Phase 1 — Set the Global Shift

The goal of Phase 1 is to pick a single `global_shift_seconds` for the participant that roughly lines up all the camera clips with the MIDI timeline.

### Method A — Compute from matching markers (recommended)

1. In Level 1, select any camera clip that clearly overlaps with one MIDI file (in raw time, they will be minutes apart — pick based on participant notes or the session structure). Also select a MIDI file. Double-click to drill into Level 2.
2. In Level 2, stay in **Independent** mode (the default).
3. Scrub the MIDI panel to a distinctive note-on event — for example, a loud chord, a high note, or the first note of a recognizable phrase. Press **M** to mark the MIDI position.
4. Scrub the camera panel to the visible keypress that corresponds to that same event. Press **C** to mark the camera frame.
5. Click **Compute Global Shift**. The tool computes:
   ```
   shift = midi_unix_marker - camera_unix_marker
   ```
   (via `compute_global_shift_from_markers`) and shows the value in a confirmation dialog.
6. Confirm. If any anchors already exist, a second confirmation warns that all anchors will be cleared.

After this, `AlignmentState.global_shift_seconds` is set; Level 1 now shows all camera bars positioned accordingly. Overlaps should be visible within ~1–2 s tolerance.

### Method B — Type a value directly

In Level 1, type a value into the Global Shift spinner and press **Apply**. Used when a known value is available (for example, reloading an alignment from another participant in the same session). Same anchor-wipe confirmation applies.

### How to tell it's right

- All camera bars in Level 1 should land roughly under the MIDI bars they were recorded during — i.e., the session's overall shape (trials, breaks, transitions) now makes sense.
- Drilling into any aligned pair in locked mode and scrubbing should keep the two panels within a second or two of the same event.

## 7.2 Phase 2 — Per-Clip Anchor Refinement

The goal of Phase 2 is precise sync for each camera clip individually. After Phase 1, clips are within ~1–2 s of truth — good enough to use locked mode as a browsing aid.

For each camera clip:

1. In Level 1, select the MIDI file that overlaps this camera clip and the camera clip itself. Drill into Level 2.
2. Switch to **Locked** mode. The panels now move together with `effective_shift = global_shift` (no anchor yet).
3. Scrub to a region where you can identify a specific visible keypress. The MIDI playhead should be within ~1–2 s of the matching MIDI note-on.
4. Switch to **Independent** mode to fine-tune each side separately. Use arrow keys (and `Tab` to switch the active panel) for exact placement.
5. Press **M** on the MIDI panel at the exact note-on tick, and **C** on the camera panel at the exact onset frame.
6. Press **A** (or click **Add Anchor**) — you'll be prompted for an optional label. A new anchor appears in the anchor table with the derived shift computed.
7. In the anchor table, click the **Active** cell to activate the new anchor. `effective_shift` now includes `anchor_shift`; locked mode will use it for precise sync.

### Why create multiple anchors per clip?

- **Verification.** Two anchors should yield very similar derived shifts (within a few ms). If they diverge, one is likely wrong — go back and review.
- **Regional accuracy.** For long clips with possible drift, one anchor near the start and one near the end lets the operator pick whichever is closer to the region of interest.
- **Flexibility.** You can add several candidates and delete the bad ones.

Only **one** anchor can be active at a time per camera clip. Clicking the active anchor's Active cell deactivates it; clicking another activates the other. With no active anchor, locked mode falls back to `global_shift` alone.

### The anchor-lock rule

When **Locked** mode is on **and** an anchor is active, the MIDI combo is disabled and forced to the MIDI file referenced by the anchor (see `_apply_anchor_lock_rule` in `level2_view.py`). This prevents the operator from accidentally navigating an "aligned" view against the wrong MIDI file.

To free the combo, either:

- Deactivate the anchor, or
- Switch to Independent mode.

## 7.3 Saving and Reviewing

When done, `File → Save Alignment…` writes the state to JSON. The JSON contains anchor pairs, `global_shift`, `active_anchor_index` per clip, and basic file metadata.

To review later, `File → Load Alignment…` reconstructs the state. **However**, because the JSON does **not** store `file_path`, `mp4_path`, `xml_path`, `total_frames`, `ticks_per_beat`, or `tempo`, Level 2 (which needs to re-parse MIDI notes and seek MP4 frames) will not function until these are re-populated from the participant folder. In the current implementation this means: for editing a loaded alignment in Level 2, also re-open the participant folder.

Level 1 works on just the JSON (it only needs `unix_start`, `duration`, `capture_fps`, and anchor pairs to compute positions).

## 7.4 Handling "No Overlap"

Sometimes a camera clip has no intersection with the selected MIDI file at the current alignment. Level 2:

- In Independent mode — no problem; each panel navigates its own full range.
- In Locked mode — the follower panel shows a gray "starts in X s" or "ended X s ago" message (computed from `out_of_range_delta`).

If you press `O` (jump to overlap) and there's genuinely no overlap, a "No Overlap" dialog appears suggesting you revisit the global shift.

## 7.5 When the Global Shift Is Wrong Later

If you discover mid-Phase-2 that Phase 1 was off, you can re-run Phase 1. The tool will warn you that all existing anchors will be cleared (across all clips) and require confirmation. This is intentional — see [Alignment Concepts §4.4](./04-alignment-concepts.md) for the rationale.

Safety: if you cancel the dialog, nothing changes. The tool never silently discards anchors.

## 7.6 Tips and Best Practices

- **Pick distinctive events** for markers: loud single notes, extreme registers (very high / very low), or notes that stand alone temporally. Dense clusters are hard to match visually.
- **Save early and often.** There is no auto-save. Save after Phase 1, then after each cluster of anchors, so you can roll back if you make a bad change.
- **Use the Level 1 timeline as a sanity check.** After setting the global shift, the camera bars should visually align with MIDI bars in a coherent session structure. Anything that looks wildly off usually indicates the wrong MIDI/camera pair was used for Phase 1.
- **Use two anchors per clip for verification.** If their derived shifts agree to within a few milliseconds, you have confidence. If they differ by 50+ ms, something is wrong.
