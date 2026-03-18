# MIDI-Camera Alignment Tool — Specification

## Problem Statement

We have two unsynchronized recording systems per participant in a piano study:

- **Disklavier MIDI** — the **reference clock** (ground truth timing), recorded at high temporal resolution
- **Overhead camera (Sony FX30)** — has a clock offset of **1–20 minutes** relative to MIDI, consistent across all files in a session

Both systems were started and stopped by humans independently. The camera was started and stopped **frequently and irregularly** — sometimes multiple camera clips fall within a single MIDI trial. The goal is to temporally align every overhead camera file to the MIDI reference timeline.

## Data Sources

### MIDI Files (Disklavier)

- Format: `.mid` files
- Contains: note-on/off events with pitch, velocity, timing; tempo; polytouch/aftertouch events
- Timing: `track_name` meta message encodes the **end time** as `YYYYMMDD_HHMMSS` (naive, no timezone). Start time is derived by subtracting duration. A `utc_offset` parameter is required for correct unix timestamps.
- Very high temporal resolution (ticks per beat, typically hundreds or thousands of ticks per beat)
- Each file has: unix start time, unix end time, duration, sampling rate

### Overhead Camera Files (Sony FX30)

- Format: `.MP4` video + XML sidecar metadata
- XML provides: `CreationDate` (timezone-aware, **start time**), duration in frames, capture FPS (~240fps), format FPS (~24fps), LTC timecodes
- Wall-clock duration = `duration_frames / capture_fps`
- Each file has: unix start time, unix end time, duration, sampling rate (frame rate)

### Key Observations

- There are typically ~10–15 clips from each source per participant
- The camera clips and MIDI files do not have a 1:1 correspondence — camera may start/stop multiple times within a single MIDI trial
- The clock difference between the two systems is a **constant offset per participant** (1–20 minutes), affecting all files uniformly

## Alignment Approach

### Phase 1: Global Offset (per participant)

Find a **single constant shift value** that applies to **all** overhead camera files for that participant.

**Method (manual):**

1. Open the alignment tool for a participant
2. Navigate to a specific overhead camera video and identify a visible keypress at a known frame/timestamp
3. Navigate to the overlapping MIDI file and find the corresponding note-on event
4. The time difference between the MIDI event time and the camera event time = **global offset**
5. Apply the global offset — this shifts all camera files by the same amount

**Result:** After applying the global offset, all camera clips are aligned to within ~1–2 seconds of their true position.

### Phase 2: Within-Clip Refinement (per camera file)

For each individual camera clip, create **one or more alignment anchors** to fine-tune alignment.

An **alignment anchor** is a pair: (MIDI timestamp, camera frame number) — two events the operator has identified as the same physical keypress. The local shift is *derived* from the anchor, not stored as a bare number.

**Method (manual):**

1. Since the global offset already places things within ~2 seconds, use **locked mode** (which uses global_shift) to scrub and find a keypress visible in both views — the two panels will be roughly in sync
2. Switch to **independent mode** to fine-tune each side separately to the exact MIDI tick and camera frame
3. Mark the MIDI timestamp and the camera frame
4. **Add as anchor** — this stores the pair in the camera clip's anchor list
5. **Activate the anchor** — locked mode now uses `global_shift + anchor_shift` for precise sync
6. Repeat to add more anchors if desired (e.g., at different points in the clip for verification or to handle drift)

**Why multiple anchors per clip:**
- **Verification:** If two anchors yield similar derived shifts, the alignment is trustworthy. If they disagree significantly, something is wrong (e.g., wrong keypress match, or clock drift within the clip).
- **Regional accuracy:** For long clips, an anchor near the beginning may be more accurate for the first half, and an anchor near the end for the second half.
- **Flexibility:** The operator can add anchors, review them, delete bad ones, and select the best one for navigation.

**Result:** Each camera clip has a list of anchors. At most one can be **activated** at a time for locked navigation. All anchors can be deactivated, in which case locked mode falls back to global shift only.

### Alignment Anchors — Data Structure

Each anchor stores:

| Field | Description |
|---|---|
| `midi_filename` | Which MIDI file the MIDI timestamp refers to |
| `midi_timestamp_seconds` | Time within the MIDI file (seconds from MIDI file start) |
| `camera_frame` | Frame number within the camera clip (0-indexed) |
| `label` | Optional operator note (e.g., "C4 onset", "loud chord") |

