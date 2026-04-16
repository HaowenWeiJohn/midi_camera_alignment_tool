# Modes

Level 2 has two transport modes that control how the MIDI panel and the camera panel relate when one is scrubbed. The current mode is shown and toggled via the **Mode** button in the top bar, and via ++l++.

## Independent (default)

- The two panels scroll **independently**.
- Scrubbing the MIDI panel does not move the camera; scrubbing the camera does not move MIDI.
- The overlap indicator playheads still update as each panel moves, so you can *see* the time mismatch on the shared axis even if nothing is being driven.
- Use this mode when you are still placing markers — you want to see both panels at the same physical moment, but choose them independently.

## Locked

- One panel drives the other using the current `effective_shift`.
- When you scrub the MIDI panel: the camera panel seeks to the corresponding frame via `engine.midi_unix_to_camera_frame`.
- When you scrub the camera panel: the MIDI panel seeks to the corresponding second via `engine.camera_frame_to_midi_seconds`.
- When the driving panel is scrubbed outside the driven panel's valid range, the driven panel shows an **out-of-range** message (see below) instead of a frame / playhead position.
- Use this mode when you are **verifying** alignment quality — scrubbing reveals any mismatch between the two modalities.

## Entering Locked mode

When the mode is toggled from Independent to Locked:

1. The view runs `_sync_from_camera()` — it takes the camera panel's current frame and pushes the corresponding MIDI time to the MIDI panel.
2. The overlap indicator is re-bound with the current `effective_shift` so its green overlay and the two playheads are consistent.

## Leaving Locked mode

When the mode is toggled from Locked to Independent:

1. Any stuck out-of-range message on either panel is cleared (the panels switch back to `show_normal`).
2. The two panels no longer drive each other; scrubbing one leaves the other alone.

## Out-of-range messaging

Only meaningful in Locked mode. The message appears on the **mirrored** panel (the panel being driven), never on the driving panel:

| Direction | Condition | Message on mirrored panel |
|---|---|---|
| MIDI drives camera, camera_unix < clip start | Camera clip hasn't started yet | *"Camera clip starts in X.XX s"* |
| MIDI drives camera, camera_unix > clip end | Camera clip already ended | *"Camera clip ended X.XX s ago"* |
| Camera drives MIDI, midi_seconds < 0 | MIDI file hasn't started yet | *"MIDI file starts in X.XX s"* |
| Camera drives MIDI, midi_seconds > duration | MIDI file already ended | *"MIDI file ended X.XX s ago"* |

The magnitudes in the message are signed seconds — `1.23` means "1.23 seconds away." Scrubbing the driving panel back into range restores the normal display automatically. Scrubbing the mirrored panel directly also clears the message (because then that panel is driving, not being driven).

## How mode affects anchors

Mode has no effect on the anchor table itself. Activating/deactivating/deleting anchors works identically in both modes. The visible consequence is only in Locked:

- **Activating** an anchor changes `effective_shift` → panels re-sync using the new shift.
- **Deactivating** an anchor restores `effective_shift = global_shift` → panels re-sync.
- **Deleting** the active anchor triggers a deactivation pathway first, then the same re-sync.

In Independent mode the anchor state still updates `effective_shift`, but the panels don't move — they only reflect the new shift on subsequent scrubs.

## How mode affects Compute Global Shift

- **Independent**: clicking **Compute Global Shift** changes `global_shift_seconds` and clears markers; the panels stay where they are.
- **Locked**: same flow. See [§7.1 Known issues](../7-troubleshooting/known-issues.md) for a small cosmetic caveat about the overlap bar playheads after a shift change in Locked mode.

## How mode affects keyboard shortcuts

Mode toggles via ++l++. Arrow-key stepping (++left++ / ++right++), anchor add (++a++), mark (++m++ / ++c++), jump-to-overlap (++o++), and active-panel switch (++tab++) all work identically in both modes. The only difference is whether your arrow-key scrubbing moves *one* panel (Independent) or *both* (Locked).
