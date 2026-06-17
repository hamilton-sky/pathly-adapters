# Phase 1 — Executor dispatcher (serial)

**Branch:** `feat/comms-board-dag-serial`
**Master design:** [../GOALS-DAG-EXECUTORS.md](../GOALS-DAG-EXECUTORS.md) §3 · **Scheduler design:** [../DAG-SCHEDULER-ARCHITECTURE.md](../DAG-SCHEDULER-ARCHITECTURE.md) · **Prev:** [PHASE-0b-planner-dag-wiring.md](PHASE-0b-planner-dag-wiring.md)
**Status:** building — `single` + `loop` + route + skill landed 2026-06-17; `team` gated.

> **Implementation status (2026-06-17)**
> - ✅ Step 1 — `get_ready_tasks(goal_id=…)` frontier filter (+ test).
> - ✅ `scheduler_loop` threads `goal_id`; task-state events split onto a `event_broadcast_fn`
>   (comms stream) so they don't collide with the worker's runner-stream `broadcast_fn`.
> - ✅ `SerialIsolation` (one worker) in `supervisor/isolation.py`.
> - ✅ `supervisor/goal_run.py` `start_goal_run` — routes single/loop/team.
> - ✅ `POST /comms/goals/run` + `goal_id` query param on `GET /comms/tasks`.
> - ✅ `core/skills/development/drain-dag.md` (the `single` agent self-loop).
> - ✅ `tests/test_comms_goals_run.py` (routing + execution via injected fakes).
> - ✅ Executor **override**: `/comms/goals/run` accepts `executor`; `start_goal_run`
>   persists the UI pick onto the goal (`set_goal_executor`).
> - ✅ **P2 board UI** (Studio): goal cards group their tasks; per-goal executor
>   selector + Run button → `/comms/goals/run`; `goal_run` SSE drives run state.
>   Typecheck green. (`team` shows "not available yet".)
> - ⛔ `team` returns 501 until the two-flow split — **de-risked:** a fresh FSM run
>   starts at the flow's FIRST state (`fsm/engine.py:31`), and `_refresh_flows`
>   auto-seeds any new `core/flows/*.flow.yaml`, so a trimmed-team flow (BUILDING
>   first) is safe to add. The remaining open question is semantic: how a team run
>   consumes the goal's DAG vs. its plan artifacts — that's the two-flow split's job.
> - ▸ Follow-up: a goal **stop** endpoint (the UI Stop button is optimistic; the loop
>   holds the board lock so `/comms/run/stop` on the same scope would actually halt it).

> Goal of P1: when a **goal** is run, read its `executor` and route the goal's
> task-DAG to one of `single` / `loop` / `team`. **Ship serial** (one task at a
> time); flipping `k>1` is P3. The DAG already exists on the board (Phase 0b).

---

## Keystone insight

The `loop` executor's engine is **already built and unwired**. Phase-0b dropped the
data (goal + `executor`; tasks + `goal_id` + `depends_on` + `task_status`); the P2
scheduler work already landed the frontier machinery:

| Already built | Where |
|---|---|
| Frontier loop (reclaim→claim→spawn→complete/fail→recompute) | `supervisor/scheduler.py` `scheduler_loop()` — **zero callers** |
| Isolation seam (`LaneIsolation` ships; `WorktreeIsolation` = P3 stub) | `supervisor/isolation.py` |
| `claim_task` / `fail_task` / `reclaim_stale_claims` / `complete_task` / `get_ready_tasks` | `db/queries/comms.py` |
| Migrations (`lane`, `claimed_*`, `failed_*`, `attempts`) | `db/migrations.py` |
| Runtime seam (`db_path`/`fsm_port`) | `supervisor/state.py:73-76` |
| Claim/fail/complete HTTP routes | `http_server/blueprints/comms.py` |
| Per-task PTY spawn (`_run_stage_via_terminal` → `TERMINAL_SPAWN`) | `supervisor/terminal.py` |

So P1 ≈ **wiring + a routing layer**, not a from-scratch build. What is genuinely
new: the **dispatcher** (read `executor`, route) and the **`single`** agent
self-loop.

---

## The three executors (GOALS-DAG-EXECUTORS §3)

