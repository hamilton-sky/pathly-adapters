# Conversation Prompts — fsm-server-sqlite

---

## Conversation 1 — Migrate `http_server.py` direct EVENTS.jsonl writes to SQLite

**Stories:** Story 1 (\_append_agent_done_event), Story 2 (record_phase_endpoint), Story 7 (test update)

### Prompt

You are a builder. This is Conversation 1 of 2 for feature `fsm-server-sqlite`.

**Context**

The `pathly_orchestrator` package runs an HTTP FSM server at port 8765. The previous feature `fsm-sqlite` migrated internal storage to SQLite via `src/pathly_orchestrator/db.py`. However, two HTTP endpoints still write events directly to `EVENTS.jsonl` by calling `open(..., "a")`, bypassing `db.py` entirely.

`eventlog.append_event` (in `src/pathly_orchestrator/eventlog.py`) already routes to SQLite when `pathly.db` exists and falls back to EVENTS.jsonl when it does not. Use it everywhere instead of calling `open(...)` directly.

**Your task**

Make exactly these changes. Do not change any other files.

### Change 1 — `_append_agent_done_event` in `http_server.py`

**File:** `src/pathly_orchestrator/http_server.py`

Current code (around line 662):
```python
def _append_agent_done_event(...) -> None:
    try:
        events_path = Path(project_root) / "pathly" / "plans" / feature / "EVENTS.jsonl"
        if not events_path.parent.exists():
            return
        event: dict[str, object] = { ... }
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        logger.debug("_append_agent_done_event error", exc_info=True)
```

Replace the body so it:
1. Resolves `feature_dir = Path(project_root) / "pathly" / "plans" / feature`
2. Returns early if `feature_dir` does not exist (same guard, different var name)
3. Builds the same `event` dict (no field changes)
4. Calls `from pathly_orchestrator import eventlog as _eventlog` then `_eventlog.append_event(str(feature_dir), event)` instead of the `open(...)` block

Do NOT remove the `try/except` wrapper. Do NOT change the function signature or the event payload fields.

### Change 2 — `record_phase_endpoint` in `http_server.py`

**File:** `src/pathly_orchestrator/http_server.py`

Current code (around line 817):
```python
feature = data["feature"]
project_root = data.get("project_root") or os.environ.get("PATHLY_PROJECT_ROOT", "")
if project_root:
    events_path = Path(project_root) / "pathly" / "plans" / feature / "EVENTS.jsonl"
else:
    events_path = Path("pathly") / "plans" / feature / "EVENTS.jsonl"

if not events_path.parent.exists():
    return jsonify({"error": f"Feature directory does not exist: {events_path.parent}"}), 400

event: dict[str, object] = { ... }
...
with open(events_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(event) + "\n")
```

Replace so that:
1. `feature_dir` is derived as before (using `project_root` or fallback)
2. The directory-existence check uses `feature_dir` not `events_path.parent`
3. The event dict is built identically
4. The write uses `from pathly_orchestrator import eventlog as _eventlog` then `_eventlog.append_event(str(feature_dir), event)` instead of `open(...)`

Keep the 400 error response when the feature dir does not exist. Keep all validation logic unchanged.

### Change 3 — Update test in `test_http_server.py`

**File:** `tests/test_http_server.py`

Find `test_record_activity_appends_complete_agent_done_event`. It currently does:
```python
event = json.loads((events_dir / "EVENTS.jsonl").read_text().strip())
```

Replace that assertion block with:
```python
from pathly_orchestrator import eventlog as _eventlog
events = _eventlog.read_events(str(events_dir))
assert len(events) == 1
event = events[0]
```

Keep all the field assertions below (`event["schema_version"]`, `event["model"]`, etc.) unchanged. Also update `test_record_activity_uses_total_tokens_when_split_is_missing` in the same way (it also reads `EVENTS.jsonl` directly).

**Do not touch any other tests.**

