# Show on the Chief button when a run the chief started has ended

Type: task
Status: open
Blocked by: 05, 06
Test first: yes

Spike S13 and "Plan discussed" part 1. A chief cannot learn that a run ended unless the person
writes to it (background tasks and cron are off on purpose), and the person expected to be told.
Tell the person, not the chief: nothing enters the tab, so nothing can be cited as typed.

1. **Record.** When a chief token's call starts work and the route answers 2xx with a `run_id`
   (the calls `chief_budget.STARTS_A_RUN` lists, and `retry`), insert a row into a new table
   `chief_session_runs(session_run_id, run_id, project_root, started_at, read_at)` (created by
   `db/migrations_chief.py`, queries in a new `db/queries/chief_session_runs.py`, static SQL).
   Do it in an `after_request` hook beside `refund_run_slot`, reading the run id from the JSON
   response; a 4xx or 5xx records nothing.
2. **Read.** `GET /chief/notices?project_root=<root>` (new file in `blueprints/chief/`) lists the
   project's recorded runs that reached a terminal status (`done`, `error`, `aborted`, `failed`)
   and are unread: `run_id`, `kind`, `status`, `outcome` and `error` (ticket 05's
   `task_unfinished`, ticket 06's `waiting_for_answer`), `cost_usd`, and the count of open
   `question`/`escalation` rows addressed to `human` on that run's board. Reuse the run read
   behind `GET /runs/<id>`. The chief gate treats it as a `read`; add its fields entry
   (`chief_field_reads.py`). Rows outlive the session, so the next chief of the project sees
   them.
3. **Mark read.** `POST /chief/notices/read {"project_root", "run_ids"}` sets `read_at`. A chief
   token is refused (unlisted in `chief_routes.ROUTE_ACTIONS`): only Studio marks notices read,
   when the person opens the Chief menu.
4. **Studio.** `ChiefButton` polls `GET /chief/notices` for the selected project (every 15 s
   while the window is focused, through `services/chiefApi.ts`) and shows the unread count as a
   badge; opening the menu lists them (run, status, cost, questions waiting) and marks them read.

Living docs: the chief paragraph and blueprint map in `src/pathly_orchestrator/CLAUDE.md`
(`chief/` line), and `studio/CLAUDE.md` for the badge.

## Not in this ticket

- A notice typed into the chief's tab: round four.
- Desktop notifications outside Studio.

## Done when

- `python -m pytest tests/http_api/test_chief_notices.py -q -p no:cacheprovider` passes and
  covers: a chief's 2xx `POST /runs` records a row and a 400 records none; a finished run appears
  in `GET /chief/notices` with its status, outcome, error, cost and questions count, a running one
  does not; marking it read hides it; a chief token's `POST /chief/notices/read` is 403; another
  project's chief sees none of it; the migration runs twice.
- `npm --prefix studio run test -- ChiefButton` passes with a test that a non-zero unread count
  shows the badge and opening the menu calls the mark-read service.

```check
$ python -m pytest tests/http_api/test_chief_notices.py -q -p no:cacheprovider
exit 0
prints passed
$ npm --prefix studio run test -- ChiefButton
exit 0
```

## Reference

- spec.md § Interfaces, § Decisions ("Notices")
- `src/pathly_orchestrator/http_server/chief_budget.py` (`STARTS_A_RUN`, `refund_run_slot`),
  `src/pathly_orchestrator/http_server/blueprints/chief/session.py`,
  `studio/src/renderer/src/components/topbar/ChiefButton/`, `studio/src/renderer/src/services/chiefApi.ts`

## Answer
