# Refuse a request whose run token Pathly does not know

Type: task
Status: open
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/run_token_guard.py (new), src/pathly_orchestrator/http_server/app.py, tests/http_api/test_unknown_run_token.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

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