| Mode | Owns the frontier | P1 build |
|---|---|---|
| **single** | the **agent** (self-loop) | ONE agent drains the whole goal in one context: GET ready → claim → do → complete, repeat. NEW: a `drain-dag` skill + spawn one agent (reuse `start_board_run`'s single-agent PTY path). |
| **loop** | the **supervisor** | a **fresh** agent per ready task. WIRE the existing `scheduler_loop` with `LaneIsolation`, concurrency pinned to **1** (serial). |
| **team** | the **FSM flow** | run the trimmed team flow (build→review→test→retro) on the goal. **GATED on the two-flow split** — stub/route in P1, build when the trimmed flow YAML exists. |

`executor` lives on the **goal** message (Phase-0b). The dispatcher reads it from
the goal row.

---

## Step 1 — `goal_id` frontier filter (db, foundation)

`get_ready_tasks` is board+scope only (`db/queries/comms.py`) — the documented
Phase-0b follow-up. The dispatcher must drain **one goal's** tasks, so add an
optional filter:

```python
def get_ready_tasks(conn, boards, scopes, goal_id: str | None = None) -> list[dict]:
    # ... existing body; when goal_id is not None, AND goal_id=? into both the
    #     pending_sql and done_sql WHERE clauses.
```

None-default keeps every existing caller unchanged. `complete_task`'s newly-ready
walk stays board+scope (it only unblocks; the dispatcher re-filters by goal on the
next tick). Mirror the optional arg through `scheduler_loop(..., goal_id=None)`.

## Step 2 — the dispatcher (supervisor)

**File — `supervisor/goal_run.py` (NEW)**, mirroring `supervisor/board_run.py`:

```python
def start_goal_run(goal_id, board, scope, *, project_root, adapter, model,
                   broadcast_fn, on_start=None, on_done=None) -> dict:
    # 1. Read the goal row; executor = row["executor"] or "single".
    # 2. board_lock.acquire(board, scope) — reuse; 409 {"ok": false} when busy.
    # 3. route:
    #    single → _run_single(...)   # one agent, drain-dag skill, whole goal
    #    loop   → _run_loop(...)     # scheduler_loop(state, board, scope,
    #                                #   isolation=LaneIsolation(), goal_id=goal_id)
    #                                #   in a daemon thread, concurrency pinned to 1
    #    team   → _run_team(...)     # GATED: trimmed team flow (deferred → 501-style
    #                                #   "executor 'team' not available until flow split")
```

- **single** reuses `start_board_run`'s single-agent spawn (`board_run.py`) with a
  new skill (Step 3); the agent owns the loop, supervisor just spawns+waits.
- **loop** constructs a `RunnerState` (`project_root`, `db_path=""`→default,
  `fsm_port`), registers it (`registry`) so abort/status work, and runs
  `scheduler_loop` in a daemon thread. **Serial cap:** pass a concurrency=1 wrapper
  (e.g. `SerialIsolation` delegating to `LaneIsolation` but `max_concurrency → 1`),
  honoring the locked "ship serial" decision.
- **adapter/model** ride with the executor (one selector, two fields — ROADMAP
  multi-adapter rider). Pass straight into the spawn; `TERMINAL_SPAWN` already
  carries `adapter`.

**File — `http_server/blueprints/comms.py`** — `POST /comms/goals/run`
`{goal_id, board, scope, adapter?, model?}` → `start_goal_run(...)`; 409 on busy
board (mirror `comms_run` at the existing `/comms/run` route). Lifecycle posts
(`🤖 started` / `✅ finished`) reuse the `_board_post` pattern.

## Step 3 — `single` executor skill (skill)

**File — `core/skills/<category>/drain-dag.md` (NEW)** — the agent self-loop:
1. `GET /comms/tasks?ready=true&feature=$SCOPE&scope=$SCOPE` (filter to this goal).
2. If empty → done. Else pick one, `POST /comms/tasks/claim` (skip if lost).
3. Execute the task (read `artifact_path`, do the work, verify).
4. `POST /comms/tasks/complete` → repeat from 1.
5. Fail-silent / `POST /comms/tasks/fail` on unrecoverable error.

Propagate: `pathly-setup claude --apply --repair ; python -m build`.

## Build order
1. Step 1 (`goal_id` filter) — unit test: two goals in one scope, ready set is
   per-goal.
2. Step 2 **loop** path — wire `scheduler_loop` serial; integration test: linear
   DAG A→B→C drains in order via a fake spawn (the scheduler's own P2 tests already
   cover the engine; this tests the *wiring*).
3. Step 2 **single** path + Step 3 skill — one agent drains a seeded DAG.
4. **team** — deferred to after the two-flow split; P1 returns a clean
   "not-yet-available" for `executor='team'`.

## DONE-STATE (manual)
`POST /comms/goals/run {goal_id}` on a Phase-0b-seeded goal → tasks transition
`pending → in_progress → done` in dependency order; `GET /comms/tasks?...` drains to
empty; a failed task cascade-blocks its dependents (sibling branches still finish).
`single` and `loop` both achieve this; `team` is gated.

## KNOWN FOLLOW-UPS (flag, not P1)
- **Parallel (`k>1`)** is P3 (`SerialIsolation` → `LaneIsolation`/`WorktreeIsolation`).
- **`team` executor** needs the two-flow split (trimmed team flow YAML).
- **Across-goal parallelism** (run Goal 1 while Goal 2 loops) needs per-goal board
  locks instead of one board/scope lock — P3.
- **Consolidation / fan-in** when a goal's frontier drains — deferred polish.
