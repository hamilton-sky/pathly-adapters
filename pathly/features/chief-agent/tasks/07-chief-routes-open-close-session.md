# Add the /chief routes to open, close and read the chief session

Type: task
Status: resolved
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

**Built**

- `src/pathly_orchestrator/http_server/blueprints/chief/__init__.py` (new, `all_blueprints`, the
  pattern of `control/__init__.py`) and `chief/session.py` (new): `POST /chief/open`,
  `POST /chief/close`, `GET /chief/session`. Registered in `http_server/app.py` next to the other
  domains. Imports of `supervisor` and `db` are inside each route.
- `src/pathly_orchestrator/supervisor/chief_session.py`: `normalise_project_root()`, applied by
  `open_chief` (after `_validate`) so the stored session, the token's `project_root` and the spawn
  `cwd` all use one form; and `chief_startup_cleanup() -> list[str]`.
- `src/pathly_orchestrator/http_server/app.py`: `main()` calls `chief_startup_cleanup()` after the
  eager DB open and before `app.run`, inside a `try` that logs a warning and goes on.
- `tests/http_api/test_chief_routes.py` (new, 65 tests incl. parametrized; committed alone first as
  `c072386` `test(chief-agent): 07 failing test` with 62 of its tests; at that commit all 62 failed for
  the right reason: 404 on the missing routes, `AttributeError` for the missing
  `chief_startup_cleanup`). The final file adds three more tests (a run id that escapes the sessions
  root, and two that run `app.main()` in a subprocess). `tests/INDEX.md` and `tests/http_api/INDEX.md`
  regenerated.
- Living docs: root `CLAUDE.md` blueprint domain map gains the `chief/` line;
  `src/pathly_orchestrator/CLAUDE.md` gains a "Chief endpoints" section (the three routes), the
  `blueprints/chief/` entry in the package tree, and the `app.py` and `chief_session.py` lines.
- `learnings.md` (two lines) and `map.md` (one Decisions line).

**Proof** (each run fresh, after the last edit to code or tests)

- `python -m pytest tests/http_api/test_chief_routes.py -q -p no:cacheprovider` -> `65 passed in
  15.61s`, exit 0. It covers every item of the Done when: open with `sse._broadcast_runner` replaced
  by a fake returns 201 `{run_id, tab_id, tier: "operator", engine}` for preset `operator` and the
  fake sees exactly one `TERMINAL_SPAWN` (topic `chief:<run_id>`, interactive, `submit` false, a
  `run_token` that resolves to role `chief`); a second open is 409 with the first `run_id` and
  `tab_id` (body keys exactly `error, run_id, tab_id`) and sends nothing; `GET /chief/session` shows it
  open (`run_id, tab_id, tier, engine, opened_at` equal to the row); close returns `{closed: true}`,
  then the session reads `{open: false}`, the token no longer resolves (`resolve_run_token` None), the
  row's reason is `closed from Studio`, the folder is gone, and the fake saw one `TERMINAL_KILL
  {tab_id, run_id}` after the close; open with a live builder token is 403 and opens nothing; engine
  `copilot` is 400 naming `claude` and `codex`; `chief_startup_cleanup()` closes an open session
  (reason `server restart`), revokes its token and removes its folder.
  Beyond the list: `/p` and `/p/` are one project on open (409), on `GET` and on close; close with a
  live run token is 403 and closes nothing; close with nothing open, a second close, and another
  project's close are `{closed: false}` with no kill; a missing or non-string field (each of
  `project_root, engine, preset, prompt, model`) is 400 naming it; a body that is not a JSON object
  is 400; the `open_chief` `ValueError` message is passed on; a run id such as `../keep` closes but
  never removes a folder outside the sessions root; `app.main()` run in a subprocess with a seeded
  open session closes it and still serves, and with `chief_startup_cleanup` replaced by a function
  that raises it logs `chief startup cleanup failed` and still serves.
- `grep -n "chief_startup_cleanup" src/pathly_orchestrator/http_server/app.py` -> lines 140 and 142
  (the import and the call), exit 0.
- `lint-imports` -> exit 0, `Orchestrator layer rule ... KEPT (3 ignored imports)`, `Contracts: 1
  kept, 0 broken.`
- Mutation checks (source edited, tests run, source restored): dropping the normalisation, dropping
  the `TERMINAL_KILL`, letting an agent close, dropping the run-id guard in the cleanup, wrapping
  the cleanup in a `try` that does not catch its error, and removing the cleanup call each made a
  named test fail. (The first version of the run-id test passed without the guard because
  `chief/../keep` cannot resolve unless `chief/` exists; the test now creates it.)
- Lint chain from `commands.md`, run piece by piece, all exit 0: `black --check src/ tests/` (583
  files unchanged), `mypy src/ ...` (`Success: no issues found in 321 source files`),
  `check_file_size.py` (`none new, none grown`; `chief_session.py` is 265 lines, `session.py` 180),
  `check_no_mirror_reads.py`, `gen_test_index.py --check`, `bandit -q -r src/ -ll -x src/pathly_data/`,
  `check_adapters.py`, `check_entry_points.py`. No `# noqa` or `# nosec` added.
