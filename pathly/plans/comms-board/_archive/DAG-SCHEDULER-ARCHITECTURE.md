# DESIGN_SPEC — P2: Supervisor-Owned DAG Task Scheduler

**Stage:** DESIGN · **Feature:** comms-board · **Date:** 2026-06-15
**Author:** architect
**Status:** decided — one architectural decision per open question below.

This spec turns the comms board into the live orchestration substrate. The board
already stores the task graph (`depends_on`), computes the ready frontier
(`get_ready_tasks`), and unlocks dependents on completion (`complete_task`). Today
execution is sequential and driven by `build.md` polling. This design moves the
frontier loop into `supervisor/`, makes parallelism a pluggable lane strategy, and
leaves a clean seam for git-worktree isolation later.

Locked decisions honored exactly:
1. Frontier loop lives in the **supervisor**, not a skill.
2. Parallelism = **lane partition first** (same worktree, no merge, ≤1 worker/lane).
3. Per-worker runtime isolation via **env-driven DB path + port**.

---

## 1. Architecture overview

### 1.1 Design principles

| Principle | What it means here |
|---|---|
| **Board is authoritative task state** | The DB (`comms_messages`, `task_status`) is the single source of truth for what is ready, claimed, done, or failed. The scheduler holds no durable queue of its own — it reconstructs the frontier from the DB every tick. This is what makes resume-after-crash deterministic. |
| **Advisory / non-blocking** | If the board returns an empty frontier or is unreachable, the scheduler degrades to the existing single-stage `_loop` (the build conversation prompt still runs). The DAG layer *supplements*; it never deadlocks the pipeline. |
| **Deterministic + resumable** | The frontier is a pure function of DB rows. A scheduler restart re-derives the exact same ready set (modulo claimed→pending reclaim on crash). No in-memory-only state decides what runs next. |
| **Isolation is pluggable** | The scheduler asks an `Isolation` provider for a workspace (`cwd` + DB path + port) per task. `LaneIsolation` (now) hands back the shared worktree; `WorktreeIsolation` (P3) hands back a per-task git worktree. The scheduler code is identical for both. |
| **Reuse the PTY machinery** | Each worker reuses `_run_stage_via_terminal` → `TERMINAL_SPAWN` SSE → `TerminalRun` registry → `_agent_done_watcher` → `/runner/terminal/result` unchanged. Parallelism is N of these in flight, not a new spawn path. |

### 1.2 Control-flow of the supervisor-owned frontier loop

```
  start_run(topic, project_root, max_cost, ...)        [api.py:start_run]
        │  spawns supervisor thread
        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  scheduler_loop(state)            supervisor/scheduler.py (NEW)   │
  │                                                                   │
  │   while not drained:                                              │
  │     ┌── abort / pause / cap checks (reuse _loop boundaries) ──┐   │
  │     │   over_iter / over_cost / _abort_flag / _pause_flag     │   │
  │     └──────────────────────────────────────────────────────────┘ │
  │                          │                                        │
  │           ┌──────────────▼───────────────┐                        │
  │           │ GET ready frontier from DB   │  get_ready_tasks()     │
  │           │ (pending, deps all done,     │  comms.py:400          │
  │           │  not claimed, not failed)    │                        │
  │           └──────────────┬───────────────┘                        │
  │                          │ list[task]                             │
  │              drained?  ──┤── yes & nothing in-flight ──► COMPLETE │
  │                          │ no                                     │
  │           ┌──────────────▼───────────────┐                        │
  │           │ partition by lane            │  task["lane"]          │
  │           │ keep ≤1 worker per lane      │  in_flight_lanes set   │
  │           └──────────────┬───────────────┘                        │
  │                          │ schedulable = ready − busy lanes       │
  │           ┌──────────────▼───────────────┐                        │
  │           │ for each schedulable task:   │                        │
  │           │   claim_task(id) ── atomic ──┼─► pending→in_progress  │
  │           │   ws = isolation.acquire(t)  │  Isolation seam        │
  │           │   spawn worker thread:       │                        │
  │           │     _run_stage_via_terminal( │  terminal.py:161       │
  │           │        cwd=ws.cwd,           │  (reused as-is)        │
  │           │        env=ws.env)           │  TERMINAL_SPAWN SSE    │
  │           └──────────────┬───────────────┘                        │
  │                          │                                        │
  │           ┌──────────────▼───────────────┐                        │
  │           │ wait for ANY worker AGENT_DONE│ run.wait_result_...   │
  │           │ (per-worker daemon watcher,   │ _agent_done_watcher   │
  │           │  already exists)              │                       │
  │           └──────────────┬───────────────┘                        │
  │            success │            failure │                         │
  │       ┌────────────▼──────┐   ┌─────────▼────────────┐            │
  │       │ complete_task(id) │   │ fail_task(id)        │            │
  │       │ comms.py:438      │   │ (NEW) mark failed,   │            │
  │       │ → newly_ready[]   │   │  cascade-block deps  │            │
  │       │ isolation.release │   │  isolation.release   │            │
  │       └────────────┬──────┘   └─────────┬────────────┘            │
  │                    │ free lane          │ free lane               │
  │                    └────────┬───────────┘                         │
  │                             ▼                                     │
  │                    recompute frontier (loop top)                  │
  └─────────────────────────────────────────────────────────────────┘
```

