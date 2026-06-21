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

### Context-retrieval (sub-feature — how agents get context from the board)

Distinct from the Board→DAG phases above. Had its **own 4-phase build plan** (spec §9.1) —
**not** the ROADMAP's P0–P3. Build kickoff prompts in [BUILD_PROMPTS.md](BUILD_PROMPTS.md).

> **✅ BUILT (2026-06-22)** — all 4 phases implemented on branch
> `shammai/comms-board-contex` (commits `88d9730b`→`53f28fd7`), unpushed, awaiting
> review. `context_refs` manifest + section index + `/section` hydration + Board
> Catalog + opt-in offline summarizer are live; default summary backend `minilm`=off
> ⇒ behavior-identical to before until enabled (`app_settings` `inference:summary_backend`).
> Deferred: the §3a Studio upload backend picker (renderer work).

| Doc | What it covers |
|---|---|
| [DESIGN_SPEC-context-retrieval.md](DESIGN_SPEC-context-retrieval.md) | The plan — `context_refs` manifest + Board Catalog + `/section` hydration + three query modes |
| [DESIGN_SPEC-local-inference.md](DESIGN_SPEC-local-inference.md) | Offline artifact summarizer feeding the catalog/index (no web API); used by Phase 4 |
| [BUILD_PROMPTS.md](BUILD_PROMPTS.md) | Phase-by-phase kickoff prompts for building it |

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
