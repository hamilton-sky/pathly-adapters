# Record a chief's runs and list the finished ones at `GET /chief/notices`

Type: task
Status: resolved
Blocked by: 05, 06, 10
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/migrations_chief.py, CLAUDE.md, src/pathly_orchestrator/db/queries/chief_session_runs.py (new), src/pathly_orchestrator/http_server/chief_run_record.py (new), src/pathly_orchestrator/http_server/app.py, src/pathly_orchestrator/http_server/blueprints/chief/notices.py (new), src/pathly_orchestrator/http_server/blueprints/chief/__init__.py, src/pathly_orchestrator/http_server/chief_field_reads.py, tests/http_api/test_chief_notices.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

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

**Built** (work started at 8adefaf0; failing test 789b6638; round 2 started at 9e3a0361, failing test 1844c7a3):
- `src/pathly_orchestrator/db/migrations_chief.py`: `add_chief_tables` also creates
  `chief_session_runs(run_id PRIMARY KEY, session_run_id, project_root, started_at, read_at)` and
  an index on `project_root`.
- `src/pathly_orchestrator/db/queries/chief_session_runs.py` (new): `record_session_run`
  (INSERT OR IGNORE), `ended_unread_runs` (join `run_history`, status `done`/`error`/`aborted`/
  `parked`, `read_at IS NULL`), `run_notice` (the run row, kind, cost and outcome through the
  `run_history_read` helpers behind `GET /runs/<id>`, nothing else), `mark_runs_read` (one UPDATE per id, scoped to the project),
  `open_questions_on_board` (question/escalation to `human`/`*` on a scope, live, not superseded,
  `pending`/`active`, no live answer reply). Every SQL one literal.
- `src/pathly_orchestrator/http_server/chief_run_record.py` (new): `record_chief_run`
  `after_request` hook, registered in `app.py` after `refund_run_slot` (so it runs before it and
  still sees `g.chief_run_slot`). Records only a 2xx JSON body with `ok` truthy and a non-empty
  string `run_id`; project root from `chief_sessions`; try/except + warning log.
- `src/pathly_orchestrator/http_server/blueprints/chief/notices.py` (new): `GET /chief/notices`
  (reads only `request.args`, 400 without `project_root`; each notice is
  `run_notice(...)` plus `open_questions` on the run's `board_scope` or `feature`) and
  `POST /chief/notices/read` (`{project_root, run_ids}` → `{marked}`; 400 on bad fields; 403 for
  any live run token; a chief token is already refused by the gate since the route is not in
  `ROUTE_ACTIONS`). Added to `blueprints/chief/__init__.py`.
- `http_server/chief_field_reads.py`: `("/chief/notices", "GET"): Fields(roots=_ROOT)`.
- Docs: root `CLAUDE.md` blueprint map `chief/` line; `src/pathly_orchestrator/CLAUDE.md` chief
  route list and a "Notices" bullet.
- `tests/http_api/test_chief_notices.py` (new, 20 tests) + `tests/INDEX.md`, `tests/http_api/INDEX.md`.

**STARTS_A_RUN check**: every start route answers its 2xx with `ok: true` and `run_id`:
`POST /runs` (flow, single/evaluator, goal: `control/_helpers.py`), `/comms/goals/run`
(`goal_executor` single/loop/team results all carry `run_id`), `/comms/run` (`board_run`
returns `run_id`), `/comms/tasks/run` (`tasks_claim.py`), `retry` (new id on success). None
needed a change.

**Proof**:
- Round 2: `python -m pytest tests/http_api/test_chief_notices.py -q -p no:cacheprovider`: 20 passed,
  exit 0. At 1844c7a3 (test only) 2 failed for the right reasons (`test_a_parked_run_is_a_notice`:
  no notice; `test_a_notice_reads_the_run_not_its_full_detail`: 500 from the patched
  `get_run_detail`), 18 passed. `tests/http_api -k "chief_gate or chief_notices"`: 1506 passed,
  1090 deselected. `tests/http_api -k chief`: 2356 passed, 240 deselected.
  `tests/db/test_chief_tables.py`: 14 passed. Lint chain (black --check, mypy,
  check_file_size "none new, none grown", check_no_mirror_reads, gen_test_index --check,
  lint-imports 1 kept, bandit): exit 0.
- Round 1: `python -m pytest tests/http_api/test_chief_notices.py -q -p no:cacheprovider`: 16 passed,
  exit 0. Covers: chief's 2xx `POST /runs` flow and `/comms/goals/run` each record one row with the
  session's root; a route 400 (`/comms/goals/run` with a not-ok result, `POST /runs` with a blank
  scope) records none; a retry answering 200 `ok: false` (already_active, old run id) records none;
  a tokenless start records none; an ended run (`error`, AGENT_DONE failed/`waiting_for_answer`,
  $0.25 invocation, 2 open human/`*` rows on its board, plus a role question and another board's
  question not counted) is listed with status, outcome, error, cost, `open_questions == 2`, and a
  `running` one is not; an answered question is not counted; mark read hides it; a chief token's
  `POST /chief/notices/read` is the gate's 403 and leaves it unread; another project's chief sees
  `[]` for its own root and the gate's 403 for the first project's; another project's mark-read
  leaves it; notices outlive a closed session (a new chief sees them); the migration runs twice on a
  fresh connection and keeps the row. At 789b6638 all 16 failed (404 on the routes, no table, no
  module).
- `python -m pytest tests/db/test_chief_tables.py` (with the new file): 30 passed.
- `python -m pytest tests/http_api -q -p no:cacheprovider -k chief`: 2352 passed, 240 deselected, exit 0.
- Lint chain from commands.md (black, mypy, check_file_size "none new, none grown",
  check_no_mirror_reads, gen_test_index --check, lint-imports 1 kept, bandit, check_adapters,
  check_entry_points): exit 0.

