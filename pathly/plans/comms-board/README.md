# comms-board — plan folder

Home for the Pathly **comms board** work: the live, DB-backed message board that is
becoming the orchestration substrate (Board → Goals → per-goal Task-DAG → pluggable
executors). Active design lives at the top level; per-phase working docs in
[`phases/`](phases/); finished/superseded history in [`_archive/`](_archive/).

## Active design

| Doc | What it covers |
|---|---|
| [ROADMAP.md](ROADMAP.md) | **Live phase tracker** — phases + statuses, multi-adapter routing (P1-rider), deferred items |
| [GOALS-DAG-EXECUTORS.md](GOALS-DAG-EXECUTORS.md) | **Current model** — Board→Goals→Task-DAG, 2 decomposers, 3 executors, schema, phase plan |
| [DAG-SCHEDULER-ARCHITECTURE.md](DAG-SCHEDULER-ARCHITECTURE.md) | P2/P3 roadmap — supervisor-owned frontier loop, lane-parallel, worktree fan-in |
| [BOARD-COMPLETION-SPEC.md](BOARD-COMPLETION-SPEC.md) | Gap-and-plan for the full single-agent + flow-of-agents board |
| [BOARD-RUNTIME-SPEC.md](BOARD-RUNTIME-SPEC.md) | Board-runtime product spec — user stories + locked decisions |
| [TASKGRAPH-DESIGN.md](TASKGRAPH-DESIGN.md) | DAG task-graph design |
| [HQ-COMMAND-CENTER.md](HQ-COMMAND-CENTER.md) | _Later / separate_ — fleet dashboard framing; overlaps `../parallel-fleet-part-2/` |

`STATE.json` / `EVENTS.jsonl` are the feature's FSM state — left in place.

## Phases (`phases/`)

Per-phase working docs for the Goals/DAG build land here as we go.

| Phase | Doc | Status |
|---|---|---|
| 0a — Goals + executor schema | [phases/PHASE-0-goals-schema.md](phases/PHASE-0-goals-schema.md) | ✅ |
| 0b — Planner → task DAG | [phases/PHASE-0b-planner-dag-wiring.md](phases/PHASE-0b-planner-dag-wiring.md) | 🔜 ready to build |
| 1 — dispatcher (serial) | _coming_ | — |
| 2 — UI (executor selector) | _coming_ | — |
| 3 — parallel (k>1 by lane) | _coming_ | — |

## Archive (`_archive/`)

Historical, superseded, or completed-pipeline docs — kept for reference, nothing
deleted. Includes the original `SPEC.md`, the storm/early-design docs, the FSM
pipeline-run artifacts (USER_STORIES, IMPLEMENTATION_PLAN, PROGRESS, RETRO,
CONVERSATION_PROMPTS, FEATURE_INDEX, `feedback/`), the big superseded specs
(LIVE-BOARD-ARCHITECTURE, BOARD-INTEGRATION-GAPS, FULL-FLOW-READINESS), and the
stray `STATE-ARTIFACT.md` board-run test artifact.