The **derived shift** for any anchor is computed as:

```
camera_time_at_anchor = camera_frame / capture_fps
camera_unix_at_anchor = raw_camera_unix_start + camera_time_at_anchor

midi_unix_at_anchor = midi_file_unix_start + midi_timestamp_seconds

anchor_shift = midi_unix_at_anchor - camera_unix_at_anchor - global_shift
```

This `anchor_shift` is the effective per-clip correction derived from this specific anchor.

*Note: `anchor_shift` depends on `global_shift` in the formula, but since changing `global_shift` clears all anchors (see Strict Phase Ordering below), `anchor_shift` is always computed against a stable `global_shift` value.*

### Aligned Time Formula

For any camera file, using the **active anchor**:

```
aligned_camera_time = raw_camera_time + global_shift + anchor_shift
```

Where `anchor_shift` is derived from the active anchor (see formula above), not stored directly.

- `global_shift`: single value per participant, applied to all camera files, default **zero**
- `anchor_shift`: derived from the selected anchor for this camera clip
- If no anchors exist yet for a clip, `anchor_shift` = 0 (only global shift applies)

### Global Shift and Anchors — Strict Phase Ordering

Global shift (Phase 1) and anchors (Phase 2) follow a **strict ordering**: anchors are calibrated relative to the current global shift. If the global shift is changed after anchors have been created, those anchors become invalid.

**Rule: Changing global shift removes all alignment anchors** across all camera clips for that participant.

**Rationale:**
1. Phase 1: Operator sets global shift → all clips are roughly aligned (~within 1–2 seconds)
2. Phase 2: Operator creates anchors per clip → the operator found matching keypresses by browsing in locked mode with the current global shift
3. If global shift changes later, the operator may have matched keypresses under the old alignment that are no longer the best matches → clearing anchors forces re-verification under the corrected global shift. Additionally, the displayed `anchor_shift` values would all change (confusing), even though the total shift is mathematically invariant.

**UI behavior:** When the operator changes the global shift value and anchors exist anywhere, a confirmation dialog appears: *"Changing global shift will remove all N anchors across M camera clips. Continue?"* The operator can cancel to preserve existing anchors, or confirm to apply the new global shift and wipe all anchors.

## Tool Design

### Technology

- **Framework:** PyQt5 (Qt for Python)
- **Code location:** All tool source code lives in the `alignment_tool/` directory within this repository

### Participant Loading

The operator loads a participant by selecting a **participant folder** via a folder picker dialog. The tool scans the selected folder for `disklavier/` and `overhead camera/` subdirectories, discovering `.mid` files and `.MP4`/`.XML` file pairs automatically. No fixed data root path is assumed.

### GUI Structure — Two Levels

The tool has a **two-level GUI**. Level 1 is the overview; Level 2 is the detail/alignment view. Both levels are displayed in a **single window** using a stacked layout: Level 2 replaces Level 1 content when drilling into a pair, and a **back button** returns to Level 1.

---

### Level 1: Timeline Overview (entry point)

This is the first screen the operator sees after loading a participant. It shows a **timeline bar chart** similar to `plot_raw_timeline_single_participant.py`:

- **Two horizontal rows** of bars on a shared time axis (seconds, relative to first MIDI start):
  - **Top row (blue):** MIDI file blocks — each bar represents one `.mid` file, positioned by its unix start time and sized by its duration
  - **Bottom row (orange):** Overhead camera blocks — each bar represents one `.MP4` clip, positioned by its (shifted) start time and sized by its duration
- The time axis reflects the **current alignment state**: camera bars are positioned using `raw_start + global_shift + anchor_shift` (where `anchor_shift` is derived from the active anchor if one exists, otherwise 0), so as shifts are applied, the camera bars visually move into alignment with the MIDI bars
- The **global shift** input field and apply button are accessible here, since it affects the entire overview
- Each bar is **clickable/selectable** — the operator selects one MIDI block and one camera block to drill into
- Each bar displays its **filename** (or a short label). On mouse hover, a **tooltip** shows full details: filename, duration, start/end timestamps

#### Selection and Drill-Down

