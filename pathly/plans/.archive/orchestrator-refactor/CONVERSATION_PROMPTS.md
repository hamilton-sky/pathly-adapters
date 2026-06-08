# Conversation Prompts — orchestrator-refactor

---

## Conv 1 — db/ package decomposition

**Goal:** Decompose `src/pathly_orchestrator/db.py` into a package with zero API breakage.

**Pre-flight:** Confirm baseline test count: `python -m pytest tests/ -q --tb=no | tail -1`

**Steps:**

1. Create `src/pathly_orchestrator/db/` directory.

2. Create `src/pathly_orchestrator/db/queries/__init__.py` (empty).

3. Create `src/pathly_orchestrator/db/migrations.py`:
   - Move all CREATE TABLE / CREATE INDEX SQL strings and `_run_migrations()`.
   - Import `sqlite3`.

4. Create each query file in `src/pathly_orchestrator/db/queries/`:
   - `fsm_events.py`: `append_event`, `read_events`, `read_last_agent_done`
   - `fsm_state.py`: `write_state`, `read_state`
   - `runner_state.py`: `write_runner_state`, `read_runner_state`, `mark_stale_runners`
   - `flow_defs.py`: `upsert_flow_definition`, `read_flow_definitions`
   - `skill_defs.py`: `upsert_skill_definition`, `read_skill_definitions`
   - `agent_defs.py`: `upsert_agent_definition`, `read_agent_definitions`
   - `invocations.py`: `write_agent_invocation`, `read_agent_invocations`
   - `overrides.py`: `write_skill_override`, `read_skill_override`
   
   Each query file imports `_get_write_lock` from `..connection`.

5. Create `src/pathly_orchestrator/db/connection.py`:
   - Move `_conn_cache`, `_cache_lock`, `_write_locks`, `get_db()`, `_get_write_lock()`.
   - Import `_run_migrations` from `.migrations` and `_seed_if_empty` from the seed module.
   - Import all `upsert_*` / `read_*` / `write_*` / `append_*` from `queries/*` for the connection module to use in get_db's _seed_if_empty call.

6. Create `src/pathly_orchestrator/db/__init__.py`:
   ```python
   from .connection import get_db
   from .queries.fsm_events import append_event, read_events, read_last_agent_done
   from .queries.fsm_state import write_state, read_state
   from .queries.runner_state import write_runner_state, read_runner_state, mark_stale_runners
   from .queries.flow_defs import upsert_flow_definition, read_flow_definitions
   from .queries.skill_defs import upsert_skill_definition, read_skill_definitions
   from .queries.agent_defs import upsert_agent_definition, read_agent_definitions
   from .queries.invocations import write_agent_invocation, read_agent_invocations
   from .queries.overrides import write_skill_override, read_skill_override

   __all__ = [
       'get_db',
       'append_event', 'read_events', 'read_last_agent_done',
       'write_state', 'read_state',
       'write_runner_state', 'read_runner_state', 'mark_stale_runners',
       'upsert_flow_definition', 'read_flow_definitions',
       'upsert_skill_definition', 'read_skill_definitions',
       'upsert_agent_definition', 'read_agent_definitions',
       'write_agent_invocation', 'read_agent_invocations',
       'write_skill_override', 'read_skill_override',
   ]
   ```

7. Delete `src/pathly_orchestrator/db.py`.

8. Run: `python -m pytest tests/ -q --tb=short` — must pass at baseline count.

9. Run: `python -c "from pathly_orchestrator.db import get_db, append_event, read_events; print('OK')"`.

**Do NOT update seed.py or any callers** — the `__init__.py` re-export handles everything.

---

## Conv 2 — runner/ package decomposition

**Goal:** Decompose `src/pathly_orchestrator/runner.py` into a package.
Eliminate the lazy import of `supervisor` inside `invoke_agent()`.

**Pre-flight:** Full test suite passes at baseline count.

**Steps:**

1. Create `src/pathly_orchestrator/runner/` directory.

2. Create `src/pathly_orchestrator/runner/argv.py`:
   - Move: `_storage_path()`, `resolve_argv()`, `resolve_interactive_argv()`

3. Create `src/pathly_orchestrator/runner/output.py`:
   - Move: `_extract_json_payload()`, `parse_result()`

4. Create `src/pathly_orchestrator/runner/events.py`:
   - Move: `read_last_agent_done()`, `tail_agent_done()`, `_patch_last_agent_done()`

