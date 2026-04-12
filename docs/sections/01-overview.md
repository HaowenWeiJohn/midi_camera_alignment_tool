# 1. Overview and Purpose

## What This Tool Does

The MIDI-Camera Alignment Tool is a desktop application that helps a human operator temporally align overhead video recordings of a pianist's hands to the MIDI events captured simultaneously by a Yamaha Disklavier. It does not attempt automatic alignment — its job is to make manual alignment fast, verifiable, and reproducible, and to persist the result as a structured JSON file that downstream analysis code can consume.

## Why This Is Necessary

Two independent recording systems are in play for each session:

- **Disklavier MIDI** — the high-temporal-resolution reference clock. Captures every note-on and note-off event. This is the ground-truth timeline of what the performer played.
- **Overhead Sony FX30 camera** — a second stream used later for analyzing hand and body motion. Records at approximately 240 fps capture rate, played back at ~24 fps as slow motion.

Both recording systems are started and stopped manually by humans. They share no common clock. As a result, every file pair has a **clock offset** that:

- Is typically between 1 and 20 minutes
- Is consistent across all files within a single participant session
- Differs unpredictably from participant to participant

The camera is also started and stopped frequently — often multiple camera clips fall inside a single MIDI trial. There is **no 1:1 correspondence** between MIDI files and camera clips.

An automatic audio-based cross-correlation approach is not available: the overhead camera does not record audio suitable for aligning to a piano signal, and the Disklavier does not produce a reliable audio track either.

## Goals

1. Give the operator an interactive view of **all** MIDI files and **all** camera clips for one participant, with their raw temporal relationships visible at a glance.
2. Allow the operator to efficiently pick a single visible keypress in a video frame and the corresponding MIDI note-on, and use that pair to compute the participant-wide global offset.
3. Allow the operator to refine each camera clip's alignment with one or more per-clip anchors, so that every clip can be navigated to sub-frame precision against the MIDI reference.
4. Persist the result as a JSON artifact that can be reloaded, audited, and consumed by analysis scripts.
5. Keep the mathematical core independent of the GUI so it is easy to reason about and test.

## Non-Goals

- **No automatic alignment.** The tool does not perform event detection, video-audio cross-correlation, or any form of automatic sync inference. It is a manual tool.
- **No multi-participant batch mode.** One participant at a time. Session state is not shared across participants.
- **No auto-save.** Saving is explicit via the File menu; the operator decides when to commit.
- **No editing of source media.** The tool reads `.mid`, `.MP4`, and `.XML` files; it never modifies them.
- **No frame-accurate preview / playback.** The camera panel shows individual frames; there is no animated timeline playback.

## Who It Is For

- Researchers and lab staff responsible for producing aligned recordings for downstream motion analysis.
- Developers maintaining or extending the tool (see [Developer Guide](./10-developer-guide.md)).

## Scope of a Single Session

- **One participant loaded at a time.** Approximately 61 participants total in the study.
- **~10–15 MIDI files** and **~10–15 camera clips** per participant.
- Everything the operator does is scoped to the currently loaded participant; file paths and raw data are never persisted — only the alignment decisions (the JSON in [Data Model and Persistence](./08-data-model-persistence.md)).
