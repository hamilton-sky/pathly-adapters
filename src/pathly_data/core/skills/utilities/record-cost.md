# record-cost

> Note: for standard pipeline stages that write AGENT_DONE, use `log-agent-done` instead.
> Use `record-cost` only when you need telemetry without an AGENT_DONE event.

Internal utility — POSTs agent completion telemetry to the Pathly HTTP backend.
Use this instead of the MCP `record_activity` tool.
Called by stage skills (build, review, test) after writing AGENT_DONE to EVENTS.jsonl.

## Arguments

`$ARGUMENTS` is a JSON object string with these fields:
- `agent` (required): agent name, e.g. `"builder"`, `"reviewer"`, `"tester"`
- `feature` (required): feature slug, e.g. `"my-feature"`
- `summary` (required): one-line summary of what was done
- `conversation` (optional): conversation number (integer), default 0
- `wall_seconds` (optional): elapsed wall-clock seconds (integer), default 0
- `tool_uses` (optional): number of tool calls made (integer), default 0
- `total_tokens` (optional): total token count from `<usage>` block, default 0
- `duration_ms` (optional): duration in milliseconds from `<usage>` block, default 0 (converted to wall_seconds by backend if wall_seconds is 0)

## Step 1 — Parse arguments

Parse `$ARGUMENTS` as JSON. If `agent`, `feature`, or `summary` are missing, print:
```
record-cost: missing required field(s): <list>. Pass a JSON object with agent, feature, summary.
```
and stop.

## Step 2 — Ensure server is running

```bash
curl -s --max-time 1 http://127.0.0.1:8765/health
```

If it returns `{"status":"ok"}`, proceed to Step 3.

If it fails or times out:
1. Start the server in the background:
   ```bash
   python -m pathly_orchestrator.http_server &
   ```
2. Wait 2 seconds, then retry the health check once.
3. If still unavailable: print a warning and continue without logging (do not fail the parent skill).

## Step 3 — POST telemetry

```bash
curl -s -X POST http://127.0.0.1:8765/record_activity \
  -H "Content-Type: application/json" \
  -d '{"agent":"<agent>","feature":"<feature>","summary":"<summary>","conversation":<conversation>,"wall_seconds":<wall_seconds>,"tool_uses":<tool_uses>,"total_tokens":<total_tokens>,"input_tokens":0,"output_tokens":0,"cost_usd":0}'
```

If the response contains `"status":"recorded"`: print nothing (silent success).
If it returns an error: print `record-cost warning: <error>` and continue (do not fail the parent skill).
