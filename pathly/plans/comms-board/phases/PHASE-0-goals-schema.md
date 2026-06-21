# Phase 0 — Goals + per-task executor schema

**Branch:** `feat/comms-board-dag-serial`
**Master design:** [../GOALS-DAG-EXECUTORS.md](../GOALS-DAG-EXECUTORS.md)
**Status:** 0a done ✅ · 0b done ✅ (both shipped to `master`)

Phase 0 lays the data substrate for the Board → Goals → per-goal Task-DAG model.

---

## 0a — schema ✅ (done + verified)

Additive migration on `comms_messages` ([db/migrations.py](../../../../src/pathly_orchestrator/db/migrations.py)):

| Field | On | Meaning |
|---|---|---|
| `goal_id` | task | the goal message this task belongs to |
| `executor` | goal | `single` \| `loop` \| `team` |
| `type = 'goal'` | message | a goal statement (existing free-text `type` column) |

The DAG of a goal = `tasks WHERE goal_id = <goal>` + their existing `depends_on` edges.
Re-uses `depends_on`, `task_status`, `lane`, `claimed_by` (already present).

**Verified:** smoke test — columns present, a `type='goal'` row with `executor='loop'`
and a `type='task'` row with `goal_id` both insert; re-running migrations is a no-op.

## 0b — planner → task DAG 🔄 (in progress)

Make decomposition emit a machine-readable DAG instead of prose:

- **Planner** posts `type=task` comms messages, each with `depends_on` (edges),
  `goal_id`, and the input artifact paths the task needs.
- **`post_message` + `/comms/post`** accept `goal_id` (+ `executor` on goals).
- A goal is created as a `type='goal'` message; tasks reference it via `goal_id`.

**Grounding:** recon workflow `phase0-recon` (parallel readers over the planner skill,
flow-seed mechanism, board-post/DAG plumbing, and consultation agents) produces the
implementation-ready wiring spec this step is built from.

## Next phases (land in this folder)

- **PHASE-1** — dispatcher (serial): route a ready task/goal to its executor (`single`/`loop`/`team`).
- **PHASE-2** — UI: per-goal executor selector + a "Run" action; goals shown as groupings.
- **PHASE-3** — parallel: flip `k>1` by lane (across-goal first, then within-goal worktrees).
