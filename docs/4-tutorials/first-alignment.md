# Your first alignment

This tutorial walks through a complete alignment from an unopened participant folder to a saved `.json` session. It uses the two-marker **Compute Global Shift** flow, which is the right starting point for every new participant.

## Before you begin

- The data is laid out as described in [§3.2 Data layout](../3-getting-started/data-layout.md).
- File modification times have been preserved on both `.mid` and `.MP4` files. Without this, the raw `unix_start` values will be off by however long ago the copy was made, and the first alignment will take a lot of scrubbing to find the right frame.

## Step 1 — Open the participant

**File → Open Participant…** (++ctrl+o++), then choose the participant's top-level folder. The status bar should now read something like:

```
Participant 042 | 12 MIDI files | 12 camera clips | Global shift: 0.000s | Anchors: 0
```

You're looking at **Level 1 — the timeline overview**.

## Step 2 — Skim the timeline

The Level 1 view shows every MIDI clip as a blue bar on the top row and every camera clip as an orange bar on the bottom. Because `global_shift_seconds` is still `0.0`, the two rows are offset by the full participant clock difference (usually several minutes apart).

- **Scroll wheel** — zoom in/out around the cursor.
- **Click + drag empty space** — pan the time view.
- **Hover** over a bar — tooltip shows filename, duration, and unix timestamps.

Pick a MIDI clip that has a short, obvious introductory pattern and the camera clip that was rolling during it.

## Step 3 — Select a pair and drill in

1. **Click** the MIDI bar → it turns dark blue with a yellow border.
2. **Click** the matching camera bar → it turns dark orange with a yellow border.
3. **Double-click** either bar (or click **Open Selected Pair**) → the app switches to **Level 2 — the detail view**.

## Step 4 — Find the same keystroke in both panels

Level 2 shows the MIDI piano roll on the left and the camera frame on the right. Between them sits the **overlap indicator** — a 30 px dual-track navigation bar that lets you scrub either panel by clicking.

1. On the **MIDI panel** (left): drag vertically to scrub (dragging *down* moves forward in time). Stop on a clean, distinctive keystroke — a sharp single note works best. Double-clicking a note snaps the playhead exactly to its start.
2. Press ++m++. The "MIDI mark" label under the piano roll flashes blue and reads something like `MIDI mark: trial_001.mid @ 12.456s`.
3. On the **camera panel** (right): use the overlap bar to navigate close to that moment, then scroll-wheel to zoom in on the keyboard (up to 20×, centered on the cursor). The ++left++ / ++right++ arrow keys step one frame at a time once the camera panel is the active panel (press ++tab++ to switch active panel, or simply scroll/click in the camera area).
4. When you have the exact frame where the physical keystroke begins, press ++c++. The "Camera mark" label flashes and reads `Camera mark: frame 2987 (12.467s)`.

!!! tip "Use the intensity probe to find the onset frame"
    The "same keystroke" is subjective to a few frames by eye. Right-click the exact piano key you marked in MIDI — a small red dot drops and the **intensity plot** below fills in with the pixel's luma over the ±120 frames around the current position. The onset frame is the clear slope change. See [§4.3 Using the intensity probe](using-intensity-probe.md).

## Step 5 — Compute the global shift

With both markers set, the **Compute Global Shift** button in the top bar becomes enabled (and the ++a++ shortcut becomes enabled for anchor creation; we'll use **Compute Global Shift** for the first pass).

1. Click **Compute Global Shift**. A confirmation dialog shows `Computed global shift: X.XXXX s — Apply this as the global shift?`
2. Click **Yes**. If there were no anchors, the new shift is applied immediately. If any anchors existed, a second dialog warns *"This will remove all N anchor(s). Continue?"* — because changing the global shift invalidates every anchor.

The markers are cleared. The overlap bar now shows a large green overlap region where previously the two tracks were far apart. Press ++l++ (or click **Mode: Independent**) to toggle into **Locked** mode: now scrubbing either panel drives the other. Spot-check a few places in the clip to confirm that the video frame matches the keystrokes on the roll.

## Step 6 — Save

**File → Save Alignment…** (++ctrl+s++). A standard save dialog appears; pick a filename such as `participant_042_alignment.json`. The save is atomic (written to a temp file first, then replaced), and the trailing `*` disappears from the window title.

## Step 7 — Verify by loading

Close the app. Re-open it. **File → Load Alignment…** (++ctrl+l++) and pick the JSON you just saved. The entire session — every file's timing data and the global shift you computed — is restored without you needing to reopen the participant folder. If the folder has since moved, the tool will ask for the new location and re-map the paths automatically (see [§6.3 Moving participant folders](../6-project-files/moving-participant-folders.md)).

## What you did

You measured one keystroke's timing in both modalities, derived the constant clock offset between the two recording systems, and persisted it. Every MIDI event in this participant's data can now be converted to a camera frame using that single number.

If later inspection shows that a particular camera clip still drifts a little after the global shift, you don't need to start over — that's what anchors are for. See the next tutorial: [Refining with anchors](refining-with-anchors.md).