5. Create `src/pathly_orchestrator/runner/history.py`:
   - Move: `build_pipeline_history_block()`

6. Create `src/pathly_orchestrator/runner/invoke.py`:
   - Move: `invoke_agent()`
   - **Change signature:** add `abort_callback: Callable[[], bool] | None = None`
   - Remove the lazy `from pathly_orchestrator import supervisor as _sup` block.
   - Replace `_abort_ref._abort_flag` poll with: `abort_callback() if abort_callback else False`
   - Remove the `_abort_ref._proc = proc` line; replace with: `if abort_callback: _proc_ref = proc` passed via the callback if needed.
   
   The clean contract: supervisor passes `abort_callback=lambda: state._abort_flag` when calling invoke_agent.
   Process handle storage: supervisor already holds the proc reference via RunnerState — have invoke_agent accept an optional `proc_callback: Callable[[Any], None] | None = None` that supervisor uses to store the proc on RunnerState.

7. Create `src/pathly_orchestrator/runner/cli.py`:
   - Move: `run_flow()`, `main()`, `resolve_stage()`, `handle_blocked()`, `handle_decide()`

8. Create `src/pathly_orchestrator/runner/__init__.py`:
   Re-export the full public API.

9. Update `src/pathly_orchestrator/supervisor.py` (the existing file, not yet refactored):
   - Update the call site for `invoke_agent` to pass `abort_callback=lambda: state._abort_flag`
   - Update the call site to pass `proc_callback=lambda p: setattr(state, '_proc', p)`

10. Delete `src/pathly_orchestrator/runner.py`.

11. Run: `python -m pytest tests/ -q --tb=short` — must pass at baseline.

---

## Conv 3 — supervisor/ package decomposition

**Goal:** Decompose `src/pathly_orchestrator/supervisor.py` (1,263 lines) into a package.

**Pre-flight:** runner/ package is in place and tests pass.

**Steps:**

1. Create `src/pathly_orchestrator/supervisor/` directory.

2. Create `src/pathly_orchestrator/supervisor/state.py`:
   - Move: `RunnerState` dataclass, `OpenSession` dataclass, all field definitions.

3. Create `src/pathly_orchestrator/supervisor/registry.py`:
   - Move: `_registry`, `_lock`, `get_state()`, `recover_stale_mirrors()`, `_write_mirror()`
   - Imports: `RunnerState` from `.state`, `db` from `pathly_orchestrator`

4. Create `src/pathly_orchestrator/supervisor/terminal.py`:
   - Move: `_run_stage_via_terminal()`
   - Imports: `RunnerState` from `.state`, `runner` from `pathly_orchestrator`

5. Create `src/pathly_orchestrator/supervisor/interactions.py`:
   - Move: `_await_agent_question()`

6. Create `src/pathly_orchestrator/supervisor/orchestrator.py`:
   - Move: `_loop()`, `_resolve_stage_supervised()`, `_agent_done_watcher()`, `_reconciliation_window()`, `_cleanup_run_id()`
   - Imports: `RunnerState` from `.state`, `get_state` from `.registry`, `_run_stage_via_terminal` from `.terminal`

7. Create `src/pathly_orchestrator/supervisor/api.py`:
   - Move: `start_run()`, `pause_run()`, `resume_run()`, `abort_run()`, `supply_decision()`, `supply_agent_answer()`, `reroute_run()`
   - Imports: `RunnerState` from `.state`, `_registry`, `_lock` from `.registry`, `_loop` from `.orchestrator`

8. Create `src/pathly_orchestrator/supervisor/__init__.py`:
   Re-export full public API.

9. Delete `src/pathly_orchestrator/supervisor.py`.

10. Run: `python -m pytest tests/ -q --tb=short` — must pass.

---

## Conv 4 — http_server/ package decomposition

**Goal:** Decompose `src/pathly_orchestrator/http_server.py` (1,784 lines) into a package.

**Pre-flight:** supervisor/ and runner/ packages are in place and tests pass.

**Critical constraint:** `from pathly_orchestrator.http_server import app` must continue to work.
`from pathly_orchestrator.http_server.sse import _runner_clients` must be importable by supervisor.

**Steps:**

1. Create directory structure.

2. Create `src/pathly_orchestrator/http_server/pricing.py`:
   - Extract `MODEL_PRICING` dict (opus, sonnet, haiku rates).

