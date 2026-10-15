# Smoke the base before the first spawn and size a goal run's budget from its DAG

Type: task
Status: resolved
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

Work started at commit `f95152a3da7cda0678363e3ac5de8713bca99a8d`. Test-only commit:
`c98210f` (`test(build-proof): 12 failing test`). At that commit both new test files fail at
collection (`ImportError: cannot import name 'run_budget'` / `base_smoke` from
`pathly_orchestrator.supervisor`).

**Built**

- `src/pathly_orchestrator/supervisor/human_escalation.py` (new, 36 lines):
  `post_human_escalation(state, text)`, the body of the old
  `orchestrator_stage._resolve_stage_supervised._post_human_escalation` closure (same
  `post_message` call: board `feature`, scope `state.topic`, `to_agent="human"`,
  `type="escalation"`, `**system_stamp()`, best-effort).
- `src/pathly_orchestrator/supervisor/base_smoke.py` (new, 123 lines): `check_base(state,
  broadcast_fn) -> bool`.
- `src/pathly_orchestrator/supervisor/run_budget.py` (new, 50 lines): `refresh(state)`.
- `src/pathly_orchestrator/supervisor/orchestrator_stage.py`: the closure is gone; the
  human-checkpoint path calls `post_human_escalation(state, _checkpoint_text(topic, file_,
  result))` (a new module-level `_checkpoint_text` holds the unchanged text); `run_budget.refresh(
  state)` is the first statement of `_resolve_stage_supervised`. 251 -> 233 lines.
