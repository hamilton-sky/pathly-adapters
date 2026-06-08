# Conversation Prompts — otel-exporter

---

## Conversation 1 — Core export module, real-time hook, and unit tests

**Delivers:** S1, S2, S4, S5 (stories from USER_STORIES.md)
**Phases:** Phase 1, Phase 2, Phase 3 (from IMPLEMENTATION_PLAN.md)

---

You are a builder working on the **otel-exporter** feature for Pathly.

### Context

Pathly is a Python-based AI pipeline orchestrator. It records agent pipeline events in EVENTS.jsonl and SQLite (`pathly.db`). The goal is to add an **optional, zero-dependency OTel exporter** that exports these events to any OTLP-compatible backend.

Project root: `C:\Users\Yafit\pathly-adapters`

### What to build in this conversation

You will create one new file and modify one existing file:

1. **NEW** `src/pathly_orchestrator/otel_export.py`
2. **MODIFY** `src/pathly_orchestrator/http_server.py` — hook into `record_activity_endpoint`
3. **NEW** `tests/test_otel_export.py`

After all three are done, run `python -m pytest tests/test_otel_export.py -v` and fix any failures before finishing.

---

### Phase 1: Create `src/pathly_orchestrator/otel_export.py`

Create this file with **no new pip dependencies** — use only `urllib.request`, `urllib.error`, `json`, `threading`, `os`, `logging`, `secrets`, `datetime` from stdlib.

#### Function: `_build_span_payload(event: dict) -> dict`

Converts a Pathly AGENT_DONE event dict to a valid OTLP JSON `ExportTraceServiceRequest`.

The structure must be:
```json
{
  "resourceSpans": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "pathly"}},
        {"key": "service.version", "value": {"stringValue": "<version>"}}
      ]
    },
    "scopeSpans": [{
      "scope": {"name": "pathly.orchestrator"},
      "spans": [{
        "traceId": "<32-char hex>",
        "spanId": "<16-char hex>",
        "name": "invoke_agent <agent>",
        "kind": 1,
        "startTimeUnixNano": "<int as string>",
        "endTimeUnixNano": "<int as string>",
        "attributes": [...],
        "status": {"code": 1 or 2}
      }]
    }]
  }]
}
```

Attribute mapping:
- `gen_ai.agent.name` ← `event["agent"]`
- `gen_ai.workflow.name` ← `event["feature"]`
- `gen_ai.usage.input_tokens` ← `event.get("tokens_in", 0)` (int)
- `gen_ai.usage.output_tokens` ← `event.get("tokens_out", 0)` (int)
- `gen_ai.request.model` ← `event.get("model", "")` (string)
- `gen_ai.conversation.id` ← `str(event.get("conversation", ""))` (string)
- `pathly.cost_usd` ← `event.get("cost_usd", 0.0)` (double)
- `pathly.tool_uses` ← `event.get("tool_uses", 0)` (int)
- `pathly.result` ← `event.get("result", "")` (string)

For OTLP JSON, each attribute is `{"key": "...", "value": {"stringValue": ...}}` or `{"key": "...", "value": {"intValue": ...}}` or `{"key": "...", "value": {"doubleValue": ...}}`.

`trace_id`: use `event.get("trace_id", "")`. If empty/missing, generate `secrets.token_hex(16)`.
`span_id`: use `event.get("span_id", "")`. If empty/missing, generate `secrets.token_hex(8)`.

Timing: parse `event.get("ts", "")` as ISO 8601 to get `start_ns` (nanoseconds since epoch). `end_ns = start_ns + event.get("wall_seconds", 0) * 1_000_000_000`. Both are stored as string representations of integers in OTLP JSON (e.g. `"1735689600000000000"`).

Status: if `result.lower()` is in `{"pass", "done"}` → `{"code": 1}` (STATUS_CODE_OK). Otherwise → `{"code": 2}` (STATUS_CODE_ERROR).

Service version: try `importlib.metadata.version("pathly-adapters")`; if that raises, use `"unknown"`.

#### Function: `_build_log_payload(event: dict, trace_id: str, span_id: str) -> dict`

