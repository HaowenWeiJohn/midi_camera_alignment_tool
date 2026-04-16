# First launch

This page walks you from a fresh install to a loaded participant in about five commands.

## Start the app

From the repo root, with your virtual environment activated:

```bash
python -m alignment_tool
```

The main window opens with the title bar reading **MIDI-Camera Alignment Tool** and a placeholder in the center:

```
No participant loaded.

Use File > Open Participant to load data,
or File > Load Alignment to resume a saved session.
```

The status bar at the bottom shows *"No participant loaded"* until you open something.

## Open a participant

1. **File → Open Participant…** (or press ++ctrl+o++).
2. Select the top-level folder for a participant (the one that contains `disklavier/` and `overhead camera/`). The folder picker shows only directories.
3. Wait briefly while the tool scans and parses every file. The cursor changes to a wait cursor during load.

If everything parses cleanly, the app switches to **Level 1** — a Gantt-style bar chart of every MIDI file (blue, top row) and camera clip (orange, bottom row) on a shared time axis. The status bar now reads:

```
Participant 042 | N MIDI files | N camera clips | Global shift: 0.000s | Anchors: 0
```

If some files were skipped, a warning dialog listing them appears before the timeline renders.

## What the title bar tells you

- `MIDI-Camera Alignment Tool` — no participant loaded.
- `MIDI-Camera Alignment Tool — Participant 042` — loaded, no unsaved changes.
- `MIDI-Camera Alignment Tool — Participant 042 *` — loaded, **unsaved changes** (a trailing asterisk).

## What the File menu offers

| Menu item | Shortcut | What it does |
|---|---|---|
| Open Participant… | ++ctrl+o++ | Scan a participant folder from scratch |
| Save Alignment… | ++ctrl+s++ | Write the current session to a JSON file (disabled until something is loaded) |
| Load Alignment… | ++ctrl+l++ | Restore a previously-saved session |
| Exit | ++ctrl+q++ | Close the app (prompts to save if dirty) |

## What to do next

- If this is your first time: jump to [§4.1 First alignment](../4-tutorials/first-alignment.md) for a guided walkthrough.
- If you have a saved JSON from a previous session: **File → Load Alignment…** (++ctrl+l++). The JSON alone is enough to fully restore the state — you don't need to re-open the participant folder first.
