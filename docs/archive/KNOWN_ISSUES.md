# Known Issues — Level 2 Locked Mode

Three issues were originally filed against Level 2 anchor/shift transitions. None corrupt saved alignment data or show incorrect values in any widget; all relate to the LOCKED-mode invariant or activation UX. The 2026-04-15 anchor-activation refactor resolved two of them and left one open. Status notes are attached to each entry below.

**Context for readers:** in the 2026-04-15 refactor, the "active anchor" became session-only state. Activation is now gated — only anchors whose `midi_filename` matches the currently displayed MIDI are activatable; others render grayed out. On any MIDI-combo change, camera-combo change, Back/Esc exit, or re-entry via `load_pair`, the active anchor is cleared. `active_anchor_index` is no longer persisted in JSON. `_apply_anchor_lock_rule` was deleted; the MIDI combo is never programmatically disabled anymore.

## Issue #2 — Deactivating an active anchor breaks the lock

**Status:** **Fixed (2026-04-15).**

**Where:** `alignment_tool/ui/level2_view.py` — `_on_anchor_deactivated`

**Symptom:** In LOCKED mode, clicking the `*` cell to deactivate the active anchor dropped `effective_shift` from `global + anchor_shift` to just `global`. Panels didn't re-sync, so the two white playheads on the overlap bar visibly diverged. Mode button still read "Locked" but panels no longer corresponded.

**Fix applied:** `_on_anchor_deactivated` now calls `_sync_from_camera()` when `mode == Mode.LOCKED`, before `_update_overlap()`. The same fix was also applied to `_on_anchor_deleted` for the "deleted the active anchor" branch — the old version had the identical omission even though its comment claimed it mirrored `_on_anchor_deactivated`.

---

## Issue #3 — Anchor activation in LOCKED mode behaves inconsistently

**Status:** **Obsoleted (2026-04-15).** The root condition (activating an anchor whose `midi_filename` ≠ the currently displayed MIDI) can no longer occur through the UI.

**Where:** `alignment_tool/ui/level2_view.py` — formerly `_apply_anchor_lock_rule`

**Original symptom:** Clicking the `*` cell to activate an anchor landed the panels in different places depending on whether the anchor's `midi_filename` matched the currently loaded MIDI file:

- **Different MIDI file:** panels jumped to the anchor point `(F_a, T_a)`.
- **Same MIDI file:** camera stayed at current frame `F`; MIDI snapped to `F`'s aligned time under the new shift (not `T_a`).

Both end states were internally consistent (lock held) but the user's observation of "what activation does" shifted between anchors based on a detail they weren't thinking about.

**Resolution:** Under the new activation rule, only anchors whose MIDI matches the displayed MIDI can be activated — the "different MIDI" branch is unreachable via normal UI. The "same MIDI" behavior (camera stays, MIDI syncs to aligned time) is now the only behavior. `_apply_anchor_lock_rule` was deleted entirely; `_on_anchor_activated` calls `_sync_from_camera()` when LOCKED, nothing else.

---

## Issue #4 — Compute Global Shift in LOCKED mode breaks the lock

**Status:** **Open.** Not addressed by the 2026-04-15 refactor.

**Where:** `alignment_tool/ui/level2_view.py` — `_on_compute_shift` (~line 499)

**Symptom:** In LOCKED mode, pressing "Compute Global Shift" applies a new `global_shift` (and clears anchors if confirmed) but doesn't re-sync panels. Panel positions are unchanged while `effective_shift` just changed, so the overlap playheads diverge — identical symptom to the pre-refactor Issue #2.

**Impact:** Same as Issue #2 was, but usually self-heals because the user typically scrubs right after applying a new shift.

**Suggested fix:** Append `if self._controller.mode == Mode.LOCKED: self._sync_from_camera()` before `_update_overlap()` at the end of `_on_compute_shift`. Mechanically identical to the fix applied to Issue #2.

---

## What is NOT affected by any of these

- Saved JSON alignment files (`core/persistence.py`) — never corrupted.
- Level 1 timeline rendering — uses `effective_shift_for_camera` correctly.
- Camera frame counter and MIDI time label displays — always truthful for their panels' actual state.
- `effective_shift` math in `core/engine.py` — correct throughout.