Builds an OTLP `ExportLogsServiceRequest`:
```json
{
  "resourceLogs": [{
    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "pathly"}}]},
    "scopeLogs": [{
      "scope": {"name": "pathly.orchestrator"},
      "logRecords": [{
        "timeUnixNano": "<start_ns as string>",
        "traceId": "<trace_id>",
        "spanId": "<span_id>",
        "body": {"stringValue": "<summary truncated to 65535 chars>"},
        "severityNumber": 9,
        "severityText": "INFO"
      }]
    }]
  }]
}
```

#### Function: `_do_export(event: dict, endpoint: str) -> None`

- Build span payload, POST to `{endpoint}/v1/traces` with `Content-Type: application/json`.
- Use `urllib.request.urlopen` with `timeout=5`.
- If `event.get("summary", "").strip()` is non-empty, build log payload and POST to `{endpoint}/v1/logs`.
- Each call wrapped in its own try/except: catch `Exception`, call `logger.warning("otel export failed: %s", exc)`.
- Log `logger.debug("otel span exported: %s %s", agent, feature)` on success.

#### Function: `export_span_async(event: dict) -> None`

- `endpoint = os.environ.get("PATHLY_OTEL_ENDPOINT", "").strip()`
- If empty: `return` immediately.
- Otherwise: `t = threading.Thread(target=_do_export, args=(event, endpoint), daemon=True); t.start()`

---

### Phase 2: Hook into `http_server.py`

Read `src/pathly_orchestrator/http_server.py` first.

In `record_activity_endpoint`, find the block that calls `_append_agent_done_event(...)` (around line 791–805). Immediately after that block ends (after `)`), add the following code:

```python
        # OTel export — fire-and-forget; no-op if PATHLY_OTEL_ENDPOINT is unset
        try:
            from pathly_orchestrator import otel_export as _otel
            _otel.export_span_async({
                "type": "AGENT_DONE",
                "agent": str(data["agent"]),
                "feature": str(data["feature"]),
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "result": str(data.get("result", "DONE")),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": float(cost_usd_val),
                "wall_seconds": wall_seconds,
                "model": str(data.get("model", "")),
                "conversation": data.get("conversation"),
                "summary": str(data.get("summary", "")),
                "trace_id": str(data.get("trace_id", "")),
                "span_id": str(data.get("span_id", "")),
            })
        except Exception:
            logger.debug("otel_export hook error", exc_info=True)
```

This goes inside the `if project_root and data.get("feature"):` block, after `_append_agent_done_event`.

---

### Phase 3: Create `tests/test_otel_export.py`

Write 9 tests. Use `pytest` and `unittest.mock`.

Test fixtures needed:
```python
MINIMAL_EVENT = {
    "type": "AGENT_DONE",
    "agent": "builder",
    "feature": "my-feature",
    "ts": "2026-01-01T00:00:00Z",
    "result": "pass",
    "tokens_in": 100,
    "tokens_out": 50,
    "cost_usd": 0.001,
    "wall_seconds": 30,
    "model": "claude-sonnet-4-6",
    "conversation": 1,
    "summary": "Built the thing",
    "trace_id": "a" * 32,
    "span_id": "b" * 16,
}
```

Tests:

1. `test_no_op_when_env_unset(monkeypatch)`:
   - `monkeypatch.delenv("PATHLY_OTEL_ENDPOINT", raising=False)`
   - With `mock.patch("threading.Thread") as mock_thread`: call `export_span_async(MINIMAL_EVENT)`.
   - Assert `mock_thread.call_count == 0`.

2. `test_span_payload_structure()`:
   - Call `_build_span_payload(MINIMAL_EVENT)`.
   - Assert `"resourceSpans"` in result.
   - Assert span name equals `"invoke_agent builder"`.
   - Assert `traceId == "a" * 32` and `spanId == "b" * 16`.
   - Assert attribute keys include `"gen_ai.agent.name"` and `"pathly.cost_usd"`.

