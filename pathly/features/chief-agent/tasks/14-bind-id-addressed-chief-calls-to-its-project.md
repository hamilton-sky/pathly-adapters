# Bind chief calls that name a run, goal, task or message by id to the chief's project

Type: task
Status: open
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
