# User Stories — otel-exporter

## S1: Real-time OTLP span export for AGENT_DONE events

**As a** Pathly operator running a pipeline against Jaeger, Grafana Tempo, Datadog, or Honeycomb,
**I want** each completed agent stage to be exported as an OTel span immediately after it is recorded,
**so that** I can see live pipeline traces in my observability backend without any post-processing step.

### Acceptance criteria

- AC1.1: When `PATHLY_OTEL_ENDPOINT` is set and an `AGENT_DONE` event reaches `/record_activity`, a single HTTP POST is made to `{PATHLY_OTEL_ENDPOINT}/v1/traces` within 2 seconds of the event being written to EVENTS.jsonl.
- AC1.2: The POST body is valid OTLP JSON (`ResourceSpans` array). Running `python -c "import json; json.loads(open('captured_span.json').read())"` on a captured request body must not raise.
- AC1.3: The span contains all required attributes: `gen_ai.agent.name`, `gen_ai.workflow.name`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.request.model`, `gen_ai.conversation.id`, `pathly.cost_usd`, `pathly.tool_uses`, `pathly.result`.
- AC1.4: Span `startTimeUnixNano` and `endTimeUnixNano` differ by `wall_seconds * 1_000_000_000`.
- AC1.5: Span status is `STATUS_CODE_OK` when `result` is `pass`, `done`, or `DONE`; `STATUS_CODE_ERROR` otherwise.
- AC1.6: Span name is `invoke_agent {agent}` (e.g. `invoke_agent builder`).
- AC1.7: The export runs in a background thread. The `/record_activity` response time is not affected (verified by: the endpoint returns 200 before the OTLP POST completes).
- AC1.8: `trace_id` and `span_id` on the span match the values from `RunnerState` at the time of the event (32-char hex for trace_id, 16-char hex for span_id). If either is absent from the event, a random value is generated.

### Edge cases

- If the event dict has no `trace_id` field (e.g. events from the CLI path, not from a supervised run), `export_span_async` generates a new random trace_id and span_id for that span.
- If `wall_seconds` is 0 or missing, span duration is 0 (not an error).
- If `tokens_in` and `tokens_out` are both 0 but `total_tokens` is non-zero, use `total_tokens` as `gen_ai.usage.input_tokens` and 0 for output.

---

## S2: OTLP LogRecord export for `summary` field

**As a** developer inspecting a pipeline trace in Grafana Tempo or Honeycomb,
**I want** each agent's narrative summary to appear as a log entry anchored to the same trace and span,
**so that** I can read what the agent actually did without leaving the trace view.

### Acceptance criteria

- AC2.1: When `summary` is present and non-empty on an `AGENT_DONE` event, a `LogRecord` is posted to `{PATHLY_OTEL_ENDPOINT}/v1/logs` in the same background thread as the span export.
- AC2.2: The `LogRecord` body is the `summary` string.
- AC2.3: The `LogRecord` carries the same `traceId` and `spanId` as the span from S1.
- AC2.4: If `summary` is absent or empty, no log POST is made (verified: mock server receives exactly 1 request, not 2).
- AC2.5: The log POST failure does not affect the span POST (each is tried independently; a log POST exception is caught and logged as a warning).

### Edge cases

- Summary strings longer than 65535 characters are truncated to 65535 before being posted (to avoid OTLP payload limits on some backends).

---

## S3: Batch/replay CLI — `pathly-otel-export`

**As a** developer who wants to send historical Pathly pipeline data to a new observability backend,
**I want** a CLI command that reads all events for a feature from SQLite and exports them as spans,
**so that** I can backfill traces without re-running the pipeline.

### Acceptance criteria

- AC3.1: Running `pathly-otel-export --feature <name> --endpoint <url>` with a valid SQLite DB exits with code 0.
- AC3.2: Only `AGENT_DONE` events are exported (other event types are skipped silently).
- AC3.3: The CLI prints one line per exported span: `exported span: invoke_agent {agent} (seq={seq})`.
- AC3.4: The CLI prints a final summary line: `done: {N} spans exported`.
- AC3.5: `--project-root` defaults to the current working directory when not supplied; the CLI resolves `<project_root>/pathly/plans/<feature>/pathly.db`.
- AC3.6: If `pathly.db` does not exist for the feature, the CLI exits with code 1 and prints a clear error message.
- AC3.7: `--dry-run` flag causes the CLI to print what it would export without making any HTTP requests; exits with code 0.
- AC3.8: The CLI is registered as `pathly-otel-export` in `pyproject.toml` pointing to `pathly_orchestrator.otel_export:cli_main`.

### Edge cases

- Features with 0 AGENT_DONE events produce "done: 0 spans exported" and exit 0.
- If the endpoint is unreachable, the CLI prints a warning per failed span and continues; exits with code 1 at the end if any span failed.

---

## S4: `PATHLY_OTEL_ENDPOINT` env var gates all export

**As a** Pathly user who does not use an OTel backend,
**I want** the exporter to be completely inert unless I explicitly configure it,
**so that** there are no unexpected outbound HTTP connections or performance costs.

### Acceptance criteria

- AC4.1: When `PATHLY_OTEL_ENDPOINT` is not set (or is empty), `export_span_async` is a no-op: it returns immediately without spawning any thread.
- AC4.2: When `PATHLY_OTEL_ENDPOINT` is not set, the HTTP server starts and handles `/record_activity` normally — verified by `python -m pytest tests/ -q` passing with no `PATHLY_OTEL_ENDPOINT` in the environment.
- AC4.3: Setting `PATHLY_OTEL_ENDPOINT=http://localhost:4318` enables export; unsetting it (or setting it to empty string) disables it.
- AC4.4: The env var is read at call time (not at module import), so changing it in tests does not require process restart.

---

## S5: Export failures are silent — never raise to caller

**As a** Pathly operator,
**I want** OTel export failures to produce a warning log entry and nothing else,
**so that** a network blip to my observability backend never disrupts the pipeline.

### Acceptance criteria

- AC5.1: A `urllib.request.urlopen` exception inside `export_span_async` is caught; a `logger.warning(...)` line is emitted; the function returns normally.
- AC5.2: An HTTP 5xx response from the endpoint is caught; a `logger.warning(...)` line is emitted with the status code; the function returns normally.
- AC5.3: An HTTP 4xx response from the endpoint is caught and logged as a warning (not an error); the function returns normally.
- AC5.4: No exception from `otel_export.py` ever propagates into `/record_activity` — verified by: mock the entire `_do_export` to raise RuntimeError; `/record_activity` still returns 200.
- AC5.5: Verify command: `python -m pytest tests/test_otel_export.py -q` passes.

---

## Delivery map

| Story | Conversation |
|---|---|
| S4 (env var gate) | Conv 1 — core module |
| S1 (real-time span) | Conv 1 — core module |
| S2 (log record) | Conv 1 — core module |
| S5 (silent failures) | Conv 1 — core module + tests |
| S3 (batch CLI) | Conv 2 — CLI + integration |
