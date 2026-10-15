# Add the floor gate to the team and goal-loop flows

Type: task
Status: resolved
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

Work started at commit `545d48b8a251caf6dd8ce59ffce47dd4ee275138`. Test-only commit: `40da70b`
(`test(build-proof): 06 failing test`, the new test file plus the regenerated `tests/INDEX.md` and
`tests/fsm_flows/INDEX.md`). At that commit
`python -m pytest tests/fsm_flows/test_floor_gate.py -q -p no:cacheprovider` gave `18 failed, 2
passed` (exit 1): no `pathly_orchestrator.fsm.gates.floor` module, no `floor_gate` in any flow, no
`proof_base` in STATE, no `FLOOR_FAILURES` block. The two that passed are the accept-side
counterparts that pass when no gate exists (a planner window explains a plan edit; a human allow
list covers the whole run); the mutation checks below show they fail when the gate is broken.

**Built**

- `src/pathly_orchestrator/fsm/gates/floor.py` (new, 239 lines): `check_floor_gate`. Reads
  `_proof_record.read_proof_base`, the tasks claimed since `started_at`
  (`task_proof.tasks_claimed_since`), snapshots the tree now and runs `proof.floor.scan(root,
  base.tree, now, allow=<union of the tasks' floor_allow>, protected=[board_home(storage)],
  may_change=<builder stage_writes, else _proof.explained over the windows since the base>,
  config_commands=<verify.build/test/lint/smoke>)`. A claimed task whose `claimed_text` differs
  from `text` adds a `task-edit` finding unless that task allows it. Findings go through
  `gate_failed` with `FLOOR_FAILURES.md` ("Floor guard: the diff weakens the bar instead of meeting
  it", each finding, the human routes `POST /comms/tasks/floor-allow` and `floor.enabled`, and a
  closing "undo each change and fix the cause"). `FLOOR_CHECKED {warnings}` is appended whenever a
  scan ran, pass or fail.
- `src/pathly_orchestrator/fsm/gates/__init__.py`: `floor_gate` in `_CHECKS`, plus a row in the
  module docstring table.
- `src/pathly_data/core/flows/team.flow.yaml`, `team-build.flow.yaml`: `floor_gate` (`on_fail:
  FLOOR_FAILURES.md`) on `BUILDING->REVIEWING` (after `command_gate`, before `scope_gate`, which
  stays last), `REVIEWING->TESTING` (before `reviewer_unchanged`, which stays last), `TESTING->RETRO`
  and the wildcard `->DONE`; `FLOOR_FAILURES: builder` in `feedback_routing`.
- `src/pathly_data/core/flows/goal-loop.flow.yaml`: `floor_gate` after the two `command_gate`s of
  `DRAINING->DONE`, `FLOOR_FAILURES: builder`, and the comment above `gates:` names it.
- `src/pathly_orchestrator/fsm_compose_responses.py`: `_exit_requirement` line for `floor_gate`
  ("scanned for weakened tests, silenced checks and plan edits: it is run, not self-reported").
- Living docs: root `CLAUDE.md` (a `floor_gate` sentence in the Ground truth paragraph; the "Four of
  the five" count was already gone, `grep` finds no hit); `src/pathly_orchestrator/CLAUDE.md` (gate
  table row, the join diagram, the Phase E flow snippet, a new "Floor gate" section with the
  transitions per flow, the `floor.enabled` setting and the goal-loop join, and the sentences that
  said no gate called the scan or declared `floor_gate`).
- Tests: `tests/fsm_flows/test_floor_gate.py` (new, 20 tests); `tests/comms_board/
  test_comms_goals_run.py` (the goal-loop `gate_types` set now includes `floor_gate`, as the ticket
  says); three existing tests whose premise the packaged flows changed (see Decisions);
  `tests/fsm_flows/review_packet_support.py` gained `_as(repo, flow, role, state, work)`.

**Proof** (each run fresh, after the last code edit)

