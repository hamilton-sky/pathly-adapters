# SPEC — Planner Hierarchy: recursive Project → Features → Goals → Tasks

> **Thesis:** Pathly already has ONE decomposition engine (Board → Items → decompose →
> child items, drained by an executor). Today it runs at exactly one level: a **goal**
> decomposes into a **task-DAG**. This feature extends that same recursion **up two
> levels** so a single big spec flows all the way to shippable tasks — with the **board at
> each level as the shared-awareness substrate** (siblings see each other).

This feature is deliberately a **multi-goal feature** — it holds one goal per new
capability below. That is itself the proof of the model it describes.

---

## The recursion (one pattern, three levels)

```
PROJECT board   ← drop a big spec (BMAD / PRD / free text)
   │  project-planner: split into FEATURES (+ each feature's starting spec)
   ▼   [features on the project board are aware of each other]
FEATURE board   ← each feature's spec
   │  feature-planner: split into GOALS (e.g. backend / frontend / db)
   ▼   [goals on the feature board are aware of each other — the "goal card" point]
GOAL card
   │  goal-planner: split into TASKS (the DAG)  ← EXISTS TODAY
   ▼   [tasks aware of each other via depends_on + context_refs]
TASKS  → executors drain (single / loop / team)
```

Each arrow is the **same** machinery: a planner reads the parent item + the board's
sibling context, and posts child items with dependency wiring. Only the *item type*
changes (feature → goal → task).

---

## Current state (what exists vs. what's new)

| Level | Status | Notes |
|---|---|---|
| **Goal → Tasks** | ✅ exists | `planning/plan` (full) + `planning/dag-sketch` (fast) + consultation flow. Being hardened (loud-failure gate on no-DAG; code-query; server-side telemetry). |
| **BMAD / PRD import** | ⚠️ partial | `planning/prd-import` handles BMAD, but **1 PRD → 1 feature** and emits the *old conversation model* (`CONVERSATION_PROMPTS`, phases), **not** the goal-DAG model. |
| **Feature → Goals** | ❌ new | No planner splits a feature into sibling goals today. |
| **Project → Features** | ❌ new | No planner splits one big spec into N features today. |

---

## Goals (deliverables)

### G0 — Reliability foundation *(prerequisite, mostly in progress)*
The upper levels are worthless if the bottom one silently drops its DAG. Land first:
- Loud failure when a decompose seeds no DAG (done: `NO_DAG_SEEDED`).
- code-query actually fires in the loop (done: role-gate fix).
- Coherent per-agent cost/tokens telemetry (done: invocation reconcile).
- Exit gates that require the *deliverable*, not just "something on the board".

### G1 — Feature-planner (`feature → goals`)  *(build second — immediate need)*
A planner that reads a feature's starting spec + the feature board, and posts **2–5 goal
cards** (e.g. `backend-api`, `frontend-dashboard`, `db-schema`), each with:
- a scope statement + acceptance boundary,
- `depends_on` between goals where real (frontend depends on backend contract),
- awareness of siblings (each goal's prompt is injected with the other goals on the board).
- Output = goal cards on the feature board (readable slugs — already shipped).
- New skill `planning/feature-decompose` + a `/comms/features/decompose` route (mirrors
  `/comms/goals/decompose`), reusing `task-dag-post`-style posting for `type=goal`.

### G2 — Project-planner (`spec → features`)  *(build third — top of funnel)*
A planner that reads a big spec dropped on the **project board** and posts **N feature
cards**, each with its own starting spec, materializing `pathly/features/<f>/` for each.
- New skill `planning/project-decompose` + `/comms/project/decompose`.
- Feature cards on the project board are aware of each other (shared architecture context).

### G3 — Modernize import to the goal-DAG model
Rework `prd-import` / `bmad-import` so it feeds **G1/G2** instead of the old conversation
model: a BMAD file → features (G2) → goals (G1) → tasks. BMAD maps almost 1:1
(PRD → epics → stories ≈ project → features → goals → tasks), so this is mostly
*translation*, not new invention.

---

## Design constraints (locked)

- **Storage stays nested + readable.** `features/<f>/goals/<slug>/` is the namespace that
  lets sibling goals coexist; the feature root holds the feature-level spec + cross-goal
  design. Slugs are now short (`goals/backend-api-<id>/`). Do **not** flatten.
- **Board is the awareness substrate at every level** — the decompose prompt at each level
  injects the sibling items (via the existing board-context retrieval).
- **Reuse, don't reinvent.** Each new level is `decompose(parent) → post child items with
  depends_on` — the same primitive as goal→tasks. New code = a skill + a thin route, not a
  new engine.

## Sequencing
`G0 (reliability) → G1 (feature→goals) → G2 (spec→features) → G3 (BMAD into the new model)`.
Bottom-up: never build a level on top of one that can silently fail.

## Non-goals (for now)
- Parallel cross-feature execution (that's the separate P3 worktree-fan-in work).
- Replacing the team/FSM conversation flow — it stays for the classic single-feature path.
