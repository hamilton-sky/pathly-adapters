# Architecture Proposal — orchestrator-refactor

## Problem

Four files violate SRP and are too large to navigate safely:

| File | Lines | Problem |
|---|---|---|
| `http_server.py` | 1,784 | Transport + business logic + SSE + runner + FSM + skills all in one |
| `supervisor.py` | 1,263 | State machine + process management + user interaction + SSE emission |
| `runner.py` | 659 | Argv building + output parsing + event mutation + CLI pipeline |
| `db.py` | 607 | Connection mgmt + migrations + 9 query domains in one file |

---

## Target structure

### Decision 1: Package-first, re-export-second

Every file becomes a package with `__init__.py` that re-exports the existing public API unchanged.
**Zero breaking changes for callers** — all existing `from pathly_orchestrator.db import get_db` imports continue to work.

### Decision 2: db/ first (lowest risk, no Flask dependency)

```
src/pathly_orchestrator/db/
  __init__.py           ← re-exports full public API (get_db, append_event, ...)
  connection.py         ← get_db(), _get_write_lock(), _conn_cache, _cache_lock, _write_locks
  migrations.py         ← _run_migrations(), schema SQL strings
  queries/
    fsm_events.py       ← append_event(), read_events(), read_last_agent_done()
    fsm_state.py        ← write_state(), read_state()
    runner_state.py     ← write_runner_state(), read_runner_state(), mark_stale_runners()
    flow_defs.py        ← upsert_flow_definition(), read_flow_definitions()
    skill_defs.py       ← upsert_skill_definition(), read_skill_definitions()
    agent_defs.py       ← upsert_agent_definition(), read_agent_definitions()
    invocations.py      ← write_agent_invocation(), read_agent_invocations()
    overrides.py        ← write_skill_override(), read_skill_override()
```

### Decision 3: runner/ (medium risk, no Flask)

```
src/pathly_orchestrator/runner/
  __init__.py           ← re-exports public API
  argv.py               ← resolve_argv(), resolve_interactive_argv(), _storage_path()
  output.py             ← parse_result(), _extract_json_payload()
  events.py             ← read_last_agent_done(), tail_agent_done(), _patch_last_agent_done()
  history.py            ← build_pipeline_history_block()
  invoke.py             ← invoke_agent()
  cli.py                ← run_flow(), main(), resolve_stage(), handle_blocked(), handle_decide()
```

The lazy import of supervisor in `invoke.py` (for abort callback) is replaced with an
explicit `abort_callback: Callable | None` parameter — removes the bidirectional coupling.

### Decision 4: supervisor/ (high cohesion, split carefully)

```
src/pathly_orchestrator/supervisor/
  __init__.py           ← re-exports public API (start_run, pause_run, ...)
  state.py              ← RunnerState dataclass, OpenSession dataclass
  registry.py           ← _registry dict, _lock, get_state(), recover_stale_mirrors()
  terminal.py           ← _run_stage_via_terminal()
  interactions.py       ← _await_agent_question(), supply_decision(), supply_agent_answer()
  orchestrator.py       ← _loop(), _resolve_stage_supervised(), _agent_done_watcher()
  api.py                ← start_run(), pause_run(), resume_run(), abort_run(), reroute_run()
```

### Decision 5: http_server/ (highest risk — Flask globals must stay accessible)

```
src/pathly_orchestrator/http_server/
  __init__.py           ← exports `app`, `main()` — used by entry point
  app.py                ← Flask app creation, register_blueprint calls, middleware setup
  middleware.py         ← before_request, after_request, rate limiting, CORS
  sse.py                ← SSE infrastructure: _menu_clients, _runner_clients, _clients,
                          _broadcast(), _broadcast_sse(), _broadcast_runner(),
                          _tail_events(), _schedule_push_clear()
  pricing.py            ← MODEL_PRICING dict (extracted from activity recording)
  blueprints/
    health.py           ← GET /health, GET /status, POST /shutdown
    fsm.py              ← POST /next_action, POST /complete_stage
    runner.py           ← POST /runner/start, /pause, /resume, /abort, /advance,
                          /decision, /agent-answer, /reroute, /retry,
                          /terminal/started, /terminal/result, GET /runner/status
    telemetry.py        ← POST /record_activity, POST /record_phase
    skills.py           ← GET /skills/catalog, POST /skills/parse, /preview, PUT /skills/export
    menu.py             ← GET /menu/<name>, GET /metrics
    chat.py             ← POST /chat
    streams.py          ← GET /events/menu, GET /events/runner, GET /events/stream
  feedback.py           ← _feedback_watcher(), _process_feedback_file() (feedback file daemons)
```

The critical constraint: SSE globals (`_menu_clients`, `_runner_clients`) must be importable
from `http_server.sse` by both blueprints and supervisor. Currently they live in `http_server.py`
module scope — moving them to `sse.py` breaks no external contract.

---

## Layer diagram (after refactor)

```
http_server/blueprints/*
      ↓
services/              (no change)
      ↓
supervisor/ + runner/
      ↓
db/                    (no change to public API)
      ↓
seed.py
```

Flask stays in `http_server/` only — blueprints, app factory, SSE.
`supervisor/` and `runner/` have zero Flask imports.
`db/` has zero HTTP/Flask knowledge.

---

## Migration strategy

1. Create package directory alongside the file (`db/` next to `db.py`).
2. Move content into submodules.
3. Write `__init__.py` that re-exports everything the old module exported.
4. Delete the old `.py` file.
5. Run full test suite — must pass with zero changes to callers.

Each conversation handles ONE package. All conversations are independent except
Conv 4 (http_server/) which depends on supervisor/ and runner/ being stable first.
