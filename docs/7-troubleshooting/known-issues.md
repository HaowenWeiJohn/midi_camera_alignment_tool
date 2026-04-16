# Known issues

This page lists active known issues that affect users. Purely cosmetic quirks are included where they might look like bugs on first sight.

## Compute Global Shift in Locked mode — overlap playheads briefly diverge

**Severity:** cosmetic.

**Where:** Level 2, when **Mode: Locked** is active and you click **Compute Global Shift**.

**Symptom:** immediately after the shift is applied (and any "clear anchors" confirmation is accepted), the two white playhead lines on the [overlap indicator](../5-reference/overlap-indicator.md) can appear slightly out of line. The underlying state is correct — the MIDI panel's red playhead and the camera panel's frame counter both already reflect the new `effective_shift`. It's only the overlap bar's two playhead lines that visibly separate until the next scrub.

**What to do:** scrub either panel briefly. The next `position_changed` signal re-syncs both overlap playheads via `_apply_sync_output`, and the visual divergence disappears.

**Why it happens:** when the shift changes, `effective_shift` changes, which moves where a given camera frame maps on the shared unix axis. The overlap indicator reads both playheads from the last panel-driven position; since no panel was moved during the shift change, the playheads are in their pre-shift positions relative to the new extents until one panel emits a fresh `position_changed`.

## Nothing else currently open

The rest of the Level-2 locked-mode integrity issues that previously lived here (active-anchor deactivation, cross-MIDI activation) were fixed during the 2026-04 refactor and are no longer reachable in the UI. If you notice drift that doesn't self-heal on the next scrub, please file a new issue with repro steps.