3. `test_span_status_ok()`:
   - Event with `result="pass"` → span `status.code == 1`.
   - Event with `result="done"` → span `status.code == 1`.
   - Event with `result="DONE"` → span `status.code == 1`.

4. `test_span_status_error()`:
   - Event with `result="fail"` → span `status.code == 2`.
   - Event with `result="error"` → span `status.code == 2`.

5. `test_do_export_swallows_network_error(monkeypatch, caplog)`:
   - `monkeypatch.setattr("urllib.request.urlopen", mock.Mock(side_effect=OSError("refused")))`.
   - Call `_do_export(MINIMAL_EVENT, "http://localhost:4318")`.
   - Assert no exception raised.
   - Assert `"otel export failed"` in caplog.text (WARNING level).

6. `test_do_export_swallows_http_error(monkeypatch, caplog)`:
   - `monkeypatch.setattr("urllib.request.urlopen", mock.Mock(side_effect=urllib.error.HTTPError(..., 503, "Service Unavailable", {}, None)))`.
   - Call `_do_export(MINIMAL_EVENT, "http://localhost:4318")`.
   - Assert no exception raised.
   - Assert warning in caplog.

7. `test_log_not_posted_when_no_summary(monkeypatch)`:
   - Event with `summary=""`.
   - `monkeypatch.setattr("urllib.request.urlopen", mock.Mock(return_value=mock.Mock(status=200)))`.
   - Call `_do_export({**MINIMAL_EVENT, "summary": ""}, "http://localhost:4318")`.
   - Assert `urlopen` called exactly once.

8. `test_log_posted_when_summary_present(monkeypatch)`:
   - Event has `summary="did things"`.
   - Assert `urlopen` called exactly twice.

9. `test_record_activity_unaffected_by_export_failure(monkeypatch)`:
   - Set `PATHLY_OTEL_ENDPOINT=http://127.0.0.1:1` (unreachable port).
   - Use Flask test client: `from pathly_orchestrator.http_server import app; client = app.test_client()`.
   - POST `/record_activity` with `{"agent": "builder", "feature": "test", "summary": "done", "input_tokens": 10, "output_tokens": 5}`.
   - Assert response status 200.

---

### Done criteria for this conversation

All of the following must pass before you finish:

```bash
cd C:\Users\Yafit\pathly-adapters
python -c "from pathly_orchestrator.otel_export import export_span_async, _build_span_payload; print('import ok')"
python -m pytest tests/test_otel_export.py -v
python -m pytest tests/ -q --ignore=tests/test_otel_export_cli.py
```

All must exit 0 with no failures.

---

## Conversation 2 — Batch CLI and CLI tests

**Delivers:** S3 (story from USER_STORIES.md)
**Phases:** Phase 4, Phase 5 (from IMPLEMENTATION_PLAN.md)

---

You are a builder continuing work on the **otel-exporter** feature for Pathly.

Conversation 1 is complete. The following already exist:
- `src/pathly_orchestrator/otel_export.py` — has `export_span_async`, `_build_span_payload`, `_build_log_payload`, `_do_export`
- `tests/test_otel_export.py` — passing

### What to build in this conversation

1. Add `cli_main()` to `src/pathly_orchestrator/otel_export.py`
2. Add entry point to `pyproject.toml`
3. Create `tests/test_otel_export_cli.py`

---

### Phase 4: Add `cli_main()` to `otel_export.py`

Read `src/pathly_orchestrator/otel_export.py` first to understand the existing code.

Append a `cli_main()` function to the bottom of the file. Use `argparse`.

```
usage: pathly-otel-export [-h] --feature FEATURE --endpoint URL
                          [--project-root PATH] [--dry-run]
```

Arguments:
- `--feature` (required): feature name, e.g. `my-feature`
- `--endpoint` (required): OTLP endpoint base URL, e.g. `http://localhost:4318`
- `--project-root` (optional, default `os.getcwd()`): path to project root
- `--dry-run` (flag): print what would be exported without making HTTP requests

Implementation steps:

