# Goals, DAGs & Pluggable Executors — design note

**Branch:** `feat/comms-board-dag-serial`
**Status:** locked model (2026-06-16). Phase 0 in progress.
**Supersedes the "flat DAG per board" framing** in earlier notes; relates to
[BOARD-COMPLETION-SPEC.md](BOARD-COMPLETION-SPEC.md) and the P2/P3 roadmap.

---

## 1. The model — Board → Goals → per-goal Task-DAG

A **board** is a workspace that holds **many goals**. Each **goal** is a unit of
work that gets decomposed into a **DAG of small tasks**. The DAG is tied to the
**goal**, not just the board.

```
BOARD (feature workspace) ── holds MANY goals
│
├─ GOAL 1  "add OAuth login"      decomposed by: CONSULTATION FLOW
│     └─ task DAG: T1 → T2 → T3   ▶ run with: TEAM flow
│
├─ GOAL 2  "fix flaky tests"      decomposed by: SINGLE PLANNER agent
│     └─ task DAG: A, B(needs A)  ▶ run with: LOOP (one agent, engine-2)
│
└─ GOAL 3  "rename config keys"   no decomposition
      └─ one task                 ▶ run with: SINGLE agent (one shot)
```

## 2. Two ways to decompose a goal (chosen per goal)

| Decomposer | Weight | Produces |
|---|---|---|
| **Consultation flow** — PO → architect → design → planner | heavy | rich artifacts on the board **+** the task DAG (planner is the last stage) |
| **Single planner agent** (planner + plan skill) | light | just the task DAG, fast |

Either way the resulting tasks carry `goal_id = <that goal>` and `depends_on`
edges among themselves. **The planner is the keystone:** its job is to emit
`type=task` comms messages (`depends_on` + `goal_id` + input artifact paths).

## 3. Three ways to execute (the `executor` choice)

| Mode | Binds to | What runs |
|---|---|---|
| **single** | a **task** | one agent, one shot, ad-hoc (today's SingleAgentButton, aimed at a task) |
| **loop** | a **goal** | one agent chews that goal's whole task-DAG, ready task at a time (engine-2) |
| **team** | a **goal** | the trimmed team flow (builder → reviewer → tester) runs on the goal |

`executor` is stored on the **goal**; `single` is an ad-hoc action on a task and
isn't stored.

## 4. Schema (additions to `comms_messages`)

The table is already ~80% there (`depends_on`, `task_status`, `lane`,
`claimed_by`, …). Phase 0 adds only:

| Field | On | Meaning |
|---|---|---|
| `type = 'goal'` | message | a goal statement (existing free-text `type` column — no schema change) |
| `goal_id` | task | the goal message this task belongs to |
| `executor` | goal | `single` \| `loop` \| `team` |

DAG of a goal = `tasks WHERE goal_id = <goal>` + their `depends_on` edges.

## 5. Parallelism opens at two levels

- **Across goals** — independent goals share no state, so Goal 1's team flow can
  run *while* Goal 2 loops. **The easy, safe parallel win**, available early.
- **Within a goal** — independent tasks (needs worktree/lane isolation) stays **P3**.

Per the locked decision in the DAG-scheduler vision: **design the data model
parallel-ready now, ship execution serial.** Flipping `k>1` is then a config flip
by lane, not a rewrite.

## 6. Relationship to the FSM flows

The monolithic `team` flow (STORM→PLAN→DESIGN→BUILD→REVIEW→TEST→RETRO) splits:

- **Consultation flow** (new): PO → architect → design → planner. Fills the board
  with the goal's knowledge + the task DAG. A human review gate follows.
- **Team flow** (trimmed): BUILD → REVIEW → TEST → RETRO — the `team` executor.

The single-agent and loop executors are board-native; the team executor reuses
the trimmed FSM flow.

## 7. Phase plan

| Phase | Deliverable |
|---|---|
| **0a — schema** ✅ | `goal_id` + `executor` columns (additive migration) |
| **0b — planner→DAG** | planner emits `type=task` (`depends_on` + `goal_id` + artifact paths); `post_message` / `/comms/post` accept `goal_id` + `executor`; `goal` message type |
| **1 — dispatcher (serial)** | when a task/goal is run, route to its executor (`single` / `loop` / `team`); start serial |
| **2 — UI** | per-goal executor selector + a "Run" action on a goal/task; goals shown as groupings on the board |
| **3 — parallel** | flip `k>1` by lane (across-goal first, then within-goal worktrees) |

**Keystone, built first:** the planner emitting the task DAG (Phase 0b).
