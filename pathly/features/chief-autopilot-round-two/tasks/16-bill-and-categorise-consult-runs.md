# Bill and categorise consult runs as `consult`

Type: task
Status: open
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
