# Using the intensity probe

The pixel-intensity probe tells you, per frame, how bright a specific point on the video is — typically a single piano key. Press a key and that key's top surface moves rapidly from well-lit to shadowed or vice versa, producing a clean slope on the luma trace at the exact frame the hammer meets the string. That slope gives you an onset frame accurate to ~1 frame without guessing.

## When to use it

- When the camera is bright enough to distinguish lit from shadowed keys.
- When you can clearly identify which key was pressed from the MIDI roll (pitch + timing).
- When eyeballing ±2 frames around a keystroke is not precise enough for your experiment.

The probe is purely a seek aid — it never modifies the alignment state. You still decide where to put the camera marker; the probe just makes it obvious which frame to pick.

## Using it

1. In Level 2, seek roughly to the moment of the keystroke you want to mark.
2. **Scroll-wheel to zoom in** on the keyboard until you can see the individual key clearly (zoom range is 1.0×–20.0×; the zoom is centered on the cursor).
3. If you're zoomed in, **click-drag** pans around; **double-click** resets zoom to fit.
4. **Right-click** the center of the key top (or a stripe of the key that will change brightness when pressed).

A red dot with a white outline appears on the key. The **intensity plot** below the splitter shows *"Sampling ±120 frames…"* for a fraction of a second while the worker thread walks the video, then fills in with a blue luma trace centered on the frame where you dropped the dot. Dotted grey vertical line = drop frame. Red vertical line = current camera playhead.

## Reading the plot

- **Flat segments** — key is at rest (fully lit or fully shadowed).
- **Sharp slope down or up** — key is moving, which is the **attack**. The first frame of the slope is the hammer-initiation frame and corresponds to the MIDI note-on within ~1 frame.
- **Rebound / settle** — a smaller counter-slope a handful of frames later as the key returns to rest.

Click anywhere on the plot to seek the camera there. This is much faster than stepping with arrow keys once you've identified the onset visually.

## Resampling

- Dropping the dot on a different pixel immediately cancels the old sample and starts a new one. The old plot is replaced as soon as the new one finishes.
- Switching to a different camera clip or clicking **Back** clears the dot and the plot automatically — late results from the old clip are discarded so a stale trace cannot overwrite the new one.

## What the probe doesn't do

- No motion detection — the probe just reports one pixel's luma. Choose a point that actually changes brightness when the key is pressed; the edge between a key top and its shadow works well.
- No MIDI-based automatic seeking — you have to scrub to roughly the right region yourself before dropping the dot.
- No export — the sampled values are not saved to disk; they live only in the plot widget until you drop a new dot or leave the clip.

## Practical recipe

1. Mark the MIDI side first (++m++ on a clean note in the piano roll).
2. Scrub the camera to within a second or two of that time using the overlap bar.
3. Zoom in on the key you expect (the MIDI panel shows which pitch — map it to the visible keyboard).
4. Right-click the key.
5. Read off the onset frame from the luma slope and click the plot there.
6. Press ++c++ to lock that as the camera marker.
7. **Compute Global Shift** or **Add Anchor**, depending on whether you're doing the first-pass alignment or a per-clip refinement.
