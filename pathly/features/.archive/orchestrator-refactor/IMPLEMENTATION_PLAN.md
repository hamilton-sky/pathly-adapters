# Implementation Plan — orchestrator-refactor

**Rigor:** standard  
**Conversations:** 5  
**Risk order:** low → high (db first, http_server last)

---

## Decision log

1. **Re-export-first** — every new package `__init__.py` re-exports the old module's full public API so callers have zero changes to make.
2. **No logic in `__init__.py`** — `__init__.py` only contains imports from submodules, never function bodies.
3. **Delete old `.py` file** at the end of each conversation — Python will shadow the old file with the new package directory; deleting removes ambiguity.
4. **One package per conversation** — independent refactors, each verified by full test suite before the next begins.
5. **runner/ before supervisor/** — supervisor imports from runner; runner must be stable first.
6. **http_server/ last** — depends on SSE globals staying accessible from a known path; refactor only after supervisor/ is stable.
7. **abort_callback injection** — `invoke_agent()` receives `abort_callback: Callable[[], bool] | None = None` instead of lazily importing supervisor. Supervisor passes a lambda wrapping RunnerState._abort_flag.

---

## Phase 1 — db/ package (Conv 1, stories S1.1–S1.4)

**Scope:** Decompose `src/pathly_orchestrator/db.py` (607 lines) into a package.

**Files to create:**
- `src/pathly_orchestrator/db/__init__.py` — re-export all 20 public functions
- `src/pathly_orchestrator/db/connection.py` — `get_db()`, `_get_write_lock()`, `_conn_cache`, `_cache_lock`, `_write_locks`
- `src/pathly_orchestrator/db/migrations.py` — `_run_migrations()`, all CREATE TABLE SQL
- `src/pathly_orchestrator/db/queries/fsm_events.py` — `append_event()`, `read_events()`, `read_last_agent_done()`
- `src/pathly_orchestrator/db/queries/fsm_state.py` — `write_state()`, `read_state()`
- `src/pathly_orchestrator/db/queries/runner_state.py` — `write_runner_state()`, `read_runner_state()`, `mark_stale_runners()`
- `src/pathly_orchestrator/db/queries/flow_defs.py` — `upsert_flow_definition()`, `read_flow_definitions()`
- `src/pathly_orchestrator/db/queries/skill_defs.py` — `upsert_skill_definition()`, `read_skill_definitions()`
- `src/pathly_orchestrator/db/queries/agent_defs.py` — `upsert_agent_definition()`, `read_agent_definitions()`
- `src/pathly_orchestrator/db/queries/invocations.py` — `write_agent_invocation()`, `read_agent_invocations()`
- `src/pathly_orchestrator/db/queries/overrides.py` — `write_skill_override()`, `read_skill_override()`
- `src/pathly_orchestrator/db/queries/__init__.py` — empty (just makes it a package)

**Files to delete:** `src/pathly_orchestrator/db.py` (after package is in place and tests pass)

**Verify:** `python -m pytest tests/ -q` — must match baseline pass count.

---

## Phase 2 — runner/ package (Conv 2, stories S2.1–S2.4)

**Scope:** Decompose `src/pathly_orchestrator/runner.py` (659 lines) into a package.

**Files to create:**
- `src/pathly_orchestrator/runner/__init__.py` — re-export public API
- `src/pathly_orchestrator/runner/argv.py` — `resolve_argv()`, `resolve_interactive_argv()`, `_storage_path()`
- `src/pathly_orchestrator/runner/output.py` — `parse_result()`, `_extract_json_payload()`
- `src/pathly_orchestrator/runner/events.py` — `read_last_agent_done()`, `tail_agent_done()`, `_patch_last_agent_done()`
- `src/pathly_orchestrator/runner/history.py` — `build_pipeline_history_block()`
- `src/pathly_orchestrator/runner/invoke.py` — `invoke_agent(abort_callback=None)` (lazy supervisor import removed)
- `src/pathly_orchestrator/runner/cli.py` — `run_flow()`, `main()`, `resolve_stage()`, `handle_blocked()`, `handle_decide()`

**Key change:** `invoke_agent()` signature gains `abort_callback: Callable[[], bool] | None = None`.
Update `supervisor.py` caller to pass `lambda: state._abort_flag` instead of relying on the lazy import.

**Files to delete:** `src/pathly_orchestrator/runner.py`

**Verify:** Full test suite passes.

---

## Phase 3 — supervisor/ package (Conv 3, stories S3.1–S3.6)

**Scope:** Decompose `src/pathly_orchestrator/supervisor.py` (1,263 lines) into a package.

**Files to create:**
- `src/pathly_orchestrator/supervisor/__init__.py` — re-export public API
- `src/pathly_orchestrator/supervisor/state.py` — `RunnerState`, `OpenSession` dataclasses
- `src/pathly_orchestrator/supervisor/registry.py` — `_registry`, `_lock`, `get_state()`, `recover_stale_mirrors()`, `_write_mirror()`
- `src/pathly_orchestrator/supervisor/terminal.py` — `_run_stage_via_terminal()`
- `src/pathly_orchestrator/supervisor/interactions.py` — `_await_agent_question()`
- `src/pathly_orchestrator/supervisor/orchestrator.py` — `_loop()`, `_resolve_stage_supervised()`, `_agent_done_watcher()`, `_reconciliation_window()`, `_cleanup_run_id()`
- `src/pathly_orchestrator/supervisor/api.py` — `start_run()`, `pause_run()`, `resume_run()`, `abort_run()`, `supply_decision()`, `supply_agent_answer()`, `reroute_run()`

**Files to delete:** `src/pathly_orchestrator/supervisor.py`

**Verify:** Full test suite passes.

---

## Phase 4 — http_server/ package (Conv 4, stories S4.1–S4.6)

**Scope:** Decompose `src/pathly_orchestrator/http_server.py` (1,784 lines) into a package.

**Files to create:**
- `src/pathly_orchestrator/http_server/__init__.py` — exports `app`, `main()`
- `src/pathly_orchestrator/http_server/app.py` — Flask app creation, register_blueprint calls, daemon thread startup
- `src/pathly_orchestrator/http_server/middleware.py` — `before_request`, `after_request`, `_JsonFormatter`, `_setup_logging()`, rate limiting globals
- `src/pathly_orchestrator/http_server/sse.py` — all SSE globals and broadcast helpers: `_menu_clients`, `_runner_clients`, `_clients`, `_tailers`, `_lock`, `_runner_lock`, `_menu_lock`, `_broadcast()`, `_broadcast_sse()`, `_broadcast_runner()`, `_tail_events()`, `_schedule_push_clear()`
- `src/pathly_orchestrator/http_server/pricing.py` — `MODEL_PRICING` dict
- `src/pathly_orchestrator/http_server/feedback.py` — `_feedback_watcher()`, `_process_feedback_file()`, `_classify_content()`, `_has_ttl()`, `_inject_ttl()`
- `src/pathly_orchestrator/http_server/blueprints/__init__.py` — empty
- `src/pathly_orchestrator/http_server/blueprints/health.py` — `GET /health`, `GET /status`, `POST /shutdown`
- `src/pathly_orchestrator/http_server/blueprints/fsm.py` — `POST /next_action`, `POST /complete_stage`
- `src/pathly_orchestrator/http_server/blueprints/runner.py` — all 12 `/runner/*` routes
- `src/pathly_orchestrator/http_server/blueprints/telemetry.py` — `POST /record_activity`, `POST /record_phase`
- `src/pathly_orchestrator/http_server/blueprints/skills.py` — skills catalog/parse/preview/export
- `src/pathly_orchestrator/http_server/blueprints/menu.py` — `GET /menu/<name>`, `GET /metrics`
- `src/pathly_orchestrator/http_server/blueprints/chat.py` — `POST /chat`
- `src/pathly_orchestrator/http_server/blueprints/streams.py` — `GET /events/menu`, `GET /events/runner`, `GET /events/stream`

**Files to delete:** `src/pathly_orchestrator/http_server.py`

**Verify:** Full test suite passes. Start server, hit `GET /health` → 200.

---

## Phase 5 — Integration + cleanup (Conv 5, stories S5.1–S5.3)

**Scope:** Final verification, update CLAUDE.md, confirm no orphan imports.

**Tasks:**
1. Run full test suite; assert 472+ pass.
2. Grep for any remaining imports of the deleted `.py` files — none should exist.
3. Update `src/pathly_orchestrator/CLAUDE.md` with new package structure diagram.
4. Confirm `pathly-fsm-http` entry point still starts correctly.
5. Run `python -c "from pathly_orchestrator import db, supervisor, runner; from pathly_orchestrator.http_server import app"` — all must import cleanly.