1. Resolve DB path: `Path(project_root) / "pathly" / "plans" / feature / "pathly.db"`.
2. If it does not exist: print error to stderr, `sys.exit(1)`.
3. Import `from pathly_orchestrator import db as _db` and open the connection.
4. Call `_db.read_events(conn, feature)` to get all events.
5. Filter to `type == "AGENT_DONE"`.
6. For each event:
   - Print `f"exported span: invoke_agent {event.get('agent', '?')} (seq={event.get('seq', '?')})"`.
   - If `--dry-run`: skip HTTP call.
   - Otherwise: call `_do_export(event, endpoint)` synchronously (not async — CLI waits). Track any exception.
7. Print `f"done: {exported_count} spans exported"`.
8. If any failures: `sys.exit(1)`. Otherwise: `sys.exit(0)`.

---

### Phase 5: Add entry point to `pyproject.toml`

Read `pyproject.toml` first.

In the `[project.scripts]` section, add:
```toml
pathly-otel-export = "pathly_orchestrator.otel_export:cli_main"
```

Add it after the last existing script entry (after `pathly-design`).

---

### Phase 6: Create `tests/test_otel_export_cli.py`

Write 6 tests. Use `pytest`, `unittest.mock`, and `tmp_path` fixture for temporary SQLite databases.

Helper to create a temp DB with AGENT_DONE events:
```python
def _make_test_db(tmp_path, n_events=2):
    from pathly_orchestrator import db as _db
    from pathlib import Path
    feature = "test-feature"
    feature_dir = tmp_path / "pathly" / "plans" / feature
    feature_dir.mkdir(parents=True)
    conn = _db.get_db(feature_dir)
    for i in range(n_events):
        _db.append_event(conn, feature, {
            "type": "AGENT_DONE",
            "agent": "builder",
            "feature": feature,
            "ts": "2026-01-01T00:00:00Z",
            "result": "pass",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost_usd": 0.001,
            "wall_seconds": 30,
            "model": "claude-sonnet-4-6",
            "conversation": i + 1,
        })
    return feature_dir, feature
```

Tests:

1. `test_cli_missing_db(tmp_path)`:
   - Call `cli_main()` via `sys.argv` patching or by calling it with argparse args pointing to a nonexistent feature.
   - Assert `SystemExit` with code 1.

2. `test_cli_dry_run(tmp_path, monkeypatch)`:
   - Create DB with 2 AGENT_DONE events using helper.
   - Monkeypatch `pathly_orchestrator.otel_export._do_export` to track calls.
   - Set `sys.argv = ["pathly-otel-export", "--feature", "test-feature", "--endpoint", "http://localhost:4318", "--project-root", str(tmp_path), "--dry-run"]`.
   - Call `cli_main()`; expect `SystemExit(0)` (or no exit if you use `sys.exit` at the end).
   - Assert `_do_export` was NOT called.

3. `test_cli_exports_spans(tmp_path, monkeypatch)`:
   - Create DB with 2 events.
   - Monkeypatch `_do_export` to be a no-op.
   - Run CLI without `--dry-run`.
   - Assert `_do_export` called twice.

4. `test_cli_zero_events(tmp_path, capsys)`:
   - Create DB with 0 AGENT_DONE events (add a different event type, e.g. `PHASE_START`).
   - Run CLI.
   - Assert `"done: 0 spans exported"` in captured stdout.

5. `test_cli_export_failure_exits_1(tmp_path, monkeypatch)`:
   - Create DB with 2 events.
   - Monkeypatch `_do_export` to raise `OSError("network error")` on first call.
   - Assert the CLI exits with code 1 but still processes remaining events (second event attempted).

6. `test_cli_non_agent_done_events_skipped(tmp_path, monkeypatch)`:
   - Create DB with 1 AGENT_DONE and 1 PHASE_START event.
   - Monkeypatch `_do_export`.
   - Assert `_do_export` called exactly once (only AGENT_DONE).

---

### Done criteria for this conversation

All of the following must pass:

```bash
cd C:\Users\Yafit\pathly-adapters
pathly-otel-export --help
python -m pytest tests/test_otel_export_cli.py -v
python -m pytest tests/ -q
```

All must exit 0 with no failures.