**Where it attaches:** This replaces the body of `orchestrator._loop`
(`supervisor/orchestrator.py:211–539`) for runs flagged DAG-enabled. The
sequential `_loop` stays as the fallback path and as the per-task worker body —
each lane worker effectively runs the existing single-stage spawn + resolve
sequence. Concretely, `_run_stage_via_terminal` (terminal.py:161–350) and
`_resolve_stage_supervised` (orchestrator.py:15–208) are called *inside* the
worker thread, one per task.

### 1.3 Why "wait for ANY", not "wait for all"

The naive scout sketch polled `pty_thread.is_alive()` with `time.sleep(0.1)`.
Better: each worker already gets a `TerminalRun` with a condition variable
(`registry.py:18–79`). The scheduler maintains a single completion queue
(`queue.Queue`) that workers push their `(task_id, outcome)` onto when their
`_run_stage_via_terminal` returns. The loop blocks on `completion_q.get()` — no
busy-wait, no fixed poll interval, and a newly-freed lane is rescheduled the
instant a worker reports. This is the one place I deviate from the scout's
pseudocode, and I think it's clearly better: event-driven, no wasted ticks, and
it composes with abort (push a sentinel to wake the loop).

---

## 2. The isolation seam

A single Protocol decouples *what isolation a task gets* from *how the scheduler
spawns it*. The runtime-config map proved every knob the seam needs is already
plumbed: `cwd` flows from `state.project_root` into the `TERMINAL_SPAWN` payload
(`terminal.py:200–211`); port is `PATHLY_FSM_HTTP_PORT` (`config.py:42–52`); DB
path is the *only* hardcoded knob (`connection.py:93–95`) and §5 fixes that.

```python
# src/pathly_orchestrator/supervisor/isolation.py  (NEW)
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol

@dataclass(frozen=True)
class TaskWorkspace:
    """Everything a worker needs to run a task in isolation."""
    cwd: str                       # working dir → TERMINAL_SPAWN "cwd"
    env: dict[str, str] = field(default_factory=dict)
    #   env carries PATHLY_DB_PATH + PATHLY_FSM_HTTP_PORT (see §5).
    #   For LaneIsolation these are the shared run's values (single DB/port).
    lease_id: str = ""             # opaque handle returned to release()

class Isolation(Protocol):
    """Give me an isolated workspace + DB + port for this task, then take it back."""

    def acquire(self, task: dict, state) -> TaskWorkspace:
        """Reserve resources for `task`. `task` is a comms_messages row dict
        (id, lane, text, depends_on, ...). May block briefly to allocate a port
        or create a worktree. MUST be idempotent w.r.t. lease_id on retry."""
        ...

    def release(self, ws: TaskWorkspace, *, success: bool) -> None:
        """Release the workspace. success=False may keep the workspace around
        for inspection (worktree impl) or be a no-op (lane impl)."""
        ...

    def max_concurrency(self, ready_lanes: set[str]) -> int:
        """Upper bound on simultaneous workers given the current ready lanes.
        LaneIsolation → len(ready_lanes). WorktreeIsolation → a fixed pool size."""
        ...
```

