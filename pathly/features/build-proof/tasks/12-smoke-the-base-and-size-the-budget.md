# Smoke the base before the first spawn and size a goal run's budget from its DAG

Type: task
Status: open
Blocked by: 01
Test first: yes

Two run-level guard rails in the supervisor, each in its own new module.

**Smoke.** New `src/pathly_orchestrator/supervisor/base_smoke.py::check_base(state, broadcast_fn) -> bool`:

- It applies only to flows whose gates include a `command_gate` with `command_key: build` (today
  `team`, `team-build` and `goal-loop`; load the flow with `fan_out.load_flow_config`).
- The command is the app setting `verify.smoke`, else `verify.build`. With neither, return
  `True` (skip, as `command_gate` does when unconfigured).
- Run it with `proof.command.run_command` in `state.project_root`, with the
  `verify.timeout_seconds` timeout (default 600) and `PATHLY_VERIFY_GATE=1`.
- Exit 0: return `True`.
- Otherwise:
  - post a human escalation on the board saying the base is red before this run spawned
    anything, with the command, the exit code or timeout, the clipped output, and how to resume
    (`POST /runner/resume-parked {"topic": …}`);
  - set `state.error_kind = "base_red"`;
  - `_set_status(state, "parked", broadcast_fn)`;
  - broadcast `RUNNER_PARKED` with `kind: "base_red"`;
  - return `False`.

Move the body of the closure `orchestrator_stage._resolve_stage_supervised._post_human_escalation`
into one module-level helper (for example `supervisor/human_escalation.py`). Both the
human-checkpoint path and this check use it, so there is no copy (`CLAUDE.md` rule 5).

In `supervisor/api.py`, `start_run` gains `smoke_base: bool = True`. Inside `_run_and_finalize`'s
`try`, before `_loop(state, broadcast_fn)`: `if smoke_base and not base_smoke.check_base(state,
broadcast_fn): return`. The `finally` still calls `on_done`, and it already reports `parked` with
its `error_kind`. `resume_parked_run` passes `smoke_base=(prior.error_kind == "base_red")`, so a
run parked mid-build on a human checkpoint is not re-parked by its own in-progress red work.

**Budget.** New `src/pathly_orchestrator/supervisor/run_budget.py::refresh(state) -> None`. For
a run with a `goal_id`, it sets `state.max_iterations` to the larger of the current value and
`count_tasks_for_goal × task_retry.resolve_max_attempts() × (MAX_FEEDBACK_ROUNDS + 1)`, under
`registry._lock`. It logs when it raises the cap, never lowers it, and never raises an error. Call
it at the top of `orchestrator_stage._resolve_stage_supervised`, which runs after every stage,
so the budget follows the DAG as decomposition adds tasks. `orchestrator.py` is at 399 lines and
is not touched. Cost caps and the `cap_exceeded` handling stay as they are.

Living docs:

- root `CLAUDE.md`: one sentence in the pipeline section that a red base parks the run before
  any spawn;
- `src/pathly_orchestrator/CLAUDE.md`: `verify.smoke`, `base_red`, the budget formula, and that
  resume only re-smokes after `base_red`.

## Not in this ticket

- Smoke for the `single` executor, board runs and consultations: they have no `command_gate`
  build and are not runs the brief names.
- A budget for runs without a goal: they keep the caller's `max_iterations`.

## Done when

- `python -m pytest tests/runner_supervisor/test_base_smoke.py -q -p no:cacheprovider` passes,
  with `fhc` and `_run_stage_via_terminal` patched as in
  `tests/runner_supervisor/test_runner_fsm_integration.py`. It covers:
  - with `verify.build` set to a command that exits 1, a `team-build` `start_run` ends `parked`
    with `error_kind` `base_red`, a `to_agent="human"` escalation is on the board, and the fake
    spawn was called 0 times;
  - with `verify.smoke` exiting 0 and `verify.build` exiting 1, the run proceeds;
  - with neither set, the run proceeds;
  - `resume_parked_run` after `base_red` smokes again, after `human_checkpoint` it does not.
- `python -m pytest tests/runner_supervisor/test_run_budget.py -q -p no:cacheprovider` passes. It
  covers:
  - a goal with 5 tasks and `goal.task_max_attempts` 3 gives `max_iterations` 60
    (`5 × 3 × (3 + 1)`);
  - a goal with no tasks yet leaves 10, and a goal with 1 task gives 12;
  - adding tasks between calls raises the cap, and deleting tasks does not lower it;
  - a run without `goal_id` is untouched.
- `python -m pytest tests/runner_supervisor -q -p no:cacheprovider` passes.

```check
# The conductor runs this block before review.
$ python -m pytest tests/runner_supervisor/test_base_smoke.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor/test_run_budget.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Stories ("Guard rails on the run"), § Decisions ("The run budget"), § Edge cases
  (resume rows)
- `src/pathly_orchestrator/supervisor/api.py` (`start_run`, `_run_and_finalize`,
  `resume_parked_run`), `supervisor/orchestrator_stage.py` (`_park`, `_post_human_escalation`),
  `supervisor/state.py::MAX_FEEDBACK_ROUNDS`, `db/queries/comms_tasks.py::count_tasks_for_goal`
- `/home/claude/hamilton-sky/feature-flow/feature_flow/conductor.py` (`run_smoke`, `run_limit`;
  read-only)

## Answer
