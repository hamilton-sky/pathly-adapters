# Implementation Plan — otel-exporter

## Overview

Add an optional, zero-dependency OTLP HTTP exporter to the Pathly orchestrator.
The exporter lives entirely in one new file (`otel_export.py`) and one new CLI entry point.
Core Pathly storage and the FSM are untouched.

No new pip dependencies. All HTTP is done with stdlib `urllib.request` + `json`.

---

## Phase 1 — Core export module (`otel_export.py`)

**Delivers:** S1, S2, S4, S5

### File

`src/pathly_orchestrator/otel_export.py` — new file, ~200 LOC

### What to implement

1. `_build_span_payload(event: dict) -> dict`
   - Converts a Pathly event dict to an OTLP `ExportTraceServiceRequest` JSON structure.
   - Reads `trace_id`, `span_id` from event; falls back to `secrets.token_hex(16/8)` if absent.
   - Maps all required attributes per the story spec (S1 AC1.3).
   - Computes `startTimeUnixNano` from `ts` field (ISO 8601 parse); `endTimeUnixNano = start + wall_seconds * 1_000_000_000`.
   - Sets span status from `result` field.
   - Span name: `invoke_agent {agent}`.
   - Resource attributes: `service.name = "pathly"`, `service.version` from package `importlib.metadata`.

2. `_build_log_payload(event: dict, trace_id: str, span_id: str) -> dict`
   - Builds an OTLP `ExportLogsServiceRequest` with one `LogRecord`.
   - Body = `event["summary"]` truncated to 65535 chars.
   - Uses the same `trace_id` + `span_id` as the span.

3. `_do_export(event: dict, endpoint: str) -> None`
   - Posts span to `{endpoint}/v1/traces`.
   - If `summary` is non-empty, posts log to `{endpoint}/v1/logs`.
   - Each POST uses `urllib.request.urlopen` with a 5-second timeout.
   - Catches all exceptions; logs warnings. Never raises.
   - Logs response status at DEBUG level on success.

4. `export_span_async(event: dict) -> None`
   - Reads `PATHLY_OTEL_ENDPOINT` env var at call time.
   - If empty/unset: returns immediately (no-op).
   - Otherwise: spawns a daemon `threading.Thread` targeting `_do_export(event, endpoint)`.
   - Thread is daemon=True so it never blocks interpreter shutdown.

### Done-when

- File exists at `src/pathly_orchestrator/otel_export.py`.
- `python -c "from pathly_orchestrator.otel_export import export_span_async; print('ok')"` exits 0.

### Verify command

```bash
cd C:\Users\Yafit\pathly-adapters
python -c "from pathly_orchestrator.otel_export import export_span_async, _build_span_payload; p = _build_span_payload({'type':'AGENT_DONE','agent':'builder','feature':'test','ts':'2026-01-01T00:00:00Z','result':'pass','tokens_in':100,'tokens_out':50,'cost_usd':0.001,'wall_seconds':30,'model':'claude-sonnet-4-6','conversation':1}); import json; print(json.dumps(p, indent=2)[:200])"
```

---

## Phase 2 — Hook into `/record_activity`

**Delivers:** S1 real-time path (AC1.7 — fire-and-forget)

### File

`src/pathly_orchestrator/http_server.py` — modify `record_activity_endpoint`

### What to change

After the `_append_agent_done_event(...)` call block (around line 805), add:

```python
# Fire-and-forget OTel export — no-op if PATHLY_OTEL_ENDPOINT is unset
if project_root and data.get("feature"):
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
```

The import is inside the function body (lazy import) to avoid any startup cost when the feature is disabled.

### Done-when

- `grep -n "otel_export" src/pathly_orchestrator/http_server.py` returns at least one match.
- Starting the server with `PATHLY_OTEL_ENDPOINT=` unset and calling `/record_activity` returns 200 in < 50ms.

### Verify command

```bash
cd C:\Users\Yafit\pathly-adapters
python -m pytest tests/ -q -k "record_activity"
```

---

## Phase 3 — Unit tests

**Delivers:** S5 AC5.4, AC5.5; S4 AC4.2; S1 verification

### File

`tests/test_otel_export.py` — new file

### Tests to write