### 2.1 LaneIsolation — the implementation we ship now

```python
# src/pathly_orchestrator/supervisor/isolation.py  (NEW, cont.)
class LaneIsolation:
    """Same worktree, no merge. Concurrency safety comes from the scheduler's
    ≤1-worker-per-lane rule (disjoint file sets per lane), NOT from per-task
    workspaces. Every task gets the SHARED run cwd/db/port."""

    def acquire(self, task: dict, state) -> TaskWorkspace:
        return TaskWorkspace(
            cwd=state.project_root,           # shared worktree (terminal.py:209)
            env={
                "PATHLY_DB_PATH": state.db_path,        # shared run DB (§5)
                "PATHLY_FSM_HTTP_PORT": str(state.fsm_port),
            },
            lease_id=task["id"],
        )

    def release(self, ws: TaskWorkspace, *, success: bool) -> None:
        return  # nothing to free; lane is freed by the scheduler, not here

    def max_concurrency(self, ready_lanes: set[str]) -> int:
        return max(1, len(ready_lanes))       # one worker per active lane
```

**Why no merge:** lanes are derived from disjoint target-path prefixes
(`backend/` → backend lane, `studio/` → frontend lane, `tests/` → tests lane,
etc.). Two tasks in different lanes never edit the same file, so concurrent
writes to one worktree cannot collide. The planner is responsible for assigning a
lane such that this invariant holds (§4.4). If two ready tasks must touch the
same file, the planner puts them in the *same* lane (serialized) — this is the
"contract task" pattern (§8).

### 2.2 WorktreeIsolation — the documented future plug (P3, do NOT build now)

```python
# Future — sketch only, not implemented in P2.
class WorktreeIsolation:
    """Per-task git worktree + private DB + private port. Enables SAME-lane
    parallelism with a fan-in merge step the scheduler runs after release()."""

    def acquire(self, task: dict, state) -> TaskWorkspace:
        wt = f"{state.project_root}/.pathly/worktrees/{task['id']}"
        # git worktree add --detach <wt> <base_sha>
        port = self._alloc_port()                 # from a free-port pool
        db   = f"{wt}/.pathly/pathly.db"           # per-worktree DB file
        return TaskWorkspace(cwd=wt,
                             env={"PATHLY_DB_PATH": db,
                                  "PATHLY_FSM_HTTP_PORT": str(port)},
                             lease_id=task["id"])

    def release(self, ws, *, success):
        # success → queue ws for fan-in merge (git merge / cherry-pick into base);
        # failure → leave worktree for inspection. Free the port back to pool.
        ...
```

The scheduler never branches on isolation type. The only P3 addition is a merge
step that consumes `release(success=True)` events — and because the board is
authoritative, that merge step is itself a (sequential, lane="merge") DAG task.

---

## 3. Schema / primitive gaps + fixes

The DAG-primitives map surfaced four gaps. Two are **blocking** for P2 (lane,
claimed-state), two are **needed for correctness** (failed-state, cascade-block).

| Gap | Impact | Fix |
|---|---|---|
| **No `lane` field** | Scheduler can't partition; `assigned_to_stage` is overloaded with FSM stage. | Add `lane TEXT` column (additive). |
| **No in-progress / claimed state** | Two scheduler ticks (or a crashed-then-restarted scheduler) double-spawn the same task — `get_ready_tasks` returns it again because `task_status` is still `pending`. | Add `claimed`/`in_progress` to `task_status` lifecycle + atomic `claim_task`. |
| **No failed state** | A failed task stays `pending` forever and re-spawns every tick; dependents never resolve. | Add `failed` to `task_status` + `fail_task`. |
| **No cascade-block** | Dependents of a failed task would either run on broken input or hang. | `fail_task` recursively marks transitive dependents `blocked`. |

### 3.1 task_status lifecycle (new states)

```
   pending ──claim_task──► in_progress ──complete_task──► done
      ▲                          │                          │
      │ (crash reclaim)          │ fail_task                │ (unlocks deps)
      └──────────────────────────┤                          ▼
                                 ▼                    newly_ready[...]
                              failed ──cascade──► blocked (transitive deps)
```

