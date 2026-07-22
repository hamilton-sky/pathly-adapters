# Symptom — missing-token-data-in-agent-done

## What broke
AGENT_DONE events written to EVENTS.jsonl do not include token or cost fields.
The pipeline walkthrough's 02-TOKEN-USAGE.md shows "not captured" for every agent and every metric.

## How it manifests
In `pathly/plans/fsm-transition-actions/EVENTS.jsonl`, all AGENT_DONE events look like:
```json
{"type": "AGENT_DONE", "agent": "builder", "conv": 1}
{"type": "AGENT_DONE", "agent": "builder", "conv": 2}
{"type": "AGENT_DONE", "agent": "reviewer"}
{"type": "AGENT_DONE", "agent": "builder", "ts": "2026-05-14T14:17:26Z"}
{"type": "AGENT_DONE", "agent": "reviewer", "ts": "2026-05-14T14:20:33Z"}
```
No `tokens_in`, `tokens_out`, `cost`, `tool_uses`, or `wall_time` fields present.

The retro agent that writes 02-TOKEN-USAGE.md reads EVENTS.jsonl and correctly reports "not captured"
because the data was never written.

## Environment
- Branch: claude/funny-pascal-86c09c (the pipeline run), current master
- Feature: fsm-transition-actions
- EVENTS.jsonl: pathly/plans/fsm-transition-actions/EVENTS.jsonl
- Retro output: pathly/pipeline-walkthrough/fsm-transition-actions/02-TOKEN-USAGE.md

## Expected behavior
AGENT_DONE events should include token usage and cost data so the retro agent can
populate 02-TOKEN-USAGE.md with real numbers instead of "not captured".
