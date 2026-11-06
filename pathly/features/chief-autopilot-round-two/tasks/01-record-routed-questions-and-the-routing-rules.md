# Record routed questions and decide who answers each one

Type: task
Status: resolved
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/migrations_consult.py (new), src/pathly_orchestrator/db/migrations_incremental.py, src/pathly_orchestrator/db/queries/consult_routes.py (new), tests/comms_board/test_consult_routes.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/comms_board/INDEX.md

The store and the rules every later consult ticket reads. No spawn here, no route trigger: pure
`db/` code (it may import nothing above `db/`).

New table `consult_routes` (additive, new `src/pathly_orchestrator/db/migrations_consult.py`
(new) wired last in `src/pathly_orchestrator/db/migrations_incremental.py::_add_additive_migrations`,
the way `migrations_task_waits.add_task_waits` is; `src/pathly_orchestrator/db/migrations.py` is at its ratchet baseline):

```
question_id TEXT PRIMARY KEY, role TEXT NOT NULL, task_id TEXT, goal_key TEXT,
asking_run_id TEXT, consult_run_id TEXT, status TEXT NOT NULL, reason TEXT,
created_at REAL NOT NULL, ended_at REAL
```

`status` is one of `queued`, `running`, `answered`, `to_person`, `withheld`, `failed`.

New `src/pathly_orchestrator/db/queries/consult_routes.py` (new), every SQL one literal:

- `CONSULT_ROLES = ("architect", "designer", "po", "planner", "tester", "reviewer")`, the roles
  `src/pathly_data/core/skills/fragments/consult.md` lists.
- `consult_limits(conn) -> (max_per_task, goal_cost_usd)`: settings `consult.max_per_task`
  (default 3) and `consult.goal_cost_usd` (default 2.0) through
  `db/queries/app_settings.get_setting`, as `supervisor/task_retry.resolve_max_attempts` reads
  `goal.task_max_attempts`; a missing, non-numeric or negative value gives the default.
- `asking_task(conn, run_id) -> dict | None`: for `sched-<task>#<n>` the task row of `<task>`
  (the pattern `supervisor/task_proof._RUN_ID` matches); otherwise the `in_progress` task whose
  `claimed_by` is the run (round one stamps it from the run token), the newest claim when there are several; None
  for no run or no task.
- `goal_key` of a question: its asking task's `goal_id`, else the asking run id.
- `route_decision(conn, question_id) -> Decision` (a small frozen dataclass: `kind` `route`,
  `person` or `none`; `reason`; `role`; `task_id`; `goal_key`; `asking_run_id`):
  - `none`: not a live `question` row; no `author_run_id`; `to_agent` `human` or `*` (round one's
    park handles it); the author run is a consult run (`consult-` prefix: no consult of a
    consult); already in `consult_routes`.
  - `person` with reason `unknown role <to>`: any other `to_agent` not in `CONSULT_ROLES`.
  - `person` with reason `routed question limit (<n>) reached for task <id>`: the asking task (or,
    with no task, the asking run) already has `max_per_task` rows whose status is not `to_person`.
  - `person` with reason `consult cost line $<x> reached for <goal_key>`: `goal_cost_usd` is 0,
    or `goal_consult_cost` is at or above it.
  - `route` otherwise.
- `record_route(conn, decision, question_id, status="queued") -> bool`: insert-or-ignore on the
  question id; True when this call inserted it.
- `set_route_status(conn, question_id, status, *, consult_run_id=None, reason=None)`: sets
  `ended_at` for an end status.
- `hand_to_person(conn, question_id, why, *, by)`: in one write lock, `to_agent='human'` on the
  question row (same id, so a task parked on it still names it), and the route row `to_person`
  with the reason (inserted when none exists); then a system-stamped `status` row
  (`db/provenance_values.SYSTEM_AUTHOR`) with `reply_to` the question and the text
  `<by> handed this question to the person: <why>` through `comms_messages.post_message` (a
  `status` row never frees a task: only `type: answer` does).
