# log-agent-done

Internal utility — writes an AGENT_DONE event to the central DB via eventlog and POSTs telemetry
to the Pathly HTTP backend. Falls back to EVENTS.jsonl in offline/codex mode. Call this once per
completed stage instead of manually recording AGENT_DONE and calling record-cost separately.

Provider-agnostic: supports Claude, OpenAI, Google Gemini, and any other model.
Pass `cost_usd` directly if the API response included it. Otherwise cost is computed
from token counts using a built-in pricing table (Claude models only).

## Arguments

`$ARGUMENTS` is a JSON object with these fields:
- `agent` (required): agent name — `"builder"`, `"reviewer"`, `"tester"`, `"planner"`, `"designer"`, `"quick"`
- `feature` (required): feature slug matching the pathly/plans/ folder name
- `conversation` (required): conversation number (integer); use 0 for non-build stages
- `result` (required): `"DONE"` or `"PASS"`
- `model` (optional): model ID used by the agent (e.g. `"claude-sonnet-4-6"`, `"gpt-4o"`, `"gemini-2.0-flash"`); used for cost computation; defaults to `"claude-sonnet-4-6"`
- `cost_usd` (optional): cost in USD if already known from API response — **takes priority over computation**; default not set
- `input_tokens` (optional): input token count; default 0
- `output_tokens` (optional): output token count; default 0
- `total_tokens` (optional): total token count from `<usage>` block — used when input/output split is unknown; default 0
- `tool_uses` (optional): tool call count from `<usage>` block; default 0
- `duration_ms` (optional): duration in milliseconds from `<usage>` block; default 0
- `wall_seconds` (optional): fallback elapsed seconds if duration_ms is 0; default 0
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

## Step 2 — Compute cost_usd

**Priority 1 — Caller-provided cost:**
If `cost_usd` is present in `$ARGUMENTS` and is a number, use it directly. Skip pricing table.

**Priority 2 — Claude pricing table (Anthropic models only):**

Only applies if model starts with `claude-`. Pricing per million tokens (as of 2025):

| Model prefix | Input $/MTok | Output $/MTok |
|---|---|---|
| `claude-opus-4` | 15.00 | 75.00 |
| `claude-sonnet-4` | 3.00 | 15.00 |
| `claude-haiku-4` | 0.80 | 4.00 |
| `claude-*` (other/unknown) | 3.00 | 15.00 |

If both `input_tokens` and `output_tokens` are provided and > 0:
```
cost_usd = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
```

Else if only `total_tokens` > 0, approximate with 80/20 split:
```
input_est  = total_tokens * 0.80
output_est = total_tokens * 0.20
cost_usd   = (input_est / 1_000_000 * input_rate) + (output_est / 1_000_000 * output_rate)
```

**Priority 3 — Non-Claude / unknown models:**
If model does not start with `claude-` and `cost_usd` was not provided:
- Set `cost_usd = 0.0`
- Set `cost_note = "cost not computed — pass cost_usd directly for non-Claude models"`
- Print: `log-agent-done: cost_usd not computed for model "<model>" — pass cost_usd in arguments if available`

**Final:** Round `cost_usd` to 6 decimal places.

Set `tokens_in` and `tokens_out`:
- If `input_tokens` / `output_tokens` provided: use directly
- If only `total_tokens`: `tokens_in = round(total_tokens * 0.80)`, `tokens_out = round(total_tokens * 0.20)`
- Else: both 0

## Step 3 — Write AGENT_DONE to DB (primary) with EVENTS.jsonl backup

**Primary path — via eventlog (writes to central SQLite DB):**

```python
python3 -c "
import datetime, sys
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
event = {
    'type': 'AGENT_DONE',
    'agent': '<agent>',
    'model': '<model>',
    'conversation': <conversation>,
    'result': '<result>',
    'summary': '<summary>',
    'tokens_in': <tokens_in>,
    'tokens_out': <tokens_out>,
    'total_tokens': <total_tokens>,
    'cost_usd': <cost_usd>,
    'tool_uses': <tool_uses>,
    'wall_seconds': <wall_seconds>,
    'ts': ts,
    'schema_version': 1,
}
try:
    from pathly_orchestrator.eventlog import append_event as _ae
    _ae('pathly/plans/<feature>', event)
    print('AGENT_DONE written to DB')
except Exception as _exc:
    # Fallback: write directly to EVENTS.jsonl when eventlog is unavailable (offline/codex mode)
    import json, pathlib
    path = pathlib.Path('pathly/plans/<feature>/EVENTS.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as _f:
        _f.write(json.dumps(event) + chr(10))
    print(f'AGENT_DONE written to EVENTS.jsonl (fallback: {_exc})')
"
```

If the directory `pathly/plans/<feature>/` does not exist, stop with an error before running the above.

## Step 4 — POST telemetry to HTTP backend

Check server health with a real JSON-capable client or the FSM HTTP health
endpoint. Do not use shell-escaped `curl` JSON on PowerShell.

If unavailable:
1. Start in background: `pathly-fsm-http`
2. Wait 2 seconds, retry once.
3. If still unavailable: print `log-agent-done: HTTP backend unavailable, skipping telemetry` and stop (do not fail).

POST telemetry with the packaged helper first:
```bash
pathly-fsm-call record-activity \
  --agent "<agent>" \
  --feature "<feature>" \
  --summary "<summary>" \
  --conversation <conversation> \
  --total-tokens <total_tokens> \
  --tool-uses <tool_uses> \
  --wall-seconds <wall_seconds> \
  --duration-ms <duration_ms> \
  --input-tokens <tokens_in> \
  --output-tokens <tokens_out> \
  --cost-usd <cost_usd>
```

If the helper is unavailable, use a JSON-capable client or the `pathly_orchestrator.fsm_http_client` module directly. Do not hand-roll shell-escaped JSON with `curl` on PowerShell.

If response contains `"status":"recorded"`: silent success.
If error: print `log-agent-done warning: <error>` and continue.
