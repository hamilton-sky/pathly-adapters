# Resolve the caller's identity from the X-Pathly-Run-Token header

Type: task
Status: resolved
Blocked by: 03
Test first: yes

Add `src/pathly_orchestrator/http_server/run_identity.py` with
`caller_identity(request) -> CallerIdentity` (SPEC.md § C4):

- `X-Pathly-Run-Token` present and resolving through `db.queries.run_tokens.resolve_run_token` →
  `kind="run"` with `run_id`, `role`, `feature`, `project_root`, `board`, `scope`.
- Header missing, empty, unknown or revoked → `kind="anonymous"`, all other fields `None`. An
  unknown or revoked token is logged once per request at info level with the remote address, so
  going around the wall is visible (SPEC § C5).
- Body fields `role`, `run_id` and `from` are never read.

Imports of `db` stay lazy inside the function (the module is in `http_server/`). The `ui` kind is
reserved in the type for RRP-2b and is never returned yet. Add `X-Pathly-Run-Token` to both CORS
`Access-Control-Allow-Headers` lists in `http_server/middleware.py`.

## Not in this ticket

- Applying a policy from the identity: a later plan (RRP-5).
- Stamping writes: ticket 09.

## Done when

- `python -m pytest tests/http_api/test_caller_identity.py -q` passes and covers: a valid token →
  `run` with the minted role and run; missing, empty, unknown and revoked → `anonymous`; a body
  `role: "human"` with no token → `anonymous`; a CORS preflight allows `X-Pathly-Run-Token`.

```check
$ python -m pytest tests/http_api/test_caller_identity.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C4, § C5
- `src/pathly_orchestrator/http_server/middleware.py` (CORS header lists)
- Ticket 03's Answer

## Answer

**Built**: `src/pathly_orchestrator/http_server/run_identity.py` (`CallerIdentity` frozen dataclass, `caller_identity(request)`, `RUN_TOKEN_HEADER`); `X-Pathly-Run-Token` added to both CORS `Access-Control-Allow-Headers` lists in `http_server/middleware.py`; `tests/http_api/test_caller_identity.py` (committed first as `ce1d8959`, 10 failing on ModuleNotFoundError); regenerated `tests/INDEX.md` and `tests/http_api/INDEX.md`; one `run_identity.py` line in the http_server tree of `src/pathly_orchestrator/CLAUDE.md`.

**Proof**:
- `python -m pytest tests/http_api/test_caller_identity.py -q -p no:cacheprovider` -> 10 passed (valid token -> `run` with run/role/feature/project_root/board/scope; missing and empty -> `anonymous` with every field None; unknown and revoked -> `anonymous` and exactly one info log line carrying the remote address; missing token not logged; body `role:"human"` with no token -> `anonymous`; body fields do not override a token; OPTIONS preflight and normal responses both list `X-Pathly-Run-Token`).
- commands.md Build, Smoke exit 0; Lint (black, file size, mirror reads, test index, lint-imports) exit 0; Test (comms_board, db, runner_supervisor, http_api) -> 926 passed, 2 skipped.

**Decisions**: token header is stripped before use, so whitespace-only counts as empty (anonymous, not logged). The log uses the existing `pathly.http` logger at info. `caller_identity` takes the Flask `request` as an argument (no import of flask at module top) and imports `db` lazily inside the function.

**Shortcuts taken**: none.

**For later tickets**: `from pathly_orchestrator.http_server.run_identity import caller_identity, CallerIdentity`; call it inside a route with `caller_identity(request)`. It does one DB lookup per call and does not cache. Ticket 07 can use `RUN_TOKEN_HEADER`'s value as the header name. Nothing calls `caller_identity` yet.
