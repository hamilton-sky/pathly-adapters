# Implementation Plan — fsm-server-sqlite

## Objective

Migrate the remaining file-based reads/writes in the FSM HTTP server layer to SQLite via the existing `db.py` module. All writes currently going to `EVENTS.jsonl` or `STATE.json` directly (bypassing `db.py`) are routed through `db.py`. Backward compatibility is preserved for legacy feature dirs that have no `pathly.db`.

## Current state (pre-migration)

The following locations still bypass `db.py`:

| Location | What it does | Bypass |
|---|---|---|
| `http_server.py::_append_agent_done_event` | appends AGENT_DONE to EVENTS.jsonl | `open(..., "a")` |
| `http_server.py::record_phase_endpoint` | appends PHASE_START/DONE to EVENTS.jsonl | `open(..., "a")` |
| `fsm_ops.py::_stage_brief` | reads last 3 events from EVENTS.jsonl | `events_file.read_text()` |
| `fsm_ops.py::build_prompt` | passes EVENTS.jsonl file path to `build_pipeline_history_block` | path string |
| `fsm.py::evaluate_transition_rules` (on_state_counter) | reads field value from STATE.json | `state_file.read_text()` |
| `fsm.py::run_transition_actions` (update_progress conv_done) | increments convs_done in STATE.json directly | `state_file.read_text()` + `tmp.write_text()` |

## Migration strategy

- Use `eventlog.append_event` (which already routes to `db.append_event`) instead of `open(..., "a")`.
- Use `eventlog.read_events` / `eventlog.read_state` instead of direct file reads.
- For `_append_agent_done_event`: add a DB-primary branch; keep the EVENTS.jsonl branch as a legacy fallback when `pathly.db` does not exist.
- For `record_phase_endpoint`: same pattern — DB-primary, EVENTS.jsonl fallback.
- For `_stage_brief`: use `eventlog.read_events` (already SQLite-aware) to get the last 3 events.
- For `build_pipeline_history_block`: accept a `feature_dir` path and derive events from `eventlog.read_events` when DB exists.
- For `on_state_counter`: replace `STATE.json` direct read with `eventlog.read_state`.
- For `update_progress conv_done`: replace `STATE.json` direct read/write with `eventlog.read_state` + `eventlog.write_state`.
- Do NOT add new modules. Do NOT add new pip dependencies.

---

## Phase 1 — Migrate `http_server.py` direct EVENTS.jsonl writes

**Stories delivered:** Story 1, Story 2

**Files changed:**
- `src/pathly_orchestrator/http_server.py`
- `tests/test_http_server.py`

### 1a — `_append_agent_done_event`

**File:** `src/pathly_orchestrator/http_server.py`

Replace the `open(events_path, "a")` block with:

```python
from pathly_orchestrator import eventlog as _eventlog
feature_dir = Path(project_root) / "pathly" / "plans" / feature
if not feature_dir.exists():
    return
_eventlog.append_event(str(feature_dir), event)
```

The `events_path` variable and the `open(...)` call are removed. Since `eventlog.append_event` already handles both SQLite and EVENTS.jsonl depending on whether `pathly.db` exists, no explicit fallback code is needed here.

**Done when:** `_append_agent_done_event` no longer references `EVENTS.jsonl` directly. The event dict is written via `eventlog.append_event`.

**Verify:**
```bash
python -m pytest tests/test_http_server.py -k "record_activity" -q
```

### 1b — `record_phase_endpoint`

**File:** `src/pathly_orchestrator/http_server.py`

Replace the `with open(events_path, "a") as f: f.write(...)` block with:

```python
from pathly_orchestrator import eventlog as _eventlog
_eventlog.append_event(str(events_path.parent), event)
```

Or resolve `feature_dir` from `project_root` + `feature` (same pattern as 1a). The `events_path` variable can be removed or kept only for the legacy dir-existence check.

**Done when:** `record_phase_endpoint` no longer calls `open(..., "a")`. The event is written via `eventlog.append_event`.

**Verify:**
```bash
python -m pytest tests/test_http_server.py -k "record_phase" -q
```

### 1c — Update `test_record_activity_appends_complete_agent_done_event`

**File:** `tests/test_http_server.py`

The test currently asserts `(events_dir / "EVENTS.jsonl").read_text()`. After migration, the event is in SQLite. Update the assertion to use `eventlog.read_events` or `db.read_events` to retrieve the event from the DB instead of reading EVENTS.jsonl directly.

**Done when:** The test reads from SQLite and asserts all previous field checks pass.

**Verify:**
```bash
python -m pytest tests/test_http_server.py -k "appends_complete_agent_done" -q
```

---

## Phase 2 — Migrate direct file reads in `fsm_ops.py` and `fsm.py`

**Stories delivered:** Stories 3, 4, 5, 6

