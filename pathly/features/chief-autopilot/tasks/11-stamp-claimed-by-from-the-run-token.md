# Record the caller's run as `claimed_by` on every task claim

Type: task
Status: open
Blocked by: 10
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/blueprints/comms/tasks.py, src/pathly_orchestrator/http_server/blueprints/comms/tasks_claim.py (new), src/pathly_orchestrator/http_server/blueprints/comms/__init__.py, scripts/file_size_baseline.txt, tests/dag_goals/test_claim_names_its_run.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

The review's B1. `db/queries/comms_tasks.py::claim_task` stores whatever `run_id` its caller
passes, and `POST /comms/tasks/claim`
(`src/pathly_orchestrator/http_server/blueprints/comms/tasks.py::comms_tasks_claim`) takes it from
the body. The `development/drain-dag` skill claims with `"$GOAL_ID-single"` while its run is a
uuid4 (`supervisor/board_run.py::start_board_run`), `/comms/tasks/run` claims as
`"task-<id8>"` and then starts a run with its own uuid, and the team build skills claim as
`"build"`. Only the loop scheduler claims with the spawn's id (`sched-<task>#N`). So no task can
be traced to the run that worked on it.

- In `comms_tasks_claim`, when the caller has a live run token
  (`run_identity.caller_identity(request).run_id`), use that run id as `claimed_by` and ignore the
  body's `run_id` (keep the body value only for a tokenless caller, as today). Move the handler to
  a new `blueprints/comms/tasks_claim.py` first: `tasks.py` is at 413 lines (ratchet baseline).
- `/comms/tasks/run` (`src/pathly_orchestrator/http_server/blueprints/comms/tasks.py`, move it to `tasks_claim.py` too): claim with
  the run id the started board run gets, not `"task-<id8>"` (start the run, then claim, or pass the
  id in).
- The loop scheduler's own claims are unchanged.

## Not in this ticket

- Using the link (tickets 05, 06, 12).

## Done when

- `python -m pytest tests/dag_goals/test_claim_names_its_run.py -q -p no:cacheprovider` passes and
  covers: a claim with drain-dag's literal body `{"run_id": "$GOAL_ID-single"}` and a live run
  token records the token's run id; a tokenless claim records the body value; `/comms/tasks/run`
  records the started run's id; a loop scheduler claim records `sched-<task>#N`.
- All existing tests under `tests/dag_goals` and `tests/comms_board` still pass.

```check
$ python -m pytest tests/dag_goals/test_claim_names_its_run.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/comms_board -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Which run a task belongs to"), review B1
- `src/pathly_data/core/skills/development/drain-dag.md`, `src/pathly_orchestrator/supervisor/scheduler.py`

## Answer
