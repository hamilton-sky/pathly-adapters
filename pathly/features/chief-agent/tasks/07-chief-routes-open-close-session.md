# Add the /chief routes to open, close and read the chief session

Type: task
Status: open
Blocked by: 06
Test first: yes

Add a new blueprint domain `src/pathly_orchestrator/http_server/blueprints/chief/` with
`__init__.py` exposing `all_blueprints` (the pattern of `blueprints/control/__init__.py`) and
`session.py`, registered in `http_server/app.py` the way `control_blueprints` is. Imports of
`supervisor` and `db` stay lazy inside each route.

- `POST /chief/open` `{project_root, engine, preset, prompt, model?}`: 403 when
  `caller_identity(request)` is a live run (an agent cannot open a chief); 400 when a field is
  missing or not a string, or `open_chief` raises `ValueError` (message passed on); 409
  `{error, run_id, tab_id}` on `ChiefAlreadyOpen`; otherwise 201 with `open_chief`'s result.
  Hand `open_chief` the runner broadcaster (`sse._broadcast_runner`, imported inside the route).
- `POST /chief/close` `{project_root}`: 403 for a live run token; closes the project's open
  session with reason `closed from Studio`; 200 `{closed: true|false}`.
- `GET /chief/session?project_root=`: `{open: false}` or `{open: true, run_id, tab_id, tier,
  engine, opened_at}`.

Add `supervisor/chief_session.py::chief_startup_cleanup()`: `close_stale_sessions` and remove
their session folders. Call it from `app.main()` before the server starts serving, inside a
`try` that logs and continues (a cleanup failure must not stop the server). A chief open across a
restart has no watcher left, so its token must not outlive the process.

Living docs in the same change: the root `CLAUDE.md` blueprint domain map gains a `chief/` line;
`src/pathly_orchestrator/CLAUDE.md` lists the three routes (HTTP endpoints) and the new files in
the package tree.

## Not in this ticket

- Refusing the chief's own token on these routes and everywhere else it has no business: the
  chief gate, ticket 08.
- `POST /chief/human-messages`: ticket 09. `GET /chief/inbox` and `GET /chief/overview`: round two.

## Done when

- `python -m pytest tests/http_api/test_chief_routes.py -q -p no:cacheprovider` passes and covers:
  open with the broadcaster replaced by a fake returns 201 with `tier: "operator"` for preset
  `operator` and the fake sees one `TERMINAL_SPAWN`; a second open returns 409 with the first
  `run_id`; `GET /chief/session` shows it open; close returns `closed: true`, then the session
  reads `open: false` and the token no longer resolves; open with a live builder token is 403;
  open with engine `copilot` is 400; `chief_startup_cleanup()` closes an open session and revokes
  its token.
- `grep -n "chief_startup_cleanup" src/pathly_orchestrator/http_server/app.py` shows the call.

```check
$ python -m pytest tests/http_api/test_chief_routes.py -q -p no:cacheprovider
exit 0
prints passed
$ grep -n "chief_startup_cleanup" src/pathly_orchestrator/http_server/app.py
exit 0
prints chief_startup_cleanup
```

## Reference

- spec.md § Interfaces, § Edge cases
- `src/pathly_orchestrator/http_server/app.py` (`main`, blueprint registration)
- `src/pathly_orchestrator/http_server/blueprints/control/` (package pattern)
- `src/pathly_orchestrator/http_server/run_identity.py::caller_identity`
- root `CLAUDE.md` § "Blueprint domain map"

## Answer