`get_ready_tasks` must be tightened to `task_status='pending'` only (it already
is — `comms.py:414`), so `in_progress` / `failed` / `blocked` are automatically
excluded from the frontier. **No change to `get_ready_tasks` is required** beyond
this confirmation — the existing `task_status='pending'` filter already does the
right thing once we stop leaving running tasks in `pending`.

### 3.2 Additive migrations (reuse `_add_additive_migrations`)

Append to the list at `migrations.py:309` (the list ends at the `depends_on`
entry on line 308):

```python
# migrations.py — inside _add_additive_migrations(), append to the tuple list
("comms_messages",  "lane",          "TEXT"),                       # P2 scheduler
("comms_messages",  "claimed_at",    "TEXT"),                       # claim timestamp
("comms_messages",  "claimed_by",    "TEXT"),                       # worker run_id
("comms_messages",  "failed_at",     "TEXT"),                       # failure timestamp
("comms_messages",  "fail_reason",   "TEXT"),                       # short error text
("comms_messages",  "attempts",      "INTEGER DEFAULT 0"),          # retry count
```

`task_status` already exists (`migrations.py:240`); we widen its *value domain*
(`pending|in_progress|done|failed|blocked`) — no DDL change, values are free-text.
The migration is safe to re-run (the `try/except sqlite3.OperationalError` at
`migrations.py:310–314` skips existing columns).

### 3.3 New / changed query helpers in `db/queries/comms.py`

**`claim_task` — the double-spawn guard (atomic compare-and-set):**

```python
def claim_task(conn, message_id: str, run_id: str) -> bool:
    """Atomically transition pending → in_progress. Returns True if THIS caller
    won the claim, False if it was already claimed/done/failed. The WHERE clause
    makes the UPDATE the compare-and-set: only one tick can flip a pending row."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):                       # same lock pattern as complete_task:454
        cur = conn.execute(
            "UPDATE comms_messages "
            "SET task_status='in_progress', claimed_at=?, claimed_by=?, "
            "    attempts=attempts+1 "
            "WHERE id=? AND task_status='pending' AND deleted_at IS NULL",
            (now, run_id, message_id),
        )
        conn.commit()
    return cur.rowcount == 1
```

`rowcount==1` ⟺ this caller flipped the row; a concurrent tick sees `rowcount==0`.
With the per-thread connection + per-connection write lock (`connection.py:97–101`)
this is safe across the supervisor's worker threads in one process. (Cross-process
safety holds too: SQLite serializes the UPDATE; the loser's WHERE no longer
matches `pending`.)

**`fail_task` — mark failed + cascade-block transitive dependents:**

```python
def fail_task(conn, message_id: str, reason: str = "") -> list[str]:
    """Mark a task failed and recursively mark every transitive dependent
    'blocked'. Returns the list of blocked dependent IDs. Idempotent: a task
    already 'failed' returns []. Mirrors complete_task's scope/dep walk."""
    from datetime import datetime, timezone
    row = conn.execute(
        "SELECT board, scope, task_status FROM comms_messages "
        "WHERE id=? AND deleted_at IS NULL", (message_id,)).fetchone()
    if row is None or row["task_status"] == "failed":
        return []
    board, scope = row["board"], row["scope"]
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET task_status='failed', failed_at=?, fail_reason=? "
            "WHERE id=?", (now, reason[:500], message_id))
        conn.commit()

    # BFS over dependents within (board, scope), marking each 'blocked'.
    all_pending = conn.execute(
        "SELECT id, depends_on FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' "
        "AND task_status IN ('pending','in_progress') AND deleted_at IS NULL",
        (board, scope)).fetchall()
    dep_index = {r["id"]: json.loads(r["depends_on"] or "[]") for r in all_pending}
    blocked, frontier = [], {message_id}
    with _get_write_lock(conn):
        changed = True
        while changed:
            changed = False
            for tid, deps in list(dep_index.items()):
                if tid in blocked:
                    continue
                if frontier & set(deps):
                    conn.execute(
                        "UPDATE comms_messages SET task_status='blocked' WHERE id=?",
                        (tid,))
                    blocked.append(tid); frontier.add(tid); changed = True
        conn.commit()
    return blocked
```

