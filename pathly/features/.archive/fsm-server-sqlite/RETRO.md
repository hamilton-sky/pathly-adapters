# Retrospective — fsm-server-sqlite

## What went well

- Clean incremental migration strategy: Conv 1 focused on `http_server.py` writes (3 stories), Conv 2 on `fsm_ops.py` / `fsm.py` / `runner.py` reads (5 stories)
- Strong test coverage maintained throughout: Conv 1 (22 tests), Conv 2 (428 tests), final suite (430 tests, 0 failures)
- Both review passes were PASS with no violations; reviewer confirmed migrations were correct and scoped appropriately
- Tester verified all acceptance criteria without failures, updating `test_observability.py` with `eventlog.read_events`
- Smooth handoff through the pipeline: builder → reviewer → tester, each stage completing as expected

## What could be improved

- No explicit documentation of the eventlog module's API contract in PROGRESS.md or CONVERSATION_PROMPTS.md, which could create friction for future migrations in other features
- Scout phases in Conv 2 took longer than Conv 1, suggesting increasing codebase complexity that wasn't explicitly called out

## What to do differently next time

- Document `eventlog` module public interface (`append_event`, `read_events`, `read_state`, `write_state`) in a shared reference so future migrations use the same spec
- Track "files touched" per conversation in PROGRESS.md — Conv 2 touched 6+ files; explicit counts help forecast builder time
- When `fsm.write_state` (STATE.json-only) and `eventlog.write_state` (SQLite+STATE.json) coexist, document the difference clearly to avoid divergence bugs in future features
