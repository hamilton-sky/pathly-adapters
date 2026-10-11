# Learnings: role-read-policy

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (plan) The 400-line ratchet (`scripts/check_file_size.py`) fails if a file over 400 lines grows or a new file passes 400. Near the limit: `runner/comms_context.py` 394, `supervisor/terminal.py` 390, `studio/src/main/ipc/terminal.ts` 391, `blueprints/comms/messages_write.py` 386, `blueprints/comms/messages_crud.py` 382. `db/migrations.py` (438) is in the baseline and may only shrink. Put new code in new files; leave a call site behind.
- (plan) New schema goes in a new module called from `db/migrations_incremental.py::_add_additive_migrations`, never in `db/migrations.py`.
- (plan) Test file basenames must be unique across all of `tests/` (no `__init__.py`); a clash only shows in a full run. After adding a test run `python scripts/gen_test_index.py` and commit the regenerated `INDEX.md`.
- (plan) Import repo paths from `tests/_paths.py` (`REPO_ROOT`, `SRC`), never `Path(__file__).parent.parent`.
- (plan) Layer rule is enforced by `lint-imports`: `db` imports nothing internal, `runner` → `db`, `supervisor` → `db`, `runner`; `http_server` may import all, but only lazily inside route functions.
- (plan) A spawn's identity is opened at ONE chokepoint: `supervisor/terminal_identity.py::_record_spawn_identity`, called from `supervisor/terminal.py` before the `TERMINAL_SPAWN` payload is built. Studio receives the payload in `renderer/.../TerminalSpawnListener.tsx` and registers runner tabs through the `terminal:register-runner` IPC; `pty_host/host.py::_child_env` builds the headless env.
- (plan) The Pathly server, if it runs during a build, writes `STATE.json`/`BOARD.json` exports under `pathly/features/`. Do not commit them as part of a ticket; the floor guard counts any change under the plans folder outside your own ticket, `map.md` and `learnings.md`.
- (01) `black --check src/ tests/` already fails on 4 codeintel-related files at the base commit; check only your own files. Full 4-domain Test takes ~3 min: run it in background.
- (02) Stored board_scope keys embed project_root, so resolve_read_policy needs project_root= (default '' misses real rows). Test-only commit: gen_test_index before committing tests.
- (03) Test DB fixture is autouse; use get_db() directly in tests/db. black reformats new files on first run — run it before the test-only commit.
- (04) Test a spawn without a PTY: call `_run_stage_via_terminal` with a broadcast_fn that raises on TERMINAL_SPAWN; the finally settles. `supervisor/orchestrator.py` is now exactly 400 lines.
