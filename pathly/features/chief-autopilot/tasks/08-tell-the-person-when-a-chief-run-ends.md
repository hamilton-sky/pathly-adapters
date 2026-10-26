# Record a chief's runs and list the finished ones at `GET /chief/notices`

Type: task
Status: open
Blocked by: 05, 06, 10
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/migrations_chief.py, src/pathly_orchestrator/db/queries/chief_session_runs.py (new), src/pathly_orchestrator/http_server/chief_run_record.py (new), src/pathly_orchestrator/http_server/app.py, src/pathly_orchestrator/http_server/blueprints/chief/notices.py (new), src/pathly_orchestrator/http_server/blueprints/chief/__init__.py, src/pathly_orchestrator/http_server/chief_field_reads.py, tests/http_api/test_chief_notices.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

Spike S13 and "Plan discussed" part 1. A chief cannot learn that a run ended unless the person
writes to it, and the person expected to be told. Tell the person, not the chief: nothing enters
the tab, so nothing can be cited as typed. This ticket is the server half; ticket 13 is Studio's.

1. **Record.** When a chief token's call starts work and the route answers 2xx with a `run_id`
   (the calls `http_server/chief_budget.py::STARTS_A_RUN` lists, and `retry`), insert a row into a
   new table `chief_session_runs(session_run_id, run_id, project_root, started_at, read_at)`
   (created by `src/pathly_orchestrator/db/migrations_chief.py`, queries in a new
   `src/pathly_orchestrator/db/queries/chief_session_runs.py` (new), static SQL). Do it in an `after_request` hook in
   `src/pathly_orchestrator/http_server/chief_run_record.py` (new), registered in `app.py` beside `refund_run_slot`, reading the
   run id from the JSON response; a 4xx or 5xx records nothing. First check that each route in
   `STARTS_A_RUN` returns `run_id` in its 2xx body (`/comms/goals/run`, `/comms/run`,
   `/comms/tasks/run`); one that does not gets it added, or is named in the Answer.
2. **Read.** `GET /chief/notices?project_root=<root>` (new `blueprints/chief/notices.py`) lists
   the project's recorded runs that reached a terminal status and are unread: `run_id`, `kind`,
   `status`, `outcome` and `error` (tickets 05 and 06: `task_unfinished`, `waiting_for_answer`),
   `cost_usd`, and the count of open `question`/`escalation` rows addressed to `human` (or `*`) on
   that run's board (the same rows that park a task, ticket 06). Reuse the read behind `GET /runs/<id>`. The chief gate treats it as a `read`; add
   its fields entry in `chief_field_reads.py`. Rows outlive the session, so the next chief of the
   project sees them.
3. **Mark read.** `POST /chief/notices/read {"project_root", "run_ids"}` sets `read_at`. It is not
   in `chief_routes.ROUTE_ACTIONS`, so a chief token is refused. (Any tokenless loopback caller can
   still call it; harmless for a read mark, and round four's grant needs a Studio-only credential,
   map.)

Living docs: the chief paragraph and the `chief/` line of the blueprint map in
`src/pathly_orchestrator/CLAUDE.md`.

## Not in this ticket

- The badge in Studio: ticket 13. A notice typed into the chief's tab: round four.

## Done when

- `python -m pytest tests/http_api/test_chief_notices.py -q -p no:cacheprovider` passes and
  covers: a chief's 2xx `POST /runs` and `/comms/goals/run` each record a row and a 400 records
  none; a finished run appears in `GET /chief/notices` with its status, outcome, error, cost and
  questions count, a running one does not; marking it read hides it; a chief token's
  `POST /chief/notices/read` is 403; another project's chief sees none of it; the migration runs
  twice.

```check
$ python -m pytest tests/http_api/test_chief_notices.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Interfaces, § Decisions ("Notices"), review m4
- `src/pathly_orchestrator/http_server/chief_budget.py`, `src/pathly_orchestrator/http_server/blueprints/chief/session.py`

## Answer