1. Click a MIDI block — it highlights (e.g., darker blue outline)
2. Click a camera block — it highlights (e.g., darker orange outline)
3. With both selected, a button (or double-click) opens **Level 2** for that pair
4. The overview remains accessible (back button or tab) so the operator can return, select a different pair, or review the overall timeline

#### What the Overview Shows

- All MIDI files and all camera clips for the participant at a glance
- Which camera clips overlap which MIDI files (visually obvious from bar positions)
- The effect of the current global shift (camera bars shift in real time as the value changes)
- Gaps, overlaps, and the general recording structure of the session

---

### Level 2: Alignment Detail View

Opened from Level 1 by selecting a MIDI + camera pair. This is the side-by-side view for navigation and alignment.

The layout has two panels: MIDI (left) and overhead camera (right).

#### MIDI Panel — Falling Keys Visualization

- A "falling keys" display similar to piano tutorial apps (e.g., Synthesia)
- Notes fall downward toward a **piano keyboard rendered at the bottom** of the display
- Note color encodes **velocity** (how hard the key was pressed)
- A **cursor/playhead line** indicates the current MIDI timestamp
- The user can navigate (scroll/scrub) to any MIDI timestamp
- The MIDI file displayed is the one selected in Level 1 (can be changed via dropdown if needed)
- **Anchor lock rule:** When an anchor is active **and** locked mode is on, the MIDI panel **automatically switches** to display the MIDI file referenced by the active anchor (`midi_filename`). The dropdown is locked/grayed in this state. The operator must deactivate the anchor or switch to independent mode to freely change the MIDI file. In independent mode, activating an anchor does **not** switch the MIDI panel — the operator can freely browse any MIDI file. The auto-switch only triggers when both conditions are met (anchor active AND locked mode on).

**Timeline resolution:** The MIDI timeline operates at the native MIDI sampling rate. For this dataset, the MIDI time resolution is **1/1920 seconds (~0.521 ms per tick)**, derived from `1 / log.time_resolution`. Navigation steps through MIDI time in tick-sized increments. The visualization resolution (how many ticks are visible on screen at once) can be zoomed, but the underlying timeline granularity is always one MIDI tick.

#### Overhead Camera Panel — Video Frame Display

- Displays the video frame at the current camera position
- A **frame counter/timestamp** showing the current frame number and camera time
- The user can navigate frame-by-frame or scrub to any position
- The camera clip displayed is the one selected in Level 1 (can be changed via dropdown if needed)

**Timeline resolution:** The camera timeline operates at the native capture frame rate of **239.76 fps (~4.17 ms per frame)**. Navigation steps one frame at a time.

**Frame indexing:** The MP4 container stores **all** ~240fps capture frames (played back in slow-motion at ~24fps). The cv2 frame index maps 1:1 to the capture frame index — `cv2.VideoCapture.set(CAP_PROP_POS_FRAMES, N)` seeks to capture frame N. The `camera_frame` field in anchors is this cv2/container frame index (0-indexed).

#### Resolution Relationship

The two timelines have different native resolutions:

| Source           | Rate      | Step size  |
|------------------|-----------|------------|
| MIDI             | 1920 Hz   | ~0.521 ms  |
| Overhead camera  | 239.76 Hz | ~4.17 ms   |

One camera frame spans approximately **8 MIDI ticks** (1920 / 239.76 ≈ 8.01). This means:
- In locked mode, advancing one camera frame advances the MIDI cursor by ~8 ticks
- In locked mode, advancing one MIDI tick does not change the displayed camera frame (the frame changes every ~8 MIDI ticks)

### Navigation Modes

There are **two navigation modes**, toggled by a button in the UI:

#### Independent Mode (default)

Both panels navigate **independently**. The MIDI cursor and the camera frame position are decoupled.

**When to use:** Phase 1 — before the global offset is known. The operator freely browses the MIDI timeline to find a note-on event, and separately browses the camera video to find the corresponding visible keypress. Since the clocks are off by minutes, there is no meaningful linked position yet.

**Workflow in this mode:**
1. Navigate the MIDI panel to a distinctive note-on event, note the MIDI unix timestamp
2. Navigate the camera panel to the matching visible keypress, note the camera unix timestamp
3. Compute offset: `global_shift = midi_unix_timestamp - camera_unix_timestamp`
4. Enter the global shift value and apply it

#### Locked Mode

