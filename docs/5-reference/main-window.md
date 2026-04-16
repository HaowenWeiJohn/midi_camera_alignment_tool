# Main window

The main window is the top-level container. It switches between three pages via an internal `QStackedWidget`:

1. A centered placeholder when no session is loaded.
2. **Level 1** — timeline overview (see [§5.2](level-1-timeline.md)).
3. **Level 2** — detail pair view (see [§5.3](level-2-view.md)).

The window opens at **1400 × 800** by default and is fully resizable.

## Title bar

Shows one of three states:

| Title | Meaning |
|---|---|
| `MIDI-Camera Alignment Tool` | No participant loaded |
| `MIDI-Camera Alignment Tool — Participant 042` | Session loaded, no unsaved changes |
| `MIDI-Camera Alignment Tool — Participant 042 *` | Session loaded, **unsaved changes** |

A trailing `*` appears whenever `_dirty` is set: after applying a global shift, adding/deleting an anchor, toggling an anchor, or rebasing paths during a load. The `*` disappears only after a successful **Save Alignment**.

## Status bar

Below the main pages, the status bar shows one of:

- `No participant loaded` — initial state.
- `Participant 042 | 12 MIDI files | 12 camera clips | Global shift: 0.000s | Anchors: 5` — full summary, updated after every state change.
- `Level 2: trial_001.mid + C0001.MP4` — while a Level 2 pair is active.
- `Saved: /path/to/alignment.json` — transient confirmation after **Save Alignment**.

## File menu

Single top-level menu — no toolbar, no other menus.

| Item | Shortcut | Behaviour |
|---|---|---|
| **Open Participant…** | ++ctrl+o++ | Folder picker. Prompts to save first if dirty. On selection, runs `ParticipantLoader.load` and swaps state to Level 1. Shows a post-load warning dialog if any files were skipped. If no `.mid` or `.MP4` files were found, shows a *"No Files Found"* warning and does not change state. |
| **Save Alignment…** | ++ctrl+s++ | File picker for `*.json`. Writes the session atomically via tempfile + `os.replace`. Disabled until a session is loaded. After success, clears the dirty flag, drops the `*` from the title, and shows the file path in the status bar. |
| **Load Alignment…** | ++ctrl+l++ | File picker for `*.json`. Prompts to save first if dirty. Rebases paths if the stored `participant_folder` doesn't exist on disk (see below). |
| **Exit** | ++ctrl+q++ | Closes the window. Prompts to save first if dirty. Releases the Level 2 video and intensity workers. |

## Unsaved-changes prompt

When closing, opening a new participant, or loading a JSON while `_dirty` is true, a modal `QMessageBox` appears:

> You have unsaved changes. What would you like to do?
>
> **Save** | **Discard** | **Cancel**

- **Save** — opens the Save dialog. If save succeeds, proceeds with the original action. If save fails or is cancelled, stays on the current session.
- **Discard** — proceeds with the original action, dropping all unsaved changes.
- **Cancel** — aborts; stays on the current session.

## Moving participant folders

When you **Load Alignment…** and the JSON's `participant_folder` no longer exists on disk, a folder-picker dialog appears with this header:

> Participant folder not found:
> `{old path}`
>
> Select the new location:

If you pick a new folder, `persistence.rebase_paths` remaps every `file_path`, `mp4_path`, and `xml_path` under that new base and the session is marked dirty (so you're nudged to re-save the JSON with the corrected paths). If you cancel the folder picker, the load aborts and the previous session remains active.

## Error dialogs

All errors come through a single router (`_show_exception` in `alignment_tool/ui/main_window.py:260-266`):

- `MediaLoadError` subclasses → `QMessageBox.critical` titled with the exception class name.
- `PersistenceError` subclasses → `QMessageBox.critical` titled with the exception class name.
- `InvariantError` subclasses → `QMessageBox.warning` (less severe).
- Any other exception → `QMessageBox.critical(title="Error")` with the exception string.

See [§7.2 Error messages](../7-troubleshooting/error-messages.md) for an exhaustive list of what each exception means.
