# Bind chief calls that name a run, goal, task or message by id to the chief's project

Type: task
Status: resolved
Blocked by: 08
Test first: yes

Ticket 08 binds the chief to its project through what a request names as a place: `project_root`,
a board scope, and a file, flow, skill or folder name (`ROUTE_FIELDS`, applied by
`chief_project.project_refusal`). Several calls name their target by id and carry none of these;
`chief_field_calls.py` lists those ids as `unbound`. A chief could therefore pause, abort or
answer a run, or acknowledge, supersede, run or stop a message, goal or task, in another project:

- `/runs/<run_id>/stop` and `/runs/<run_id>/<action>` (`run_id`);
- `/comms/acknowledge` (`message_id`), `/comms/answer` (`question_id`), `/comms/supersede`
  (`old_id` and `new_id`);
- `/comms/goals/run`, `/comms/goals/stop`, `/comms/goals/decompose` and `POST /runs` with
  `kind=goal` (`goal_id`); `/comms/tasks/run` and `/comms/tasks/stop` (`message_id`); and the
  `goal_id` and `run_id` that a `/comms/post` row carries;
- `/runner/agent-answer` (`topic`), which ticket 10 already checks through
  `RunnerState.project_root`.

Add `src/pathly_orchestrator/http_server/chief_bind.py::target_in_project(conn, session, rule,
body, view_args) -> bool | None`, called from `chief_gate` after the action check, for chief
tokens only. It returns True (allow), False (403 `{"error": "not in this chief's project"}`) or
None (the route did not name such a target):

- A run id (`request.view_args["run_id"]`): the run's `project_root` from `run_history`
  (`db/queries/run_history_read`), else from a live `RunnerState` or registry entry for it.
  When neither knows the run, refuse: the chief never acts on a run it cannot place.
- A message id (a goal and a task are `comms_messages` rows too, so `goal_id`, a task's
  `message_id`, `question_id`, `old_id` and `new_id` all use this rule; a goal row is the one
  `db/queries/comms_goal_fields.get_goal_board_scope` reads, and the decomposer later reads the
  `scope` of that row, which no sink guards): the `comms_messages` row's `board` and `scope`. A
  `project` row must have the session's project scope
  (`fsm_compose.resolve_board_scope("project", project_root, "")`). A `feature` row is in the
  project when a directory of that name exists under `<project_root>/pathly/features/` or
  `pathly/features/.archive/` (feature scopes are names, not paths; say so in the docstring). A
  `global` row is refused for every write. An unknown id passes, and the route answers 404.

Imports stay lazy. Static SQL only.

Take every id this ticket binds out of `unbound` in `chief_field_calls.py` and say in
`chief_field_types.py` (the `unbound` paragraph) that what is left there is a read or a feature
name. Keep `chief_bind` and `ROUTE_FIELDS` consistent: `test_chief_gate_tables.py` stays green.

Living docs: one sentence in the "Chief gate" paragraph of `src/pathly_orchestrator/CLAUDE.md`.

## Not in this ticket

- Binding non-chief callers: unchanged.
- Making feature scopes unique across projects: out of scope; the directory check is the best
  this ticket can do with name-keyed feature boards.

## Done when

- `python -m pytest tests/http_api/test_chief_bind.py -q -p no:cacheprovider` passes and covers,
  with two projects in temporary directories and an operator chief on project A: `POST
  /runs/<id>/pause` on a run recorded for project B is 403 and on one for project A passes the
  gate; an unknown run id is 403; `/comms/acknowledge` on a project-B project-board row is 403,
  on a project-A row passes, on a feature row whose feature directory exists only in B is 403,
  and on a global row is 403; `/comms/supersede` with an `old_id` in B is 403; an unknown message
  id gets 404 from the route; `/comms/goals/run`, `/comms/goals/stop` and `/comms/goals/decompose`
  with a `goal_id` of a project-B goal are 403 and pass for a project-A goal; so do `POST /runs`
  with `kind=goal`, `/comms/tasks/run` and `/comms/tasks/stop` (a task `message_id`) and a
  `/comms/post` that carries the `goal_id` of a project-B goal; a builder token and no token are
  unaffected.

