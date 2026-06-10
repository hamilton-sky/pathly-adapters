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

Pass `cost_usd` from the provider's output payload. Do not compute cost in the skill. The server resolves cost via the pricing registry.

Set `tokens_in` and `tokens_out`:
- If `input_tokens` / `output_tokens` provided: use directly
- Else: both 0

## Step 3 — Write AGENT_DONE via HTTP endpoint (primary) with DB/EVENTS.jsonl fallback

Build the event dict first:

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
import json, pathlib

_written = False

# Primary path: POST to HTTP endpoint
try:
    import urllib.request
    body = json.dumps({
        'type': event['type'],
        'feature': '<feature>',
        'project_root': str(pathlib.Path.cwd()),
        'payload': event,
    }).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8765/runner/event',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    import urllib.error
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print('AGENT_DONE written via HTTP /runner/event')
                _written = True
    except urllib.error.URLError:
        pass  # server unreachable — fall through to local fallback
except Exception:
    pass

# Fallback: write via eventlog (DB-primary, EVENTS.jsonl secondary)
if not _written:
    try:
        from pathly_orchestrator.eventlog import append_event as _ae
        _ae('pathly/plans/<feature>', event)
        print('AGENT_DONE written to DB (fallback)')
    except Exception as _exc:
        # Last resort: write directly to EVENTS.jsonl
        path = pathlib.Path('pathly/plans/<feature>/EVENTS.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as _f:
            _f.write(json.dumps(event) + chr(10))
        print(f'AGENT_DONE written to EVENTS.jsonl (last resort: {_exc})')

# AC2.5 dual-write: always append to EVENTS.jsonl as backup
path = pathlib.Path('pathly/plans/<feature>/EVENTS.jsonl')
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, 'a', encoding='utf-8') as _f:
    _f.write(json.dumps(event) + chr(10))
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
  --model "<model>" \
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
