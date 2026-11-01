# Record the caller's run as `claimed_by` on every task claim

Type: task
Status: resolved
Blocked by: 10
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/blueprints/comms/tasks.py, src/pathly_orchestrator/supervisor/board_run.py, src/pathly_orchestrator/http_server/blueprints/comms/tasks_claim.py (new), src/pathly_orchestrator/http_server/blueprints/comms/__init__.py, scripts/file_size_baseline.txt, tests/dag_goals/test_claim_names_its_run.py, src/pathly_orchestrator/CLAUDE.md, CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

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
- `/comms/tasks/run` (`src/pathly_orchestrator/http_server/blueprints/comms/tasks.py`, move it to
  `tasks_claim.py` too): mint the run id first, claim with it, then start the board run with it.
  `supervisor/board_run.py::start_board_run` takes no run id today: add an optional `run_id`
  keyword (default: a new uuid4, as now), so claiming after the start cannot race the agent.
  `board_run.py` is at 484 lines against a baseline of 490: keep the change within that room.
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

**Built** (work started at a1246cbe; failing test 8b9838b2):
- `src/pathly_orchestrator/http_server/blueprints/comms/tasks_claim.py` (new, blueprint
  `comms_tasks_claim`): `POST /comms/tasks/claim` and `POST /comms/tasks/run`, moved from `tasks.py`.
  - claim: a caller with a live run token (`run_identity.caller_identity(request)`, kind `run`)
    claims as that token's `run_id`; the body `run_id` is ignored then. A tokenless caller keeps
    the body value, and a blank one is still 400.
  - run: mints `str(uuid.uuid4())` first, claims with it, then calls
    `start_board_run(..., run_id=run_id)`. `start_board_run` is still imported lazily inside the
    handler, so the monkeypatches in `test_comms_task_run.py` work. `_release_claim` stays in
    `tasks.py` (`/comms/tasks/stop` uses it), and `tasks_claim.py` imports it from there.
- `blueprints/comms/__init__.py` registers the new blueprint.
- `tasks.py` is 413 → 220 lines. Its `scripts/file_size_baseline.txt` entry is removed.
- `supervisor/board_run.py::start_board_run`: new keyword `run_id: str = ""`, used as
  `run_id = run_id or str(uuid.uuid4())`. The Returns docstring went from three lines to two, so
  the file stays at 484, its baseline.
- `src/pathly_orchestrator/CLAUDE.md`: the claim and run route lines, the `claimed_text` note
  (it said team builders claim with `"build"`), the comms file list and the `board_run.py` line.
- `tests/dag_goals/test_claim_names_its_run.py` (new, 5 tests), plus `tests/INDEX.md` and
  `tests/dag_goals/INDEX.md`.

**Proof**:
- `python -m pytest tests/dag_goals/test_claim_names_its_run.py -q -p no:cacheprovider`: 5
  passed, exit 0. The tests cover:
  - a drain-dag body `{"run_id": "$GOAL_ID-single"}` with a live token records the token's run;
  - a tokenless claim records the body value;
  - `/comms/tasks/run` claims, before the run starts, with the id it then passes to
    `start_board_run` and returns;
  - `start_board_run(run_id=...)` uses the id it is given;
  - a `scheduler_loop` claim records `sched-<task>#1`.

  At 8b9838b2 three tests failed for the right reasons: the claim stored `$GOAL_ID-single`, the
  run's `run_id` was None, and `start_board_run` raised TypeError on the unexpected `run_id`. The
  sched and tokenless tests already passed, which is expected.
- `python -m pytest tests/dag_goals tests/comms_board -q -p no:cacheprovider`: 1711 passed,
  exit 0.
- Lint chain from commands.md: exit 0 (black, mypy, check_file_size "none new, none grown",
  INDEX check, lint-imports, bandit, adapters, entry points).
- Extra: `python -m pytest tests/http_api -q -p no:cacheprovider -k "chief or task"`: 2338 passed, 226 deselected, exit 0.

**Decisions**:
- A live token with a blank or missing body `run_id` is accepted, because the token names the
  run. Only a tokenless caller needs the body field.
- `/comms/tasks/run` returns `result["run_id"]` as before. A real `start_board_run` echoes the id
  it was given, and the old fakes that return `"r1"` keep passing.
- `_release_claim` is shared by importing it from `tasks.py` (`_helpers.py` is not in Touches).

**Shortcuts taken**: none.

**For later tickets**: `claimed_by` now names the run that claimed the task:
- the token's run id for an agent;
- the started board run's uuid for `/comms/tasks/run`;
- `sched-<task>#N` for the loop scheduler.

Tickets 05, 06 and 12 can join `claimed_by` to `run_tokens.run_id` / `author_run_id`.

The skill text still tells agents to send `run_id` (`drain-dag.md`, `development/build.md`,
`team/build.md`). It is harmless now, because the token wins. The root `CLAUDE.md` blueprint map
(`comms/ ... tasks, tasks_status, tasks_floor ...`) does not list `tasks_claim`; it was not in
Touches.
