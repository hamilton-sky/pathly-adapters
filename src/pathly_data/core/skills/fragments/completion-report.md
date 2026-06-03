## Completion report (usage parse + log-agent-done)

After the stage agent completes (Phase 3), parse the `<usage>` block from its response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

Compute the `wall_seconds` fallback: run
`python -c "import time; print(int(time.time()) - <STAGE>_START)"` using the `<STAGE>_START`
integer recorded at the start of this stage.

Then invoke the `log-agent-done` skill with:

`summary` should be a one-sentence description of what the agent did and the outcome (e.g. "Implemented Conv 1 — added auth middleware to api.ts, all tests pass").

```json
{"agent":"<agent>","feature":"<FEATURE>","conversation":<N>,"result":"<RESULT>","summary":"<one sentence describing what was done and the outcome>","total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"duration_ms":<duration_ms>,"wall_seconds":<computed>}
```
(`wall_seconds` is the fallback computed from `<STAGE>_START`; `log-agent-done` prefers
`duration_ms` if > 0.)

Return. The orchestrator determines the next state from `transition_rules`.
