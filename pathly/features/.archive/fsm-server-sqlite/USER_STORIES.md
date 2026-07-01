# User Stories — fsm-server-sqlite

## Background

The previous `fsm-sqlite` feature migrated `eventlog.py` and `supervisor.py` to SQLite via `db.py`. However, two HTTP server endpoints still write events directly to `EVENTS.jsonl` by calling `open(..., "a")`, bypassing `db.py` entirely. One location in `fsm_ops.py` reads `EVENTS.jsonl` directly instead of using `eventlog.read_events`. Two locations in `fsm.py` read/write `STATE.json` directly without going through `eventlog`. This feature closes those gaps, making the entire FSM server SQLite-primary.

---

## Story 1 — `_append_agent_done_event` writes to SQLite

**Delivered by:** Conversation 1

**As** a pipeline operator,
**I want** AGENT_DONE events emitted by the `record_activity` endpoint to be stored in `pathly.db`,
**so that** the SSE event stream and retro summaries are driven by a single authoritative store.

### Acceptance criteria

- AC1: After calling `POST /record_activity` with a `project_root` and `feature`, the AGENT_DONE event is readable via `db.read_events(conn, feature)`.
- AC2: When `pathly.db` exists in the feature dir, no `EVENTS.jsonl` file is written or appended by `_append_agent_done_event`.
- AC3: When `pathly.db` does NOT exist (legacy dir), the function falls back to appending to `EVENTS.jsonl` as before.
- AC4: The event payload shape is unchanged: `schema_version`, `type`, `agent`, `model`, `result`, `total_tokens`, `tokens_in`, `tokens_out`, `tool_uses`, `wall_seconds`, `cost_usd`, and optional `conversation` fields are all present.

### Verify

```bash
python -m pytest tests/test_http_server.py -k "record_activity" -q
```

---

## Story 2 — `record_phase` endpoint writes to SQLite

**Delivered by:** Conversation 1

**As** a pipeline operator,
**I want** PHASE_START and PHASE_DONE events from the `record_phase` endpoint to be stored in `pathly.db`,
**so that** all FSM events flow through the same storage layer.

### Acceptance criteria

- AC1: After calling `POST /record_phase` with a valid body, the event is readable via `db.read_events(conn, feature)`.
- AC2: When `pathly.db` exists in the feature dir, `EVENTS.jsonl` is not appended to by `record_phase_endpoint`.
- AC3: When `pathly.db` does NOT exist (legacy dir), the function falls back to writing `EVENTS.jsonl`.
- AC4: The existing `400` validation behavior for bad inputs is unchanged.

### Verify

```bash
python -m pytest tests/test_http_server.py -k "record_phase" -q
```

---

## Story 3 — `_stage_brief` reads recent events from SQLite

**Delivered by:** Conversation 1

**As** a pipeline operator,
**I want** the `stage_brief.recent_events` field in `/next_action` responses to read from SQLite when `pathly.db` is present,
**so that** event history returned to agents is consistent with the actual store.

### Acceptance criteria

- AC1: When `pathly.db` exists, `_stage_brief` returns the last 3 events from `db.read_events`, not from an EVENTS.jsonl file read.
- AC2: When `pathly.db` does NOT exist, `_stage_brief` falls back to reading `EVENTS.jsonl` (no regression).
- AC3: The `recent_events` field shape in the `/next_action` response is unchanged.

### Verify

```bash
python -m pytest tests/test_fsm_ops.py -q
```

---

## Story 4 — `fsm.py::evaluate_transition_rules` `on_state_counter` reads STATE from eventlog

**Delivered by:** Conversation 2

**As** a pipeline operator,
**I want** the `on_state_counter` transition rule to read FSM state through `eventlog.read_state` rather than directly opening `STATE.json`,
**so that** the rule works correctly on SQLite-primary feature dirs that have no `STATE.json`.

### Acceptance criteria

- AC1: When a feature dir has `pathly.db` and no `STATE.json`, `evaluate_transition_rules` with `on_state_counter` correctly reads the field value from the DB.
- AC2: When only `STATE.json` exists (legacy dir), behavior is unchanged.
- AC3: `python -m pytest tests/test_fsm.py -q` passes without errors.

### Verify

```bash
python -m pytest tests/test_fsm.py -q
```

---

## Story 5 — `fsm.py::run_transition_actions` `update_progress` reads/writes STATE through eventlog

**Delivered by:** Conversation 2

**As** a pipeline operator,
**I want** the `update_progress` transition action to update `convs_done` through `eventlog.write_state` rather than directly patching `STATE.json`,
**so that** the in-DB state record is kept in sync after a conversation completes.

### Acceptance criteria

- AC1: When `pathly.db` exists, after `update_progress conv_done` runs, `db.read_state(conn, feature)["convs_done"]` equals the incremented value.
- AC2: `STATE.json` is still written as a snapshot (the human-readable file is preserved for agents using their write tools directly).
- AC3: When only `STATE.json` exists (legacy dir), behavior is unchanged — `convs_done` is incremented in the file.
- AC4: `python -m pytest tests/test_fsm.py -q` passes without errors.

### Verify

```bash
python -m pytest tests/test_fsm.py -q
```

---

## Story 6 — `build_pipeline_history_block` reads events from SQLite

**Delivered by:** Conversation 2

**As** a pipeline operator,
**I want** `build_pipeline_history_block` in `runner.py` to read events from SQLite when available,
**so that** the prompt context block injected into agent instructions reflects the complete event history.

### Acceptance criteria

- AC1: When `pathly.db` exists at the resolved feature path, `build_pipeline_history_block` returns a non-empty history block containing events from the DB.
- AC2: When no `pathly.db` exists, the function reads from `EVENTS.jsonl` as before (no regression).
- AC3: The returned string format is unchanged (same Markdown block structure).

### Verify

```bash
python -m pytest tests/test_runner.py -q
```

---

## Story 7 — Existing tests updated for SQLite-primary writes

**Delivered by:** Conversation 2

**As** a developer,
**I want** the existing test `test_record_activity_appends_complete_agent_done_event` to assert against SQLite instead of a raw `EVENTS.jsonl` file,
**so that** the test suite validates the new storage path rather than the old one.

### Acceptance criteria

- AC1: `test_record_activity_appends_complete_agent_done_event` passes after the change — it reads the event from `db.read_events` or `eventlog.read_events`, not directly from `EVENTS.jsonl`.
- AC2: No other test in `test_http_server.py` that previously read `EVENTS.jsonl` directly fails due to the migration.
- AC3: `python -m pytest tests/ -q` shows zero failures and zero errors.

### Verify

```bash
python -m pytest tests/ -q
```

---

## Story 8 — Full test suite green after migration

**Delivered by:** Conversation 2 (verified at end)

**As** a developer,
**I want** the full test suite to pass after all changes are applied,
**so that** no regressions are introduced by the SQLite migration.

### Acceptance criteria

- AC1: `python -m pytest tests/ -q` exits with code 0.
- AC2: No test file imports `EVENTS.jsonl` path logic that was removed.
- AC3: Coverage of the new SQLite paths in `http_server.py` is demonstrated by at least one test per changed function.

### Verify

```bash
python -m pytest tests/ -q
```