1. `test_no_op_when_env_unset` — call `export_span_async({...})` with no env var; assert no threads spawned (monkeypatch `threading.Thread`).
2. `test_span_payload_structure` — call `_build_span_payload(minimal_event)` and assert all required attributes are present in the JSON structure.
3. `test_span_status_ok` — result=`pass` → `STATUS_CODE_OK`.
4. `test_span_status_error` — result=`fail` → `STATUS_CODE_ERROR`.
5. `test_do_export_swallows_network_error` — monkeypatch `urllib.request.urlopen` to raise `OSError`; call `_do_export`; assert no exception raised and warning logged.
6. `test_do_export_swallows_http_error` — monkeypatch to raise `urllib.error.HTTPError` with code 503; assert warning logged, no raise.
7. `test_log_not_posted_when_no_summary` — monkeypatch `urlopen`; call `_do_export` with event missing `summary`; assert `urlopen` called exactly once (only spans endpoint).
8. `test_log_posted_when_summary_present` — event has `summary = "did things"`; assert `urlopen` called twice.
9. `test_record_activity_unaffected_by_export_failure` — integration test: start Flask test client, set `PATHLY_OTEL_ENDPOINT=http://127.0.0.1:1`, POST `/record_activity` with valid body; assert 200 returned.

### Done-when

- `python -m pytest tests/test_otel_export.py -q` exits 0 with 9 tests passing.

### Verify command

```bash
cd C:\Users\Yafit\pathly-adapters
python -m pytest tests/test_otel_export.py -v
```

---

## Phase 4 — Batch CLI (`pathly-otel-export`)

**Delivers:** S3

### Files

- `src/pathly_orchestrator/otel_export.py` — add `cli_main()` function (same file as Phase 1)
- `pyproject.toml` — add entry point

### What to implement in `cli_main()`

```
usage: pathly-otel-export --feature FEATURE --endpoint URL
                          [--project-root PATH] [--dry-run]
```

1. Parse args with `argparse`.
2. Resolve `project_root` (arg or `os.getcwd()`).
3. Open SQLite DB at `<project_root>/pathly/plans/<feature>/pathly.db`; exit 1 with message if not found.
4. Call `db.read_events(conn, feature)` to get all events.
5. Filter to `type == "AGENT_DONE"`.
6. For each event: if `--dry-run`, print line and skip; else call `_do_export(event, endpoint)` synchronously (not async — CLI waits for each).
7. Track failures; print summary; exit 1 if any failed.

### pyproject.toml change

Add to `[project.scripts]`:
```toml
pathly-otel-export = "pathly_orchestrator.otel_export:cli_main"
```

### Done-when

- `pathly-otel-export --help` exits 0 and shows usage.
- `grep "pathly-otel-export" pyproject.toml` returns a match.

### Verify command

```bash
cd C:\Users\Yafit\pathly-adapters
# After pip install -e .
pathly-otel-export --help
```

---

## Phase 5 — CLI tests

**Delivers:** S3 AC3.1–AC3.8 verification

### File

`tests/test_otel_export_cli.py` — new file

### Tests to write

1. `test_cli_help_exits_0` — subprocess call `pathly-otel-export --help`; assert exit code 0.
2. `test_cli_missing_db` — call `cli_main` with a feature that has no DB; assert SystemExit(1).
3. `test_cli_dry_run` — create a temp SQLite DB with 2 AGENT_DONE events; run with `--dry-run`; assert 0 HTTP calls made and exit 0.
4. `test_cli_exports_spans` — create temp DB; monkeypatch `_do_export`; run CLI; assert `_do_export` called twice (once per event).
5. `test_cli_zero_events` — DB has no AGENT_DONE events; assert "done: 0 spans exported" in stdout and exit 0.
6. `test_cli_export_failure_exits_1` — monkeypatch `_do_export` to raise on first call; assert exit 1 at end.

### Done-when

- `python -m pytest tests/test_otel_export_cli.py -q` exits 0.

### Verify command

```bash
cd C:\Users\Yafit\pathly-adapters
python -m pytest tests/test_otel_export_cli.py -v
```

---

## Full test suite regression

After both conversations complete:

```bash
cd C:\Users\Yafit\pathly-adapters
python -m pytest tests/ -q
```

Must pass with 0 failures.

---

## File change summary

| File | Change |
|---|---|
| `src/pathly_orchestrator/otel_export.py` | New — all export logic + CLI |
| `src/pathly_orchestrator/http_server.py` | +8 lines in `record_activity_endpoint` |
| `pyproject.toml` | +1 script entry point |
| `tests/test_otel_export.py` | New — 9 unit tests |
| `tests/test_otel_export_cli.py` | New — 6 CLI tests |