Both panels navigate **together**. Moving either panel's cursor moves the other. Locked mode is **always available** — it can be activated at any time regardless of whether global shift or anchors have been set.

**The effective shift used in locked mode depends on the current alignment state:**

| State | Effective shift | Typical accuracy |
|---|---|---|
| No global shift, no active anchor | 0 | Clocks differ by minutes — follower will likely be out of range |
| Global shift set, no active anchor | `global_shift` | ~1–2 seconds |
| Global shift set, anchor activated | `global_shift + anchor_shift` | Sub-frame precision |

**When to use:**
- **Before global shift:** Can be activated, but not very useful since clocks differ by minutes — the follower panel will show "out of range"
- **After global shift, before anchors:** Useful for browsing roughly-aligned clips to find matching keypresses for anchor creation
- **After anchor activation:** Precise sync for verification and further refinement

**Translation formulas (locked mode):**

All times in these formulas are **unix timestamps**:

```
effective_shift = global_shift + anchor_shift
```
(where `anchor_shift` = 0 if no anchor is activated)

When navigating via MIDI:
```
camera_unix = midi_unix - effective_shift
camera_frame = round((camera_unix - raw_camera_unix_start) × capture_fps)
```
*(Result is rounded to the nearest integer frame.)*

When navigating via camera:
```
camera_unix = raw_camera_unix_start + camera_frame / capture_fps
midi_unix = camera_unix + effective_shift
midi_position_in_file = midi_unix - midi_file_unix_start
```

Equivalently, when an anchor is active, thinking in terms of the anchor as a "pin point" using **local coordinates** (no unix time needed):
```
Δt from anchor:
  midi_seconds_from_file_start = anchor_midi_timestamp_seconds + Δt
  camera_frame                 = anchor_camera_frame + Δt × capture_fps
```

**Behavior details:**
- The active panel (whichever the user is scrubbing) is the "driver" — the other panel follows
- If the computed target time falls **before** the follower clip's start, the follower panel shows a gray/blank state with a message: *"Camera clip starts in X.XX s"* or *"MIDI file starts in X.XX s"*
- If the computed target time falls **after** the follower clip's end, the follower panel shows: *"Camera clip ended X.XX s ago"* or *"MIDI file ended X.XX s ago"*
- The driver panel always shows data normally regardless of the follower's state
- See **Timeline Overlap Handling** section below for full analysis of all overlap cases
- Stepping one camera frame (~4.17ms) moves the MIDI cursor by ~8 ticks; stepping one MIDI tick (~0.52ms) may not visibly change the camera frame (it updates only when crossing a frame boundary)
- **Activating a different anchor** changes the effective shift — the panels re-sync, which may shift the follower's view
- **Deactivating all anchors** makes locked mode fall back to `global_shift` only

**Toggle button:** A clearly visible toggle in the toolbar switches between Independent and Locked mode. The current mode is always indicated.

### Navigation Controls

Both Level 2 panels support **keyboard and mouse** navigation:

- **Arrow keys:** Step forward/backward by one unit (one frame for camera, one tick for MIDI). Hold Shift+Arrow for larger jumps (e.g., 10 frames or 100 ticks)
- **Mouse drag:** Scrub the timeline by dragging on the panel or a scrub bar
- **Scroll wheel:** Zoom in/out on the timeline (adjusting how much time is visible)
- **Hotkeys:**
  - Mark MIDI position (e.g., `M`)
  - Mark camera position (e.g., `C`)
  - Toggle Independent/Locked mode (e.g., `L`)
  - Add anchor (e.g., `A`, when both markers are set)

### Alignment Controls

#### Global Shift (Phase 1) — accessible in both Level 1 and Level 2

- A numeric input field showing the current `global_shift_seconds` value (default: 0)
- A button to **compute from current positions** (Level 2 only): after the operator has navigated to matching events in Independent mode, clicking this computes `midi_unix_time - camera_unix_time` and fills the field. This button is only present in Level 2, where navigable panels exist. In Level 1, the operator can only type a value directly.
- A button to **apply**: writes the value and recalculates all aligned camera positions
- Editing this value affects **all** camera files for this participant
- **Warning:** If any anchors exist when the operator applies a new global shift, a confirmation dialog appears: *"Changing global shift will remove all N anchors across M camera clips. Continue?"* On confirm, all anchors are cleared. On cancel, the global shift is not changed.