### Acceptance criteria

- [ ] `_append_agent_done_event` contains no `open(` call for EVENTS.jsonl
- [ ] `record_phase_endpoint` contains no `open(` call for EVENTS.jsonl
- [ ] Both use `eventlog.append_event`
- [ ] `test_record_activity_appends_complete_agent_done_event` passes
- [ ] `test_record_activity_uses_total_tokens_when_split_is_missing` passes
- [ ] Full suite: `python -m pytest tests/test_http_server.py -q` exits 0

### Verify command

```bash
python -m pytest tests/test_http_server.py -q
```

### VERIFY.md instruction

After all checks pass, write `pathly/plans/fsm-server-sqlite/VERIFY.md` with line 1 exactly:
```
CONV-1-PASS
```
Then add a brief summary of what was changed below line 1.

---

## Conversation 2 — Migrate direct file reads in `fsm_ops.py`, `fsm.py`, and `runner.py`

**Stories:** Story 3 (_stage_brief), Story 4 (on_state_counter), Story 5 (update_progress), Story 6 (build_pipeline_history_block), Story 8 (full suite green)

### Prompt

You are a builder. This is Conversation 2 of 2 for feature `fsm-server-sqlite`.

**Context**

Conversation 1 already migrated `_append_agent_done_event` and `record_phase_endpoint` in `http_server.py` to use `eventlog.append_event` instead of `open(...)`. Now migrate three remaining direct file access locations in `fsm_ops.py`, `fsm.py`, and `runner.py`.

`eventlog.read_events(storage_path_str)` and `eventlog.read_state(storage_path_str)` already read from SQLite when `pathly.db` is present and fall back to EVENTS.jsonl / STATE.json when it is not. Use these functions instead of direct file reads.

**Your task**

Make exactly these changes across ≤4 files. Do not change any other files.

### Change 1 — `_stage_brief` in `fsm_ops.py`

**File:** `src/pathly_orchestrator/fsm_ops.py`

Current code (around line 268):
```python
recent_events: list[dict] = []
events_file = storage_path / "EVENTS.jsonl"
if events_file.exists():
    try:
        lines = [ln for ln in events_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for line in lines[-3:]:
            try:
                recent_events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except OSError:
        pass
```

Replace with:
```python
recent_events: list[dict] = []
try:
    from pathly_orchestrator import eventlog as _eventlog
    all_events = _eventlog.read_events(str(storage_path))
    recent_events = all_events[-3:] if len(all_events) >= 3 else list(all_events)
except Exception:
    pass
```

### Change 2 — `build_prompt` call to `build_pipeline_history_block` in `fsm_ops.py`

**File:** `src/pathly_orchestrator/fsm_ops.py`

Current code (around line 187):
```python
from pathly_orchestrator.runner import build_pipeline_history_block
import os
events_path = os.path.join(project_root, "pathly", "plans", feature, "EVENTS.jsonl")
history = build_pipeline_history_block(events_path)
```

Replace with:
```python
from pathly_orchestrator.runner import build_pipeline_history_block
import os
feature_dir = os.path.join(project_root, "pathly", "plans", feature)
history = build_pipeline_history_block(feature_dir)
```

Then update `build_pipeline_history_block` in `runner.py` to accept either the old EVENTS.jsonl path or the new feature_dir path. Inside the function, detect whether the path ends in `EVENTS.jsonl` (legacy callers) or is a directory. When given a directory path, use `eventlog.read_events(path)` to get events. When given a file path (EVENTS.jsonl), keep the existing file-read logic as a fallback.

The returned string format must be unchanged.

### Change 3 — `evaluate_transition_rules` `on_state_counter` in `fsm.py`

**File:** `src/pathly_orchestrator/fsm.py`