- `routes_for_questions(conn, ids) -> list[dict]`, `pending_routes(conn, ids) -> list[str]` (the
  ids whose route is `queued` or `running`).
- `goal_consult_cost(conn, goal_key) -> float`: `SUM(cost_usd)` of `agent_invocations` whose
  `run_id` is a `consult_run_id` of that `goal_key`.
- `end_stale_routes(conn) -> list[str]`: every `queued` or `running` route handed to the person
  with reason `server restart` (ticket 04 calls it at start).

Add a "Consult routes" paragraph to `src/pathly_orchestrator/CLAUDE.md` (file list and the two
settings).

## Not in this ticket

- Starting a consult run and posting its answer: ticket 02. Calling `route_decision` when a
  question is posted, and `end_stale_routes` at start: ticket 04.
- Parking a task on a role question: tickets 06 and 07.

## Done when

- `python -m pytest tests/comms_board/test_consult_routes.py -q -p no:cacheprovider` passes and
  covers: each `none`, `person` and `route` case above with its reason; the per-task count with
  three routed rows and one `to_person` row (the fourth question is `person`, a `to_person` row
  does not count); `goal_cost_usd` 0 and a goal over its line both give `person`; a `sched-T#2`
  run and a single run's claim both find their task; `record_route` twice inserts once;
  `hand_to_person` leaves the question id unchanged with `to_agent` `human`, adds one `status`
  reply and does not free a task parked on it; `end_stale_routes` hands `queued` and `running`
  routes to the person and leaves `answered` ones; bad settings fall back to 3 and 2.0.
- All existing tests under `tests/db` and `tests/comms_board` still pass.

```check
$ python -m pytest tests/comms_board/test_consult_routes.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/db tests/comms_board -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Caps and cost", "Handing a question to the person")
- `src/pathly_orchestrator/db/queries/task_waits.py`, `src/pathly_orchestrator/db/migrations_task_waits.py`,
  `src/pathly_orchestrator/db/provenance_values.py`

## Answer

Work started at `62b7d06d1675c75b331adff0c79bd487c0a1cff6`; test-only commit `20db563`.

**Built**

- `src/pathly_orchestrator/db/migrations_consult.py` (new): `add_consult_routes(conn)`, the
  `consult_routes` table as specified plus an index on `goal_key`; `CREATE ... IF NOT EXISTS`.
- `src/pathly_orchestrator/db/migrations_incremental.py`: import + `add_consult_routes(conn)` as
  the last call of `_add_additive_migrations`.
- `src/pathly_orchestrator/db/queries/consult_routes.py` (new, 332 lines): `CONSULT_ROLES`,
  `STATUSES`, `END_STATUSES`, `Decision`, `consult_limits`, `asking_task`, `goal_key`,
  `route_decision`, `record_route`, `set_route_status`, `hand_to_person`, `routes_for_questions`,
  `pending_routes`, `goal_consult_cost`, `end_stale_routes`. Imports only `db/` modules.
- `tests/comms_board/test_consult_routes.py` (new, 35 tests).
- `src/pathly_orchestrator/CLAUDE.md`: package tree entries for both files and a "Consult routes"
  section (after "A task waits on its question") with the rules and the two settings.
- `tests/INDEX.md`, `tests/comms_board/INDEX.md`: regenerated with `scripts/gen_test_index.py`.

**Proof**

- `python -m pytest tests/comms_board/test_consult_routes.py -q -p no:cacheprovider`: `35 passed`,
  exit 0. Before the code it failed at collection with
  `ModuleNotFoundError: No module named 'pathly_orchestrator.db.migrations_consult'`. Covers every
  `none` case (missing / non-question / deleted row, no author run, `human`, `*`, ` Human `, a
  `consult-` author, already routed), `person` for `unknown role wizard`, the per-task limit with
  three routed rows and one `to_person` row (fourth question: `routed question limit (3) reached
  for task <id>`; with two counted + one `to_person` it routes), the limit for a taskless run,
  `goal_cost_usd` 0 (`consult cost line $0.00 reached for goal-1`) and a goal over its line
  ($2.25 of consult invocations: `$2.00`), `route` with role/task/goal, `sched-T#2` and a single
  run's newest claim finding their task, `record_route` twice inserting once, `hand_to_person`
  keeping the id with `to_agent` `human`, one system `status` reply, the parked task still
  `blocked` on `waiting_for_answer:<id>`, `end_stale_routes` handing `queued` and `running` to the
  person and leaving `answered` alone, and bad settings (`abc`/`x`, `-1`/`-0.5`, empty, `2.5`/`nan`)
  giving `(3, 2.0)`.
