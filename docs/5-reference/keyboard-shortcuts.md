# Keyboard shortcuts

A single cheat sheet for every key binding in the app.

## Global (Main window)

| Key | Action |
|---|---|
| ++ctrl+o++ | Open Participant |
| ++ctrl+s++ | Save Alignment (disabled until a session is loaded) |
| ++ctrl+l++ | Load Alignment |
| ++ctrl+q++ | Exit |

## Level 2 only

Active when Level 2 is the current page. Shortcuts are registered with `Qt.WidgetWithChildrenShortcut` scope, so they fire regardless of which child widget has keyboard focus.

| Key | Action |
|---|---|
| ++m++ | Mark MIDI at the current playhead time |
| ++c++ | Mark Camera at the current frame |
| ++l++ | Toggle **Independent** ↔ **Locked** mode |
| ++a++ | Add anchor from current markers (no-op if either marker is unset) |
| ++r++ | Re-sample the intensity probe centered on the current camera frame (no-op if no probe dot is dropped) |
| ++left++ | Step active panel backward: MIDI by 1 tick, camera by 1 frame |
| ++right++ | Step active panel forward: MIDI by 1 tick, camera by 1 frame |
| ++shift+left++ | Coarse backward step: MIDI 100 ticks, camera 10 frames |
| ++shift+right++ | Coarse forward step: MIDI 100 ticks, camera 10 frames |
| ++o++ | Jump both panels to the start of the overlap region (shows "No Overlap" if none) |
| ++tab++ | Switch active panel (the one arrow keys drive) |
| ++esc++ | Back to Level 1 |

## Mouse

Mouse interactions are covered on each widget's reference page:

- [Level 1 timeline](level-1-timeline.md) — click bars, drag to pan, wheel to zoom, double-click to drill in.
- [MIDI panel](midi-panel.md) — drag to scrub (vertical), wheel to zoom, double-click a note to snap, hover to highlight.
- [Camera panel](camera-panel.md) — wheel to zoom, left-drag to pan when zoomed, double-click to reset zoom, right-click to drop probe dot.
- [Overlap indicator](overlap-indicator.md) — click/drag on the MIDI or camera track to seek.
- [Intensity plot](intensity-plot.md) — left-click anywhere in the plot frame to seek the camera there.
- [Anchor table](anchor-table.md) — click Active cell to toggle, double-click MIDI Time / Camera Frame to jump.

## What about typing into controls?

Menu shortcuts (++ctrl+o++ etc.) work regardless of focus. Level 2 letter shortcuts (++m++, ++c++, ++l++, ++a++, ++r++, ++o++) likewise fire regardless of focus — with two exceptions:

- The "Anchor Label" input dialog shown when adding an anchor is modal and blocks shortcut routing until you confirm or cancel.
- The anchor table's **Label** cell opens an inline editor when you double-click it (or press ++f2++ on a selected row). While that editor is focused, letter keys are absorbed by the editor. Press ++enter++ or ++esc++ (or click outside) to release focus and re-enable the shortcuts.