Current code (around line 177):
```python
try:
    state_file = storage_path / "STATE.json"
    if state_file.exists():
        state_doc = json.loads(state_file.read_text(encoding="utf-8"))
        field_val = int(state_doc[field])
        compare_val = int(state_doc[compare_to])
        if op_fn(field_val, compare_val):
            return next_s
except (KeyError, ValueError, TypeError, json.JSONDecodeError, OSError):
    pass
```

Replace with:
```python
try:
    from pathly_orchestrator import eventlog as _eventlog
    state_doc = _eventlog.read_state(str(storage_path)) or {}
    field_val = int(state_doc[field])
    compare_val = int(state_doc[compare_to])
    if op_fn(field_val, compare_val):
        return next_s
except (KeyError, ValueError, TypeError):
    pass
```

The `state_file.exists()` guard is no longer needed because `eventlog.read_state` returns `None` (handled by `or {}`).

### Change 4 — `run_transition_actions` `update_progress conv_done` in `fsm.py`

**File:** `src/pathly_orchestrator/fsm.py`

Current code (around line 378):
```python
if mark == "conv_done":
    content = content.replace(f"| {conv} |", f"| {conv} | DONE |", 1)
    state_file = storage_path / "STATE.json"
    if state_file.exists():
        try:
            state_doc = json.loads(state_file.read_text(encoding="utf-8"))
            state_doc["convs_done"] = int(state_doc.get("convs_done", 0)) + 1
            tmp = storage_path / "STATE.json.tmp"
            tmp.write_text(json.dumps(state_doc, indent=2) + "\n", encoding="utf-8")
            tmp.replace(state_file)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
```

Replace the state-file read/write block (the inner `if state_file.exists()` block) with:
```python
if mark == "conv_done":
    content = content.replace(f"| {conv} |", f"| {conv} | DONE |", 1)
    try:
        from pathly_orchestrator import eventlog as _eventlog
        state_doc = _eventlog.read_state(str(storage_path)) or {}
        state_doc["convs_done"] = int(state_doc.get("convs_done", 0)) + 1
        _eventlog.write_state(str(storage_path), state_doc)
    except (ValueError, OSError):
        pass
```

`eventlog.write_state` writes to both SQLite and STATE.json (as a snapshot), so agents reading STATE.json directly continue to work.

### Tests to add/update

**File:** `tests/test_fsm.py` (or `tests/test_fsm_ops.py` if that file exists — check first)

Add these tests:

**Test A — `on_state_counter` reads from SQLite when pathly.db exists**
```python
def test_on_state_counter_reads_from_db(tmp_path):
    # Create a feature dir with pathly.db (no STATE.json)
    # Write state with convs_done=3, convs_total=5 via db.write_state
    # Call evaluate_transition_rules with an on_state_counter rule: convs_done lt convs_total -> BUILDING
    # Assert it returns "BUILDING"
```

**Test B — `update_progress conv_done` increments convs_done in DB**
```python
def test_update_progress_conv_done_increments_db(tmp_path):
    # Create a feature dir with pathly.db
    # Write initial state convs_done=1
    # Call run_transition_actions with update_progress mark: conv_done
    # Assert db.read_state returns convs_done=2
```

### Acceptance criteria

- [ ] `_stage_brief` does not read EVENTS.jsonl directly
- [ ] `build_pipeline_history_block` uses `eventlog.read_events` when a dir path is passed
- [ ] `evaluate_transition_rules on_state_counter` does not read STATE.json directly
- [ ] `run_transition_actions update_progress conv_done` does not write STATE.json directly
- [ ] `python -m pytest tests/test_fsm.py -q` exits 0
- [ ] `python -m pytest tests/ -q` exits 0 (full suite)

### Verify command

```bash
python -m pytest tests/ -q
```

### VERIFY.md instruction

After all checks pass, update `pathly/plans/fsm-server-sqlite/VERIFY.md`: append a line:
```
CONV-2-PASS
```
And add a brief summary of what was changed in Conversation 2 below it.
