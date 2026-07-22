# RETRO — board-scoped-storage (P2+P3; P1 shipped earlier)

**Shipped:** 2026-07-22 · branch `dogfood/run-identity` · goal `b2539475` (3/3 tasks) · in-session build (per the SPEC's Windows-watcher constraint)

## Outcome

The shared top-level buckets (`pathly/debugs/`, `pathly/explorations/`, `pathly/fixes/`)
are retired. P2 moved all **10** bucket folders (drift: +1 since the 2026-07-05 inventory
of 9) under their boards via pure `git mv` — 9 → `pathly/project/<kind>/<slug>`, 1
slug-match → `features/production-readiness-plan/explorations/` — with **0 DB refs**
re-verified first and 38 tracked files preserved as renames. P3 retired the buckets from
discovery (`cli/_discovery.py` SCAN_ROOTS, `db_api_explorer` fallback scan, Studio
sections/`KNOWN_PATHLY_DIRS` → `Project` section) while keeping the names reserved, and
closed a real invariant hole found while grounding: `find_topic_dir` could not resolve
feature-tier nested runs by slug (writes landed where reads couldn't find them).

## Ordering mattered — and paid off

run-identity shipped FIRST, so identity was location-independent before anything moved:
the move needed no re-keying, and **the SPEC's tracked slug-collision follow-up
(§5 "Known follow-up": two same-slug runs under different boards colliding on
`(project_root, slug)`) is CLOSED by run-identity** — every spawn now issues a unique
`run_id` as the primary telemetry identity with `board_scope` carried alongside, so the
basename key no longer has to disambiguate parents.

## Friction

- The Windows watcher constraint was real twice over: closing Studio's window wasn't
  enough — an `electron-vite dev` supervisor kept respawning it; the process tree had to
  be stopped (with user approval). And the FSM server died with Studio (Studio-spawned),
  restarted from repo code — which usefully applied the run-identity migrations live.
- The mirror-read gate's line-window heuristic flagged a PRE-EXISTING line after a nearby
  comment edit changed its window classification — fixed by adding the legit marker to
  that sibling read.

## Out of scope (unchanged)

S2 — the stale `pathly/plans/` DB refs — remains a separate DB-only migration.
