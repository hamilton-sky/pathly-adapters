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
   │    └ consultation tier: team runs FIRST → feature artifacts, THEN emits the goals
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
A decomposer that reads a feature's starting spec + the feature board and posts **2–5 goal
cards** (e.g. `backend-api`, `frontend-dashboard`, `db-schema`), each with a scope statement +
acceptance boundary, `depends_on` where real (frontend depends on the backend contract), and
sibling-awareness (each goal's prompt is injected with the other goals on the board). Output =
goal cards on the feature board (readable slugs — already shipped).

**Rigor ladder — the goal-decompose tiers, one level up.** Goal→tasks already ships three tiers
(`planner` / `plan` / `consultation`); feature→goals gets the same ladder:

| Tier | What runs | Produces |
|---|---|---|
| **light** | one planner (mirrors `planning/dag-sketch`) | bare sibling-goal cards straight from the spec |
| **full** | one planner (`planning/plan`-style) | goals + scope/acceptance + `depends_on` |
| **consultation** | the **team** — PO→architect→researcher→designer→`feature-decompose` | **feature-level artifacts first**, then the sibling goals |

**The consultation tier is the consultation flow lifted one level.** It reuses
`consultation.flow.yaml`'s stages verbatim (PO→architect→researcher→designer); the *only* change
is the terminal stage — `planning/feature-decompose` emits `type=goal` siblings where
`planning/plan` emits a `type=task` DAG. Those upstream stages write the feature's cross-goal
architecture / research / design to the feature root (`features/<f>/`) — the very "cross-goal
design" the storage constraint below already assumes exists. That artifact pass is what makes the
split coherent: `backend-api` and `frontend` agree on a contract because both fell out of one
architecture pass.

**Produce-once, inherit-many.** Each emitted goal carries `context_refs` pointing at the feature
artifacts, so when a goal is later split into its own task DAG the team *consumes* the feature
architecture/design instead of re-deriving it. Cross-goal design is paid for once at the feature
level; every goal inherits it.

**Gate + human checkpoint.** The terminal gate counts **goals**, not tasks:
`count(type=goal, scope=feature) ≥ 2 → DONE`, else a loud `NO_GOALS_SEEDED` (the goal-level
`NO_DAG_SEEDED` pattern, different unit). After emitting siblings the flow **stops for human
review** — it does not auto-cascade into per-goal DAGs. Emit goals → human edits the goal set →
*then* decompose each goal (light or consultation, chosen per goal).

**Build surface.** New skill `planning/feature-decompose` (terminal emitter, `type=goal`) + a
`feature-consultation` flow (= `consultation.flow.yaml` with the `feature-decompose` terminal +
a goal-counting gate) + a `/comms/features/decompose` route (mirrors `/comms/goals/decompose`,
takes a rigor param `light|full|consultation`). UI home: **Evaluate → Whole board**, with the
rigor selector shown alongside the evaluator — the per-goal RIGOR ladder, one altitude up.

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
- **Reuse, don't reinvent — only the terminal emit changes per level.** Each new level is
  `decompose(parent) → post child items with depends_on` — the same primitive as goal→tasks, and
  the **same team pipeline** (PO→…→planner). What differs by altitude is the **terminal emit
  type**: feature→`type=goal`, goal→`type=task`. New code = a terminal skill + a thin route,
  never a new flow engine.

## Sequencing
`G0 (reliability) → G1 (feature→goals) → G2 (spec→features) → G3 (BMAD into the new model)`.
Bottom-up: never build a level on top of one that can silently fail.

## Non-goals (for now)
- Parallel cross-feature execution (that's the separate P3 worktree-fan-in work).
- Replacing the team/FSM conversation flow — it stays for the classic single-feature path.