**`reclaim_stale_claims` — crash-resume safety:**

```python
def reclaim_stale_claims(conn, board: str, scope: str) -> list[str]:
    """On scheduler startup, revert in_progress tasks with no live worker back
    to pending so they re-enter the frontier. Called once per run resume.
    The scheduler passes the set of run_ids it actually has in-flight; anything
    in_progress that isn't live is stale (the previous process died)."""
    rows = conn.execute(
        "SELECT id FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' AND task_status='in_progress' "
        "AND deleted_at IS NULL", (board, scope)).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    with _get_write_lock(conn):
        conn.execute(
            f"UPDATE comms_messages SET task_status='pending', claimed_by=NULL "
            f"WHERE id IN ({ph})", ids)
        conn.commit()
    return ids
```

**`get_ready_tasks` — confirmed no change.** The `task_status='pending'` filter
(`comms.py:414`) already excludes `in_progress`/`failed`/`blocked`. The only thing
that changes is that the *scheduler* must call `claim_task` immediately after
reading the frontier, before spawning — see §1.2.

---

## 4. File-by-file change spec (ordered)

Ordered so each step compiles/tests on its own. **Layer rule reminder:**
`db/` imports nothing upward; `supervisor/` may import `db` + `runner`;
`http_server/` imports all (lazily in handlers).

### Step 1 — DB layer (foundation, no behavior change yet)
1. **`db/migrations.py`** (`_add_additive_migrations`, after line 308) — add the 6
   columns from §3.2.
2. **`db/queries/comms.py`** — add `claim_task`, `fail_task`, `reclaim_stale_claims`
   (§3.3). Re-export them from `db/__init__.py` (package re-exports all symbols per
   layer convention).

### Step 2 — Isolation seam
3. **`supervisor/isolation.py`** (NEW) — `TaskWorkspace`, `Isolation` Protocol,
   `LaneIsolation` (§2, §2.1). Stub-document `WorktreeIsolation` in a comment block
   only.

### Step 3 — Runtime isolation knob (§5)
4. **`db/connection.py`** (`get_db`, line 93–95) — honor `PATHLY_DB_PATH` env override.
5. **`supervisor/state.py`** (`RunnerState`, lines 32–41) — add `db_path: str` and
   `fsm_port: int` fields, defaulted to the shared run values.

### Step 4 — The scheduler itself
6. **`supervisor/scheduler.py`** (NEW) — `scheduler_loop(state, broadcast_fn,
   isolation)`. Implements §1.2: reclaim → frontier → partition by lane → claim →
   `isolation.acquire` → spawn worker thread (worker body = existing
   `_run_stage_via_terminal` + `_resolve_stage_supervised`) → completion queue →
   `complete_task`/`fail_task` → recompute. Reuses every boundary check from
   `_loop` (abort/pause/cap, orchestrator.py:232–273) — factor those into shared
   helpers rather than copy-paste.
7. **`supervisor/orchestrator.py`** (`_loop`, line ~218) — at the top, branch:
   if the run is DAG-enabled (the feature has `type='task'` rows for `BUILDING`)
   *and* the DAG flag is on, delegate the BUILDING stage to `scheduler_loop`;
   otherwise keep the existing sequential body. Everything pre-BUILDING
   (STORM/PLAN/DESIGN) and post-BUILDING (REVIEW/TEST) stays sequential.
8. **`supervisor/api.py`** (`start_run`, lines 13–71) — accept `dag: bool`
   (default off in P2, on in P2.5), construct the `Isolation` impl, populate
   `state.db_path` / `state.fsm_port`, pass to the loop.

### Step 5 — HTTP routes
9. **`http_server/blueprints/comms.py`** — add two routes mirroring the existing
   pattern (`comms_tasks_complete` at line 351 is the template):
   - `POST /comms/tasks/claim` → `claim_task`, returns `{ "claimed": bool }`.
   - `POST /comms/tasks/fail` → `fail_task`, returns `{ "ok": true,
     "blocked": [...] }` and broadcasts a `COMMS_UPDATE` `event:"task_failed"`
     per blocked id (reuse the broadcast already done for `task_unblocked`).
   The scheduler runs in-process and can call the query helpers directly; the
   routes exist for parity, for external drivers, and for Studio/manual ops.
