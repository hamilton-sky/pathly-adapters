# User Stories — orchestrator-refactor

## S1 — db/ package

**S1.1** As a developer, I can import `from pathly_orchestrator.db import get_db, append_event` and get identical behaviour after the refactor, so callers need zero changes.

**S1.2** As a developer, `db/connection.py` owns all connection state (`_conn_cache`, `_cache_lock`, `_write_locks`) so there is one place to change the locking model.

**S1.3** As a developer, `db/queries/` contains one file per entity domain (fsm_events, fsm_state, runner_state, flow_defs, skill_defs, agent_defs, invocations, overrides) so each file is under 100 lines.

**S1.4** All 472 existing tests pass without modification after the db/ refactor.

---

## S2 — runner/ package

**S2.1** As a developer, I can import `from pathly_orchestrator.runner import invoke_agent, parse_result` and get identical behaviour.

**S2.2** `invoke_agent()` no longer imports `supervisor` lazily — it accepts an optional `abort_callback: Callable[[], bool] | None` parameter instead, eliminating the bidirectional coupling.

**S2.3** Argv construction (`argv.py`), output parsing (`output.py`), event mutation (`events.py`), and CLI pipeline (`cli.py`) live in separate files under 150 lines each.

**S2.4** All existing tests pass without modification after the runner/ refactor.

---

## S3 — supervisor/ package

**S3.1** `RunnerState` and `OpenSession` dataclasses live in `supervisor/state.py`.

**S3.2** The registry (`_registry`, `_lock`, `get_state()`) lives in `supervisor/registry.py`.

**S3.3** The pipeline orchestrator (`_loop`, `_resolve_stage_supervised`, `_agent_done_watcher`) lives in `supervisor/orchestrator.py`.

**S3.4** Terminal coordination (`_run_stage_via_terminal`) lives in `supervisor/terminal.py`.

**S3.5** The public API (`start_run`, `pause_run`, `resume_run`, `abort_run`, `supply_decision`, `supply_agent_answer`, `reroute_run`) is re-exported from `supervisor/__init__.py` unchanged.

**S3.6** All existing tests pass without modification after the supervisor/ refactor.

---

## S4 — http_server/ package

**S4.1** `from pathly_orchestrator.http_server import app, main` continues to work — entry point is unchanged.

**S4.2** SSE infrastructure (`_menu_clients`, `_runner_clients`, `_clients`, `_broadcast*`, `_tail_events`) lives in `http_server/sse.py` and is importable by both blueprints and supervisor.

**S4.3** Each blueprint file is under 200 lines: health, fsm, runner, telemetry, skills, menu, chat, streams.

**S4.4** `http_server/pricing.py` holds the `MODEL_PRICING` dict — no hardcoded rates in route handlers.

**S4.5** `http_server/middleware.py` owns rate limiting and request/response logging — testable independently.

**S4.6** All existing tests pass without modification after the http_server/ refactor.

---

## S5 — Integration + cleanup

**S5.1** Full test suite (472+ tests) passes after all four packages are in place.

**S5.2** No `.py` single-file remnants remain alongside the new packages — old files deleted.

**S5.3** `src/pathly_orchestrator/CLAUDE.md` updated to reflect the new package structure.
