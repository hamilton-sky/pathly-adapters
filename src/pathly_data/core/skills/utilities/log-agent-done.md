# log-agent-done

Internal utility — writes an AGENT_DONE event to EVENTS.jsonl and POSTs telemetry
to the Pathly HTTP backend. Call this once per completed stage instead of manually
appending AGENT_DONE and calling record-cost separately.

## Arguments

`$ARGUMENTS` is a JSON object with these fields:
- `agent` (required): agent name — `"builder"`, `"reviewer"`, `"tester"`, `"planner"`, `"designer"`, `"quick"`
- `feature` (required): feature slug matching the plans/ folder name
- `conversation` (required): conversation number (integer); use 0 for non-build stages
- `result` (required): `"DONE"` or `"PASS"`
- `total_tokens` (optional): total token count from `<usage>` block, default 0
- `tool_uses` (optional): tool call count from `<usage>` block, default 0
- `duration_ms` (optional): duration in milliseconds from `<usage>` block, default 0
- `wall_seconds` (optional): fallback elapsed seconds if duration_ms is 0, default 0
- `summary` (optional): one-line summary for the activity log; defaults to `"<agent> conv <conversation> <result>"`

## Step 1 — Parse and validate

Parse `$ARGUMENTS` as JSON. If `agent`, `feature`, `conversation`, or `result` are missing, print:
```
log-agent-done: missing required field(s): <list>
```
and stop.

Compute final `wall_seconds`:
- If `duration_ms` > 0: `wall_seconds = duration_ms // 1000`
- Else: use provided `wall_seconds` (default 0)

Build `summary` if not provided: `"<agent> conv <conversation> <result>"`

## Step 2 — Write AGENT_DONE to EVENTS.jsonl

Append this JSON line to `pathly/plans/<feature>/EVENTS.jsonl`:
```json
{"type":"AGENT_DONE","agent":"<agent>","model":"<model>","conversation":<conversation>,"result":"<result>","tokens_in":0,"tokens_out":0,"total_tokens":<total_tokens>,"cost_usd":0,"tool_uses":<tool_uses>,"wall_seconds":<wall_seconds>,"ts":"<iso-timestamp>","schema_version":1}
```

If the file does not exist, create it. If the directory does not exist, stop with an error.

## Step 3 — POST telemetry to HTTP backend

Check server health:
```bash
curl -s --max-time 1 http://127.0.0.1:8765/health
```

If unavailable:
1. Start in background: `python -m pathly_orchestrator.http_server &`
2. Wait 2 seconds, retry once.
3. If still unavailable: print `log-agent-done: HTTP backend unavailable, skipping telemetry` and stop (do not fail).

POST telemetry:
```bash
curl -s -X POST http://127.0.0.1:8765/record_activity \
  -H "Content-Type: application/json" \
  -d '{"agent":"<agent>","feature":"<feature>","summary":"<summary>","conversation":<conversation>,"total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"wall_seconds":<wall_seconds>,"duration_ms":<duration_ms>,"input_tokens":0,"output_tokens":0,"cost_usd":0}'
```

If response contains `"status":"recorded"`: silent success.
If error: print `log-agent-done warning: <error>` and continue.
