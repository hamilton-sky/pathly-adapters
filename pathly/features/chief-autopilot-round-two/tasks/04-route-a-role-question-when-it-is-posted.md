# Route a run's role question to a consult when it is posted

Type: task
Status: open
Blocked by: 01, 02
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/consult_trigger.py (new), src/pathly_orchestrator/supervisor/consult_router.py (new), src/pathly_orchestrator/http_server/app.py, tests/comms_board/test_consult_router.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/comms_board/INDEX.md

The trigger, server-driven with no chief turn (spec Decisions, "What triggers the router").

New `src/pathly_orchestrator/supervisor/consult_router.py` (new):
`on_question(question_id, *, project_root, broadcast_fn, host_present, start=start_consult) ->
str` returns what it did (`none`, `person`, `routed`, `no_host`):

- `route_decision` (ticket 01) `none` → nothing.
- `person` → `consult_routes.hand_to_person(question_id, decision.reason, by="pathly")`.
- `route` with `host_present` False → nothing (`no_host`): the question stays as posted (spec
  Decisions, "No spawn host").
- `route` → `record_route` (insert-or-ignore, so a second call for the same question routes
  nothing), then `start(question_id, project_root=..., broadcast_fn=..., block=False)` on a daemon
  thread named `consult-<question id prefix>`. A start that raises before the spawn hands the
  question to the person with the error and sets the route `failed`.

New `src/pathly_orchestrator/http_server/consult_trigger.py` (new), an `after_request` hook
registered in `src/pathly_orchestrator/http_server/app.py` after `record_chief_run`: for `POST /comms/post` answered 200
with `ok` and a `message_id`, when the request body's `type` is `question`, it calls `on_question`
with the body's `project_root`, `broadcast_fn=sse._broadcast_spawn` and
`host_present=bool(sse._spawn_clients)` (the queue a spawn host reads, `/events/spawn`). It never
changes the response and never raises (a failure is logged).

At server start, `app.main` calls `consult_routes.end_stale_routes` once, next to
`chief_startup_cleanup` and under the same "something already answers" check, and logs the
handed-on question ids.

Mind the tests that post role questions: a test without a spawn host routes nothing; a test that
registers a fake host (`SpawnHost` in `tests/comms_board/chief_acceptance_support.py`) and posts a role
question now gets a consult spawn. Any thread this starts in a test must end inside it
(`tests/chief_session_guard._no_watcher_outlives_its_test`).

## Not in this ticket

- Parking the asking task until the answer comes: tickets 06 (loop) and 07 (single).
- Showing the routes to the chief: ticket 09.

## Done when

- `python -m pytest tests/comms_board/test_consult_router.py -q -p no:cacheprovider` passes and
  covers, through `POST /comms/post` with a run token and a fake host and `start`: a question to
  `architect` records one route and calls `start` once; posting the response's hook twice (same
  message id) calls it once; a question to `human` and a tokenless question route nothing; a
  question to `builder` becomes `to: human`; the fourth role question of one task becomes
  `to: human` without a `start` call; a goal at its cost line routes nothing new; no spawn host →
  `no_host` and the question is unchanged; `end_stale_routes` at start hands a `running` route's
  question to the person.
- All existing tests under `tests/comms_board` and `tests/http_api` still pass.

```check
$ python -m pytest tests/comms_board/test_consult_router.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board tests/http_api -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Happy path 1-2, § Edge cases
- `src/pathly_orchestrator/http_server/chief_run_record.py` (an after-request hook that reads the
  response), `src/pathly_orchestrator/http_server/sse.py` (read-only)

## Answer
