# MIDI-Camera Alignment Tool — Documentation

A PyQt5 desktop tool for temporally aligning overhead camera recordings (Sony FX30, ~240 fps) to Disklavier MIDI files in a multi-participant piano study. Two recording systems run on unsynchronized clocks with a constant offset of 1–20 minutes per participant; the tool provides a manual two-phase alignment workflow (global offset → per-clip anchor refinement) and persists the result as JSON.

---

## Quick Links

1. [Overview and Purpose](./sections/01-overview.md) — problem statement, goals, who this is for.
2. [Getting Started](./sections/02-getting-started.md) — install, run, and load your first participant.
3. [Data Sources and File Layout](./sections/03-data-sources.md) — the expected participant folder, MIDI, and Sony FX30 formats.
4. [Alignment Concepts and Math](./sections/04-alignment-concepts.md) — shifts, anchors, effective shift, phase ordering.
5. [Architecture](./sections/05-architecture.md) — module map, signal flow, Qt widget hierarchy.
6. [User Interface Walkthrough](./sections/06-ui-walkthrough.md) — Level 1 timeline, Level 2 detail view, all controls and shortcuts.
7. [Workflows](./sections/07-workflows.md) — step-by-step operator procedures for each alignment phase.
8. [Data Model and Persistence](./sections/08-data-model-persistence.md) — dataclasses and the JSON schema.
9. [Module Reference](./sections/09-module-reference.md) — per-file API and responsibilities.
10. [Developer Guide](./sections/10-developer-guide.md) — invariants, performance notes, extension points.
11. [Troubleshooting and FAQ](./sections/11-troubleshooting.md) — common issues and answers.

---

## At a Glance

| Aspect | Detail |
|---|---|
| Framework | PyQt5 (Qt for Python) |
| Entry point | `python -m alignment_tool` |
| UI shape | Two-level drill-down in a single `QStackedWidget` |
| Level 1 | Timeline overview — bar chart of all MIDI + camera clips |
| Level 2 | Side-by-side alignment: piano roll + video frame + anchor table |
| Time math core | `alignment_tool/alignment_engine.py` (pure functions, Qt-free) |
| Storage | JSON per participant (Save/Load from the File menu) |
| Participants | ~61 total, processed one at a time; ~10–15 MIDI + ~10–15 camera files each |

## Two-Phase Alignment Summary

**Phase 1 — Global offset.** A single scalar `global_shift` applies to all camera clips for one participant. It absorbs the 1–20 minute clock offset between the camera and the Disklavier. After applying it, clips are aligned to within ~1–2 seconds of truth.

**Phase 2 — Per-clip anchors.** For each camera clip the operator creates one or more `Anchor(midi_filename, midi_timestamp_seconds, camera_frame)` pairs — two events identified as the same physical keypress. The tool derives `anchor_shift` from the active anchor and uses `effective_shift = global_shift + anchor_shift` for locked-mode navigation.

**Strict phase ordering.** Changing `global_shift` after anchors exist invalidates them; the tool enforces this with a confirmation dialog that clears all anchors across all clips.

See [Alignment Concepts and Math](./sections/04-alignment-concepts.md) for formulas and the derivation.

---

## Where to Start

- **If you are an operator** doing alignments, read [Getting Started](./sections/02-getting-started.md), then [Workflows](./sections/07-workflows.md) and [UI Walkthrough](./sections/06-ui-walkthrough.md).
- **If you are a developer** modifying the tool, read [Architecture](./sections/05-architecture.md), [Module Reference](./sections/09-module-reference.md), and [Developer Guide](./sections/10-developer-guide.md).
- **If you are reviewing the math**, go straight to [Alignment Concepts and Math](./sections/04-alignment-concepts.md) and the `alignment_engine.py` source.

## Historical / Specification Document

The original design specification (problem framing, rationale for design choices, JSON schema draft) lives at [../docs/implementation_history_doc/ALIGNMENT_TOOL_SPEC.md](./implementation_history_doc/ALIGNMENT_TOOL_SPEC.md). This documentation set reflects the current implementation; the spec is kept for history.