3. Create `src/pathly_orchestrator/http_server/sse.py`:
   - Move all SSE globals: `_menu_clients`, `_runner_clients`, `_clients`, `_tailers`, `_lock`, `_runner_lock`, `_menu_lock`, `_push_timer`, `_push_timer_lock`
   - Move all broadcast helpers: `_broadcast()`, `_broadcast_sse()`, `_broadcast_runner()`, `_tail_events()`, `_schedule_push_clear()`, `_fire_push_clear()`, `_push_menu_to_sse()`

4. Create `src/pathly_orchestrator/http_server/middleware.py`:
   - Move: `_JsonFormatter`, `_setup_logging()`, rate limiting globals (`_RATE_LIMIT_WINDOW`, `_RATE_LIMIT_MAX`, `_rate_counters`, `_rate_lock`), metrics globals (`_metrics`, `_metrics_lock`)
   - Move: `before_request` and `after_request` handler functions (as plain functions; `app.before_request` decorator applied in `app.py`)

5. Create `src/pathly_orchestrator/http_server/feedback.py`:
   - Move: `_classify_content()`, `_has_ttl()`, `_inject_ttl()`, `_process_feedback_file()`, `_feedback_watcher()`

6. Create `src/pathly_orchestrator/http_server/blueprints/health.py` — `GET /health`, `GET /status`, `POST /shutdown`
7. Create `src/pathly_orchestrator/http_server/blueprints/fsm.py` — `POST /next_action`, `POST /complete_stage`
8. Create `src/pathly_orchestrator/http_server/blueprints/runner.py` — all 12 `/runner/*` routes + `_topic_from_body()` + `_append_agent_done_event()`
9. Create `src/pathly_orchestrator/http_server/blueprints/telemetry.py` — `POST /record_activity`, `POST /record_phase`
10. Create `src/pathly_orchestrator/http_server/blueprints/skills.py` — skills catalog/parse/preview/export
11. Create `src/pathly_orchestrator/http_server/blueprints/menu.py` — `GET /menu/<name>`, `GET /metrics`
12. Create `src/pathly_orchestrator/http_server/blueprints/chat.py` — `POST /chat`
13. Create `src/pathly_orchestrator/http_server/blueprints/streams.py` — `GET /events/menu`, `GET /events/runner`, `GET /events/stream`
14. Create `src/pathly_orchestrator/http_server/blueprints/__init__.py` (empty).

15. Create `src/pathly_orchestrator/http_server/app.py`:
    - Create Flask app, register all blueprints, set up middleware hooks, start daemon threads.

16. Create `src/pathly_orchestrator/http_server/__init__.py`:
    ```python
    from .app import app, main
    __all__ = ['app', 'main']
    ```

17. Delete `src/pathly_orchestrator/http_server.py`.
    **Important:** also delete `src/pathly_orchestrator/api/__init__.py` and merge its routes into `http_server/blueprints/` — the Blueprint that was created in studio-backend Conv 4 now lives inside the http_server package.

18. Run: `python -m pytest tests/ -q --tb=short` — must pass.
19. Run: `python -c "from pathly_orchestrator.http_server import app; print('app OK')"`.
20. Start server: `pathly-fsm-http &` then `curl http://127.0.0.1:8765/health` — expect `{"ok": true}`.

---

## Conv 5 — Integration + cleanup

**Goal:** Final sweep, documentation, and confirmation.

**Steps:**

1. Run: `python -m pytest tests/ -q` — assert 472+ tests pass.

2. Run: `python -c "
from pathly_orchestrator.db import get_db, append_event
from pathly_orchestrator.runner import invoke_agent, parse_result
from pathly_orchestrator.supervisor import start_run, get_state
from pathly_orchestrator.http_server import app
print('All imports OK')
"`

3. Grep for any imports of the old deleted files:
   ```bash
   grep -r "from pathly_orchestrator.db import\|import pathly_orchestrator.db" src/ tests/ --include="*.py" | grep -v "__pycache__"
   ```
   (These should all resolve cleanly through the package `__init__.py` — the grep is just confirming no stale absolute-path imports exist.)

4. Update `src/pathly_orchestrator/CLAUDE.md`:
   - Add package structure diagram showing db/, runner/, supervisor/, http_server/ layouts.
   - Note that `from pathly_orchestrator.db import X` still works (re-export).

5. If `src/pathly_orchestrator/api/` still exists as a standalone package (from studio-backend Conv 4), remove it — its routes are now inside `http_server/blueprints/`.

6. Confirm `pathly-fsm-http` entry point in `pyproject.toml` still points to the correct module.
