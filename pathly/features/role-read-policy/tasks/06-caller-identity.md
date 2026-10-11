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

**Built**: `src/pathly_orchestrator/http_server/run_identity.py` (`CallerIdentity` dataclass, `caller_identity(request)`); `X-Pathly-Run-Token` added to both CORS `Allow-Headers` strings in `http_server/middleware.py`; `tests/http_api/test_caller_identity.py` (+ regenerated INDEX.md files).

**Proof**: `python -m pytest tests/http_api/test_caller_identity.py -q -p no:cacheprovider` -> 8 passed (valid token -> run; missing/empty/unknown/revoked -> anonymous; body role human with no token -> anonymous; body role does not override token; preflight allows header). The test failed (8 failed) at the test-only commit. Commands.md Test: 916 passed, 2 skipped. check_file_size, lint-imports, gen_test_index --check, black on my files all clean.

**Decisions**: `CallerIdentity` is a frozen dataclass with `kind` Literal incl. reserved `ui`. Empty header skips the DB and is not logged; only a non-empty unresolved token is logged at info with remote_addr.

**Shortcuts taken**: none.

**For later tickets**: import `from ..http_server.run_identity import caller_identity` lazily inside route functions; call `caller_identity(request)` with the Flask request.
