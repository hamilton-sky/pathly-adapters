# FEATURE_INDEX — parallel-scout-standard

**Feature:** parallel-scout-standard
**Rigor:** lite
**Status:** NOT STARTED
**Date planned:** 2026-05-11

## What this feature does

Creates a shared `scout-flow` sub-skill and standardizes the 3-phase analyze → scout → act
pattern across all agent-facing skills (plan, build, review) and the standalone agent
contracts (planner, builder, reviewer, architect).

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| FEATURE_INDEX.md | planner | all | Entry point — codebase paths + conversation map |
| USER_STORIES.md | planner | planner, reviewer | What to build and how to verify it |
| IMPLEMENTATION_PLAN.md | planner | builder | Phases, dependencies, verification per conversation |
| PROGRESS.md | planner | builder | Conversation status tracking |
| CONVERSATION_PROMPTS.md | planner | builder | Verbatim prompts, one per conversation |

## Codebase touchpoints

| File | Conversation | Change |
|---|---|---|
| `src/pathly_data/core/skills/scout-flow.md` | Conv 1 | CREATE — new sub-skill |
| `src/pathly_data/core/skills/plan.md` | Conv 2 | MODIFY — add 3-phase analyze/scout/plan structure |
| `src/pathly_data/core/skills/build.md` | Conv 2 | MODIFY — add 3-phase analyze/scout/implement structure |
| `src/pathly_data/core/skills/review.md` | Conv 2 | MODIFY — add 3-phase analyze/scout/review structure |
| `src/pathly_data/core/skills/team-flow/plan.md` | Conv 3 | MODIFY — replace inline scout logic with scout-flow calls |
| `src/pathly_data/core/agents/planner.md` | Conv 4 | MODIFY — add phase: analyze behavior + Scout Findings protocol |
| `src/pathly_data/core/agents/builder.md` | Conv 4 | MODIFY — normalize NEEDS_CONTEXT format to match scout-flow canonical |
| `src/pathly_data/core/agents/reviewer.md` | Conv 4 | MODIFY — add phase: analyze behavior + Scout Findings protocol |
| `src/pathly_data/core/agents/architect.md` | Conv 4 | MODIFY — add phase: analyze behavior + Scout Findings protocol |

## Conversation map

| Conv | Title | Stories | Status |
|---|---|---|---|
| 1 | Create scout-flow sub-skill | S-1 | TODO |
| 2 | Update standalone skills (plan, build, review) | S-2, S-3, S-4 | TODO |
| 3 | Update team-flow/plan to use scout-flow | S-5 | TODO |
| 4 | Update agent contracts | S-6 | TODO |

## Optional plan files

| File | Included |
|---|---|
| HAPPY_FLOW.md | no — merged into IMPLEMENTATION_PLAN.md |
| EDGE_CASES.md | no — merged into USER_STORIES.md |
| ARCHITECTURE_PROPOSAL.md | no — architecture notes in IMPLEMENTATION_PLAN.md |
| FLOW_DIAGRAM.md | no |
