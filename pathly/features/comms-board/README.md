# comms-board — plan folder

Home for the Pathly **comms board**: the live, DB-backed message board that is the
orchestration substrate (Board → Goals → per-goal Task-DAG → pluggable executors).

**Status (2026-06-22):** the board is **shipped to `master`** — start a feature, create
or drag artifacts onto the board, turn the board into a goal + Task-DAG (evaluator /
planner / consultation), and execute it with the `single` / `loop` / `team` executors.
The context-retrieval, summarizer, and memory-consolidation sub-features are live too.
**The only unbuilt phase is P3 (parallel).** Per-phase design specs for the shipped work
have moved to [`_archive/`](_archive/) — they are history now, not active plans.

## Live docs (top level)

| Doc | What it covers |
|---|---|
| [ROADMAP.md](ROADMAP.md) | **Live tracker** — what shipped, the remaining P3 + deferred-polish items |
| [GOALS-DAG-EXECUTORS.md](GOALS-DAG-EXECUTORS.md) | **The model** — Board→Goals→Task-DAG, 2 decomposers, 3 executors, schema |
| [MEMORY-CONSOLIDATION.md](MEMORY-CONSOLIDATION.md) | The 💡 channel + dedup/reflection pass (`/comms/consolidate`) |
| [HQ-COMMAND-CENTER.md](HQ-COMMAND-CENTER.md) | _Later / separate_ — fleet dashboard framing; overlaps `../parallel-fleet-part-2/` |

`STATE.json` / `EVENTS.jsonl` are the feature's own FSM state — left in place.
`artifacts/` holds board-run output (e.g. `BOARD_EVAL.md` from an evaluator run).

## Shipped — specs now in `_archive/`

Everything below is **built and on `master`**; the design specs are kept for reference.

| Area | Archived spec(s) |
|---|---|
| Goals/DAG phases 0a, 0b, P1, P2 | [`_archive/phases/`](_archive/phases/) |
| Board completion + runtime product specs | `_archive/BOARD-COMPLETION-SPEC.md`, `_archive/BOARD-RUNTIME-SPEC.md` |
| DAG scheduler + task-graph design | `_archive/DAG-SCHEDULER-ARCHITECTURE.md`, `_archive/TASKGRAPH-DESIGN.md` |
| Context-retrieval sub-feature (manifest + `/section` + catalog + summarizer) | `_archive/DESIGN_SPEC-context-retrieval.md`, `_archive/DESIGN_SPEC-local-inference.md`, `_archive/BUILD_PROMPTS.md` |

Plus the original storm/early-design history: `SPEC.md`, `LIVE-BOARD-ARCHITECTURE.md`,
`BOARD-INTEGRATION-GAPS.md`, `FULL-FLOW-READINESS.md`, the FSM pipeline-run artifacts
(`USER_STORIES`, `IMPLEMENTATION_PLAN`, `PROGRESS`, `RETRO`, `CONVERSATION_PROMPTS`,
`FEATURE_INDEX`, `feedback/`), and the `STATE-ARTIFACT.md` board-run test artifact.

## What's left

Only **P3 (parallel)** — across-goal lanes → worktree fan-in → consolidation — which
lives in `../parallel-fleet-part-1/` and `-part-2/`, plus a few small deferred-polish
items. See [ROADMAP.md](ROADMAP.md) for the live list.
