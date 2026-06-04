## Completion report (AGENT_DONE)

After the stage agent completes, write an AGENT_DONE event **directly** to EVENTS.jsonl.
This is **mandatory** — the supervisor reads this field as the authoritative result.

1. Compute wall_seconds: `python3 -c "import time; print(int(time.time()) - BUILD_START)"`
2. Parse from the sub-agent's `<usage>` block: `total_tokens`, `tool_uses`, `duration_ms` (0 if absent).
3. Write the event directly — **do not invoke a skill**, run this command:

```bash
python3 -c "
import json, datetime, sys
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
event = {
  'type': 'AGENT_DONE',
  'agent': 'AGENT_ROLE',
  'model': 'claude-sonnet-4-6',
  'conversation': CONV_N,
  'result': 'DONE',
  'summary': 'SUMMARY_SENTENCE',
  'total_tokens': TOTAL_TOKENS,
  'tool_uses': TOOL_USES,
  'wall_seconds': WALL_SECONDS,
  'cost_usd': 0.0,
  'ts': ts,
  'schema_version': 1,
}
path = '<feature_path>/EVENTS.jsonl'
with open(path, 'a', encoding='utf-8') as f:
    f.write(json.dumps(event) + chr(10))
print('AGENT_DONE written')
"
```

Replace the UPPER_CASE placeholders with actual values:
- `AGENT_ROLE` — e.g. `builder`, `reviewer`, `tester`
- `CONV_N` — integer conversation number (0 for non-build stages)
- `SUMMARY_SENTENCE` — one sentence: what was done and the outcome
- `TOTAL_TOKENS`, `TOOL_USES`, `WALL_SECONDS` — from `<usage>` block or wall_seconds computation

`<feature>` and `<feature_path>` are pre-substituted by the runner — use the values as written.

Return. The orchestrator determines the next state from `transition_rules`.
