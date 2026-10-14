# Prove each goal-loop task after it reports success

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 15
Test first: yes
Floor: allow skip

Today a DAG task passes on its own `AGENT_DONE` outcome. Add
`src/pathly_orchestrator/supervisor/task_proof.py::wrap(spawn_fn)` and apply it inside
`supervisor/drain.py::drain_frontier`, inside the cost tracker:
`spawn_fn=tracker.wrap(task_proof.wrap(spawn_fn))`. When `spawn_fn` is `None`, resolve
`pathly_orchestrator.supervisor._run_stage_via_terminal` at call time, as
`cost_cap.CostCapTracker.wrap` does, so tests that patch it still work.

For a run id of the form `sched-<task_id>#<n>` the wrapper does the following (any other run id
passes straight through):

1. Read the task (`db/queries/task_proof.get_task`). Register the task in a module-level,
   lock-guarded in-flight registry with its declared `files`, and take `proof.tree.snapshot`
   of `state.project_root`.
2. Call the spawn. If it raised, or `scheduler._outcome_is_failure(outcome)` is already true,
   return as is.
3. Take the after snapshot. Then check, in order:
   - The floor (skipped when `fsm/gates/_proof.floor_enabled()` is false or either snapshot
     is `None`): `proof.floor.scan(root, before, after, allow=<the task's floor_allow>,
     protected=[board_home(storage)], may_change=stage_writes(storage, "builder"),
     config_commands=<verify.build, verify.test, verify.smoke settings>)`. Leave out the paths
     declared in the `files` of every task whose window overlapped this one (spec.md
     § Decisions, the per-task diff base). A declared directory covers everything under it,
     as `fragments/task-dag-post.md` promises.
   - Task text: when `claimed_text` is set, differs from `text`, and `task-edit` is not allowed,
     add a `task-edit` finding.
   - Checks: `proof.checks.checks_in(claimed_text or text)`. A `ParseError` is a failure that
     quotes the error. No block is not a failure. Otherwise
     `run_checks(checks, cwd=project_root, timeout=<verify.timeout_seconds, default 600>)`.
4. Record the result with `fsm/gates/_proof_record.record_task_proof` in the run's storage
   path: `checks` is `passed`, `failed`, `none` or `error` (a `ParseError`); `floor` is `off`
   when the scan was skipped, `failed` on any floor or `task-edit` finding, else `clean`. The
   join's task-check gate reads this record and does not run a proven task's checks again. On
   any finding or failing check, return the outcome with `outcome: "failed"` and an `error`
   holding a short heading per part ("Floor guard", "Task text", "Checks") and the report,
   clipped to 4000 characters.

Each attempt is judged on its own diff. A weakening an earlier failed attempt left in place is
therefore not seen again by the next attempt; the retry prompt carries the earlier finding, and
the floor gate at the goal-loop join re-checks the whole run's diff (spec.md § Decisions, "Floor
gate in goal-loop").

The existing path does the rest: `scheduler_loop` sees the failure and
`task_retry.resolve_task_failure` retries or escalates. Raise the reason caps so the report
survives, editing the existing lines in place:

- `[:500]` to `[:4000]` in `scheduler.py` (the two `reason = ...` lines);
- `[:500]` to `[:4000]` in `task_retry.retry_task` and in `db/queries/comms_tasks.py::fail_task`;
- `[:2000]` to `[:4000]` in `task_retry.build_retry_context`.

`supervisor/task_prompt.build_task_prompt` uses `task.get("claimed_text") or task.get("text")`
as the task body, so a retry shows the frozen task.

Living docs: root `CLAUDE.md` ("Comms board", where `loop` runs `goal-loop`) gets one sentence
that each task is now proven after it reports success. `src/pathly_orchestrator/CLAUDE.md` gets
the `TASK_PROOF` event and the retry-path behaviour.

The `Floor:` line above is needed because the tests have a fake task add `@pytest.mark.skip` to
a test file in a temp repo, and that line sits in this ticket's test source.

## Not in this ticket

- Proof in `team`/`team-build`, where the builder claims and completes tasks itself: tickets 06
  and 07.
- The join gates on `goal-loop`'s `DRAINING->DONE` (`floor_gate` and `task_checks`), which judge
  builder fix rounds after the drain and tasks completed by them: tickets 06 and 07.
- Re-running tasks in a separate worktree: `WorktreeIsolation` stays a stub.

## Done when

- `python -m pytest tests/dag_goals/test_task_proof.py -q -p no:cacheprovider` passes. It drives
  `drain.drain_frontier` with `SerialIsolation`, a `git init` project under `tmp_path`, and a fake
  spawn that edits files and reports success. It covers:
  - a task whose check block has `$ python -c "import sys; print('red-marker'); sys.exit(3)"`
    is retried, its second prompt contains `red-marker` and `got: exit 3`, and with
    `goal.task_max_attempts` set to 2 it ends `failed`;
  - a task that adds `@pytest.mark.skip` is retried with `skip:` in its `fail_reason`;
  - the same task with `floor_allow` `["skip"]` passes;
  - a task whose agent changes its own `text` in the DB is retried with `task-edit`;
  - a task that edits a file under the board home other than its feedback files is retried with
    `plan-edit`;
  - a task with no check block and a clean diff is `done`, a `TASK_PROOF` event with
    `checks: "none"` exists, and `_proof_record.task_proven` is true for the done task;
  - with `floor.enabled` set to `false`, the skip passes.
- `python -m pytest tests/dag_goals -q -p no:cacheprovider` passes (scheduler, retry and drain
  tests unchanged).

```check
# The conductor runs this block before review.
$ python -m pytest tests/dag_goals/test_task_proof.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("The per-task diff base in goal-loop", "Floor gate in goal-loop"),
  § Edge cases
- `src/pathly_orchestrator/supervisor/drain.py::drain_frontier`,
  `supervisor/cost_cap.py::CostCapTracker.wrap`, `supervisor/scheduler.py::scheduler_loop` (the
  `task_run_id = f"sched-{task_id}#..."` line and the completion handler),
  `supervisor/task_retry.py`
- `tests/dag_goals/test_task_retry.py`, `tests/dag_goals/test_drain_shared.py` (fixtures for
  goals and tasks)

## Answer