- `python -m pytest tests/fsm_flows/test_floor_gate.py -q -p no:cacheprovider`: `20 passed in
  15.23s`, exit 0. It drives `next_action` and `complete_stage` over the packaged flows in a `git
  init` project: team-build skip blocks BUILDING->REVIEWING with `FLOOR_FAILURES.md` to `builder`
  and passes after `set_floor_allow(..., ["skip"])`; an edit to `USER_STORIES.md` is a `plan-edit`,
  is accepted when a planner `SPAWN_WINDOW` explains it, and a builder edit after the planner is
  still blamed; a skip added in REVIEWING blocks REVIEWING->TESTING and a skip added in RETRO
  (after TESTING->RETRO passed) blocks RETRO->DONE, then passes to `{"done": True}` once removed;
  goal-loop after a clean drain blocks DRAINING->DONE on a skip and returns `{"done": True}` once
  it is removed; `floor.enabled` `false` skips (`GATE_SKIPPED floor_disabled`); also a clean build
  passes and records `FLOOR_CHECKED`, a changed task text is a `task-edit` (cleared by allowing
  it), no `proof_base` and a base without a tree skip, and the flows carry the gate on the right
  edges in the right order.
- `python -m pytest tests/fsm_flows tests/comms_board/test_comms_goals_run.py -q -p no:cacheprovider`:
  `668 passed, 9 skipped in 125.95s`, exit 0 (the skips are older tests; `test_two_flows.py` still
  finds the `verify_gate` first).
- The docs command printed `docs current`, exit 0.
- Mutation checks on `floor.py`: replacing the `_proof.explained` call with `False` fails
  `test_a_plan_edit_by_a_planner_spawn_is_accepted`, `test_a_skip_added_in_retro_blocks_retro_to_done`
  (REVIEW.md) and `test_a_claimed_tasks_allow_list_covers_the_whole_run`; replacing the allow
  union with `frozenset()` fails `test_a_skip_blocks_building_and_passes_once_a_human_allows_it` and
  the allow-list test. The file was restored (diffed identical).
