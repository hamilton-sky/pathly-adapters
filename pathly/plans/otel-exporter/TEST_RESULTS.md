# TEST_RESULTS — otel-exporter

RESULT: PASS

## Story Group Summary

| Story | Title | Status |
|---|---|---|
| S1 | Real-time OTLP span export | PASS |
| S2 | Log record | PASS |
| S3 | Batch CLI | PASS |
| S4 | Env var gate | PASS |
| S5 | Silent failures | PASS |

---

## Detailed Test Plan

### S1 — Real-time OTLP span export

**AC1.1: export_span_async fires HTTP POST to /v1/traces when PATHLY_OTEL_ENDPOINT is set**
- Test: `test_log_posted_when_summary_present` — verifies urlopen called with /v1/traces URL
- Status: PASS

**AC1.2: POST body is valid OTLP JSON (ResourceSpans array)**
- Test: `test_span_payload_structure` — asserts `resourceSpans` key present and well-formed
- Status: PASS

**AC1.3: Span has all required attributes**
- Test: `test_span_payload_structure` — checks attr_keys for gen_ai.agent.name and pathly.cost_usd; code inspection confirms all 9 required attributes present in `_build_span_payload`
- Status: PASS
- Notes: All required attributes verified: gen_ai.agent.name, gen_ai.workflow.name, gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, gen_ai.request.model, gen_ai.conversation.id, pathly.cost_usd, pathly.tool_uses, pathly.result

**AC1.4: startTimeUnixNano and endTimeUnixNano differ by wall_seconds * 1e9**
- Test: Manual verification — `int(endTimeUnixNano) - int(startTimeUnixNano) == 30000000000` for wall_seconds=30
- Status: PASS

**AC1.5: STATUS_CODE_OK when result in {pass, done, DONE}; STATUS_CODE_ERROR otherwise**
- Test: `test_span_status_ok` (pass, done, DONE) and `test_span_status_error` (fail, error)
- Status: PASS
- Notes: Implementation uses `.lower()` on result before set membership check — "DONE" maps to 1 correctly

**AC1.6: Span name is "invoke_agent {agent}"**
- Test: `test_span_payload_structure` — asserts `span["name"] == "invoke_agent builder"`
- Status: PASS

**AC1.7: Export runs in background thread (daemon=True)**
- Test: Manual verification via threading.Thread introspection — daemon=True confirmed
- Status: PASS
- Notes: otel_export.py line 155: `threading.Thread(target=_do_export, args=(event, endpoint), daemon=True)`

**AC1.8: trace_id and span_id from event used; random generated if absent**
- Test: `test_span_payload_structure` (explicit ids used); manual check confirms secrets.token_hex(16)/token_hex(8) when absent (len 32 and 16 respectively)
- Status: PASS

---

### S2 — Log record

**AC2.1: LogRecord posted to /v1/logs when summary non-empty**
- Test: `test_log_posted_when_summary_present` — urlopen called twice (traces + logs)
- Status: PASS

**AC2.2: Same traceId/spanId as span**
- Test: Code inspection — `_do_export` extracts trace_id/span_id from span payload and passes them to `_build_log_payload`
- Status: PASS

**AC2.3/AC2.4: Truncated at 65535**
- Test: Manual verification — `_build_log_payload` with 70000-char summary returns body of len 65535
- Status: PASS

**AC2.5: No log if summary empty**
- Test: `test_log_not_posted_when_no_summary` — urlopen called only once (traces only) when summary=""
- Status: PASS

---

### S3 — Batch CLI

**AC3.1: pathly-otel-export CLI with --feature**
- Test: All CLI tests use --feature flag; `cli_main` uses argparse with `required=True`
- Status: PASS

**AC3.2: --endpoint**
- Test: All CLI tests pass --endpoint; confirmed required
- Status: PASS

**AC3.3: --project-root**
- Test: `test_cli_missing_db`, `test_cli_dry_run`, etc. all use --project-root
- Status: PASS

**AC3.4: --dry-run**
- Test: `test_cli_dry_run` — confirms no _do_export calls and "dry-run" in stdout
- Status: PASS

**AC3.5: Exits 0 on success**
- Test: `test_cli_exports_spans`, `test_cli_dry_run`, `test_cli_zero_events` — all assert exit code 0
- Status: PASS

**AC3.6: Exits 1 on failure**
- Test: `test_cli_missing_db`, `test_cli_export_failure_exits_1` — assert exit code 1
- Status: PASS

**AC3.7: Filters non-AGENT_DONE events**
- Test: `test_cli_non_agent_done_events_skipped` — mixed event types, only 1 AGENT_DONE exported
- Status: PASS

**AC3.8: Registered in pyproject.toml**
- Test: pyproject.toml line 30: `pathly-otel-export = "pathly_orchestrator.otel_export:cli_main"`; import check confirms `cli_main` importable
- Status: PASS

---

### S4 — Env var gate

**AC4.1: No-op when env var unset**
- Test: `test_no_op_when_env_unset` — threading.Thread not called when PATHLY_OTEL_ENDPOINT absent
- Status: PASS

**AC4.2: Read at call time not import time**
- Test: Code inspection — `export_span_async` calls `os.environ.get("PATHLY_OTEL_ENDPOINT")` at invocation time (line 152), not at module level
- Status: PASS

**AC4.3/AC4.4: No side effects at import**
- Test: Code inspection — no module-level os.environ reads for PATHLY_OTEL_ENDPOINT
- Status: PASS

---

### S5 — Silent failures

**AC5.1: Network OSError swallowed**
- Test: `test_do_export_swallows_network_error` — OSError caught, warning logged
- Status: PASS

**AC5.2: HTTP 503 swallowed**
- Test: `test_do_export_swallows_http_error` — HTTPError caught, warning logged
- Status: PASS

**AC5.3-5.4: Errors do not propagate**
- Test: Both swallow tests confirm no exception raised; http_server wraps export in try/except (line 818-837)
- Status: PASS

**AC5.5: /record_activity returns 200 even on export failure**
- Test: `test_record_activity_unaffected_by_export_failure` — endpoint pointed at unreachable port, response status still 200
- Status: PASS

---

## Test execution summary

```
tests/test_otel_export.py      9/9 passed
tests/test_otel_export_cli.py  6/6 passed
Full suite                     445 passed, 3 skipped, 0 failed
```

Run date: 2026-06-05
