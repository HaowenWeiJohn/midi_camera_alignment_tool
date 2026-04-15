# Known Issues — Level 2 Locked Mode

Three open issues affect Level 2 anchor/shift transitions. None corrupt saved alignment data or show incorrect values in any widget; all relate to the LOCKED-mode invariant or activation UX.

## Issue #2 — Deactivating an active anchor breaks the lock

**Where:** `alignment_tool/ui/level2_view.py` — `_on_anchor_deactivated` (~line 549)

**Symptom:** In LOCKED mode, clicking the `*` cell to deactivate the active anchor drops `effective_shift` from `global + anchor_shift` to just `global`. Panels don't re-sync, so the two white playheads on the overlap bar visibly diverge. Mode button still reads "Locked" but panels no longer correspond.

**Impact:** Alignment verification in LOCKED mode becomes unreliable until the user manually scrubs to re-engage the lock.

**Suggested fix:** Append `if self._controller.mode == Mode.LOCKED: self._sync_from_camera()` after `_reset_panels_to_normal()`.

---

## Issue #3 — Anchor activation in LOCKED mode behaves inconsistently

**Where:** `alignment_tool/ui/level2_view.py` — `_apply_anchor_lock_rule` (~lines 289–298)

**Symptom:** Clicking the `*` cell to activate an anchor lands the panels in different places depending on whether the anchor's `midi_filename` matches the currently loaded MIDI file:

- **Different MIDI file:** panels jump to the anchor point `(F_a, T_a)`.
- **Same MIDI file:** camera stays at current frame `F`; MIDI snaps to `F`'s aligned time under the new shift (not `T_a`).

Both end states are internally consistent (lock holds), but the user's observation of "what activation does" changes between anchors based on a detail they aren't thinking about.

**Impact:** UX confusion; no numeric value is wrong.

**Suggested fix:** Pick one behavior and apply it unconditionally. Recommendation: **always jump to the anchor point** on activate. Remove `set_position(anchor.midi_timestamp_seconds)` (line 295) and `_sync_from_camera()` (line 298) from inside `_apply_anchor_lock_rule`; let `_on_anchor_activated` perform an explicit `camera_panel.set_frame(anchor.camera_frame)` + `midi_panel.set_position(anchor.midi_timestamp_seconds)` instead. `_toggle_mode` keeps its own `_sync_from_camera()` call.

---

## Issue #4 — Compute Global Shift in LOCKED mode breaks the lock

**Where:** `alignment_tool/ui/level2_view.py` — `_on_compute_shift` (~line 479)

**Symptom:** In LOCKED mode, pressing "Compute Global Shift" applies a new `global_shift` (and clears anchors if confirmed) but doesn't re-sync panels. Panel positions are unchanged while `effective_shift` just changed, so the overlap playheads diverge — identical symptom to Issue #2.

**Impact:** Same as Issue #2, but usually self-heals because the user typically scrubs right after applying a new shift.

**Suggested fix:** Append `if self._controller.mode == Mode.LOCKED: self._sync_from_camera()` before `_update_overlap()` at the end of `_on_compute_shift`.

---

## What is NOT affected by any of these

- Saved JSON alignment files (`core/persistence.py`) — never corrupted.
- Level 1 timeline rendering — uses `effective_shift_for_camera` correctly.
- Camera frame counter and MIDI time label displays — always truthful for their panels' actual state.
- `effective_shift` math in `core/engine.py` — correct throughout.
