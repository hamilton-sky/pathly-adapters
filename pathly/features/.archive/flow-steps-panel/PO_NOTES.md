# PO Notes — Flow Steps Dock

**Author:** po · **Feature:** flow-steps-panel · **Date:** 2026-07-16

## Problem
The fixed **top pipeline bar** (`STORMING → … → DONE`) is always on screen, shows a
`No active feature` empty state when idle, is hardcoded to the full `team` sequence (wrong for
consultation / debug / quick-fix runs, which have entirely different phases), and eats vertical
space the board needs. There's no per-run way to see *where a flow is* or to *steer* it.

## What we're building
Replace the top pipeline bar with a **collapsible right-side dock** that renders the
**currently-running flow** as a stepper — driven by that flow's *own* states — and lets the
supervisor **reroute** the run to a different next phase.

## Who it's for
The human supervisor driving *headless* runs (the primary Pathly persona). This is the
"human-in-the-supervisory-loop" surface: see where the flow is and steer it, without entering
the per-step loop.

## Scope (MVP)
- Right-side dock, collapsible to a thin rail (mirrors the Skill Composition sidebar).
- **Flow-aware stepper** — reads the running flow's `states`; consultation, team, team-build,
  debug, quick-fix, **and any user-created flow** all render their own phases; current phase
  highlighted with role + engine.
- **Reroute** — a "send it here next" control offering the flow's *reachable-next* states
  (+ back to a prior stage), wired to `POST /runner/reroute`, keeping the current model.
- **Multiple flows** — a toggle to switch the dock between concurrently-running flows.

## Out of scope (for now)
- Loop / single-executor configuration in the dock (flows only).
- Editing per-phase host/agent/skill — that stays the existing Configure-phase modal; the dock
  can link to it, it doesn't replace it.

## Acceptance
1. Activating **any** flow (built-in or user-created) shows its real states in the dock, current
   phase highlighted. Idle → dock collapsed / empty.
2. The reroute control only offers states the flow can actually reach; choosing one calls
   `/runner/reroute` and the run continues there.
3. The old top pipeline bar is gone; the runner controls (pause/resume/abort) still work from
   the dock; the board gains the reclaimed vertical space.

## Edge cases
- No active flow → collapsed rail, no phantom stepper.
- Gate / terminal-precursor states (`NO_DAG_SEEDED`, `NO_GOALS_SEEDED`) are **not** phases → dim
  or omit; never show as steps.
- A flow that loops back (`REVIEWING → BUILDING`) → mark the loop, don't double-draw the stepper.
