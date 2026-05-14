# Fix — Add token/cost fields to AGENT_DONE events

## Solution
Update four skill implementation files to write complete AGENT_DONE events with all required fields per the schema in `src/pathly_orchestrator/events.py`.

## Changes Required

### 1. pathly-build/SKILL.md (line 147)
**Before:**
```json
{"type": "AGENT_DONE", "agent": "builder", "ts": "<iso-timestamp>"}
```

**After:**
```json
{"type": "AGENT_DONE", "agent": "builder", "model": "<model>", "conversation": <N>, "result": "DONE", "tokens_in": <count>, "tokens_out": <count>, "cost_usd": <cost>, "tool_uses": <count>, "wall_seconds": <seconds>, "timestamp": "<iso-timestamp>"}
```

Where:
- `<model>` = the model ID passed to builder (e.g., "claude-sonnet-4-6")
- `<N>` = conversation number from STATE.json or PROGRESS.md
- `<count>` = actual counts from agent output or 0 if unknown
- `<cost>` = computed cost or 0.0 if unknown
- `<seconds>` = elapsed time in seconds or 0 if unknown

### 2. pathly-team/build/SKILL.md (line 129)
**Before:**
```json
{"type": "AGENT_DONE", "agent": "builder"}
```

**After:**
```json
{"type": "AGENT_DONE", "agent": "builder", "model": "<model>", "conversation": <N>, "result": "DONE", "tokens_in": <count>, "tokens_out": <count>, "cost_usd": <cost>, "tool_uses": <count>, "wall_seconds": <seconds>, "timestamp": "<iso-timestamp>"}
```

### 3. pathly-team/review/SKILL.md (line 142)
**Before:**
```json
{"type": "AGENT_DONE", "agent": "reviewer"}
```

**After:**
```json
{"type": "AGENT_DONE", "agent": "reviewer", "model": "<model>", "conversation": <N>, "result": "PASS", "tokens_in": <count>, "tokens_out": <count>, "cost_usd": <cost>, "tool_uses": <count>, "wall_seconds": <seconds>, "timestamp": "<iso-timestamp>"}
```

Note: `result` is "PASS" for reviewer (phase 3 passes review).

### 4. pathly-team/retro/SKILL.md (line 30)
**Before:**
```json
{"type": "AGENT_DONE", "agent": "quick"}
```

**After:**
```json
{"type": "AGENT_DONE", "agent": "quick", "model": "<model>", "conversation": 0, "result": "DONE", "tokens_in": <count>, "tokens_out": <count>, "cost_usd": <cost>, "tool_uses": <count>, "wall_seconds": <seconds>, "timestamp": "<iso-timestamp>"}
```

Note: Quick is a non-build agent, so `conversation` is always 0.

## Implementation Notes

1. **Token/cost capture**: LLM agents can extract token counts from their own invocation metadata. If running in environments where token counts are unavailable (legacy systems), use 0 as placeholder. The eventlog `summary()` function gracefully defaults missing fields to 0.

2. **Model name**: Captured from the spawned agent's model parameter or the adapter's config.

3. **Result status**: 
   - Builder/architect/quick: "DONE"
   - Reviewer: "PASS" (when no failures found)
   - Tester: "PASS" or "FAIL"

4. **Timestamp**: The eventlog module auto-generates this if missing, but explicit timestamps are preferred for accurate wall-clock tracking.

5. **Backward compatibility**: Adding fields to JSON events is safe — the eventlog parser ignores unknown fields and defaults missing fields to 0/0.0. No migration needed for existing EVENTS.jsonl files.

## Verification
After applying fixes:
1. Run a full pipeline: `/pathly-team <feature>`
2. Check EVENTS.jsonl: all AGENT_DONE events should include the five token/cost fields
3. Run retro: `02-TOKEN-USAGE.md` should show actual token counts, not "not captured"
4. Compute costs using the formula from eventlog: `cost = (tokens_in + tokens_out) * model_rate`

## Files to Modify
1. C:/Users/Yafit/.claude/skills/pathly-build/SKILL.md
2. C:/Users/Yafit/.claude/skills/pathly-team/build/SKILL.md
3. C:/Users/Yafit/.claude/skills/pathly-team/review/SKILL.md
4. C:/Users/Yafit/.claude/skills/pathly-team/retro/SKILL.md