```check
$ python -m pytest tests/http_api/test_chief_bind.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- ticket 08 (the gate and its route table), spec.md § Edge cases
- `src/pathly_orchestrator/http_server/blueprints/control/runs_read.py`,
  `runs_control.py`, `db/queries/run_history_read.py`
- `src/pathly_orchestrator/fsm_compose_paths.py::resolve_board_scope`

## Answer

**Built**

- `http_server/chief_bind.py` (new, 142 lines): `target_in_project(conn, session, rule, body, view_args) -> bool | None`, called by `chief_gate._refusal` for a chief token on a POST, after `project_refusal` and the action check and before the `/comms/post` sender check; False answers 403 `{"error": "not in this chief's project"}` with the action, tier and allowed list like every gate refusal. It reads the ids from the route's `ROUTE_FIELDS` entry and returns True when every id is in the session's project, False when any is not, None when the route names none. A URL variable is read from `view_args` only, a body key never stands in for it. The module docstring states the rules (below) and that a feature scope is a name, not a path. `is_id(value)` is the shared "can be looked up" test: a string, not blank, at most 512 characters, no control character (`Cc`) or lone surrogate (`Cs`).
- `db/queries/placement.py` (new, 33 lines, static SQL, two statements): `run_project_root(conn, run_id)` (`run_history.project_root`) and `message_board_scope(conn, message_id)` (`board`, `scope` of the `comms_messages` row, deleted rows included). The imports of `db`, `supervisor.board_lock` and `blueprints.control._helpers.find_registry_run` are inside the functions of `chief_bind`.
- Run placement (`/runs/<run_id>/stop` and `/runs/<run_id>/<action>`): `run_history.project_root`, else the `project_root` of a registry entry of any status (`find_registry_run(run_id, statuses=None)`), else the board its board lock is held on (a board, single or loop run is not in `run_history` until its first spawn); the first source that knows the run decides, and a run none of them knows is refused.
- Message placement (`/comms/acknowledge`, both ids of `/comms/supersede`, `question_id` of `/comms/answer`, `goal_id` of `/comms/goals/run|stop|decompose`, `POST /runs` and `POST /comms/post`, the task `message_id` of `/comms/tasks/run|stop`): a `project` row is the chief's when its scope spells the session's root (`chief_project.is_own`, the rule a posted scope gets); a `feature` row when its scope is one plain folder name (`is_segment`, not `.archive`) and a folder of that name exists under `<root>/pathly/features/` or `<root>/pathly/features/.archive/`; a `global` row and any other board never. An id no row has passes and the route answers it. The `run_id` that a `/comms/post` row carries is only a correlation stamp: a run placed in another project is refused and a run no source knows passes.
- `http_server/chief_field_types.py`: `Fields` gained `run_ids`, `stamped_run_ids` and `row_ids` (all ID kind, so the key lists and the key-walk tests still hold them); the `unbound` paragraph now says what is left there. `http_server/chief_field_calls.py`: every bound id moved out of `unbound` into the right tuple (`/runs/<run_id>/<action>` and `/runs/<run_id>/stop` -> `run_ids`; `/comms/post` -> `row_ids=("goal_id",)` and `stamped_run_ids=("run_id",)`; `/comms/acknowledge`, `/comms/tasks/run`, `/comms/tasks/stop` -> `row_ids=("message_id",)`; `/comms/supersede` -> `old_id`, `new_id`; `/comms/goals/run|stop|decompose` and `/runs` -> `goal_id`; `/comms/answer` -> `question_id`, with `option_id` staying unbound because the cite rule refuses it to a chief). `/runner/agent-answer` keeps `unbound=("topic",)`: ticket 10's cite rule already places it through `RunnerState.project_root`. `chief_fields.py` and `chief_gate.py` docstrings name the new step.
- `chief_gate._human_escalation_check` and `chief_cite.cite_refusal` use `is_id` (see Decisions: two existing 500s).
- Living docs: `src/pathly_orchestrator/CLAUDE.md` (module list entries for `chief_bind.py` and `placement.py`; a new "Ids" bullet in the "Chief gate" paragraph; "Not bound" and "Not here yet" rewritten to what is really left; the `goal_decomposer` sentence and the cite spend sentences updated).
- Tests (all in `tests/http_api/`): `test_chief_bind.py` (294 lines, 55 tests: the Done-when cases), `test_chief_bind_edges.py` (331, 154: placement sources, odd feature scopes, deleted and padded ids, an answer to a foreign question, post stamps, malformed ids), `test_chief_bind_contract.py` (119, 4: the tri-state contract, a session with no usable root, a registry entry with no root, the table pin), `chief_bind_support.py` (136, helpers and an autouse fixture that frees the board locks). Eight existing test files got setup lines only (a folder for feature `demo` in the chief's project, a `run_history` row for the run `x`, `project_root` on a registry stand-in): `chief_cite_support.py`, `test_chief_cited_answers.py`, `test_chief_cited_edges.py`, `test_chief_cited_escalations.py`, `test_chief_gate.py`, `test_chief_gate_actions.py`, `test_chief_gate_flow_skill.py`, `test_chief_gate_root_naming.py`; no assertion in them changed. `tests/INDEX.md` and `tests/http_api/INDEX.md` regenerated.

**Proof** (Python 3.12.3 venv unless stated; all run on the tree that was committed, except that two test files had a comment moved afterwards and were re-run on their own, noted below)

- Test first: commit `3472c14` holds only test files. Run against the base source (a throwaway `git worktree` at `3472c14` with `PYTHONPATH=<worktree>/src`, `pathly_orchestrator.__file__` printed from the worktree): `python -m pytest tests/http_api/test_chief_bind.py -q -p no:cacheprovider` -> `31 failed, 24 passed`, exit 1; with `test_chief_bind_edges.py` too -> `91 failed, 120 passed`. The failures are assertions (the gate answered 200 where it should refuse, 200 where a 4xx was expected); none is an import or collection error. The passes are the controls (a run or row of the chief's own project, builder and no-token callers). At that commit the contract tests were still in the edges file; they moved to `test_chief_bind_contract.py` when it reached 399 lines. The worktree was removed.
- Done when, `python -m pytest tests/http_api/test_chief_bind.py -q -p no:cacheprovider`: `55 passed in 14.80s`, exit 0. All three bind files: `213 passed in 51.64s`. The Done-when cases it covers: pause on a B run 403 / on an A run passes the gate (all seven verbs: pause, resume, advance, reroute, retry, abort, stop), an unknown run 403, a finished run, the action check first; acknowledge on a B project row 403, A row passes, a feature row whose folder exists only in B 403, a feature row with the folder in A passes, a global row 403; supersede with a B `old_id` or a B `new_id` 403, an unknown id 404 from the route; `/comms/goals/run|stop|decompose`, `POST /runs` `kind=goal` and `/comms/tasks/run|stop` with a B id 403 and nothing started, and with an A id passing the gate and answered 200 by the route, a goal under a feature folder of A or only of B; a `/comms/post` with a B `goal_id` 403 and nothing stored; builder token and no token unaffected.
- `python -m pytest tests/http_api -q -p no:cacheprovider`: `1970 passed in 572.04s (0:09:32)`, exit 0. (This is the `http_api` part of `commands.md` Test.)
- `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/consistency -q -p no:cacheprovider`: `1619 passed, 2 skipped in 275.97s`, exit 0 (the other three Test domains plus `consistency`; the 2 skips are not mine and no skip was added). I did not run `commands.md` Test as the one `-x` command; these two runs cover the same four domains.
- After the last edit to `test_chief_gate.py` and `test_chief_gate_flow_skill.py` (a comment moved above its line, found after the runs above): `python -m pytest tests/http_api/test_chief_gate.py tests/http_api/test_chief_gate_flow_skill.py tests/http_api/test_chief_bind_contract.py -q -p no:cacheprovider` -> `135 passed in 31.40s`, exit 0.
- Python 3.13.16 (`venv313`, repo editable install): `python -m pytest tests/http_api/test_chief_*.py -q -p no:cacheprovider` (the three bind files, the changed cite and gate files, and the audit, separator, tables and keys tests) -> `1815 passed in 578.47s`, exit 0.
- Smoke (`commands.md`): exit 0. Build `python -m build --wheel`: exit 0 (`pathly_adapters-2.24.1-py3-none-any.whl`). Lint, the whole `&&` chain as one command: exit 0 (`black --check src/ tests/` 654 files unchanged, `mypy` no issues in 338 source files, `check_file_size.py` `OK: 1033 source files checked; 18 known over 400 lines, none new, none grown.`, `check_no_mirror_reads.py` OK, `gen_test_index.py --check` up to date, `lint-imports` 1 kept 0 broken, `bandit -q -r src/ -ll -x src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`). `git diff` adds no `noqa`, `nosec`, skip or xfail.
- Mutation check (a scratch script, every edit reverted in `finally`, `git status` afterwards listed only the intended files, and the runs above are on the restored code): 34 mutations. Placement: acted run always allowed, stamped run always allowed, history / registry / board lock ignored, history-vs-registry order, registry entry without `project_root`, project row always allowed, feature name rule dropped, `.archive` scope allowed, archive folder ignored, live folder ignored, global row allowed, unknown message refused, deleted row treated as unknown, a session with no root binds nothing, blank id read as malformed, `is_id` always true, body standing in for the URL variable. Table, each bound family put back to `unbound`: run stop, run verbs, goal run, goal stop, goal decompose, `POST /runs` goal, task run, task stop, acknowledge, supersede `old_id`, supersede `new_id`, answer `question_id`, post `goal_id`, post `run_id`. Gate and cite: the gate not calling `target_in_project`, `_human_escalation_check` without `is_id`, the cite rule's `topic` without `is_id`. First pass: 32 KILLED, 1 SURVIVED, 1 harness error. The survivor was removing `if own is None: return False` from `_in_project` (the tests only gave a session with no root a project row, so the guard never ran; with a feature row it would have been `os.path.join(None, ...)`, a 500): `test_a_session_with_no_usable_root_is_bound_to_nothing` now also asks about a feature row. The harness error was my own edit for "answer `question_id` unbound" repeating the `unbound` keyword (a SyntaxError that pytest reports as an ERROR, not a kill): rewritten. Both re-run: KILLED (`test_chief_bind_contract.py::test_a_session_with_no_usable_root_is_bound_to_nothing`, `test_chief_bind_edges.py::test_an_answer_to_a_question_of_another_project_is_refused`).
- Floor guard, after the feature commit: `FLOW_DIR=pathly/features FLOW_TICKETS=tasks python3 scripts/floor-guard.py chief-agent 14 53be531ed4821a77e8eda8f31d242686a57db893` printed `floor guard: clean`, exit 0. `python -m pytest tests/http_api/test_chief_bind.py -q -p no:cacheprovider` run once more on the committed tree: `55 passed in 14.09s`, exit 0.

**Decisions**

- The ids live in the table, not in `chief_bind`: `Fields.run_ids`, `stamped_run_ids` and `row_ids` are ID-kind keys, so `ROUTE_FIELDS` stays the inventory, the key allowlist is not weakened, the key-walk tests still require a view to read every listed key, and `test_chief_gate_tables.py` needed no edit. `test_chief_bind_contract.py` pins the exact bound set and the two POST keys left in `unbound`.
- A run is placed from three sources, history first; a run only a board lock knows (a board, single or loop run before its first spawn) is placed by its board with the message rule, which keeps "stop a board run" reachable for a chief of that project.
- The `/comms/post` `run_id` is a stamp, so an unknown id passes: the chief's own session run id is placed by none of the three sources (checked with a minted chief token), so refusing unknown ids would stop a chief stamping its posts with its own run. A run placed in another project is refused, because the row would be stamped with it.
- A `project` row is placed with `is_own(scope, root)` (the `root_spelling` rule `chief_project` applies to posted scopes), not by comparing with the string `resolve_board_scope` returns, so one spelling rule binds both a scope the chief names and one a row holds (a trailing slash is the same project).
- A feature scope must be one plain folder name: `../proj-b`, `a/b`, `.`, `..`, `.archive`, `demo\x`, `C:` and the empty scope are refused even when a folder they name exists (the tests create those folders so only the name rule can refuse). The project's own root as a feature scope is refused too.
- `goal_id` on `POST /runs` is bound whenever the body carries it, not only for `kind=goal` (a foreign goal id is never a chief's business).
- A malformed id (not a string, over 512 characters, a control character, a lone surrogate) is 403 from the gate, never a 500; a blank or null id names nothing and the route answers its own 400. This also fixed two 500s that existed before: `chief_gate._human_escalation_check` with a lone-surrogate `message_id`, and a lone-surrogate `topic` on `/runner/agent-answer`, which crashed `record_citation` and spent the citation; the cite rule now leaves a target it cannot look up to the route and spends nothing (tests in the edges file).
- The ticket's `topic` bullet adds no new binding: ticket 10 places it through `RunnerState.project_root`, and the `unbound` entry stays with a comment saying so.
- `messages_crud.py` (398 lines), the reads' `unbound` entries and `commands.md` are untouched.

**Shortcuts taken**

- The feature check is by folder name: two projects that both have a feature `demo` share the board, so a chief of either reaches the other's rows on it. The ticket leaves this out; the docstring, the CLAUDE.md "Ids" bullet and learnings (14) say so.
- The gate reads the placement once; the route reads again. A run that finishes or a row that is superseded in between keeps its project, so the verdict holds, but nothing locks across the two.
- A registry entry that has no `project_root` (a test stand-in) is not placed and the run is refused, via `getattr(..., None)`.
- `target_in_project` is POST only; the id-addressed reads stay unbound (no ticket yet).

**For later tickets**

- Ticket 15 (`max_cost_usd` on `POST /runs`): the `/runs` entry is now `Fields(roots=..., scopes=..., flows=("flow",), row_ids=("goal_id",), keys={"kind": ENUM, **_ENGINE})`, so a new key goes into `keys`.
- Ticket 16 (binding rows): `/comms/supersede` now refuses a chief's foreign `old_id` or `new_id`; refusing a binding row for everyone but a chief is still the route's job and is unchanged here.
- Binding the id-addressed reads (`GET /runs/<id>`, `/db/runs/<id>/cost`, `/comms/artifacts?message_id=`, `/comms/tasks?goal_id=`, `/runner/status`) needs `run_ids` / `row_ids` on the `chief_field_reads` entries and the `method != "GET"` guard dropped in `chief_gate._refusal`; `placement.py` and `chief_bind._placed_run` need no change. See learnings (14).
- Unique feature scopes across projects would turn the folder check into an exact one.

**Minors noticed, not fixed**

- `POST /comms/post` with a lone surrogate in `text` is a 500 (`UnicodeEncodeError`) for every caller, chief or not; the gate's key check only reads the kind of `text`.
- A caller with no token gets a 500 from `/comms/acknowledge` with a lone-surrogate `message_id` (this ticket leaves non-chief callers as they were).
- `/comms/acknowledge` of an unknown id is a 200 no-op where `/comms/supersede` answers 404.
- `bandit` prints `Test in comment: ... is not a test name or id, ignoring` warnings for comments in `src/` (it exits 0), and `mypy` prints `annotation-unchecked` notes; both existed before.
- The 2 skipped tests in `tests/comms_board tests/db tests/runner_supervisor tests/consistency` are not mine.