10. **`http_server/blueprints/runner.py`** — no new route needed. Optionally add a
    `lanes` array to the `GET /runner/status` snapshot (§6).

### Step 6 — Skills: remove polling, add lane emission
11. **`core/skills/development/build.md`** — **REMOVE Step 4.6 "DAG task loop"**
    (the `GET /comms/tasks?ready=true` + `POST /comms/tasks/complete` polling block,
    build.md:122–131). The builder no longer polls; it executes exactly the one
    conversation prompt the scheduler handed it. Keep Step 4.5 (`BUILD_START`) and
    Step 5 (verify + edit). The supervisor now owns the loop.
12. **`core/skills/planning/plan.md`** — **ADD `lane` to the task post** (the
    `/comms/post` block at plan.md:266–301). The planner must emit, per phase:
    - `lane`: derived from the phase's primary target-path prefix
      (`backend`/`frontend`/`data`/`tests`) — must be assigned so that two
      tasks sharing any file land in the same lane.
    - `depends_on`: unchanged (already resolved phase-number → message_id).
    Update **`core/templates/plan/CONVERSATION_PROMPTS.template.md`** docs to note
    the planner now tags lanes (advisory text only).
13. **Core→adapter sync:** run `pathly-setup claude --apply --repair` after editing
    skills (per project rule — core is the source of truth; adapters are stitched).

### Step 7 — Snapshots / tests
14. Update affected snapshot tests (`tests/snapshots/development__*.claude.md`) for
    the removed build.md step; add scheduler unit + integration tests (§7).

---

## 5. Per-worker runtime isolation plan

Grounded in the runtime-config map. The checklist: **port is ready, cwd is ready,
budgets are ready, DB is the one hardcoded knob.**

| Resource | Current | P2 (LaneIsolation) | P3 (WorktreeIsolation) |
|---|---|---|---|
| **HTTP port** | `PATHLY_FSM_HTTP_PORT`, env-configurable (`config.py:42–52`) | **shared** — one FSM server for the run; lane workers talk to the same 8765 | per-task port from a pool |
| **SQLite DB** | hardcoded `~/.pathly/pathly.db` (`connection.py:93–95`) | **shared** — one DB for the run (lanes write disjoint task rows; SQLite WAL handles concurrent threads, `connection.py:97–101`) | per-worktree DB file |
| **cwd** | `state.project_root` → `TERMINAL_SPAWN.cwd` (`terminal.py:209`) | **shared** worktree | per-task worktree |
| **iteration / cost budget** | per-run in `RunnerState` (`state.py:32–41`), enforced before each stage (`orchestrator.py:257–273`) | per-run, shared across lanes (see §8 cost note) | per-run |

### 5.1 What changes in P2 (minimal)

Only **one** real change to runtime config: make the DB path env-overridable so
the *seam* exists, even though LaneIsolation passes the shared path through it.

```python
# db/connection.py  get_db(), replace lines 93–95
db_dir = Path(os.environ.get("PATHLY_DB_DIR", str(Path.home() / ".pathly")))
db_dir.mkdir(parents=True, exist_ok=True)
db_path = os.environ.get("PATHLY_DB_PATH") or str(db_dir / "pathly.db")
```

(`import os` already present in that module.) Note: the per-thread connection
cache (`connection.py:97–101`) keys on `_local.conn`, not on path — fine for P2
because all lane threads in one process share one DB path. P3 worktree isolation
runs each worker as a *separate process* (separate PTY already), so each process
reads its own `PATHLY_DB_PATH` from the spawned env.

### 5.2 Threading env into the spawned argv

`TaskWorkspace.env` is the carrier. The worker passes it to
`_run_stage_via_terminal`, which adds it to the `TERMINAL_SPAWN` payload so Studio
spawns the PTY with that environment:

```python
# terminal.py — TERMINAL_SPAWN payload (lines 200–211), add one field:
payload = {
    ...,
    "cwd": ws.cwd,           # was state.project_root; now from TaskWorkspace
    "env": ws.env,           # NEW: { PATHLY_DB_PATH, PATHLY_FSM_HTTP_PORT }
    ...,
}
```

