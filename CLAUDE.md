# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Desktop PyQt5 application for temporally aligning overhead camera recordings (Sony FX30, ~240fps) to Disklavier MIDI files in a piano study. Two unsynchronized recording systems have a constant clock offset (1-20 min) per participant. The tool provides a two-phase manual alignment workflow: a global offset applied to all clips, then per-clip anchor refinement.

## Agent Usage

- When spawning subagents via the Agent tool, always use `model: "opus"` to ensure the most capable model is used
