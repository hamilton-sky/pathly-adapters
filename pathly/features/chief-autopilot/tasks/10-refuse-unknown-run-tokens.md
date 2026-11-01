# Refuse a request whose run token Pathly does not know

Type: task
Status: resolved
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

**Built** (attempt 1, b340adf4 + d027287c; attempt 2, b56b28e6 + this commit):
- `src/pathly_orchestrator/http_server/run_token_guard.py` (new): a `before_request` hook,
  registered in `app.py` between `_log_request` and `chief_gate`. A non-empty
  `X-Pathly-Run-Token` that is never minted, or revoked, gets 401 `{"error": "unknown run token"}`
  (after `forget_run_slot()`, logged at info). A revoked `chief` token is left to `chief_gate`,
  which keeps its 401 `{"error": "chief session closed"}`. No header, an empty header and any live
  token pass on unchanged.
- `chief_gate.py` docstring and `src/pathly_orchestrator/CLAUDE.md` describe the new rule.
- Tests pinning the old rule updated to it (401 for an invented or revoked token, no header for an
  anonymous caller): `test_chief_gate.py`, `test_chief_routes.py`, `test_floor_allow_route.py`,
  `test_comms_provenance.py`, `test_comms_edit_restamp.py`, and now `test_rrp_acceptance.py`
  (`test_token_resolves_to_none_once_the_spawn_settles`: the late post is 401 `unknown run token`
  and stores nothing).
- `tests/http_api/test_unknown_run_token.py` (new, 10 tests), plus `tests/http_api/INDEX.md`.
- `tests/http_api/chief_audit_support.py::_fd_path`: a readlink target that is not an absolute
  path (`pipe:[N]`, `socket:[N]`, `anon_inode:...`) is None, so `_absolute()` no longer joins it to
  the cwd. Pinned by `test_the_audit_does_not_read_a_pipe_as_a_file_in_the_cwd` (`os.pipe()`).

**Proof**:
- `python -m pytest tests/http_api/test_unknown_run_token.py -q -p no:cacheprovider`: 10 passed,
  exit 0 (invented and revoked tokens 401 on `GET /db/settings`, `/comms/post`,
  `/chief/human-messages`; nothing written; no header and empty header anonymous; live builder and
  live chief unchanged; a chief revoked at close 401). At b56b28e6 the pipe test failed with
  `assert 'pipe:[89228]' is None`, the rest passed.
- `python -m pytest tests/http_api tests/comms_board tests/fsm_flows -q -p no:cacheprovider`:
  4726 passed, 9 skipped, exit 0 (a first run had one failure, `test_build_proof_acceptance.py::test_6_dependent_task_prompt_carries_its_dependency_result`, a timing flake: that harness sends no run token, the file passes alone and `tests/fsm_flows` passed 3 runs of 3; the rerun was clean).
- `python -m pytest tests/http_api/test_chief_gate_audit.py -k operator`: 1 passed.
- Lint chain from commands.md: exit 0.

**Decisions**:
- A revoked chief token keeps `chief session closed` (left to `chief_gate`) rather than the
  generic `unknown run token`: `test_chief_gate.py::test_a_revoked_chief_token_gets_401` pins that body.
- The guard runs after `_log_request` and before `chief_gate`, so the gate never sees a dead token.
- `_fd_path` treats any non-absolute readlink result as unnamed, the meaning `_absolute()`'s
  docstring already gave it; macOS `F_GETPATH` is unchanged.

**Callers that can send a stale token**: only agent processes send the header, from
`$PATHLY_RUN_TOKEN` (the fragments' curl calls in `src/pathly_data/core/skills/fragments/`,
`pathly api` in `chief_cli.py::_api`, the board-run and catalog prompt text). Studio
(`spawnEnv.ts` only sets the env var), the hooks in `src/pathly_hooks/` and `pathly-fsm-call` send
none. A process still running after its spawn settled (a backgrounded child of a headless agent)
and a chief tab's `pathly api` after close now get 401 instead of acting as anonymous.

**Shortcuts taken**: none.

**For later tickets**: any test that posts with a revoked or invented token now gets 401; send no
header for an anonymous caller. `test_chief_gate_audit.py[operator]` failed only when it was the
first test in its process to import torch; it is fixed in the support module, not the test.

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