Studio's PTY spawner (`node-pty`) already accepts an `env` map; the IPC payload
just needs the field forwarded. In P2 `ws.env` carries the shared DB path + 8765,
so behavior is unchanged — but the wire is in place for P3 to pass per-task values
with zero supervisor changes.

---

## 6. Studio visibility — reuse what exists

No new SSE channel. Parallel lanes surface through machinery Studio already
renders:

| Surface | Mechanism | Change |
|---|---|---|
| **One terminal tab per running worker** | `TERMINAL_SPAWN` already fires per `_run_stage_via_terminal` call with a unique `tab_id`/`run_id` (`terminal.py:200–223`). N concurrent workers → N tabs. | none — emergent from parallelism. Add the worker's `lane` to the `label` (`f"{adapter} — {lane}"`) so tabs are legible. |
| **Lane / task board state** | The existing `COMMS_UPDATE` SSE on the comms stream already broadcasts `task_unblocked` (`comms.py` complete path). Add `task_claimed` and `task_failed` events from the new `/claim` and `/fail` routes. | small — two new event names on the existing channel; Studio's task board already subscribes. |
| **Run-level lane summary** | `GET /runner/status` snapshot. | optional — add `"lanes": [{ "lane": "...", "task_id": "...", "run_id": "..." }]` derived from in-flight workers so a non-terminal view can show "3 lanes active". |

The principle: Studio learns about parallelism the same way it learns about
sequential stages — TERMINAL_SPAWN for execution, COMMS_UPDATE for board state.
No bespoke "scheduler" UI is required for P2.

---

## 7. Phasing + verification

### P2 — sequential, scheduler owns the loop
- **Scope:** `scheduler_loop` runs with `max_concurrency` pinned to 1 (single
  worker), DAG flag on for one test feature. Proves the board-driven frontier loop
  (reclaim → claim → spawn → complete → recompute) without touching parallelism.
- **Tests:**
  - *Unit (frontier logic, fake spawn):* inject a fake `_run_stage_via_terminal`
    that returns immediately. Seed a linear DAG (A→B→C). Assert: claim/complete
    order is A,B,C; `claim_task` returns False on a re-claim; `get_ready_tasks`
    never returns an `in_progress` task.
  - *`claim_task` race:* two threads call `claim_task` on the same pending row;
    assert exactly one gets `True`, the other `False` (double-spawn guard).
  - *`fail_task` cascade:* A→B→C; fail A; assert B,C become `blocked` and never
    enter the frontier.
  - *Crash-resume:* mark a task `in_progress`, call `reclaim_stale_claims`, assert
    it returns to the frontier.

### P2.5 — lane-parallel (≤1 worker/lane)
- **Scope:** `LaneIsolation.max_concurrency = len(ready_lanes)`. Planner emits
  lanes. Shared worktree/DB/port. No merge.
- **Tests:**
  - *Integration (3-task diamond DAG):* post A (lane=data) → {B (lane=backend),
    C (lane=frontend)} → D (lane=tests), where B and C both depend on A and D
    depends on both. With a fake spawn that records start/finish timestamps,
    assert: A finishes before B and C start; B and C run **concurrently** (their
    intervals overlap); D starts only after both B and C complete. This is the
    canonical proof of correct frontier + lane parallelism.
  - *Same-lane serialization:* two ready tasks in lane=backend → assert they run
    sequentially (intervals do not overlap), proving ≤1/lane.
  - *Disjoint-file invariant (lint, not runtime):* a planner-side check that two
    tasks in different lanes declare no overlapping target paths.