#### Anchor List (Phase 2) — in Level 2

The anchor list is a panel in Level 2 showing all alignment anchors for the **currently selected camera clip**.

**Display:** A table/list with columns:
| # | MIDI File | MIDI Time (s) | Camera Frame | Derived Shift (s) | Label | Active |
|---|-----------|---------------|--------------|-------------------|-------|--------|

**Actions:**
- **Add Anchor:** The operator navigates to matching events (MIDI timestamp + camera frame), then clicks "Add Anchor". This saves the current MIDI file name, MIDI timestamp (seconds from file start), and camera frame number as a new anchor pair. An optional label can be entered (e.g., "C4 onset at start").
- **Activate / Deactivate:** Click on an anchor row to **activate** it (at most one can be active at a time; activating one deactivates the previous). Click the active anchor again to **deactivate** it. When an anchor is active, locked mode uses `global_shift + anchor_shift`. When no anchor is active, locked mode uses `global_shift` only. The active anchor also determines the camera clip's position on the Level 1 timeline.
- **Delete Anchor:** Remove an anchor from the list.
- **Derived Shift:** Shown as a read-only computed column so the operator can compare anchors — if all derived shifts are similar (~within a few ms), the alignment is consistent. If they diverge, it may indicate a wrong match or clock drift.

#### Marker System

To support both global shift computation and anchor creation:
- The operator can **mark** the current MIDI position (e.g., a button or hotkey "Mark MIDI") — this captures the **current MIDI file name** and the **current timestamp** (seconds from file start)
- The operator can **mark** the current camera frame (e.g., "Mark Camera") — this captures the **current frame number**
- When both markers are set, the UI shows:
  - The computed offset (difference in unix time)
  - A button to **apply as global shift**
  - A button to **add as anchor** for the current camera clip

---

## Timeline Overlap Handling

When a MIDI file and a camera clip are paired in Level 2, their timelines may have various temporal relationships. After alignment (global shift + anchor shift), both are projected onto the MIDI reference timeline. The overlap determines what the operator sees at any given position.

### Overlap Cases

After alignment is applied, the MIDI file occupies `[midi_start, midi_end]` and the camera clip occupies `[aligned_cam_start, aligned_cam_end]` on the same timeline.

#### Case 1: Camera fully within MIDI (common)
```
MIDI:   |============================|
Camera:      |================|
```
Camera was started during a MIDI trial and stopped before it ended. The entire camera clip has corresponding MIDI data.

#### Case 2: MIDI fully within camera
```
MIDI:        |================|
Camera: |============================|
```
Camera was recording before MIDI started and continued after. The entire MIDI file has corresponding camera data.

#### Case 3: Partial overlap — MIDI starts first
```
MIDI:   |================|
Camera:         |================|
```
Overlap region from aligned camera start to MIDI end. MIDI has data before camera; camera has data after MIDI.

#### Case 4: Partial overlap — camera starts first
```
MIDI:          |================|
Camera: |================|
```
Overlap region from MIDI start to aligned camera end. Camera has data before MIDI; MIDI has data after camera.

#### Case 5: No overlap
```
MIDI:   |========|
Camera:                |========|
```
No shared time. Can happen when: global shift hasn't been applied yet (clips are minutes apart), or operator selected a non-overlapping pair intentionally.

### Behavior by Mode

#### Level 1 — Timeline Overview

All overlap cases are **visually apparent** from the bar chart. Bars render at their aligned positions; the operator can see overlap, gaps, and containment at a glance. No special handling is needed — the visual layout is self-explanatory.

Selecting a non-overlapping pair for drill-down into Level 2 is allowed (the operator may need to do this during Phase 1 to set the global shift).

#### Level 2 — Independent Mode

**No impact from overlap.** Each panel navigates within its own clip's full time range independently. Both panels always have data to show. The operator can navigate freely regardless of whether the clips overlap.

#### Level 2 — Locked Mode

This is where overlap matters most. The "driver" panel (whichever the operator is scrubbing) navigates freely. The "follower" panel computes its position via the effective shift (`global_shift` alone, or `global_shift + anchor_shift` if an anchor is active) and may go out of range.

**Three situations for the follower panel:**

