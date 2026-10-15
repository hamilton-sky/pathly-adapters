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

Work started at commit `6699655ecb52741010ae5700b248a746a03bce3f`. Test-only commit: `5824678`
(`test(build-proof): 07 failing test`). At that commit `test_task_checks_gate.py` and
`test_task_checks_edges.py` give `21 failed, 1 passed`: the gate module is missing
(`ModuleNotFoundError: No module named 'pathly_orchestrator.fsm.gates.task_checks'`), the flows
carry no `task_checks` gate (`'task_checks' is not in list`, the goal-loop gate list), and every
scenario advances instead of blocking (`AssertionError: {... 'current_state': 'REVIEWING' ...}`
where the test wants `blocked`). The one pass is "goal-loop join passes when every task is proven
or passes", which the absent gate also satisfies.

**Built**

- `src/pathly_orchestrator/fsm/gates/task_checks.py` (new, 170 lines): `check_task_checks`.
  - Reads `_proof_record.read_proof_base`; none gives `GATE_SKIPPED` `no_proof_base`.
  - Tasks: `db.queries.task_proof.tasks_completed_since(get_db(), board, scope, goal_id,
    proof_base.started_at)` (lazy import, so a test can patch it); any exception (a base whose
    `started_at` is not a time included) gives `GATE_SKIPPED` `tasks_unreadable`. It then drops every
    task for which `_proof_record.task_proven` is true.
  - Per remaining task: `proof.checks.checks_in(claimed_text or text)`. A `ParseError` records
    `checks: "error"` with the report `The check block in this task cannot be read: <parser
    message>`; no block records `none`; otherwise `run_checks(checks, project_root_of(storage),
    command._resolve_timeout({}))` records `passed` or `failed`. Each result is written with
    `_proof_record.record_task_proof(storage, task, "gate:<prev>-><next>", result, "n/a")` (a failed
    write is logged, not raised).
  - Any `failed`/`error` task: `gate_failed` with `on_fail` and `extra {tasks, count}`. The file starts
    "Task checks: a completed task's check block failed.", says the supervisor ran each block "from
    the text the task had when it was claimed, so editing the task text now changes nothing", then has
    one `## Task <id>: <first line>` section per failing task (at most 8, each clipped head and tail
    to 4000 characters, then "... and N more failing tasks"), and ends with the action line (fix the
    code; a human can correct the text and `refreeze` through `POST /comms/tasks/floor-allow`).
- `src/pathly_orchestrator/fsm/gates/__init__.py`: import, `_CHECKS["task_checks"]`, and the module
  docstring's table row and its "only `command_gate` executes" sentence.
- `src/pathly_data/core/flows/team.flow.yaml` and `team-build.flow.yaml`: `task_checks` /
  `TASK_CHECK_FAILURES.md` right after `floor_gate` on `BUILDING->REVIEWING` (before `scope_gate`) and
  `REVIEWING->TESTING` (before `reviewer_unchanged`), and last on the wildcard `->DONE`;
  `TASK_CHECK_FAILURES: builder` in `feedback_routing`. `goal-loop.flow.yaml`: last gate of
  `DRAINING->DONE`, plus the routing line and a header comment. `feedback_priority` is untouched.
