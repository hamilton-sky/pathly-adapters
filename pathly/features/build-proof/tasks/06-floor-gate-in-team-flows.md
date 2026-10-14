# Add the floor gate to the team and goal-loop flows

Type: task
Status: open
Blocked by: 02, 03, 04, 15
Test first: yes
Floor: allow skip

New gate type `floor_gate` in `src/pathly_orchestrator/fsm/gates/floor.py`, registered in the
`_CHECKS` dict in `fsm/gates/__init__.py`.

The base is the run-wide `proof_base` (`fsm/gates/_proof_record.read_proof_base`), stamped the
first time the run enters a state with an outgoing `floor_gate` and kept until DONE. Every floor
gate checks the whole diff since then (spec.md § Decisions, "The diff base for the floor
gate"). That is what covers builder fix rounds: they run inside REVIEWING, TESTING and RETRO,
and after the goal-loop drain, while the FSM stays in the state, and only the next
transition's gates see them.

`check_floor_gate(gate, storage_path, prev_state, next_state, flow, goal_id, feature_scope, board)`:

- Skip (`gate_skipped`) when `_proof.floor_enabled()` is false, when there is no `proof_base`,
  when its `tree` is `None`, or when the snapshot taken now is `None`.
- Tasks: `task_proof.tasks_claimed_since(board, feature_scope, goal_id, proof_base.started_at)`.
  The allow list is the union of their `floor_allow`. A task whose `claimed_text` differs from
  its `text` is a `task-edit` finding unless that task allows `task-edit`.
- `proof.floor.scan(root, proof_base.tree, now, allow=…, protected=[board_home(storage)],
  may_change=<stage_writes(storage, "builder")(path) or explained(path, windows since
  proof_base.started_at)>, config_commands=<verify.* settings>)`.
- Findings: `gate_failed(...)`. The reason starts "Floor guard: the diff weakens the bar instead
  of meeting it", lists each finding, and ends by saying how to fix it (undo the weakening and
  fix the cause). It also says that a human can allow a category for a claimed task through
  `POST /comms/tasks/floor-allow`, or turn the guard off with the `floor.enabled` setting (the
  only way out when no task was claimed).
- Append a `FLOOR_CHECKED {warnings}` event either way.

Flows, each at the place spec.md § Migration and compatibility gives (after the existing gates,
before the other new ones), with `FLOOR_FAILURES: builder` added to each flow's
`feedback_routing`:

- `src/pathly_data/core/flows/team.flow.yaml` and `team-build.flow.yaml`: add
  `{type: floor_gate, on_fail: FLOOR_FAILURES.md}` to `BUILDING->REVIEWING`,
  `REVIEWING->TESTING`, `TESTING->RETRO` and the wildcard `->DONE`. The `->DONE` entry covers an
  `INCOMPLETE_TASKS` builder fix round inside RETRO, which no other floor gate sees.
- `src/pathly_data/core/flows/goal-loop.flow.yaml`: add the same gate to `DRAINING->DONE`, after
  the two `command_gate` entries. A builder fix round after the drain (`BUILD_FAILURES`,
  `TEST_FAILURES` or `INCOMPLETE_TASKS` routed to `builder`) is a plain feedback spawn, not a
  `sched-<id>#<n>` task spawn, so the per-task proof never sees it. This gate does. It also sees
  a weakening that an earlier failed task attempt left in place, which the next attempt's own
  diff does not show. Update the comment above `gates:` in that file to name it.
- Update the expected goal-loop gate set in
  `tests/comms_board/test_comms_goals_run.py` (the `gate_types == {...}` assertion) to include
  `floor_gate`. The change of expectation is deliberate.

In `fsm_compose_responses._exit_requirement`, add a line for `floor_gate`: the diff is scanned
for weakened tests, silenced checks and plan edits; it is run, not self-reported.

Living docs: a `floor_gate` row wherever `src/pathly_orchestrator/CLAUDE.md` lists the gates,
which transitions carry it in each flow, the `floor.enabled` setting, and the goal-loop join. In
the root `CLAUDE.md` "Ground truth" paragraph, name `floor_gate` as a gate that measures the diff
instead of trusting the agent. Remove the gate count ("Four of the five") if it is still there,
so the paragraph stays true as other gates are added. Verify-then-fix: change only those claims.

The `Floor:` line above is needed because the tests write `@pytest.mark.skip` into a test file in
a temp repo.

## Not in this ticket

- `task_checks` and `scope_gate` in the same transitions: tickets 07 and 08.
- The per-task proof inside the goal-loop drain, which sends a failure back to the task that
  caused it: ticket 05.
- Adding the root-cause guide to the builder's feedback prompt: ticket 11.

## Done when

- `python -m pytest tests/fsm_flows/test_floor_gate.py -q -p no:cacheprovider` passes, driving
  `fsm_ops.next_action` and `complete_stage` in a `git init` project under `tmp_path`. It covers:
  - team-build: a builder diff with `@pytest.mark.skip` blocks BUILDING->REVIEWING with
    `FLOOR_FAILURES.md` routed to `builder`, and passes after a human sets `floor_allow`
    `["skip"]` on the claimed task;
  - team-build: an edit to `USER_STORIES.md` is a `plan-edit`, and the same edit is accepted
    when a planner `SPAWN_WINDOW` explains it;
  - team-build: a skip added in REVIEWING blocks REVIEWING->TESTING, and a skip added in RETRO
    (after TESTING->RETRO passed) blocks RETRO->DONE;
  - goal-loop: after a clean drain to the join, a skip written into the tree (as a builder fix
    round would) blocks DRAINING->DONE with `FLOOR_FAILURES.md` routed to `builder`, and the
    join passes once the skip is removed;
  - `floor.enabled` `false` skips the gate.
- `python -m pytest tests/fsm_flows tests/comms_board/test_comms_goals_run.py -q -p no:cacheprovider`
  passes (`test_two_flows.py` still finds the `verify_gate` first).
- The root `CLAUDE.md` names `floor_gate` and no longer counts the gates. The command below
  prints `docs current`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_floor_gate.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows tests/comms_board/test_comms_goals_run.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import pathlib;r=' '.join(pathlib.Path('CLAUDE.md').read_text(encoding='utf-8').split());print('docs current' if 'floor_gate' in r and 'Four of the five' not in r else 'docs stale')"
exit 0
prints docs current
```

## Reference

- spec.md § Decisions ("The diff base for the floor gate", "Telling an upstream role's legitimate plan
  edit from the builder's", "Floor gate in goal-loop"), § Happy path, § Edge cases
- `src/pathly_orchestrator/supervisor/orchestrator_stage.py::_resolve_stage_supervised` (the
  feedback spawn that runs fix rounds while the FSM stays in the state)
- `src/pathly_orchestrator/fsm/gates/__init__.py::run_gates` (the `->X` wildcard lists are
  appended to the edge's own list)
- `src/pathly_orchestrator/fsm/gates/command.py` (gate shape, `gate_failed`, `gate_skipped`)
- `tests/fsm_flows/test_command_gate.py`, `tests/fsm_flows/test_gates.py` (gate test setup)

## Answer
