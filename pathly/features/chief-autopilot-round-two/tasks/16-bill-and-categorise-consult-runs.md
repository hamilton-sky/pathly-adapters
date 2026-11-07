# Bill and categorise consult runs as `consult`

Type: task
Status: resolved
Blocked by: 02
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/supervisor/terminal.py, src/pathly_orchestrator/supervisor/terminal_reconcile.py, src/pathly_orchestrator/supervisor/terminal_identity.py, src/pathly_orchestrator/fsm_compose_vars.py, src/pathly_orchestrator/db/queries/invocation_projection.py, tests/telemetry/test_consult_billing.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/telemetry/INDEX.md

Split from ticket 02. "Consult spawns are billed and appear in the Monitor like any other run, with
their own run category." Ticket 02's `start_consult` spawns with `flow="consult"` and substitutes
`<run_category>` with `consult`; the rest of the telemetry path knows only `flow | single | loop`,
so today the category is dropped to NULL and the run token's role is unresolved.

1. `fsm_compose_vars._inject_prompt_vars`: its docstring lists `consult` among the run types. Add a
   small helper beside it, `spawn_category(flow: str) -> str` (`consult` for `consult`, `single`
   for `board-run`, else `flow`), and use it for the `TERMINAL_SPAWN` payload's `category` in
   `terminal._run_stage_via_terminal` (search `"category": "single" if`). `terminal.py` is at 398
   lines: the call replaces the inline expression, so the file does not grow.
2. `terminal_reconcile._synthesize_agent_done_if_missing` stamps `consult` for
   `flow == "consult"` (search `"loop" if (state.flow or "").lower() == "goal-loop"`), so a consult
   whose agent wrote no `AGENT_DONE` still gets a billed row.
3. `invocation_projection._agent_done_rec`'s category guard accepts `consult` (edit the tuple
   `("flow", "single", "loop")` in place: the file is at its ratchet baseline, the edit is
   line-neutral).
4. `terminal_identity._spawn_role` returns `current_state` for `flow == "consult"` as it does for
   `board-run` (search `== "board-run"`), so the consult's run token names the role.

Document the `consult` category in `src/pathly_orchestrator/CLAUDE.md` (the telemetry run-type
paragraph lists `flow` / `single` / `loop`).

## Not in this ticket

- Studio's Monitor showing the category: ticket 10. `GET /runs` kind `consult`: ticket 09.
- The 403 on a consult's own answer post: ticket 17.

## Done when

- `python -m pytest tests/telemetry/test_consult_billing.py -q -p no:cacheprovider` passes and
  covers, driving `start_consult` with a fake `spawn_fn` (round one learnings 05: driving a whole
  board spawn): the `TERMINAL_SPAWN` payload's `category` is `consult`; a consult whose agent writes
  its `AGENT_DONE` with `category: consult` and one that writes none both leave exactly one
  `agent_invocations` row with category `consult` and the `BILLING_UPDATE`'s cost folded in; the
  run token minted for the consult has the asked role; `spawn_category("board-run")` is still
  `single` and `spawn_category("team-build")` is `flow`.