- Test command from `commands.md` (`tests/comms_board tests/db tests/runner_supervisor
  tests/http_api`) -> `1373 passed, 2 skipped in 277.73s`, exit 0 (the 2 skips are not mine).
  `tests/consistency` (57 passed), `tests/local_operator` + `tests/hq_copilot` (98 passed; they walk
  `app.url_map`). Smoke command exit 0. `python -m build --wheel` exit 0, and the wheel holds
  `blueprints/chief/__init__.py` and `session.py`.

**Decisions**

- The four notes the ticket 06 reviewers recorded: (1) `project_root` is normalised once, by
  `chief_session.normalise_project_root` (`replace("\\", "/").rstrip("/")`, the form the board code
  already uses, `or` the input for a bare `/`), inside `open_chief` and in all three routes. This
  reverses ticket 06's decision to store the root "as given": the session row, the minted token's
  `project_root` and the spawn `cwd` are now the normalised form. (2) The close route sends
  `TERMINAL_KILL {type, tab_id, run_id}` on topic `chief:<run_id>` (the shape the other stop routes
  use); `_broadcast_runner` mirrors it to `/events/spawn`. It is best effort (a failure is logged,
  the session is closed either way), and only sent when this call closed the session. (3) Folders:
  `chief_startup_cleanup` removes the folder of every session `close_stale_sessions` returns. (4) A
  refused spawn with only `pathly-pty-host` is unchanged: the session closes after `start_timeout` as
  `never started`, and the route still answers 201.
- Close order: the session is closed first (the token is revoked), then the tab is killed, so a
  failed kill never leaves a live token.
- "An agent" is `caller_identity(request).kind == "run"`, i.e. any live run token, the rule of
  `/comms/tasks/floor-allow`. A chief's own token is a live run token, so it is already 403 on open
  and close; an unknown, revoked or absent token counts as a human (the RRP-2b limit, stated in the
  docs).
- Bodies are read with `request.get_json(silent=True)` (what `control/` and `hq/` do), not the comms
  `read_json_body`, which is private to `comms/`. A body that is not a JSON object, or a request
  without a JSON content type, is a 400. `model` may be absent (""), but a present non-string,
  including `null`, is a 400, as the ticket says "not a string".
- `prompt` is required for now, as the ticket says; ticket 17 relaxes it for built-in presets.
- `GET /chief/session` with no `project_root` is a 400 (the ticket did not say).
- The cleanup guards each run id with `_RUN_ID_RE` before removing a folder (the same trust-boundary
  check `close_chief` makes), though ids in the DB are always generated by `open_chief`.
- `app.main()` is tested in a subprocess (about 0.5 s each, `PYTHONPATH=src`, `HOME` and
  `USERPROFILE` set to a temp dir): in the test process `main()` would reset the root logger and the
  middleware globals and start threads.

**Shortcuts taken**

- `chief_startup_cleanup` removes only the folders of the sessions it closes. A folder left behind
  by an earlier close whose `rmtree` failed (logged as a warning) is never swept, so a dead hook
  secret can stay in `~/.pathly/chief/`. It is harmless (the hook route checks the session is open),
  but if it matters, sweep every `chief-<12 hex>` folder under `_chief_root()` at startup, when no
  chief can be open.

**For later tickets**

- Ticket 08 (chief gate): a request's `project_root` must go through `normalise_project_root` before
  it is compared with the token's `project_root` (minted from the normalised form). `/chief/open` and
  `/chief/close` already refuse every live run token, the chief's included; `GET /chief/session` is
  open to any caller, so the gate decides whether the chief may read it.
- Ticket 15: `GET /chief/session` builds its dict by hand in `chief_session_state`; it must gain
  `runs_started`, `max_runs_per_session` and `max_cost_usd_per_run` (spec § Interfaces).
- Ticket 17: the route requires a string `prompt` (`_OPEN_FIELDS` in `chief/session.py`) and
  `open_chief._validate` requires it non-empty; a built-in preset with no `prompt`, and appending the
  `chief-connect` fragment, change one or both. The route passes `body["prompt"]` straight to
  `open_chief`.
- Round two (launcher): on a 409 the body carries the open `run_id` and `tab_id` to show the tab. A
  tab killed by close makes Studio post `/runner/terminal/result` for a dropped run, which answers 404
  (harmless).
