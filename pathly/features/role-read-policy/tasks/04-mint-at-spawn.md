# Mint a run token at spawn, send it in the TERMINAL_SPAWN payload, revoke it when the spawn ends

Type: task
Status: resolved
Blocked by: 03
Test first: yes

Every runner, board and goal spawn passes `supervisor/terminal_identity.py::_record_spawn_identity`
before `supervisor/terminal.py` builds the `TERMINAL_SPAWN` payload. Mint the token there:

- In `terminal_identity.py`, add `_mint_spawn_token(state, run_id, role, slug, board_scope) ->
  str | None` that calls `db.queries.run_tokens.mint_run_token` with the run's role (the Pathly
  role the stage runs as: `state` already knows the current stage; board runs carry their role in
  the board-run state), feature slug, project root, board and scope. Best-effort like the identity
  row: on any error log at debug and return `None`; a spawn never fails because of the token.
- In `_settle_spawn_identity`, revoke the run's tokens (`revoke_run_tokens`).
- In `supervisor/terminal.py`, add `"run_token": <token or None>` to the `TERMINAL_SPAWN` payload.
  `terminal.py` is 390 lines and must stay at or under 400: keep the call site to a couple of
  lines and put any logic in `terminal_identity.py`.

The role for each kind of spawn is the part to get right; write in the Answer which field each
kind reads it from (FSM stage, loop task, board run, decompose).

## Not in this ticket

- Putting the token into the child process env: ticket 05.
- Using the token on requests: ticket 06.

## Done when

- `python -m pytest tests/runner_supervisor/test_spawn_run_token.py -q` passes and covers: an FSM
  stage spawn's payload has a `run_token` that resolves to that `run_id` and the stage's role; a
  board run's token resolves to the board run's role and `(board, scope)`; after the spawn settles
  the token resolves to `None`; a DB error while minting leaves `run_token: None` and the spawn
  still goes out.
- `supervisor/terminal.py` is at most 400 lines.
- `tests/runner_supervisor/test_run_identity_stamps.py` still passes.

```check
$ python -m pytest tests/runner_supervisor/test_spawn_run_token.py tests/runner_supervisor/test_run_identity_stamps.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "print('terminal.py lines ok:', sum(1 for _ in open('src/pathly_orchestrator/supervisor/terminal.py',encoding='utf-8')) <= 400)"
prints terminal.py lines ok: True
```

## Reference

- SPEC.md § C4 (spawn-issued token; the open item about a record written at spawn is answered by
  `run_tokens`)
- `src/pathly_orchestrator/supervisor/terminal_identity.py`, `supervisor/terminal.py` (payload),
  `supervisor/board_run.py`, `supervisor/task_prompt.py` (where role is known)
- Ticket 03's Answer

## Answer

**Built**: `supervisor/terminal_identity.py` (`_spawn_role`, `_mint_spawn_token`; `_settle_spawn_identity` now revokes the run's tokens first, even when the identity row was skipped); `supervisor/terminal.py` (+3 lines: mint call, import, `"run_token"` in payload; now 393 lines); `supervisor/state.py` (new `agent_role` field); `supervisor/orchestrator.py` (one line setting `state.agent_role` from the FSM response; file is now exactly 400); new `tests/runner_supervisor/test_spawn_run_token.py` plus regenerated INDEX.md files.

**Proof**: `pytest test_spawn_run_token.py test_run_identity_stamps.py` -> 10 passed (4 new). terminal.py lines check printed `terminal.py lines ok: True`. `check_file_size.py` OK none grown; `lint-imports` 1 kept 0 broken. Ticket Test command: 906 passed, 2 skipped. The test-only commit bba56ed failed before the code (no `agent_role` field).

**Decisions**: role per spawn kind: FSM stage -> `state.agent_role`, set in `orchestrator.py` from the FSM `/next_action` response `agent` (the stage's real role; `current_state` is an FSM state name like BUILDING, not a role). Loop task (flow `goal-loop`, no agent_role) -> `builder`, matching `task_prompt._TASK_ROLE`. Board run (single-agent, evaluator, decompose via board-run flow) -> `current_state`, which `board_run._default_spawn` sets to the selected agent or mode. Feedback re-spawns reuse the stage's agent_role (target agent not used). Anything else -> None. Board = `state.scope_tier`, scope = issued board scope, feature = storage slug.

**Shortcuts taken**: feedback-loop spawns (`target_agent`) carry the stage role, not the target agent's, and a board run with no agent gets the mode name (e.g. `single-agent`) as role. Matters once reads are enforced; fix by passing the role into those spawns.

**For later tickets**: ticket 05 reads `payload["run_token"]` (may be None). `orchestrator.py` is at 400 lines, no room left. Tokens are revoked in `_settle_spawn_identity`, which runs in the spawn's finally.
