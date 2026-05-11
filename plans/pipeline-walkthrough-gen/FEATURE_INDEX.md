# Feature Index: pipeline-walkthrough-gen

**Rigor:** lite
**Status:** IN PROGRESS
**Date:** 2026-05-11

## Problem

The three pipeline-walkthrough metrics files (`01-PIPELINE-FLOW.md`, `02-TOKEN-USAGE.md`,
`03-ARTIFACT-MAP.md`) are never generated. Templates exist at
`src/pathly_data/core/templates/pipeline-walkthrough/` but no retro step fills and
writes them.

## Fix

Add a pipeline-walkthrough generation step to both:
- `src/pathly_data/core/skills/retro.md` (standalone `/retro` skill)
- `src/pathly_data/core/skills/team-flow/retro.md` (Stage 5 sub-skill)

The new step reads EVENTS.jsonl, fills template placeholders, and writes the three
files to `pipeline-walkthrough/$FEATURE/`.
