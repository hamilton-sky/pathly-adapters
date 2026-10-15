# Prove each goal-loop task after it reports success

Type: task
Status: resolved
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

Work started at commit `6c637c2c7d1a1c1e011a34a1cde921349d03253b`. The test-only commit is
`1778ae4` (`test(build-proof): 05 failing test`). An earlier builder was interrupted after that
commit and left the implementation uncommitted in the working tree; this builder re-read all of
it, re-ran every proof below from scratch and committed it.

**Built**

- New `src/pathly_orchestrator/supervisor/task_proof.py` (365 lines): `wrap(spawn_fn)`, the
  lock-guarded in-flight registry (`_IN_FLIGHT`, `_open_window`, `_close_window`), the floor scan
  call, the `task-edit` finding, the check run, the error text (`## Floor guard`, `## Task text`,
  `## Checks`, at most 4000 characters) and the `TASK_PROOF` record.
- `supervisor/drain.py`: `spawn_fn=tracker.wrap(task_proof.wrap(spawn_fn))`; the import is inside
  `drain_frontier`.
- Reason caps edited in place: `scheduler.py` (the two `reason = ...` lines) and
  `task_retry.retry_task` and `db/queries/comms_tasks.py::fail_task` from `[:500]` to `[:4000]`;
  `task_retry.build_retry_context` from `[:2000]` to `[:4000]`.
- `supervisor/task_prompt.py`: the task body is `task.get("claimed_text") or task.get("text") or ""`.
- Docs: root `CLAUDE.md` ("Comms board", one sentence) and `src/pathly_orchestrator/CLAUDE.md`
  (new section "Task proof in the goal-loop drain", the `TASK_PROOF` writer, the 4000-character
  cap in the retry section, the package-map entries, and the "nothing calls it yet" sentences for
  `claimed_text`/`floor_allow`, `run_checks` and `floor.scan`).
- Tests: `tests/dag_goals/task_proof_support.py`, `test_task_proof.py` (10 tests),
  `test_task_proof_window.py` (6 tests) and the two `INDEX.md` files. All but one test are in the
  test-only commit; the later one,
  `test_the_whole_report_survives_into_the_retry_prompt_and_the_final_failure`, pins the 4000
  caps (a 3000-character check output must reach the next prompt and the final `fail_reason`).
  With `retry_task` set back to `[:500]` it fails, with the original caps it passes.

**Proof** (each command run fresh after the last edit, venv on PATH)

- `python -m pytest tests/dag_goals/test_task_proof.py -q -p no:cacheprovider`: `10 passed`,
  exit 0. It drives the real `drain.drain_frontier` with `SerialIsolation`, a `git init` repo
  under `tmp_path` and a fake spawn, and covers each listed case:
  - red check: `test_a_failing_check_is_retried_with_its_real_output_then_fails` (second prompt
    holds `got: exit 3` and `red-marker`, `goal.task_max_attempts=2` ends `failed`, two
    `TASK_PROOF` records with `checks: failed`);
  - skip: `test_a_task_that_adds_a_skip_is_retried_with_the_finding` (`skip:` in `fail_reason`
    and in the second prompt);
  - `floor_allow ["skip"]` passes: `test_what_a_human_allowed_for_the_task_passes`;
  - `task-edit`: `test_a_task_that_edits_its_own_text_is_retried_with_task_edit`;
  - `plan-edit` (plan file flagged, a feedback file under the board home not):
    `test_a_task_that_edits_a_plan_file_is_retried_with_plan_edit`;
  - no check block and a clean diff: `test_a_clean_task_is_done_and_proven_with_or_without_a_check_block`
    (`TASK_PROOF checks: "none"`, `_proof_record.task_proven` true for the done task);
  - `floor.enabled=false`: `test_with_the_floor_off_the_skip_passes` (`floor: "off"`).
- `python -m pytest tests/dag_goals -q -p no:cacheprovider`: `231 passed`, exit 0 (scheduler,
  retry and drain tests unchanged).
- Also run: `python -m pytest tests/dag_goals/test_task_proof_window.py` is part of the 231
  (`16 passed` together with the first file, exit 0).
- Full Test command `python -m pytest tests/ -q -x -p no:cacheprovider`: `2745 passed, 14 skipped
  in 463.56s`, exit 0.