- `src/pathly_orchestrator/supervisor/api.py`: `start_run(..., smoke_base: bool = True)`; inside
  `_run_and_finalize`'s `try`, `if smoke_base and not base_smoke.check_base(state,
  broadcast_fn): return` before `_loop`; `resume_parked_run` passes `smoke_base=(prior.error_kind
  == "base_red")`.
- `src/pathly_orchestrator/supervisor/goal_verify.py`: one docstring reference
  (`orchestrator_stage.py::_post_human_escalation` -> `human_escalation.py::post_human_escalation`),
  since the closure it named no longer exists.
- `CLAUDE.md` (one sentence in the ground-truth paragraph of the pipeline section) and
  `src/pathly_orchestrator/CLAUDE.md` (new section "Run guard rails", the `verify.smoke` note under
  "Command resolution", three lines in the supervisor package map, and the
  `post_human_escalation` name in "Human checkpoints").
- `tests/runner_supervisor/test_base_smoke.py` (21 tests), `tests/runner_supervisor/
  test_run_budget.py` (15 tests) and the regenerated `tests/INDEX.md`,
  `tests/runner_supervisor/INDEX.md`. After the test-only commit I fixed one bug in my own test
  (`test_check_base_clips_a_huge_output` put the 50000-character flood in the command text, which
  the escalation also quotes; it now floods the output instead). The assertions are unchanged.

**Proof** (each run fresh, after the last edit)

- `python -m pytest tests/runner_supervisor/test_base_smoke.py -q -p no:cacheprovider`:
  `21 passed in 7.08s`, exit 0. Covers: `verify.build` exiting 1 on `team`, `team-build` and
  `goal-loop` -> status `parked`, `error_kind` `base_red`, the fake spawn called 0 times and
  `fhc.next_action` 0 times, `on_done` told `parked`/`base_red`; one `to_agent="human"`
  `escalation` (author_source `system`) holding the command, `exited 1`, the output, "before this
  run spawned anything" and `resume-parked {"topic": "smoke-demo"}`; a `RUNNER_PARKED` of kind
  `base_red`; the command run with cwd = project root and `PATHLY_VERIFY_GATE=1` (read from a
  log the command wrote); a timeout (`timed out after 1s`) and an unrunnable command both park;
  `verify.smoke` exiting 0 with `verify.build` exiting 1 -> `done`, spawned once, build never run;
  a red smoke with a green build parks; neither setting -> `done`; `consultation` (no build gate)
  and `smoke_base=False` are not smoked even with a red build; `resume_parked_run` after
  `base_red` smokes again (log: 1, 2, then 3 lines; the 3rd resume, with a green base, reaches
  `done`), after `human_checkpoint` it does not (log empty, parked again as `human_checkpoint`).
  Mutation check: `smoke_base = True` in `resume_parked_run` fails the human-checkpoint test,
  `smoke_base = False` fails the base_red test.
- `python -m pytest tests/runner_supervisor/test_run_budget.py -q -p no:cacheprovider`:
  `15 passed in 4.23s`, exit 0. Covers: 5 tasks x `goal.task_max_attempts` 3 -> 60; 0 tasks
  keeps 10; 1 task -> 12 (also with the setting unset, default 3); a larger caller cap (100) is
  kept; adding tasks between calls 24 -> 60; soft-deleting 3 of 5 tasks leaves 60; no `goal_id` ->
  10 with 5 tasks in the DB; another goal's tasks do not count; it logs on a raise and is silent
  on the next unchanged call; a failing task count or settings read leaves the cap and does not
  raise; `_resolve_stage_supervised` raises the cap (60) before its `complete_stage` call and also
  when the stage is then parked on a human (24).
- `python -m pytest tests/runner_supervisor -q -p no:cacheprovider`: `266 passed in 62.80s`, exit 0.
- Full Test command `python -m pytest tests/ -q -x -p no:cacheprovider`: `2691 passed, 14 skipped
  in 436.19s`, exit 0.
- Full Lint command from `commands.md`: exit 0 (black 522 files unchanged; mypy `Success: no
  issues found in 293 source files`; file size `953 source files checked; 19 known over 400 lines,
  none new, none grown`; mirror reads OK; test INDEX up to date; lint-imports `1 kept, 0 broken`;
  bandit no findings; adapters OK; entry points listed). Smoke: exit 0. Build (`python -m build
  --wheel`): `Successfully built pathly_adapters-2.24.1-py3-none-any.whl`, exit 0.

**Decisions**

- `post_human_escalation(state, text)` takes the finished text and uses `state.topic` as the
  scope. The only production caller passes `topic = state.topic`, so the checkpoint post is
  unchanged. The checkpoint text stayed byte-for-byte what it was (including its
  `{"topic": 'x'}` repr quoting); the new base-red text uses `json.dumps` so the resume call it
  shows is valid JSON.
- The base-red park (set `error_kind`, `_set_status(..., "parked")`, `RUNNER_PARKED`) is written
  out in `base_smoke.py` as the ticket lists it, not shared with the `_park` closure: that closure
  is not in this ticket, and its body is a few lines.
- `check_base` reuses `fsm.gates.command._get_setting` and `_resolve_timeout({})` (a lazy import,
  as `goal_verify.py` already imports from that module) so `verify.smoke`, `verify.build` and
  `verify.timeout_seconds` are read exactly as the gate reads them.
- A command that cannot run (not found, unparseable) counts as red, like the gate's
  fail-closed `command_not_executable`.
- `check_base` fails open if the check itself raises (a logged warning): an unhandled exception
  there would kill the supervisor thread in `running` status, since `_loop`'s own catch-all is
  not yet in force. `run_command` and `load_flow_config` never raise, so this guards the rest.
- `run_budget.refresh` imports its DB and `task_retry` pieces inside the function (as
  `task_retry` and the gates do), so the test can patch them at their home modules. It holds
  `registry._lock` only to compare and set `max_iterations`.

**Shortcuts taken**

- The smoke runs once at the start (and after a `base_red` resume), not between stages, so a base
  that goes red mid-run is still left to the gates. Worth upgrading only if mid-run drift shows
  up as misattributed failures.
- A slow `verify.smoke` / `verify.build` delays every start of those flows by up to
  `verify.timeout_seconds` (600 s). A project with a slow build should set a cheaper
  `verify.smoke`.
- `iterations` counts `_loop` stage passes, so a fan-out drain is one pass however many tasks it
  runs; the formula is therefore generous for `goal-loop`. Worth tightening only if a runaway
  `goal-loop` ever needs a tighter cap.
- The `team`/`team-build` flows loaded for the smoke go through `fan_out.load_flow_config` a
  second time per run (once in `check_base`, once in `_loop`); it is cheap and kept separate so
  `_loop` is untouched.

**For later tickets**

- Ticket 14 (acceptance): a red base is "blocked before any agent is spawned" through
  `supervisor.start_run` with `verify.build` red; `start_run(..., smoke_base=False)` turns the
  smoke off for a test that wants a red base mid-run. A scripted-agent acceptance run whose
  project root is not a clean green base needs `verify.build` (or `verify.smoke`) green, or unset,
  at `start_run`; otherwise it parks `base_red` before the first spawn.
- Any other test or caller that calls `start_run` for `team`, `team-build` or `goal-loop` with a
  red `verify.build` configured now parks; none in the repo did (full suite green).
- `supervisor/api.py` is 290 lines and `orchestrator_stage.py` 233; `orchestrator.py` is
  untouched (399).