**Decisions**:
- The hook keys off the gate's slot mark (`g.chief_run_slot`), which is set exactly for a chief
  token's `STARTS_A_RUN`/`retry` call that took a slot, so no rule list is duplicated.
- Terminal = `done`, `error`, `aborted`, `parked`. A parked run's row is final:
  `registry._set_status` finalises `run_history` on `parked`, and `api.resume_parked_run` starts a
  new run id (round 2, finding 1).
- `open_questions` counts by the run's board (`run_history.board_scope`, else `feature`), not by
  `author_run_id`: a flow's questions are posted by its stage runs, whose ids differ from the parent.
- `run_id` is the primary key: a run is recorded once.
- `POST /chief/notices/read` also refuses any live run token (not only the chief's), like
  `/chief/open` and `/chief/close`: the read mark is the person's act.

**Shortcuts taken**:
- Resuming a parked run starts a new run id, and `resume` is not a starting verb
  (`chief_budget.STARTING_VERBS` is `retry` only), so the resumed run is not recorded and its end
  is not a notice. Recording it would mean treating a resume of a parked run as a start.
- `open_questions` counts every open question/escalation on the board, not only the run's own;
  two runs on one board show the same count. The board has no project column, so a same-named
  feature of another project counts too (round 2, finding 3).
- Unread rows are never pruned and every notice is listed: each costs a few indexed reads
  (run row, cost sum, latest outcome event, question count). Add a cap if a project piles up
  hundreds of unread notices.

**Review fixes** (round 1, quality review):
1. major, parked never a notice: verified first. `registry._set_status` finalises `run_history`
   for `parked` (registry.py:273-275, "resuming a parked run starts a NEW run_id"), and
   `supervisor/api.resume_parked_run` calls `start_run`, which mints a fresh run id. So the finding
   is right. `ended_unread_runs` now includes `parked`; new test `test_a_parked_run_is_a_notice`
   (status `parked`, its open escalation counted). Wording fixed in the module docstring,
   `src/pathly_orchestrator/CLAUDE.md` Notices paragraph, and a new map.md line (map lines are
   append-only, so the old 08 line stays and the new one corrects it).
2. minor, full `get_run_detail` per notice: `chief_session_runs.run_notice` reads the run row and
   calls only `_classify_kind`, `_run_cost` and `_run_outcome` (the helpers `get_run_detail` uses
   for those fields, so the figures still match `GET /runs/<id>`); stages, logs, board posts and
   artifacts are no longer read. New test `test_a_notice_reads_the_run_not_its_full_detail` patches
   `get_run_detail` to raise and checks kind, status, outcome, error and cost. No cap: see Shortcuts.
3. minor, same-named feature across projects: noted, not filtered. `comms_messages` has no project
   column (only `board` and `scope`), and `run_history` stores no board kind, so there is nothing to
   filter by; the board itself is shared between such projects. Written in the
   `open_questions_on_board` docstring, the CLAUDE.md Notices paragraph and Shortcuts.
4. minor, missing tests: added `test_a_failure_to_record_lets_the_start_through`
   (`record_session_run` raising `OperationalError`: the start still answers 200 with `run-1`,
   nothing recorded) and `test_an_agents_run_token_may_not_mark_notices_read` (a builder token:
   403, notice still unread). Both pass against the round-1 code, as the review said the behaviour
   was there and only the tests were missing.
5. minor, "shows the count": now "will show the count (ticket 13)" in
   `src/pathly_orchestrator/CLAUDE.md` and the `notices.py` docstring.

**For later tickets**:
- 13: read `GET /chief/notices?project_root=<root>` (`notices` list; badge = its length) and mark
  with `POST /chief/notices/read {project_root, run_ids}` with no run token.
- 09: the record is made by the hook only for a chief token; tokenless starts are not notices.

## Review findings (round 1, quality review)

QUALITY
Probed: hook records only with g.chief_run_slot (chief gate only), reads it before refund pops it, records nothing on 4xx/5xx/ok:false (retry's old run id), project root from the session, failures caught (no 500). GET /chief/notices root bound to the session's root (403 otherwise). POST /chief/notices/read refused to chief and other run tokens, fields type-checked. SQL static. Layer rules and 400-line limit kept.
1. major src/pathly_orchestrator/db/queries/chief_session_runs.py (ended_unread_runs): a chief's run that parks is never a notice. The query excludes parked because it "may resume", but resume never reopens that run id: registry._set_status finalises run_history on parked and supervisor/api.resume_parked_run starts a new run with a fresh id. A chief's headless flow parks at a human checkpoint, and a team goal run can park too: exactly the run the person must come back to. Fix: add 'parked' to the terminal statuses, test a parked run, correct the "parked ... may resume" wording here, in src/pathly_orchestrator/CLAUDE.md (Notices paragraph) and in map.md.
2. minor src/pathly_orchestrator/http_server/blueprints/chief/notices.py (_notice): each notice calls get_run_detail in full (stages, logs, board posts, artifacts) and throws most away; rows are never pruned and ticket 13 will poll this route. Fix: read only the run row, outcome and cost, or cap the number of notices per call.
3. minor chief_session_runs.py (open_questions_on_board): count matches scope only; two projects with a same-named feature add to each other's count. Note it, or also filter by board where known.
4. minor tests/http_api/test_chief_notices.py: no test that a failure inside the hook still lets the 2xx through (e.g. record_session_run raising), and none that a non-chief run token gets 403 from POST /chief/notices/read. Add both.
5. minor src/pathly_orchestrator/CLAUDE.md (Notices paragraph): "Studio's Chief button shows the count (ticket 13)" describes unbuilt work; say "will show".

REVIEW: FAIL
