# Record routed questions and decide who answers each one

Type: task
Status: open
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