- Lint chain, each piece exit 0: `black --check src/ tests/` (529 files unchanged), `mypy src/
  --ignore-missing-imports --no-strict-optional` (`no issues found in 295 source files`),
  `scripts/check_file_size.py` (`19 known over 400 lines, none new, none grown`; `task_proof.py`
  is 365, `scheduler.py` stays 393, `comms_tasks.py` stays 418), `check_no_mirror_reads.py`,
  `gen_test_index.py --check`, `lint-imports` (1 kept, 0 broken), `bandit -q -r src/ -ll -x
  src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`.
- Build `python -m build --wheel`: built `pathly_adapters-2.24.1-py3-none-any.whl`, exit 0. Smoke
  command: exit 0.

**Decisions**

- The proof reads the task again after the spawn (`get_task`), so the checks run against the
  `claimed_text` and `floor_allow` as they are when the agent returns, and a human allow list set
  mid-attempt counts. The before-read only registers the window and the declared `files`.
- `TASK_PROOF` is written for every attempt that reported success and was judged, failed ones
  included (`checks: failed`, `floor: failed`), because `task_proven` takes the newest record for
  the current `claimed_at`; a failed attempt's record therefore keeps a task unproven until a
  later attempt passes. Nothing is written when the spawn raised or reported failure.
- A `claimed_text` of `None` (a task claimed before the column existed, or never claimed) gives no
  `task-edit` finding; an empty-string `claimed_text` is compared like any other.
- Two windows overlap when both were registered in the same project root (`realpath`) at the same
  time; each registers its declared `files` with the other, so the set to leave out is complete
  whichever finishes first. `_left_out` reads a finding as `<category>: <path>: <text>` (the format
  `floor.scan` writes) and drops it when `<path>` equals a declared entry or sits under it.
- Error text budget: Floor guard section up to 1200 characters (at most 20 findings, then "... and
  N more"), Task text up to 400, Checks gets what is left of 4000 (at least 200), clipped head
  (a third) and tail, because a test runner's summary is at the end of its output.
- The outcome is returned as a shallow copy with `outcome: "failed"` and `error`, so `cost_usd`
  survives and the tracker outside the wrapper still counts a failed attempt (asserted:
  `tracker.total == 0.5` for two attempts at 0.25).
- A `project_root` that is not a directory, a task row that is missing or not a `task`, an
  unreadable task, a failing snapshot or any exception in the judging passes the outcome through
  unchanged with a log line. No git gives `floor: "off"` and the checks still run.
- `Floor: allow skip` is used only by the test source, as the ticket says.

**Shortcuts taken**

- Lane-parallel tasks share one working tree, so an undeclared written path is blamed on every
  overlapping task, and a path another overlapping task declared is excused for all of them.
  Stops working when two parallel tasks both touch the same declared directory and one of them
  weakens a test there; worth upgrading when `WorktreeIsolation` exists.
- The in-flight registry is module-level state in one process. Right for the one server process
  that runs the drain; a second drain process would not see the first one's windows.
- Each attempt is judged on its own diff, as the ticket specifies, so a weakening an earlier failed
  attempt left in place is not seen again. The goal-loop join gate (tickets 06 and 07) re-checks
  the whole run.
- The checks run in the project root with the server's account and `verify.timeout_seconds`
  (default 600); `run_command` kills only the direct child on a timeout.
- Check blocks are read with `checks_in`, which does not see a fence that follows a 4-backtick or
  an unclosed fence (a known limit of ticket 01), so such a block counts as "no block".

**For later tickets**

- 06 and 07 (the join gates): `record_task_proof` is now called, so `task_proven(storage, task)`
  is real for a goal-loop task that passed this proof. A task that was proven here has a
  `TASK_PROOF` with its current `claimed_at`; the join's `task_checks` should skip it and run only
  tasks without one (a builder fix round completes tasks itself and writes none). The record
  goes in the run's storage dir, `state.storage_path` (else the resolved storage), the same dir
  the gates read.
- `goal-loop` still records no `SPAWN_WINDOW`, and this wrapper does not write one either: the
  per-task before/after trees live only inside the wrapper call.
- Anything else that calls `drain_frontier` is now proven too (the only caller today is
  `fan_out._drain`). A test that drives `drain_frontier` with a project root that is a real
  directory and a task row on the board gets a snapshot, a floor scan and the task's checks; a
  test that wants none of that uses a root that is not a directory or a run id that is not
  `sched-<id>#<n>`.
- `task_retry` now keeps 4000 characters of a failure reason in `fail_reason`, `retry_task`'s
  update and the retry prompt block; ticket 14's acceptance test should expect the real check
  output in the second prompt.
