# Why alignment is needed

## The recording setup

Two independent recording systems run in parallel during each participant's session:

1. A **Yamaha Disklavier** writes performances to `.mid` files on its host computer.
2. A **Sony FX30 camera** overhead records video to `.MP4` files (with a matching `.XML` sidecar) at roughly 240 frames per second.

Both systems are time-stamped using the host clock at the moment each file is *closed* — there is no wired sync, no SMPTE timecode, no clapper, and no embedded event broadcast between the two machines.

## The clock-offset problem

In practice the two host clocks drift against each other by a **constant 1–20 minutes per participant**:

- The offset is stable within a participant's recording session (it does not meaningfully drift over one hour of recording).
- The offset varies between participants because the machines reboot and NTP-sync independently.
- The offset cannot be recovered automatically from file headers — the Disklavier's embedded track-name timestamp is unreliable on many takes, and the FX30 XML `CreationDate` is likewise not trusted (see the docstrings in `alignment_tool/io/midi_adapter.py:1-9` and `alignment_tool/io/camera_adapter.py:1-8`).

Because of this, a MIDI event at `t = 123.5 s` in `trial_001.mid` does **not** correspond to the frame with wall-clock timestamp `123.5 s` in `C0001.MP4`. The real correspondence is `midi_unix_time = camera_unix_time + Δ` for some participant-specific Δ that has to be measured.

## Why it has to be manual

Automatic onset detection is possible in principle but was ruled out for this dataset:

- The overhead camera view does not always capture every keypress with a clean visual signature — some keystrokes are occluded by hands, and illumination varies trial-to-trial.
- A mismatched or missed automatic onset would produce a silently-wrong alignment; a researcher then has to verify every result anyway.
- The manual workflow is fast in practice: one M/C marker pair, one click, done.

This tool therefore exists to let a researcher:

1. Look at a MIDI file and a video of the same piece side-by-side.
2. Identify the same keystroke in both.
3. Have the tool compute and save the resulting time offset.

## What alignment unlocks

Once a participant's `global_shift_seconds` (and any per-clip anchors) are saved, downstream analyses can:

- Seek to an arbitrary MIDI event in the corresponding camera frame.
- Crop video clips around particular notes or phrases.
- Train per-frame or per-event models that need both modalities time-aligned.

Without this alignment step, the MIDI and video are effectively two disconnected datasets.
