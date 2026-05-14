# Root Cause — missing AGENT_DONE token/cost fields

## Problem
AGENT_DONE events written to EVENTS.jsonl lack required token and cost fields:
- `tokens_in` (input token count)
- `tokens_out` (output token count)
- `cost_usd` (cost in USD)
- `tool_uses` (number of tool calls)
- `wall_seconds` (elapsed time)

## Impact
- The retro skill reads EVENTS.jsonl and attempts to extract token metrics for 02-TOKEN-USAGE.md
- Since all fields are 0 or missing, the retro skill reports "not captured" for every agent and every metric
- Pipeline telemetry and cost tracking are non-functional

## Root Cause
Four skill implementations write AGENT_DONE events without the required fields:

### 1. pathly-build (generic canonical behavior)
**File:** `C:/Users/Yafit/.claude/skills/pathly-build/SKILL.md` (line 147)
```json
{"type": "AGENT_DONE", "agent": "builder", "ts": "<iso-timestamp>"}
```
Missing: `tokens_in`, `tokens_out`, `cost_usd`, `tool_uses`, `wall_seconds`

### 2. pathly-team/build (team orchestrator implementation)
**File:** `C:/Users/Yafit/.claude/skills/pathly-team/build/SKILL.md` (line 129)
```json
{"type": "AGENT_DONE", "agent": "builder"}
```
Missing: All token/cost fields AND timestamp

### 3. pathly-team/review (team orchestrator implementation)
**File:** `C:/Users/Yafit/.claude/skills/pathly-team/review/SKILL.md` (line 142)
```json
{"type": "AGENT_DONE", "agent": "reviewer"}
```
Missing: All token/cost fields AND timestamp

### 4. pathly-team/retro (team orchestrator implementation)
**File:** `C:/Users/Yafit/.claude/skills/pathly-team/retro/SKILL.md` (line 30)
```json
{"type": "AGENT_DONE", "agent": "quick"}
```
Missing: All token/cost fields AND timestamp

## Authoritative Schema
**File:** `src/pathly_orchestrator/events.py` (lines 34-43)

AGENT_DONE event schema requires:
- `agent` (str) — agent name
- `model` (str) — model ID
- `conversation` (int) — conversation number (0 for non-build agents)
- `result` (str) — "PASS" | "FAIL" | "DONE" | "BLOCKED"
- `tokens_in` (int) — input tokens
- `tokens_out` (int) — output tokens
- `cost_usd` (float) — cost in USD
- `tool_uses` (int) — number of tool calls
- `wall_seconds` (int) — elapsed seconds
- `timestamp` (str) — ISO-8601 UTC (optional, auto-generated if missing)

Example from schema:
```json
{"type":"AGENT_DONE","agent":"builder","model":"claude-sonnet-4-6","conversation":1,"result":"DONE","tokens_in":22000,"tokens_out":4000,"cost_usd":0.0,"tool_uses":23,"wall_seconds":85,"timestamp":"2026-05-11T09:06:25Z"}
```

## Evidence from Real Run
**File:** `pathly/plans/fsm-transition-actions/EVENTS.jsonl` (lines 4-5, 17, 23, 25)

Actual AGENT_DONE events observed:
```json
{"type": "AGENT_DONE", "agent": "builder", "conv": 1}
{"type": "AGENT_DONE", "agent": "builder", "conv": 2}
{"type": "AGENT_DONE", "agent": "reviewer"}
{"type": "AGENT_DONE", "agent": "builder", "ts": "2026-05-14T14:17:26Z"}
{"type": "AGENT_DONE", "agent": "reviewer", "ts": "2026-05-14T14:20:33Z"}
```

Note: Some have `conv` (non-standard), some have `ts`, none have token/cost fields.

## Why This Matters
1. **Retro skill depends on this data**: The retro skill's `summary()` function (eventlog.py lines 147-189) reads AGENT_DONE events and sums tokens and costs. When all fields are missing or zero, it reports "not captured".
2. **Cost tracking is broken**: The pipeline cannot track actual token usage or compute costs for billing/optimization.
3. **Telemetry is lost**: No data to analyze which agents are most expensive or which features consume the most resources.

## Fix Required
Update all four skill implementations to write complete AGENT_DONE events with:
- All five token/cost fields (tokens_in, tokens_out, cost_usd, tool_uses, wall_seconds)
- Model name (from the agent spawn)
- Conversation number (if applicable)
- Result status
- ISO-8601 timestamp
