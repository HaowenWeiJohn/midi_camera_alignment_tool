# Architecture

> Living overview of the `alignment_tool` package. For the history of how we got here, see `docs/superpowers/specs/2026-04-13-alignment-tool-refactor-design.md`.

## Package Layering

```
ui → services → io → core
```

- **`core/`** — pure Python. Dataclasses (`models`), time math (`engine`), JSON persistence (`persistence`), exception hierarchy (`errors`). No Qt, no external I/O.
- **`io/`** — filesystem and hardware surfaces: MIDI parsing (`midi_adapter`), Sony FX30 XML + cv2 wrapping (`camera_adapter`), folder scan (`participant_loader`), background video decode (`frame_worker`). May use `QThread` / `pyqtSignal`; never `QWidget`.
- **`services/`** — Qt-free controllers. `AlignmentService` is the *only* code path that mutates `AlignmentState` at runtime (persistence load does bulk replacement). `Level2Controller` extracts mode, marker, and sync logic out of the Level 2 view.
- **`ui/`** — every PyQt widget.

The import direction is enforced by `tests/test_no_qt_in_core.py`, which imports `core` and `services` in a subprocess where `PyQt5` is poisoned in `sys.modules`.

## Two-Phase Alignment

The tool reconciles two unsynchronized clocks:

1. **Global offset** — one scalar `global_shift_seconds` on `AlignmentState` absorbs the 1–20 minute clock offset for a whole participant. Applied uniformly to every camera clip.
2. **Per-clip anchor refinement** — each `CameraFileInfo` may hold `Anchor` pairs (`midi_timestamp_seconds`, `camera_frame`). The `active_anchor_index` selects which anchor derives the clip's `anchor_shift`; the effective shift is `global_shift + anchor_shift`.

**Invariant:** changing `global_shift_seconds` invalidates every anchor. This is enforced inside `AlignmentService.set_global_shift` — no other code path writes the field. Callers either pass `clear_anchors_if_needed=True` (and get a `ShiftChangeResult.cleared_anchor_count`) or catch `AnchorsExistError` and prompt the user.

## Data Flow

- **State ownership** — one `AlignmentState` lives on `MainWindow`. `AlignmentService` and `Level2Controller` hold references (not copies).
- **Write path** — widget signal → `ui/*` handler → `service.method(...)` → mutation or typed exception → UI refreshes.
- **Read path** — widgets query `service.effective_shift_for(camera_index)` and friends; they never recompute the formulas themselves.
- **Level-2 sync (FREE vs LOCKED)** — `Level2Controller.on_midi_position_changed` / `on_camera_position_changed` return a `SyncOutput(new_midi_time, new_camera_frame, out_of_range_delta)`. The view renders this output through `QSignalBlocker`-guarded `set_*` calls. OOR feedback is symmetric — both directions emit a delta when the driver crosses the driven side's valid range.

## Persistence

Schema v1, JSON, atomic write via `tempfile` + `os.replace`. Every field needed for Level 2 to function is persisted (media paths, `total_frames`, `ticks_per_beat`, etc.), so a fresh `File → Load Alignment` yields a fully operational state without also re-opening the source folder.

Missing or mismatched `schema_version` → `UnsupportedSchemaVersionError`. Unparseable JSON → `CorruptAlignmentFileError`.

## Threading

One `QThread` owns a `FrameWorker`. The worker keeps a monotonic `_generation` counter; frames dispatched before the last `open_video` are discarded. `CameraPanelWidget.hideEvent` stops the worker so cv2 handles don't leak across Level-1 ↔ Level-2 transitions.

## Testing

Qt-free suite under `tests/` (58 tests): `core` and `services` tested without a running `QApplication`. `pytest-qt` is intentionally not used; UI is verified manually.
