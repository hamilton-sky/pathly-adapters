# Run task check blocks at every join where a builder may have completed a task

Type: task
Status: open
Blocked by: 01, 03, 15
Test first: yes

In `team` and `team-build`, the builder claims a board task (`POST /comms/tasks/claim`), does it
and completes it itself (`POST /comms/tasks/complete`). The supervisor never sees per-task
success, so the stage's end is where the checks run. A builder also completes tasks in fix
rounds: `require_tasks_done` on `REVIEWING->TESTING` and `->DONE` routes `INCOMPLETE_TASKS.md` to
the builder, and `team/build.md` tells that builder to finish the task there. In `goal-loop` the
same file reaches a builder after the drain. Those completions must be checked too.

New gate type `task_checks` in `src/pathly_orchestrator/fsm/gates/task_checks.py`, registered in
`fsm/gates/__init__.py::_CHECKS`:

- Read `proof_base` (`fsm/gates/_proof_record.read_proof_base`). Skip (`gate_skipped`,
  `no_proof_base`) when it is missing.
- Tasks: `task_proof.tasks_completed_since(board, feature_scope, goal_id,
  proof_base.started_at)`, minus every task for which `_proof_record.task_proven(storage, task)`
  is true. So each completion is checked once: a task proven by an earlier gate, or inside the
  goal-loop drain, is not run again, and a task re-claimed since is.
- For each remaining task, parse `proof.checks.checks_in(claimed_text or text)`.
  - A `ParseError` fails, quoting the error, and records `checks: "error"`.
  - No block records `checks: "none"`.
  - Otherwise `run_checks(checks, cwd=project_root_of(storage_path),
    timeout=<command.py::_resolve_timeout({})>)`, recording `passed` or `failed`.
  - Record through `_proof_record.record_task_proof(..., run_id=<"gate:" + the transition>,
    floor="n/a")`.
- Any failure: `gate_failed` with `on_fail` (`TASK_CHECK_FAILURES.md`). The reason has one
  section per failing task (its first line, then the report) and says the checks were run
  from the text the task had when it was claimed.

Flows, each at the place spec.md § Migration and compatibility gives (after `floor_gate` when it
is there, before `scope_gate` and `reviewer_unchanged`), with `TASK_CHECK_FAILURES: builder`
added to each flow's `feedback_routing`:

- `team.flow.yaml` and `team-build.flow.yaml`: add
  `{type: task_checks, on_fail: TASK_CHECK_FAILURES.md}` to `BUILDING->REVIEWING`,
  `REVIEWING->TESTING` and the wildcard `->DONE`;
- `goal-loop.flow.yaml`: add it to `DRAINING->DONE`, as the last gate;
- update the expected goal-loop gate set in `tests/comms_board/test_comms_goals_run.py` (the
  `gate_types == {...}` assertion) to include `task_checks`. The change is deliberate.

Add an `_exit_requirement` line in `fsm_compose_responses.py`: each completed task's check block
is run by the supervisor; a self-reported pass does not count.

Living docs. This gate runs commands, so it makes two claims stale that say `command_gate` is
the only gate that executes anything. Fix both in this ticket:

- root `CLAUDE.md`, the "Ground truth" paragraph: today it says "Four of the five FSM transition
  gates read state an *agent produced*" and that `command_gate` "is the one that
  **executes**". Name `task_checks` as a second gate that executes: it runs each completed
  task's check block, from the text frozen at claim, with the same runner as `command_gate`
  (`proof/command.py`). Remove the gate count ("Four of the five") if it is still there, so
  the paragraph stays true as other gates are added. Verify-then-fix: change only those claims;
- `src/pathly_orchestrator/CLAUDE.md`, "Transition gates": add the `task_checks` row to the
  table (the transitions that carry it, the once-per-completion rule), and fix the sentence
  "The first four read state that agents produced; only `command_gate` executes something".

## Not in this ticket

- Re-running a task's checks after they passed, to catch a later regression: rejected (spec.md
  § Decisions, "When task checks run"). `command_gate test` covers the suite.
- Checking each goal-loop task attempt inside the drain: ticket 05.
- The planner skill that writes check blocks: ticket 13.

## Done when

- `python -m pytest tests/fsm_flows/test_task_checks_gate.py -q -p no:cacheprovider` passes. On a
  feature under `tmp_path`, with tasks claimed through `claim_task` and completed through
  `complete_task`, it covers:
  - team-build: a completed task whose check exits 1 blocks BUILDING->REVIEWING, and
    `TASK_CHECK_FAILURES.md` holds `got: exit 1` and is routed to `builder`; editing the live
    `text` to a passing check does not help (`claimed_text` is used);
  - team-build: a task first completed in REVIEWING (after BUILDING->REVIEWING passed) with a
    failing check blocks REVIEWING->TESTING, and one completed in RETRO blocks RETRO->DONE;
  - a task whose checks passed at BUILDING->REVIEWING is not run again at REVIEWING->TESTING:
    exactly one `TASK_PROOF` event exists for it after both gates;
  - goal-loop: at DRAINING->DONE, a task with a passing `TASK_PROOF` for its current
    `claimed_at` is not run, and a task completed without one (as by a fix round) is run and
    fails the join;
  - a task with no block passes and leaves `checks: "none"`; a malformed block fails with the
    parser's message; a task completed before `proof_base.started_at` is not run.
- `python -m pytest tests/fsm_flows tests/comms_board/test_comms_goals_run.py -q -p no:cacheprovider`
  passes.
- Both docs name the gate and neither keeps the stale claim. The command below prints
  `docs current`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_task_checks_gate.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows tests/comms_board/test_comms_goals_run.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import pathlib;r=' '.join(pathlib.Path('CLAUDE.md').read_text(encoding='utf-8').split());o=' '.join(pathlib.Path('src/pathly_orchestrator/CLAUDE.md').read_text(encoding='utf-8').split());ok='task_checks' in r and 'Four of the five' not in r and 'is the one that **executes**' not in r and 'task_checks' in o and 'executes something.**' not in o;print('docs current' if ok else 'docs stale')"
exit 0
prints docs current
```

## Reference

- spec.md § Stories ("Checks the supervisor runs"), § Decisions ("When task checks run"),
  § Interfaces (`TASK_PROOF`)
- `src/pathly_orchestrator/fsm/gates/command.py`, `fsm/gates/tasks.py` (goal versus scope
  selection)
- `src/pathly_data/core/skills/team/build.md` (how the builder claims and completes, and the
  `INCOMPLETE_TASKS.md` step)
- root `CLAUDE.md` ("Ground truth" paragraph), `src/pathly_orchestrator/CLAUDE.md`
  ("Transition gates")

## Answer
