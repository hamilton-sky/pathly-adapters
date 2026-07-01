---

---
# Goals, DAGs & Pluggable Executors — design note

**Branch:** `feat/comms-board-dag-serial`
**Status:** locked model (2026-06-16). Phase 0 in progress.
**Supersedes the "flat DAG per board" framing** in earlier notes; relates to
[BOARD-COMPLETION-SPEC.md](_archive/BOARD-COMPLETION-SPEC.md) and the P2/P3 roadmap.

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
│     └─ task DAG: A, B(needs A)  ▶ run with: LOOP (fresh agent per task)
│
└─ GOAL 3  "rename config keys"   no decomposition
      └─ one task                 ▶ run with: SINGLE (one agent, whole goal)
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

Refined 2026-06-17. The axis is **agent topology per goal** — one agent / looped
fresh agents / a team-of-roles — a clean progression of isolation + rigor + cost.

| Mode | Owns the frontier | What runs |
|---|---|---|
| **single** | the **agent** (self-loop) | ONE agent runs the *whole goal* in one context; after each task it calls the board HTTP for the next ready task and continues until the DAG is drained. Cheapest; one long context; no review. |
| **loop** | the **supervisor** | a **fresh** agent per ready task (or batch); when it finishes, the supervisor respawns the next — new context each task. This is the **P2 supervisor-owned frontier loop**; flipping `k>1` (P3) fans it out to N concurrent agents. |
| **team** | the **FSM flow** | the trimmed team flow (builder → reviewer → tester) runs on the goal — heaviest, with review/test gates. |

`executor` is stored on the **goal** message for **all three** modes. The per-task
**Run** action (run one task with one ad-hoc agent) is a separate UI affordance — it
is **NOT** the `single` executor and isn't stored. (Earlier drafts called the ad-hoc
one-task run "single"; `single` now means *one agent, the whole goal*.)

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

| Phase | Deliverable | Status |
|---|---|---|
| **0a — schema** | `goal_id` + `executor` columns (additive migration) | ✅ done |
| **0b — planner→DAG** | planner emits `type=task` (`depends_on` + `goal_id` + artifact paths); `post_message` / `/comms/post` accept `goal_id` + `executor`; `goal` message type | ✅ done |
| **1 — dispatcher (serial)** | when a task/goal is run, route to its executor (`single` / `loop` / `team`); start serial | ✅ done (+ `/comms/goals/stop`) |
| **2 — UI** | per-goal executor selector + a "Run" action on a goal/task; goals shown as groupings on the board | ✅ done |
| **3 — parallel** | flip `k>1` by lane (across-goal first, then within-goal worktrees) | 🔭 next (only unbuilt phase) |

**Keystone, built first:** the planner emitting the task DAG (Phase 0b).