- Beyond the Done when: Test (`python -m pytest tests/ -q -x -p no:cacheprovider`) `2765 passed,
  14 skipped in 459.58s`, exit 0. Lint chain, each link run: `black --check src/ tests/` (531 files
  unchanged), `mypy` (no issues in 296 files), `check_file_size.py` (none new, none grown),
  `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (1 kept, 0 broken),
  `bandit -q -r src/ -ll -x src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`: all
  exit 0. Smoke and `python -m build --wheel` exit 0.

**Decisions**

- The gate is exactly the ticket's `may_change`: `stage_writes(storage, "builder")(path)` or
  `_proof.explained(...)`. The windows are read once, lazily on the first protected path that needs
  them (a clean run reads none). If `windows_since` raises, a path some role may write
  (`_proof.any_role_writes`) is excused and `FLOOR_CHECKED` gets a "spawn windows unreadable"
  warning; a path no role may write still counts. That is `scope_gate`'s fail-open rule.
- Skip reasons (all `GATE_SKIPPED`): `floor_disabled`, `no_proof_base`, `no_snapshot` (base tree is
  `None`), `snapshot_failed` (snapshot now is `None`), `tasks_unreadable` (DB error or an unparsable
  `started_at`), `scan_failed` (an unexpected exception, logged), and `scan_incomplete` when
  `FloorReport.error` is set and nothing was found (the warning stays in `FLOOR_CHECKED`), as ticket
  02's handoff asked. Findings are real even when `error` is set, so they still fail.
- The allow list is the union over the claimed tasks; `task-edit` is judged per task. A claimed
  task with `claimed_text` `NULL` (claimed before this feature) is not a `task-edit`.
- `config_commands` reads `verify.build`, `verify.test`, `verify.lint` and `verify.smoke`. The
  ticket said "the verify.* settings"; `lint` is documented as a key.
- `FLOOR_FAILURES` is in `feedback_routing` only. `feedback_priority` is untouched (a test pins its
  exact list for `team`, ticket 09's learning), so the file ranks after every listed file; no
  `escalation_routing` entry, so it stays with the builder.
- Three existing tests changed, each because the packaged flows now hold a `floor_gate`, not to
  loosen anything: `test_proof_base.py::test_no_base_is_stamped_without_a_floor_or_task_checks_gate`
  now strips `floor_gate` from the loaded flow first (it still asserts no base is stamped);
  `test_review_base_state.py::test_leaving_another_state_keeps_the_review_base` and
  `test_review_packet.py::test_the_diff_leaves_out_everything_under_pathly` wrote `REVIEW.md` and
  `IMPLEMENTATION_PLAN.md` raw, which the gate rightly reads as a plan edit, so they now write them
  inside a `reviewer` / `planner` spawn window (`review_packet_support._as`), as a headless run does.
  Their assertions are unchanged. `test_proof_base.py`'s `floored` / `goal_loop` fixtures now append
  a second `floor_gate` to a flow that already has one; harmless for what they assert.

**Shortcuts taken**

- An interactive `/pathly` run records no `SPAWN_WINDOW`, but `next_action` still stamps
  `proof_base`, so `floor_gate` runs there and a plan file another role wrote (the reviewer's
  `REVIEW.md`, a retro document) is not explained and reads as a builder `plan-edit` that loops
  (the old `test_leaving_another_state_keeps_the_review_base` showed it: the gate blocked
  REVIEWING->TESTING). It stops working for any interactive team run; the way out is `floor.enabled`
  `false`, written in `src/pathly_orchestrator/CLAUDE.md` ("Floor gate", Limits). I kept the
  ticket's `may_change` literally. Making a run with no window at all skip the plan-edit judgement
  (as `scope_gate` does for a dirty baseline path) would fix it, but it would also stop judging the
  goal-loop join when the drain recorded no window (a fan-out drain records none, only the feedback
  spawns do), which the spec wants judged. A human should decide, or ticket 14 / a follow-up can
  stamp a "supervised" flag in STATE that `next_action` has when the supervisor drives it.
- `_proof.explained` is not memoized across paths; it costs a few git processes per protected
  changed path per window of a role that may write it. Fine for a handful of plan files; worth a
  per-gate blob cache if a run changes dozens of plan files.
- The gate catches broad `Exception` around the scan and the DB reads (each logged with a
  traceback and turned into a `GATE_SKIPPED` or a warning), never an empty catch.
- A test edit made by the tester in TESTING that trips the floor is sent to the builder, who did
  not make it, as the spec's Risks accept.

**For later tickets**

- Ticket 07 (`task_checks`): put it after `floor_gate` and before `scope_gate` on
  `BUILDING->REVIEWING`, after `floor_gate` and before `reviewer_unchanged` on
  `REVIEWING->TESTING`, after `floor_gate` in `->DONE` and after `floor_gate` in goal-loop's
  `DRAINING->DONE`; `test_floor_gate.py::test_the_team_flows_carry_the_gate_on_every_edge_out_of_a_stage`
  pins `->DONE` as exactly `[require_tasks_done, floor_gate]`, and
  `test_goal_loop_carries_the_gate_after_the_command_gates` pins goal-loop's four gates, so both
  change deliberately then. The "Proof base" paragraph in `src/pathly_orchestrator/CLAUDE.md` says
  no flow declares `task_checks` yet; edit that when 07 lands. Its `TASK_PROOF` writer for the team
  flows is 07's.
- Ticket 14 (acceptance through `supervisor.start_run`): the supervisor records the builder,
  reviewer and feedback-spawn windows, so a scripted reviewer that writes `REVIEW.md` and a scripted
  planner that edits `IMPLEMENTATION_PLAN.md` are explained; a scripted builder that edits the plan
  is a `plan-edit` and a builder that adds `@pytest.mark.skip` needs `FLOOR_FAILURES.md` to reach
  the builder. Any test that writes `REVIEW.md` or a plan file raw and then calls `complete_stage`
  on a packaged team flow in a git repo is now blocked; use `review_packet_support._as`.
- Every gate run takes a working-tree snapshot (`git add -A` on an index copy), at four edges per
  team run.
