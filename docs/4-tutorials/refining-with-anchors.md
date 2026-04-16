# Refining with anchors

A single global shift handles most of a participant's clock offset but cannot correct for per-clip drift (for example, when the camera was briefly stopped and restarted between trials, so the mtime-derived start time is a little off for that clip specifically). Anchors let you refine one clip at a time without disturbing any of the others.

## When to add an anchor

After running the [first-alignment](first-alignment.md) flow, enable **Locked** mode (++l++) and scrub through a few clips. For each clip:

- If the video frame visibly matches the piano roll everywhere, the global shift is enough — no anchor needed.
- If the frame consistently *leads* or *lags* the roll by a fixed amount, that clip needs an anchor.

The drift is almost always within one or two seconds on clips recorded back-to-back. Larger gaps usually mean a different global shift applies, not an anchor.

## Adding an anchor

1. In Level 2, with the clip showing drift, find a clean keystroke that is clearly visible both in the piano roll and on camera.
2. Press ++m++ on the MIDI panel to set the MIDI marker at the selected time.
3. Press ++c++ on the camera panel to set the camera marker at the exact onset frame (the intensity probe helps here — see [§4.3](using-intensity-probe.md)).
4. Click **Add Anchor (A)** in the anchor-table header (or press ++a++).
5. An input dialog asks for an **optional label** — type something descriptive like `"phrase 2 opening"` or leave it blank.
6. The new anchor appears as the last row in the table. Its **Derived Shift (s)** column shows the `anchor_shift` the tool computed for it.

The markers clear after the anchor is created, ready for the next one.

## Activating an anchor

An anchor sitting in the table does nothing on its own. To apply its correction to the clip, **click the cell in the Active column** for that row. A `*` appears and the cell turns dark green — the anchor is now active. If Locked mode is on, the two panels re-sync using the new `effective_shift`.

Only **one** anchor per clip is active at any time. Clicking the Active cell on a different row deactivates the previous one and activates the new one. Clicking the Active cell on the already-active row deactivates it (`effective_shift` falls back to just `global_shift`).

!!! note "Session-only state"
    The active-anchor flag does **not** persist across save/load. Every camera clip starts with no active anchor when you re-open a JSON file. Saved anchors are still there — you just have to reactivate whichever you want. This is deliberate: a just-loaded session with all anchors inactive is visually identical to the "only global shift" baseline, so you can confirm the baseline before re-engaging any refinements.

## Anchor filtering

Only anchors whose **`midi_filename`** matches the MIDI currently selected in the top combo box are activatable. Anchors whose MIDI doesn't match the current selection are still shown in the table but greyed out and non-selectable. This keeps the meaning of "active" unambiguous when the same camera clip is being viewed against different MIDI files.

## Jumping to an anchor

- **Double-click** the **MIDI Time (s)** cell → the MIDI panel jumps to that time.
- **Double-click** the **Camera Frame** cell → the camera panel jumps to that frame.

Both jumps respect the greyed-out rule: they only fire for anchors whose MIDI matches the current selection.

## Deleting an anchor

Select a row and click **Delete Selected**. The anchor is removed immediately; no confirmation dialog. If the deleted anchor was the active one, the clip's `effective_shift` drops back to just the global shift and the view re-syncs if in Locked mode.

## What happens if you re-run Compute Global Shift

The global shift and the anchors are *not* independent. Because each anchor's derived shift is defined relative to the current global shift, changing the global shift would change what each anchor means. Rather than silently rewriting them, the tool raises a warning:

> This will remove all N anchor(s). Continue?

Say Yes only if you want to start over on this participant. If you have good anchors and only want to nudge the global shift by a small amount, delete the anchors first, tune the global shift, then re-add the anchors on the specific clips that still drift.