### P3 — worktree isolation (future, not built here)
- Swap `LaneIsolation` → `WorktreeIsolation`; add the fan-in merge task. The
  scheduler and all P2/P2.5 tests pass unchanged (that's the seam working).
- New tests: same-lane parallel via separate worktrees; merge-conflict surfaces as
  a `fail_task` on the merge task.

---

## 8. Risks & non-goals

| Risk | Mitigation |
|---|---|
| **Double-spawn** (two ticks spawn one task) | `claim_task` atomic compare-and-set (§3.3). Frontier never re-yields an `in_progress` task. The unit race test gates this. |
| **Partial failure of a branch** | `fail_task` cascade-blocks transitive dependents (§3.3) so they neither run on broken input nor hang. The run surfaces `task_failed` and can `escalate`. Sibling lanes continue. |
| **Deterministic resume after crash** | Board is authoritative; `reclaim_stale_claims` on startup reverts orphaned `in_progress` → `pending`. The frontier is a pure function of DB rows, so resume re-derives the same ready set. |
| **Cost budget across parallel workers** | Budget is per-run (`state.cost_usd_so_far`, `max_cost_usd`, `state.py:32–41`), and workers update it under `_lock` (`orchestrator.py:463–471`). With N workers in flight, the cap can be *overshot by up to (N−1) in-flight stage costs* before the next check trips. P2.5 mitigation: check the cap **before claiming** each task (claim is the spawn gate), and treat the cap as a soft ceiling, not a hard stop mid-flight. Accept bounded overshoot ≤ active-lane count; document it. |
| **Deadlock — a lane never frees** | A worker that hangs (no AGENT_DONE, no PTY result) is bounded by the existing `_TERMINAL_RESULT_TIMEOUT` (terminal.py timeout path → RuntimeError → `fail_task`). No lane can be held forever; a stuck task fails and cascades rather than wedging the scheduler. |
| **Frontier starvation** | If the planner mis-assigns lanes such that all ready tasks share one lane, the scheduler degrades to sequential — correct, just not parallel. Acceptable; the disjoint-file lint warns the planner. |

### Explicit non-goals (deferred)
- **Git worktrees / per-task workspaces** — seam only (`WorktreeIsolation` is a
  documented stub). Not built in P2/P2.5.
- **Fan-in merge** — arrives with P3 worktrees as a sequential `lane="merge"` task.
- **Cross-lane shared-file edits** — NOT supported by LaneIsolation. The planner
  must serialize them into one lane (the **"contract task" pattern**: a single
  task that owns the shared interface file, with the lanes that consume it
  depending on it). Concurrent edits to one file across lanes are explicitly out
  of scope until worktrees + merge land.
- **Task priority / SLA / TTL** — no priority column; ready tasks run in discovery
  order. Out of scope.
- **Per-task retry policy** — `attempts` is recorded, but auto-retry-on-fail is
  deferred; P2 surfaces failure and escalates.

---

## Appendix — ground-truth file:line index (verified against source)

| Claim | Location |
|---|---|
| Frontier query (`task_status='pending'`, deps all done) | `db/queries/comms.py:400–435` |
| Completion + newly-ready walk (idempotent) | `db/queries/comms.py:438–484` |
| Write-lock pattern reused by claim/fail | `db/queries/comms.py:454`; `db/connection.py:97–101` |
| Additive-migration helper (re-runnable) | `db/migrations.py:283–314`; `depends_on` at 308 |
| `comms_messages` task columns; **no lane**, **no in-progress** | `db/migrations.py:217–244` (`task_status` 240, `assigned_to_stage` 241) |
| Task GET / complete routes (template for claim/fail) | `http_server/blueprints/comms.py:317`, `351` |
| Sequential loop attach point | `supervisor/orchestrator.py:211–539` (FSM poll 277, spawn 380, resolve 484, continue 522) |
| Per-task PTY spawn reused unchanged | `supervisor/terminal.py:161–350`; `TERMINAL_SPAWN` 200–223 (`cwd` 209) |
| AGENT_DONE watcher (per-worker daemon) | `supervisor/terminal.py:63–104` |
| `TerminalRun` condition-var completion signal | `supervisor/registry.py:18–79` |
| `RunnerState` budget fields | `supervisor/state.py:32–41`; cap check `orchestrator.py:257–273`; cost update 463–471 |
| Port env knob (ready) | `config.py:42–52` |
| DB path hardcoded (only knob to fix) | `db/connection.py:93–95` |
| Builder polling step to REMOVE | `core/skills/development/build.md:122–131` |
| Planner task post to extend with `lane` | `core/skills/planning/plan.md:266–301` |
