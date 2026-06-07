## Completion report (AGENT_DONE)

After the stage agent completes, write an AGENT_DONE event to the **central DB** via eventlog.
This is **mandatory** — the supervisor reads this event as the authoritative result.

1. Compute wall_seconds: `python3 -c "import time; print(int(time.time()) - BUILD_START)"`
2. Parse from the sub-agent's `<usage>` block: `total_tokens`, `tool_uses`, `duration_ms` (0 if absent).
3. Compute `cost_usd` from `total_tokens` and `model` using an 80/20 input/output token split:

   | Model prefix | Input $/MTok | Output $/MTok |
   |---|---|---|
   | `claude-opus-4` | 15.00 | 75.00 |
   | `claude-sonnet-4` | 3.00 | 15.00 |
   | `claude-haiku-4` | 0.80 | 4.00 |
   | other / unknown | — | set `cost_usd = 0.0` |

   Formula:
   ```
   in_est  = total_tokens * 0.8
   out_est = total_tokens * 0.2
   cost_usd = round((in_est / 1_000_000 * input_rate) + (out_est / 1_000_000 * output_rate), 6)
   ```

4. Write the event to the central DB — **do not invoke a skill**, run this command:

```bash
python3 -c "
import json, datetime
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
event = {
  'type': 'AGENT_DONE',
  'agent': 'AGENT_ROLE',
  'model': 'MODEL_ID',
  'conversation': CONV_N,
  'result': 'DONE',
  'summary': 'SUMMARY_SENTENCE',
  'total_tokens': TOTAL_TOKENS,
  'tool_uses': TOOL_USES,
  'wall_seconds': WALL_SECONDS,
  'cost_usd': COST_USD,
  'ts': ts,
  'schema_version': 1,
}
try:
    from pathly_orchestrator.eventlog import append_event as _ae
    _ae('<feature_path>', event)
    print('AGENT_DONE written to DB')
except Exception as _exc:
    # Fallback: write to EVENTS.jsonl when eventlog unavailable (offline/codex mode)
    import pathlib
    path = pathlib.Path('<feature_path>/EVENTS.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as _f:
        _f.write(json.dumps(event) + chr(10))
    print(f'AGENT_DONE written to EVENTS.jsonl (fallback: {_exc})')
"
```

5. POST to the activity log — non-blocking; skip silently if server is unavailable:

```bash
pathly-fsm-call record-activity \
  --agent "AGENT_ROLE" \
  --feature "<feature>" \
  --summary "SUMMARY_SENTENCE" \
  --conversation CONV_N \
  --model "MODEL_ID" \
  --total-tokens TOTAL_TOKENS \
  --tool-uses TOOL_USES \
  --wall-seconds WALL_SECONDS \
  --cost-usd COST_USD
```

Replace the UPPER_CASE placeholders with actual values:
- `AGENT_ROLE` — e.g. `builder`, `reviewer`, `tester`
- `MODEL_ID` — model used in this stage (e.g. `claude-sonnet-4-6`)
- `CONV_N` — integer conversation number (0 for non-build stages)
- `SUMMARY_SENTENCE` — one sentence: what was done and the outcome
- `TOTAL_TOKENS`, `TOOL_USES`, `WALL_SECONDS` — from `<usage>` block or wall_seconds computation
- `COST_USD` — computed in step 3

`<feature>` and `<feature_path>` are pre-substituted by the runner — use the values as written.

Return. The orchestrator determines the next state from `transition_rules`.
