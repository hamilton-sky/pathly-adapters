# fsm-fan-out — parallel work inside ONE FSM state

**Goal.** Let a single FSM state execute N tasks at once and join, so Pathly keeps *one
engine* (the FSM) and *one authority* (the DB) without giving up parallelism.

```
  BUILDING ──┬─ agent → task A ─┐
             ├─ agent → task B ─┼── join ──► REVIEWING
             └─ agent → task C ─┘

  fsm_state.current is STILL the string "BUILDING" the whole time.
  One row. One scalar. Written by eventlog.write_state exactly as today.
```

The parallelism lives **inside a state's execution**, not in the state vocabulary. This is
deliberately *not* Harel-style orthogonal regions (`current` becoming a set of concurrent
sub-states): that would touch `write_state`'s legality check, the `STATE.json` export, the
`pathly-*` CLI, every gate and Studio's flow editor — a large blast radius for a capability
the fan-out shape delivers with the scalar intact.

---

## Where Pathly already is

Most of this is **built**. The audit that matters:

| Piece | State | Where |
|---|---|---|
| Thread fan-out + completion queue | **built** | `scheduler.py` — daemon thread per task, `completion_q` |
| Concurrency policy | **built** | `isolation.py` — `Isolation.max_concurrency(ready_lanes)` |
| One-worker-per-lane rule | **built** | `scheduler_loop`, `<=1` worker per `lane` |
| File-collision guard | **built** | `file_claims.py` — `try_claim`/`overlaps`/`release` |
| Dependency graph | **built** | `comms_messages.depends_on`, `get_ready_tasks` |
| Per-task retry + escalation | **built** | `task_retry.py` (convergence Phase 1) |
| Deadlock detection | **built** | `task_retry.detect_deadlocks` |
| Spawn concurrency caps | **built** | Studio spawn scheduler (global ≤8, headless ≤5) |
| Per-task worktrees (same-lane parallelism) | **stub** | `isolation.WorktreeIsolation` — documented, unimplemented |

**The road is laid and the speed limit is set to 1.** `LaneIsolation` — which returns
`max(1, len(ready_lanes))` workers — exists, works, and is **instantiated nowhere in
production**. The only isolation any caller uses is `SerialIsolation`, whose entire job is
to override `max_concurrency` to return `1`. Its own docstring says it: *"Flipping to
parallel (P3) is just swapping this back to LaneIsolation."*

So Pathly is on this track in capability, and off it in two respects:

1. **`scheduler_loop` is wired as a rival ENGINE, not as a component of a state.**
   `goal_executor._run_loop` calls it top-level, as a peer of `orchestrator._loop`. That is
   the second engine the convergence work was supposed to remove.
2. **`team-build`'s BUILDING drains serially by construction** — one task per FSM cycle,
   looping `BUILDING → REVIEWING → BUILDING` via the `on_board_count` transition rule.

---

## The design

### 1. Flow YAML surface

A state opts in. Absent → today's exact behavior, so no existing flow changes.

```yaml
parallel_states:
  BUILDING:
    max_workers: 4          # optional cap; default = isolation's own answer
    isolation: lane         # lane (default) | serial | worktree (P3)
```

`fsm/state.py::validate_flow_dict` gains `parallel_states` as a known key and validates
that each name is a declared state.

### 2. The engine change — `orchestrator._loop`

The loop already resolves one stage and calls `_run_stage_via_terminal` once. A parallel
state takes one branch instead:

```
  next_action() ──► current_state = "BUILDING"
        │
        ├─ NOT parallel ──► spawn one agent            (today, unchanged)
        │
        └─ parallel ──────► scheduler_loop(...)        ← the fan-out
                              goal_id  = state.goal_id
                              isolation = LaneIsolation()
                              spawn_fn = _run_stage_via_terminal
                              returns when the frontier is drained
        │
        ▼
  run_gates(BUILDING → REVIEWING)      ← the JOIN. Unchanged: one gate run,
        │                                after all workers finished.
        ▼
  complete_stage() ──► write_state("REVIEWING")
```

