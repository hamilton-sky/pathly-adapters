# Learnings: chief-agent

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (plan) 400-line ratchet (`scripts/check_file_size.py`): an oversized file may only shrink, a new file may not pass 400. Frozen and touched by this plan: `db/queries/invocation_projection.py` (454), `studio/.../HQ/useHQ.tsx` (874), `db/migrations.py` (438). Near the limit: `runner/comms_context.py` 394, `supervisor/terminal.py` 390, `blueprints/comms/messages_write.py` 386. New code goes in new files; leave a call site.
- (plan) New tables go in a new migration module called from `db/migrations_incremental.py::_add_additive_migrations`; role-read-policy added `db/migrations_provenance.py` the same way.
- (plan) A new HTTP domain is a new package under `http_server/blueprints/` with an `all_blueprints` list, registered in `http_server/app.py` like `comms` and `control`. Update the blueprint domain map in root `CLAUDE.md` and `src/pathly_orchestrator/CLAUDE.md`.
- (plan) A one-off agent spawn already exists: `supervisor/board_run.py::start_board_run` (takes the per-board lock in `supervisor/board_lock.py`, injectable `spawn_fn`, `on_start`/`on_done`). It locks by `(board, scope)`, so a chief turn on the project board would block the evaluator and consolidate there.
- (plan) Run category is a closed set in three places: the projection guard in `db/queries/invocation_projection.py::_agent_done_rec` (`flow|single|loop`), the `category` in the `TERMINAL_SPAWN` payload (`supervisor/terminal.py`), and Studio's TS unions (`types/global.d.ts`, `Monitor/EngineBoard/types.ts`, `CliMonitorBar/types.ts`, `TerminalSpawnListener.tsx`).
- (plan) Agent contracts are stitched per adapter: `director.yaml` exists in `src/pathly_data/adapters/{claude,codex,copilot,antigravity}/_meta/`; a new role needs the same four, then `python scripts/check_adapters.py`.
- (plan) Test basenames must be unique across `tests/`; run `python scripts/gen_test_index.py` after adding one. Import repo paths from `tests/_paths.py`.