- `python -m pytest tests/db tests/comms_board -q -p no:cacheprovider`: `1685 passed, 2 skipped`,
  exit 0.
- Lint (commands.md) exit 0: black unchanged, mypy no issues, file size "none new, none grown",
  mirror reads OK, test indexes up to date, lint-imports 1 kept 0 broken, bandit no findings in the
  new files (only the existing `nosec` warnings), adapters and entry points OK. Smoke exit 0.

**Decisions**

- "Live question row" = `type='question' AND deleted_at IS NULL`, as `task_waits` reads "live";
  an already-answered question is not excluded (not in the rules).
- Role matching trims and lower-cases `to_agent` (as `open_questions_by_run` does); the decision's
  `role` is that normalised value.
- The per-task count uses `task_id` when there is a task, else `task_id IS NULL AND
  asking_run_id=?`; the limit reason names the task id, or the run id when there is none.
- `$<x>` in the cost reason is the line, two decimals (`$2.00`).
- `consult.max_per_task` 0 is accepted (routes nothing per task); only missing, non-numeric
  (including `2.5`, as `int()` reads it) or negative values fall back. A non-finite cost (`nan`,
  `inf`) falls back too.
- `record_route` and `set_route_status` raise `ValueError` on an unknown status. `record_route`
  stores the decision's `reason` (empty -> NULL) and sets `ended_at` when inserted with an end
  status. `set_route_status` keeps the existing `consult_run_id`/`reason` when given None.
- `hand_to_person` returns False when the question row does not exist; it fills role, task, goal
  key and asking run from the question when it inserts a route. The status reply has `from_agent`
  `system`, `to_agent` `*`, board and scope of the question. `end_stale_routes` uses
  `by="the server"`; a route whose question row is gone is still set `to_person`.
- `IN (SELECT value FROM json_each(?))` keeps the id-list queries one literal (no f-string SQL).

**Shortcuts taken**

- `asking_task` and `goal_key` are re-read in `hand_to_person` for an insert rather than passed in;
  fine at board sizes.

**For later tickets**

- 04: call `route_decision` then `record_route(conn, decision, qid)` for `route`, and
  `hand_to_person(conn, qid, decision.reason, by=...)` for `person`; `end_stale_routes(conn)` at
  start returns the handed ids.
- 02: `set_route_status(conn, qid, "running", consult_run_id=...)` then an end status; consult run
  ids must start with `consult-` so `route_decision` never routes a consult's own question.
- 02, 16: `goal_consult_cost` counts only invocations whose `run_id` is some route's
  `consult_run_id`, so store the consult run id on the route (`set_route_status(...,
  consult_run_id=...)`) when the run starts, or its cost never reaches the goal's line.

**Review fixes (round 1)** — rework started at `1a345bd`; test-only commit `13c9086` (8 new
tests failed: `True is False` for the recount, newlines in the reason/reply, `to_person` instead
of the ended status).