**`scheduler_loop` stops being an engine and becomes the fan-out executor of one state.**
That is what makes this a convergence rather than a third path: the FSM keeps ownership of
flow, states, gates and transitions; the scheduler owns only "run these N ready tasks".

### 3. What `goal_executor` becomes

`executor: loop` today means *"bypass the FSM, drain the DAG"*. After this it means
*"run the `team-build` flow, whose BUILDING state is parallel"* — the same work, through
the one engine, with gates, escalation ladders, park/resume and the audit trail it
currently forfeits. `_run_loop` reduces to a thin alias, then is retired.

### 4. Prompt composition — the three-line prerequisite

A DAG task's prompt (`scheduler.py`, `compose_skill("development/execute-task")`) does NOT
carry the runner-contract block that `fsm_compose.build_prompt` appends (*"you are headless
… never call `complete-stage`"*). Under fan-out those agents run inside an FSM stage, so
they must have it, or one will try to advance the flow itself.

Fix: extract that f-string (`fsm_compose.py`, `### Runner contract`) to a shared constant
and append it in both paths. **This is the whole obstacle that the reverted compiled
executor was built to route around** — see `src/pathly_orchestrator/CLAUDE.md`. Do this
first; it is independently correct and unblocks everything else.

---

## Invariants this must preserve

- `fsm_state.current` stays a **scalar**. One row per (project_root, feature), written by
  `eventlog.write_state` on transition only — never mid-fan-out.
- **Gates run once, at the join.** `require_tasks_done` is already the right predicate for
  "did the fan-out finish"; `command_gate` runs the project's verify once, not per task.
- **Park/resume keeps working.** The FSM state is `BUILDING` throughout, so a parked run
  resumes into BUILDING and re-derives its frontier from `get_ready_tasks` — no per-worker
  state to restore.
- **Billing identity stays per-spawn.** Each worker already mints its own
  `sched-<task_id>#<attempt>` run_id (convergence Phase 1); the FSM parent row is unchanged.
- **Cost/iteration caps.** `cost_cap.CostCapTracker.wrap(spawn_fn)` already exists for
  exactly this and folds into `scheduler_loop`'s `abort_check`. Note its documented limit:
  it stops *scheduling* past the cap, it cannot preempt in-flight work — and with N workers
  the overshoot is up to N tasks instead of 1.

## Risks, honestly

- **File collisions are the real danger.** `file_claims.py` guards it, but it needs the
  task's declared file set to be accurate. A task that touches an undeclared file can
  clobber a sibling. Gate parallelism on tasks having declared footprints, or keep
  `SerialIsolation` for flows whose tasks don't.
- **Same-lane parallelism needs worktrees** (`WorktreeIsolation`, still a stub). Until then
  `max_workers` is bounded by the number of distinct lanes, not by the cap.
- **Interleaved terminal output.** Studio opens a tab per spawn; N at once is a UX question
  the Monitor already handles for the loop executor, but it should be checked.
- **Failure semantics at the join.** If 1 of 4 workers fails: does BUILDING fail, or does
  the gate see 3 done + 1 needing retry? Prefer the latter — `task_retry.resolve_task_failure`
  already implements retry-then-escalate, so the join should report "frontier drained,
  these escalated" and let `require_tasks_done` block the transition.

## Phasing

| Phase | Change | Risk |
|---|---|---|
| **A** | Share the runner-contract constant between `build_prompt` and the DAG prompt path | tiny, independently correct |
| **B** | `parallel_states` YAML key + validation, no engine change yet | none (inert) |
| **C** | `_loop` branches to `scheduler_loop` for a parallel state, `SerialIsolation` first | behavior-preserving: still one at a time |
| **D** | Swap to `LaneIsolation` on one flow, measure | the real change |
| **E** | Retire `goal_executor._run_loop`; `executor: loop` becomes a parallel flow | removes the second engine |

Phase C is the important one: it moves the fan-out **inside** the FSM while still running
serially, so the architecture converges before any concurrency behavior changes. Parallelism
then becomes one line — the swap `LaneIsolation()` for `SerialIsolation()` — exactly as
`isolation.py` always intended.