- `src/pathly_orchestrator/fsm_compose_responses.py`: a `task_checks` branch in `_exit_requirement`
  ("Each completed task's check block is run by the supervisor; a self-reported pass does not count.
  Complete a task only once its checks pass.").
- Living docs: root `CLAUDE.md` ("Ground truth" paragraph) and `src/pathly_orchestrator/CLAUDE.md`
  (see Decisions).
- Tests: `tests/fsm_flows/test_task_checks_gate.py` (8 tests, every Done-when case),
  `tests/fsm_flows/test_task_checks_edges.py` (14: flow wiring, exit requirement, report shape, re-runs,
  fail-open), `tests/fsm_flows/task_checks_support.py` (helpers), regenerated `tests/INDEX.md` and
  `tests/fsm_flows/INDEX.md`. Three existing tests changed on purpose (the test-only commit): the
  `->DONE` list and goal-loop gate list in `test_floor_gate.py` (ticket 06 said they would),
  `test_proof_base.py::test_no_base_is_stamped_without_a_floor_or_task_checks_gate` (it stripped
  `floor_gate` from the packaged flow; now strips `task_checks` too), and the goal-loop gate-type set in
  `tests/comms_board/test_comms_goals_run.py`.

**Proof** (each run fresh, after the last code edit; the venv from the operator note on PATH)

- `python -m pytest tests/fsm_flows/test_task_checks_gate.py -q -p no:cacheprovider`: `8 passed in
  11.47s`, exit 0. On a `git init` feature under `tmp_path`, through the real `next_action` and
  `complete_stage` over the packaged `team-build` and `goal-loop` flows, it covers:
  - a completed task whose check exits 1 blocks BUILDING->REVIEWING; `TASK_CHECK_FAILURES.md` holds
    `got: exit 1`, the output marker, the task id and "text the task had when it was claimed"; the
    result is `blocked`, `target_agent == "builder"`, `file == "TASK_CHECK_FAILURES.md"`; the
    `TASK_PROOF` is `failed` / `n/a` with run id `gate:BUILDING->REVIEWING`. The live `text` is then
    rewritten to a passing check (and `task-edit` allowed, so `floor_gate` lets it through): the
    gate blocks again with `got: exit 1`;
  - a failing task completed in REVIEWING (after BUILDING->REVIEWING passed with nothing to run)
    blocks REVIEWING->TESTING, and one completed in RETRO blocks RETRO->DONE (and then a human fix
    plus `refreeze` lets it reach `{"done": True}`, with proofs `["failed", "passed"]`);
  - a counting check (appends a character to a log outside the repo) passes at BUILDING->REVIEWING and
    the log still reads `x` after REVIEWING->TESTING; exactly one `TASK_PROOF` exists for it;
  - goal-loop DRAINING->DONE: a task with a passing `TASK_PROOF` for its current `claimed_at` is not
    run (its log is never created, one proof only), a task completed without a proof is run and
    blocks the join (`gate:DRAINING->DONE`);
  - no block records `checks: "none"` with the join passing; a malformed block fails with
    `str(ParseError)` in the file and `checks: "error"`; a task completed before `proof_base.started_at`
    is not run (no `TASK_PROOF`).
- `python -m pytest tests/fsm_flows tests/comms_board/test_comms_goals_run.py -q -p no:cacheprovider`:
  `690 passed, 9 skipped in 143.40s`, exit 0.
- The docs command printed `docs current`, exit 0.
- Mutation checks (not kept): reading `text` instead of `claimed_text` fails the frozen-text test;
  skipping the `task_proven` filter fails the "not run again" test and the goal-loop proven-task test.
- Beyond the Done when: Test (`python -m pytest tests/ -q -x -p no:cacheprovider`) `2787 passed, 14
  skipped in 463.53s`, exit 0. The Lint chain from `commands.md` run as one `&&` command: exit 0
  (black 535 files unchanged; mypy `no issues found in 297 source files`; file size `none new, none
  grown`; mirror reads OK; test INDEX up to date; lint-imports `1 kept, 0 broken`; bandit exit 0;
  adapters OK; entry points OK). Smoke exit 0. `python -m build --wheel` exit 0.

**Decisions**

- The ticket's `tasks_completed_since(board, feature_scope, goal_id, started_at)` has a `conn` first
  argument in the code (`tasks_completed_since(conn, board, scope, goal_id, since)`); the gate calls it
  with `get_db()`, `board or "feature"` and `feature_scope or ""`. With neither `goal_id` nor a scope the
  query returns `[]` and the gate passes.
- A base with no `tree` does not skip the gate (unlike `floor_gate`): task checks need `started_at`
  only, and `started_at` is set outside git too.
- One gate run records a `TASK_PROOF` for a task that fails and for one that passes, so the next join
  runs only what is not proven. A failed record stays unproven (`task_proven` is false for it), so a
  fix round that completes the task again, with no new claim, is run again.
- Failure text caps: 8 tasks, 4000 characters each. `run_checks` clips each failing check's output to
  8000 characters but has no cap on a whole report (ticket 01's note), and the feedback file ends up in
  a builder prompt, which is one argv string.
- `task_checks` sits after `floor_gate` and before `scope_gate` / `reviewer_unchanged` as spec.md §
  Migration gives. Because `floor_gate` runs first, a builder that edits a task's live text trips
  `task-edit` (FLOOR_FAILURES.md) before the checks run; the test reaches the gate by allowing
  `task-edit` for that task.
- Docs. Root `CLAUDE.md`: "Four of the five" was already gone (ticket 06 reworded the paragraph), so
  only `command_gate ... is the one that **executes**` was stale; it now says `command_gate`
  "**executes**" and a new `task_checks` sentence says it also executes (frozen text, same runner,
  once per completion, where wired). `src/pathly_orchestrator/CLAUDE.md`: the `task_checks` table row,
  the "first four read state ...; `command_gate` and `task_checks` execute something" sentence, a "Task
  checks gate" section after the Floor gate section, and the places the new gate made false: "no gate
  does yet" (twice: the `*_since` reads, the check-block paragraph), "no flow declares a `task_checks`
  gate yet / the only writer of `TASK_PROOF`", the Review packet's "nothing writes them yet", the drain
  section's "(planned)", and the gate lists in the architecture diagram and the Phase E flow excerpt.

**Shortcuts taken**

- `task_proven` is called once per candidate task and reads the whole event log each time (ticket 15's
  note). Fine for tens of tasks; it stops being cheap for hundreds of tasks and thousands of events. Worth
  upgrading (one read per gate run, or a `TASK_PROOF`-only query) if the gate shows up in a profile.
- `_run_checks_of` (parse, none, run) and `_clip` copy the shape of `supervisor/task_proof.py`'s
  `_run_task_checks` and `_clip`, because `fsm/gates` must not import `supervisor`. A third caller would
  be the time to move them into `proof/checks.py`.
- The checks run one task after another in the gate's own process, in the project root, with the
  server's account and no extra environment (`command_gate` sets `PATHLY_VERIFY_GATE=1`; `run_checks`
  has no `extra_env`). A join with many tasks and slow checks holds the `complete_stage` call for the
  sum of their times (each command is bounded by `verify.timeout_seconds`).
- A passing run appends no event of its own beyond each `TASK_PROOF`; there is no `GATE_PASSED` for the
  gate and no record that it ran when there was nothing to run.

**For later tickets**

- Ticket 14 (acceptance): the checks run in the project root before `scope_gate` on
  BUILDING->REVIEWING and before the next `floor_gate` scan, so a check that writes into the repo (a
  build output, a log, a cache that the project's `.gitignore` does not cover) shows up as the
  builder's change. Keep scripted check commands read-only, or write outside the repo as the tests do.
  `fsm_ops` stamps the proof base on the first `next_action` of BUILDING, so a task claimed and
  completed before that is outside the window.
- `tests/fsm_flows/task_checks_support.py` has the helpers (`red`/`green`/`counting` task texts,
  `drained_goal_loop`, `to_retro`, `claim_again`, `blocked`); import `flow`, `repo` from it as the other
  support module does.
- `src/pathly_orchestrator/CLAUDE.md`: its one-line `fsm/gates/` module list under "Modules split
  under the 400-line ratchet" (`artifact` · `tasks` · `scope` · `command`) predates tickets 06 to 09 and
  does not name `floor`, `reviewer` or `task_checks`; I left that line alone.

## Review findings (round 1, quality review)

QUALITY
1. major src/pathly_orchestrator/fsm/gates/task_checks.py: `_clip`, `_CLIPPED` and `_run_checks_of` are verbatim copies of `_clip`, `_CLIPPED` and `_run_task_checks` in `src/pathly_orchestrator/supervisor/task_proof.py` (lines ~52, ~236-241 and ~220-231). The "cannot be read" message and the `checks_in(claimed_text or text)` / `run_checks(..., _resolve_timeout({}))` logic are copied too. Root CLAUDE.md rule 5 says "Never duplicate a helper across files". The two copies must agree, because the join relies on the drain's proof and its own proof meaning the same thing for `task_proven`. Fix any change to one (fallback to `text`, timeout, error wording) by hand in the other, or the two will diverge. - Keep one copy. `supervisor/task_proof.py` already lazily imports from `fsm.gates`, so it can call the gate module's runner. Alternatively move a `run_task_checks(task, cwd, timeout)` into `proof/checks.py` and a head-and-tail clip into `proof/command.py` (next to `clip`) and use them from both places. Delete the copies.
2. minor src/pathly_orchestrator/fsm/gates/task_checks.py: `_failure_text` always says "make each failing check pass by fixing the code". For an `error` result (an unparsable block in the frozen text) the builder cannot do that, and only a human re-freeze helps. - Give the unparsable-block case its own action line that sends the builder to ask for a human.
3. minor src/pathly_orchestrator/fsm/gates/task_checks.py: `_proof_record.task_proven` reads the whole event log once per completed task, so the cost is tasks times events at every join. The new doc admits this. - Read the events once per gate run and test membership in memory, or add a batch helper to `_proof_record`.

Notes
- The last commit touching the ticket is 454ac2c, which is `HEAD`. There are no later commits that I skipped.
- I did not read the ticket's `## Answer`. I read the ticket at 6699655 and the diff with `pathly/features/build-proof/tasks/` excluded.
- Done when, re-run with the dev venv:
  - `tests/fsm_flows/test_task_checks_gate.py` and `test_task_checks_edges.py`: 22 passed.
  - `tests/fsm_flows` plus `tests/comms_board/test_comms_goals_run.py`: 690 passed, 9 skipped.
  - The docs command printed `docs current`.
- Extra checks:
  - `check_file_size.py` reported no new or grown oversized file.
  - `gen_test_index.py --check` reported the indexes up to date.
  - `lint-imports` reported the contracts kept.
  - mypy was clean on `task_checks.py`.
  - `ruff format --check` was clean on the new files.
- The edits to existing tests (`test_floor_gate.py`, `test_proof_base.py`, `test_comms_goals_run.py`) only follow the deliberate gate-set and ordering change. No check was weakened.
- I left no files behind.

REVIEW: FAIL
