# Refuse a request whose run token Pathly does not know

Type: task
Status: open
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/run_token_guard.py (new), src/pathly_orchestrator/http_server/app.py, src/pathly_orchestrator/http_server/chief_gate.py, tests/http_api/test_chief_gate.py, tests/http_api/test_chief_routes.py, tests/http_api/test_floor_allow_route.py, tests/comms_board/test_comms_provenance.py, tests/comms_board/test_comms_edit_restamp.py, tests/comms_board/test_rrp_acceptance.py, tests/http_api/chief_audit_support.py, tests/http_api/test_unknown_run_token.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

The review's M1. `src/pathly_orchestrator/http_server/chief_gate.py::chief_gate` acts only on a
live chief token; a request with no token, an unknown token or a revoked one passes untouched and
is treated as anonymous, which on loopback may do everything (`src/pathly_orchestrator/http_server/middleware.py`). So a
token leaked from a finished run, or an invented one, is a way around the chief gate (and
`pathly api` sends whatever `PATHLY_RUN_TOKEN` holds, `chief_cli.py::_api`).

Add a `before_request` check in a new `http_server/run_token_guard.py`, registered in `app.py`
before the chief gate: a request that carries `X-Pathly-Run-Token` whose value does not resolve to
a live token (`src/pathly_orchestrator/db/queries/run_tokens.py`: unknown, or `revoked_at` set) gets 401
`{"error": "unknown run token"}`. A request with no header is unchanged (anonymous, as today), and
so is a live token of any role.

Check every caller Pathly ships: the fragments in `src/pathly_data/core/skills/fragments/` send
`$PATHLY_RUN_TOKEN` (set only while the spawn's token is live), the hooks in `src/pathly_hooks/`,
`pathly-fsm-call` and Studio. Name in the Answer any that can send a stale token (for example an
agent still running after its run's token was revoked) and what it now gets.

## Not in this ticket

- Requiring a token on routes that take none today: the anonymous loopback path stays.

## Done when

- `python -m pytest tests/http_api/test_unknown_run_token.py -q -p no:cacheprovider` passes and
  covers: an invented token and a revoked one are 401 on a GET, on `/comms/post` and on
  `/chief/human-messages`; no header is unchanged; a live builder and a live chief token are
  unchanged; a chief whose token was revoked at close gets 401 (already true) and a request with
  the token header empty is treated as no header.
- All existing `tests/http_api`, `tests/comms_board` and `tests/fsm_flows` tests still pass
  (`tests/fsm_flows/test_human_escalation_gate.py` sends run tokens).

```check
$ python -m pytest tests/http_api/test_unknown_run_token.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api tests/comms_board tests/fsm_flows -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Unknown run tokens"), review M1
- `src/pathly_orchestrator/http_server/run_identity.py::caller_identity`

## Answer

## Footprint change (before the build)

A scout found existing tests that pin today's rule (an invented or revoked token passes as
anonymous): `test_chief_gate.py` (the "nope" and revoked-builder cases), `test_chief_routes.py`
(`"not-a-token"` on `/chief/open`), `test_floor_allow_route.py`, `test_comms_provenance.py` and
`test_comms_edit_restamp.py` (revoked tokens). They contradict this ticket, so with the person's OK
of 2026-10-29 for footprint misses `Touches:` now names them and `chief_gate.py` (its docstring
says unknown tokens pass untouched). Update each to the new rule: expect 401 where the token is
invented or revoked, or drop the header where the test is about an anonymous caller. Never delete
or skip one.

## Attempt note

Attempt 1 (started at 4597c16f). Built and committed: the guard
(`src/pathly_orchestrator/http_server/run_token_guard.py`, registered in `app.py` between
`_log_request` and `chief_gate`; it calls `forget_run_slot()` before refusing, logs at info, and
leaves a revoked `chief` token to `chief_gate` so that one keeps its 401 `chief session closed`),
the `chief_gate.py` docstring, `src/pathly_orchestrator/CLAUDE.md`, the new
`tests/http_api/test_unknown_run_token.py` (9 passed) and the five pinned tests in `Touches:`
updated to the new rule. Lint passes; `tests/runner_supervisor` and `tests/dag_goals` pass (587).

Blocked: `python -m pytest tests/http_api tests/comms_board tests/fsm_flows` fails on a test
outside `Touches:` that pins the old rule:
`tests/comms_board/test_rrp_acceptance.py::test_token_resolves_to_none_once_the_spawn_settles`
posts with the builder's revoked token and asserts 200 + `author_source="none"` ("a run that
outlives its token still gets its post stored, but unverified"); it now gets 401
`unknown run token`. Needed: add `tests/comms_board/test_rrp_acceptance.py` to `Touches:` so the
last two lines of that test become "the late post is 401 `unknown run token` and stores nothing".

Pre-existing, not this ticket: `tests/http_api/test_chief_gate_audit.py::test_a_chief_touches_nothing_outside_its_project[operator]`
fails the same way with this ticket's code stashed (an `open` of `.../server/pipe:[N]` during
`POST /comms/features/decompose adapter='..'`).

Callers that can send a stale token (for the Answer once resolved): only agent processes send the
header, from `$PATHLY_RUN_TOKEN` (the fragments' curl calls, `pathly api` in `chief_cli.py`, the
board-run and catalog prompt text); Studio (`spawnEnv.ts` only sets the env var), the hooks in
`src/pathly_hooks/` and `pathly-fsm-call` send none. A process still running after its spawn
settled (a backgrounded child of a headless agent) or a chief tab's `pathly api` after close now
gets 401 instead of acting as anonymous.

## Footprint change (attempt 2)

Attempt 1 found one more test that pins the old rule: `tests/comms_board/test_rrp_acceptance.py::test_token_resolves_to_none_once_the_spawn_settles`
posts with a revoked builder token and expects 200. With the person's OK of 2026-10-29 for
footprint misses, `Touches:` now names it; its last lines expect the 401.

`tests/http_api/test_chief_gate_audit.py::test_a_chief_touches_nothing_outside_its_project[operator]`
fails whenever it is the first test in its process to import torch (it does here, on master too,
inside this ticket's check run): `ctypes.util.find_library` runs `ldconfig` through a pipe during
the audited decompose request, and `_fd_path` in `tests/http_api/chief_audit_support.py` returns
readlink's `pipe:[N]` text, which is then joined to the cwd as if it were a file. Its `_absolute()`
docstring already says a descriptor the platform cannot name is None. So `Touches:` also names
`chief_audit_support.py`: make `_fd_path` return None for a readlink target that is not an absolute
path (`pipe:`, `socket:`, `anon_inode:`), with a test of that next to the existing audit tests if
one fits in the file.