1. Race past the cap: `record_route` now counts again inside the insert (`INSERT OR IGNORE ...
   SELECT ... WHERE :cap IS NULL OR (SELECT COUNT(*) ... ) < :cap`, under the write lock, cap read
   there) for a `route` decision not inserted as `to_person`; over the cap it inserts nothing and
   returns False. Tests: two questions both decided `route` with `consult.max_per_task` 1, the
   second `record_route` returns False and `route_decision` then gives the limit reason; same for
   a taskless run.
2. Agent text in a system row: `to_agent` goes through `_one_line` (whitespace runs one space,
   non-printables dropped) and is capped at `ROLE_ECHO_MAX` = 40 before it reaches the decision's
   role/reason or the route row; `hand_to_person` makes `by` (40) and `why` (`WHY_MAX` = 300) one
   line too, so no caller can put a multi-line block into the `SYSTEM_AUTHOR` reply. Tests: a
   newline-laden 236-char role gives a one-line reason of at most 53 chars; the reply is one line.
3. `hand_to_person` reads only `deleted_at IS NULL` questions, so a deleted question returns
   False and `end_stale_routes` takes the `set_route_status` path (no re-address, no reply).
4. The upsert's `DO UPDATE` has `WHERE consult_routes.status IN ('queued','running')`: an
   `answered`, `failed` or `withheld` route keeps its status and reason (spec's failure table
   wants `failed`/`withheld` kept while the question goes to the person; the question is still
   re-addressed and the reply posted).
5. CLAUDE.md "Consult routes" now says the per-task cap is hard (recounted at insert) and the cost
   line is soft (checked against billed costs, so concurrent consults can end past it), plus the
   one-line echo and the ended-route/deleted-question behaviour.

Proof after the fixes: `test_consult_routes.py` `43 passed`, exit 0; `tests/db tests/comms_board`
`1693 passed, 2 skipped`, exit 0; Lint chain exit 0 (`tests/comms_board/INDEX.md` regenerated
for the new tests); `consult_routes.py` 360 lines.

For 04: when `record_route` returns False for a `route` decision, call `route_decision` again:
`none` (another call routed it) or `person` with the limit reason (hand it on).


## Review findings (round 1, quality review)

Reviewed 62b7d06..e587bb8. Both Done when commands pass (35 passed; tests/db tests/comms_board 1685 passed, 2 skipped).

QUALITY
1. major src/pathly_orchestrator/db/queries/consult_routes.py: a race lets a task go past the per-task cap. route_decision counts a task's routes with no lock held, and record_route then inserts with INSERT OR IGNORE on question_id alone, without counting again. Questions posted at the same moment from one run (each /comms/post is its own Flask thread) can all see count < max_per_task and all be recorded and routed. Fix: move the cap check into the write: inside _get_write_lock, count again before inserting, or INSERT ... SELECT ... WHERE (SELECT COUNT(*) ...) < ?; or one decide_and_record that holds the lock around both steps.
2. major src/pathly_orchestrator/db/queries/consult_routes.py: an agent can put its own text into a row stamped as the system. to_agent has no length or character check (messages_write.py takes data.get("to") as is). It becomes the reason "unknown role <to>", and when ticket 04 passes that reason to hand_to_person it goes into a status reply stamped SYSTEM_AUTHOR. Fix: make the role one line and cap its length (e.g. first 40 chars, newlines removed, or repr) before it goes into a reason, or use a fixed reason that does not echo the input.
3. minor consult_routes.py: hand_to_person reads the question without deleted_at IS NULL, so end_stale_routes can re-address a deleted question and post a status reply to it. Fix: filter deleted rows so a deleted question takes the set_route_status path.
4. minor consult_routes.py: hand_to_person's upsert sets any existing route to to_person, even one already answered. Fix: add WHERE consult_routes.status IN ('queued','running') to the DO UPDATE.
5. minor consult_routes.py: the cost line is checked only against costs already billed, so concurrent consults can start under it and end past consult.goal_cost_usd. The CLAUDE.md "Consult routes" paragraph should say the line is soft.

REVIEW: FAIL