| Situation | Follower display |
|---|---|
| Computed position is within follower's clip range | Normal data display |
| Computed position is before follower's clip start | Gray panel: *"Camera clip starts in X.XX s"* or *"MIDI file starts in X.XX s"* |
| Computed position is after follower's clip end | Gray panel: *"Camera clip ended X.XX s ago"* or *"MIDI file ended X.XX s ago"* |

The driver panel always shows data normally.

#### Overlap Region Indicator

A small **timeline bar** in the Level 2 view shows the spatial relationship:
- Renders the full extent of both clips (aligned) as two overlapping bars
- Highlights the **overlap region** (where both have data)
- Marks the current **playhead position** on this bar
- Gives the operator spatial awareness of where they are relative to the boundaries of each clip

### Dynamic Changes to Overlap

#### When global shift changes
- All anchors are cleared (see "Strict Phase Ordering")
- All camera clips reposition based on global shift only
- Overlap relationships across all clips may change
- Level 1 overview updates to reflect new positions

#### When active anchor changes (within a clip)
- Different anchors may yield slightly different derived shifts
- The camera clip's aligned position may shift slightly on the Level 1 timeline
- In Level 2 locked mode, the timelines re-pin to the new anchor's sync point
- The overlap region indicator updates accordingly

### Anchor Creation and Overlap

Anchors can only be meaningfully created for matching keypresses that exist in both timelines. However, the tool **does not restrict** anchor creation based on computed overlap, because:

1. Before any alignment exists, the computed "overlap" is meaningless (clips may be minutes apart in raw time)
2. The anchor itself *defines* the alignment — creating an anchor establishes where the clip lands
3. The operator is the judge of whether the keypress match is correct

After adding or selecting an anchor, the Level 1 overview updates to show the new aligned position.

---

### Persistence — JSON Output

The alignment result is saved as a **JSON file** per participant. The tool must support:

- **Save**: Export the current alignment state to JSON via **File > Save** menu with a file dialog
- **Load**: Import a previously saved JSON file via **File > Load** menu with a file dialog to resume or review alignment

There is no auto-save — the operator explicitly saves when ready. The confirmation dialog for global shift changes (which clears anchors) provides sufficient protection; if needed, the operator can reload from the last saved JSON.

#### JSON Structure (draft)

```json
{
  "participant_id": "009",
  "utc_offset_hours": -5,
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
        },
        {
          "midi_filename": "20250815_144525_pia02_s009_001.mid",
          "midi_timestamp_seconds": 120.456,
          "camera_frame": 23901,
          "label": "loud chord"
        }
      ],
      "active_anchor_index": 0
    },
    {
      "filename": "C0002.MP4",
      "xml_filename": "C0002M01.XML",
      "raw_unix_start": 1723741400.0,
      "raw_unix_end": 1723741600.0,
      "duration": 200.0,
      "capture_fps": 239.76,
      "alignment_anchors": [],
      "active_anchor_index": null
    }
  ],
  "alignment_notes": ""
}
```

**What is stored vs. derived:**
- **Stored:** anchor pairs (MIDI timestamp + camera frame) — the raw evidence
- **Derived at load time:** `anchor_shift`, `aligned_unix_start`, `aligned_unix_end` — computed from the active anchor

```
anchor_shift = (midi_unix_start + midi_timestamp_seconds) - (raw_camera_unix_start + camera_frame / capture_fps) - global_shift

aligned_unix_start = raw_unix_start + global_shift + anchor_shift
aligned_unix_end   = raw_unix_end   + global_shift + anchor_shift
```

If `alignment_anchors` is empty (no anchors yet), `anchor_shift` = 0 and only the global shift applies.

## Data Model Summary

```
Participant
├── participant_id
├── utc_offset_hours                 (for MIDI timestamp conversion)
├── global_shift_seconds             (single value, default 0)
├── midi_files[]
│   └── each: filename, unix_start, unix_end, duration, sample_rate
├── camera_files[]
│   └── each: filename, xml_filename, raw_unix_start, raw_unix_end,
│             duration, capture_fps,
│             alignment_anchors[]
│               └── each: midi_filename, midi_timestamp_seconds,
│                         camera_frame, label
│             active_anchor_index    (which anchor is active, or null)
└── alignment_notes                  (free text for the operator)
```

## Processing Scope

- Each participant is processed **separately** (one at a time)
- Approximately 61 participants total
- Each participant has ~10–15 MIDI files and ~10–15 camera clips