**Files changed (≤4):**
- `src/pathly_orchestrator/fsm_ops.py`
- `src/pathly_orchestrator/fsm.py`
- `tests/test_fsm_ops.py` (new or existing)
- `tests/test_fsm.py` (existing)

### 2a — `_stage_brief` reads recent events via eventlog

**File:** `src/pathly_orchestrator/fsm_ops.py`

Replace:
```python
events_file = storage_path / "EVENTS.jsonl"
if events_file.exists():
    # ... read_text, splitlines, json.loads last 3
```

With:
```python
from pathly_orchestrator import eventlog as _eventlog
all_events = _eventlog.read_events(str(storage_path))
recent_events = all_events[-3:] if len(all_events) >= 3 else all_events
```

`eventlog.read_events` already handles DB-primary + EVENTS.jsonl fallback. Remove the direct file read.

**Done when:** `_stage_brief` does not open `EVENTS.jsonl` directly.

### 2b — `build_pipeline_history_block` reads events via eventlog

**File:** `src/pathly_orchestrator/fsm_ops.py` (call site) and `src/pathly_orchestrator/runner.py` (function)

In `build_prompt` (fsm_ops.py line 188):
```python
events_path = os.path.join(project_root, "pathly", "plans", feature, "EVENTS.jsonl")
history = build_pipeline_history_block(events_path)
```

Update `build_pipeline_history_block` in `runner.py` to accept either a path string (EVENTS.jsonl path for legacy) or derive the feature_dir and use `eventlog.read_events`. Alternatively, change `build_prompt` to pass the feature_dir path and let `runner.py` resolve via eventlog.

**Note:** Keep the function signature backward-compatible so any other callers are not broken.

**Done when:** `build_pipeline_history_block` uses `eventlog.read_events` when `pathly.db` is present.

### 2c — `evaluate_transition_rules` `on_state_counter` reads state via eventlog

**File:** `src/pathly_orchestrator/fsm.py`

Replace the `on_state_counter` block:
```python
state_file = storage_path / "STATE.json"
if state_file.exists():
    state_doc = json.loads(state_file.read_text(encoding="utf-8"))
```

With:
```python
from pathly_orchestrator import eventlog as _eventlog
state_doc = _eventlog.read_state(str(storage_path)) or {}
```

`eventlog.read_state` already has DB-first + STATE.json fallback.

**Done when:** The `on_state_counter` block does not reference `STATE.json` directly.

### 2d — `run_transition_actions` `update_progress` increments convs_done via eventlog

**File:** `src/pathly_orchestrator/fsm.py`

In the `conv_done` branch of `update_progress`, replace:
```python
state_file = storage_path / "STATE.json"
if state_file.exists():
    state_doc = json.loads(state_file.read_text(...))
    state_doc["convs_done"] = ...
    tmp = storage_path / "STATE.json.tmp"
    tmp.write_text(json.dumps(state_doc, ...), ...)
    tmp.replace(state_file)
```

With:
```python
from pathly_orchestrator import eventlog as _eventlog
state_doc = _eventlog.read_state(str(storage_path)) or {}
state_doc["convs_done"] = int(state_doc.get("convs_done", 0)) + 1
_eventlog.write_state(str(storage_path), state_doc)
```

`eventlog.write_state` writes to both SQLite and STATE.json as a snapshot.

**Done when:** The `update_progress conv_done` branch does not write `STATE.json` directly.

---

## Phase 3 — Full test suite verification

**Stories delivered:** Stories 7, 8

**Files changed:**
- `tests/test_http_server.py` (already updated in Phase 1)
- `tests/test_fsm_ops.py` (new assertions for SQLite read paths)
- `tests/test_fsm.py` (assertions for on_state_counter and update_progress via DB)

**Done when:** `python -m pytest tests/ -q` exits 0 with no failures or errors.

**Verify:**
```bash
python -m pytest tests/ -q
```

---

## Scope summary

| File | Phase | Change type |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | 1 | Replace 2 `open(...)` blocks with `eventlog.append_event` |
| `src/pathly_orchestrator/fsm_ops.py` | 2 | Replace EVENTS.jsonl direct read in `_stage_brief`; update call to `build_pipeline_history_block` |
| `src/pathly_orchestrator/runner.py` | 2 | Update `build_pipeline_history_block` to use `eventlog.read_events` |
| `src/pathly_orchestrator/fsm.py` | 2 | Replace 2 STATE.json direct read/write blocks |
| `tests/test_http_server.py` | 1 | Update 1 test assertion from EVENTS.jsonl to SQLite |
| `tests/test_fsm_ops.py` | 2 | Add/update tests for SQLite read paths |
| `tests/test_fsm.py` | 2 | Add/update tests for on_state_counter and update_progress |

Total: 7 files across 2 conversations — within the ≤4 files per conversation constraint per conversation.