- `python scripts/check_file_size.py` passes (no file grew past its limit or baseline).
- All existing tests under `tests/telemetry` and `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/telemetry/test_consult_billing.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
$ python -m pytest tests/telemetry tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Consult run identity")
- root `CLAUDE.md` § Telemetry ("Every run gets a row", "Run TYPE is a stamped column")
- round one learnings (05): driving a whole board spawn in a test

## Answer

Work started at `81a9a6025a099316fd8edbb9467afb2fd4530ec1` (built on HEAD `30c7d1c`, a tree-same
merge of master on top). Test-only commit `58209df`: at that commit
`tests/telemetry/test_consult_billing.py` fails 6 of 6 (TERMINAL_SPAWN `category` is `'flow'`, the
consult's run-token role is `None`, `cannot import name 'spawn_category'`). The test file was
re-formatted by `black` in the code commit (one wrapped line, no assertion changed).

**Built**

- `src/pathly_orchestrator/fsm_compose_vars.py`: `spawn_category(flow)` (`consult` -> `consult`,
  `board-run` -> `single`, else `flow`) beside `_inject_prompt_vars`, whose docstring now lists
  `consult`.
- `src/pathly_orchestrator/supervisor/terminal.py`: the `TERMINAL_SPAWN` payload's `category` is
  `spawn_category(state.flow or "")` (top-level import; `fsm_compose_vars` imports only `re` and
  `pathlib` at top). Still 398 lines.
- `src/pathly_orchestrator/supervisor/terminal_reconcile.py`: the synthetic `AGENT_DONE` stamps
  `consult` for `flow == "consult"` (`loop` for goal-loop, else `single`, as before).
- `src/pathly_orchestrator/db/queries/invocation_projection.py`: the category guard accepts
  `consult` (line-neutral, 454 lines, at its baseline).
- `src/pathly_orchestrator/supervisor/terminal_identity.py`: `_spawn_role` returns
  `current_state` for `consult` as for `board-run`.
- `src/pathly_orchestrator/CLAUDE.md`: the projection's `category` note lists `consult` and says
  where it is stamped.
- `tests/telemetry/test_consult_billing.py` (new, 3 functions / 6 cases); `tests/INDEX.md`,
  `tests/telemetry/INDEX.md` regenerated.

**Proof (fresh, after the last edit)**

- `python -m pytest tests/telemetry/test_consult_billing.py -q -p no:cacheprovider`: `6 passed`,
  exit 0. It drives `start_consult(..., block=True)` with a `spawn_fn` that calls the real
  `consult_run._default_spawn` (so the real `_run_stage_via_terminal`) with a broadcast acting as
  the spawn host (records the payload and `lookup_run_token` of its `run_token`, optionally writes
  the agent's `AGENT_DONE` with `category: consult`, then `mark_started` + `mark_pty_result` with
  `cost_usd 0.42`), early-advance off so the slow path writes the synthetic `AGENT_DONE` and the
  `BILLING_UPDATE` before it returns. Covers: payload `category == "consult"`; with and without the
  agent's `AGENT_DONE`, exactly one `agent_invocations` row for the run, category `consult`,
  `cost_usd == 0.42`; the token's `run_id` is the consult's and its `role` is the asked `tester`;
  `spawn_category` of `consult`/`board-run`/`team-build` is `consult`/`single`/`flow`.
- `python scripts/check_file_size.py`: `OK: 1074 source files checked; 16 known over 400 lines,
  none new, none grown.`, exit 0.
- `python -m pytest tests/telemetry tests/runner_supervisor -q -p no:cacheprovider`: `581 passed`,
  exit 0.
- Lint chain from `commands.md` (black, mypy, file size, mirror reads, index check, lint-imports,
  bandit, adapters, entry points): exit 0.
- Also `python -m pytest tests/comms_board tests/db tests/http_api tests/dag_goals tests/fsm_flows tests/consistency -q -x -p no:cacheprovider`
  (the rest of Quick): `5435 passed, 11 skipped`, exit 0.

**Decisions**

- The test uses the real spawn path rather than a fake that only writes events, so the payload,
  the token and the billing all come from production code; the slow path (`PATHLY_RUNNER_EARLY_ADVANCE=0`)
  keeps it deterministic (no reconciliation thread outliving the test).
- `terminal_reconcile` uses a small dict lookup instead of a nested conditional: same line count.

**Shortcuts taken**: none.

**For later tickets**

- The root `CLAUDE.md` § Telemetry ("Run TYPE is a stamped column") still lists `flow` / `single` /
  `loop` only; it is not in this ticket's Touches. Ticket 10 (Monitor showing the category) or a
  doc pass should add `consult` there, and `useRecentEngines` must accept `consult` as a bucket.
