# Decompose tiers — one planner agent, three depths

## Problem

Goal decompose had two modes that both under-deliver on the **context-retrieval** design:
- **Planner** (`_decompose_planner`) — fast, but posts **bare task titles**: no plan artifacts, no
  `context_refs`, no `depends_on`. Executors have nothing to hydrate from the catalog.
- **Consultation** — runs the full team flow but its terminal `team/plan` stage doesn't seed
  `context_refs` either (a `task-dag-post` stopgap was added, then superseded by this design).

Meanwhile the **real decomposer already exists**: `planning/plan` mechanically derives, per task,
`context_refs` (`{artifact, anchor: "phase-N"}` into EDGE_CASES/HAPPY_FLOW/ARCHITECTURE_PROPOSAL),
`depends_on` edges, and an `artifact_path` — exactly what `drain-dag`/`review` hydrate. It just
wasn't wired into either decompose path.

## Model — one planner agent, two dials

The planner agent (`planning/plan`) is the **same** across modes. Decompose varies:
- **Depth** = how much upstream context is gathered before the planner runs.
- **Rigor** = which templates the planner fills (artifact richness) — nano/lite/standard/strict.

### Three tiers

| Mode | Runs | Produces | Use |
|---|---|---|---|
| **Quick** (`planner`) | lightweight inline prompt, one agent | bare task list, no artifacts | "just give me a checklist" |
| **Plan** (`plan`) **← new** | `planning/plan` as one board agent | full plan files + `context_refs`/`depends_on` DAG | most goals — the missing middle |
| **Consultation** (`consultation`) | PO→arch→research→design **then `planning/plan`** | richest artifacts + catalog-wired DAG | complex/risky goals |

`Plan` and `Consultation` share the **same terminal planner** (`planning/plan`); Consultation just
precedes it with context-gathering stages. Rigor: each mode carries a sensible default (Quick≈bare,
Plan=standard, Consultation=strict); an explicit rigor knob is a later refinement (don't make the
user pick depth AND rigor — auto-suggest via the `director`'s rigor selection, override optional).

## The enabling fix — `planning/plan` must accept a pre-existing goal

`planning/plan` Step 6 was written for the team flow, where the planner **creates** the goal. Its
idempotency guard skips if a goal OR tasks exist. In a decompose the goal **already exists**, so it
would skip and seed nothing. Fix: **skip only if TASKS already exist; otherwise find-or-create the
goal** and seed tasks under it. Backward-compatible — the team flow (no pre-existing goal) still
creates one; a decompose (goal present) now uses it.

## Changes

1. `core/skills/planning/plan.md` — Step 6 idempotency: skip only on existing *tasks*; use the
   existing goal when present (don't post a duplicate).
2. `supervisor/goal_decomposer.py` — add `_decompose_plan` (runs `planning/plan` as a single board
   agent); dispatch `mode='plan'`. Keep `planner` (quick) and `consultation`.
3. `core/flows/consultation.flow.yaml` — PLANNING agent `team/plan` → `planning/plan`; drop the
   `composition: {PLANNING: consultation-plan}`.
4. **Retire `task-dag-post`** — delete the fragment, the `consultation-plan` block, and its test.
   `planning/plan` supersedes it (does `context_refs` + `depends_on`, which the stopgap did not).
5. Studio `DecomposeConfigPopover` — third MODE option ("Plan"), `DecomposeMode` union gains `plan`.

## Out of scope (follow-ups)

- Explicit rigor selector in the UI (nano/lite/standard/strict) + director auto-rigor.
- Threading `goal_id` through `start_run` so the consultation planner needn't board-lookup it.
- True parallel DAG execution (depends_on edges are seeded but executors still run serial).
