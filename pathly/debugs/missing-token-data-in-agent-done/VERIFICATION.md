# Verification — AGENT_DONE token/cost fields fix

## Changes Applied

Fixed four skill implementation files to include complete AGENT_DONE event schema:

1. **C:/Users/Yafit/.claude/skills/pathly-build/SKILL.md** (line 147)
   - Before: `{"type": "AGENT_DONE", "agent": "builder", "ts": "<iso-timestamp>"}`
   - After: `{"type": "AGENT_DONE", "agent": "builder", "model": "<model>", "conversation": <N>, "result": "DONE", "tokens_in": <count>, "tokens_out": <count>, "cost_usd": <cost>, "tool_uses": <count>, "wall_seconds": <seconds>, "timestamp": "<iso-timestamp>"}`

2. **C:/Users/Yafit/.claude/skills/pathly-team/build/SKILL.md** (line 129)
   - Before: `{"type": "AGENT_DONE", "agent": "builder"}`
   - After: Full event with all token/cost fields

3. **C:/Users/Yafit/.claude/skills/pathly-team/review/SKILL.md** (line 142)
   - Before: `{"type": "AGENT_DONE", "agent": "reviewer"}`
   - After: Full event with all token/cost fields

4. **C:/Users/Yafit/.claude/skills/pathly-team/retro/SKILL.md** (line 30)
   - Before: `{"type": "AGENT_DONE", "agent": "quick"}`
   - After: Full event with all token/cost fields

## Compatibility Check

### Schema Definition (events.py)
✓ AGENT_DONE schema expects all five token/cost fields
✓ Schema defines optional timestamp (auto-generated if missing)
✓ All other fields are required

### Implementation (eventlog.py)
✓ `append_event()` — Line 59 defaults schema_version, line 60 defaults timestamp
✓ `summary()` — Lines 172-176 read all token/cost fields using `.get()` with defaults
✓ Summary function correctly aggregates tokens and costs

### Integration
✓ retro skill reads EVENTS.jsonl and expects token metrics
✓ retro skill's template generation uses summary() function
✓ No other code writes AGENT_DONE events (confirmed via grep)

## Backward Compatibility

✓ Existing EVENTS.jsonl files continue to parse (schema_version check passes)
✓ summary() function defaults missing fields to 0 (lines 172-176)
✓ No schema version bump required
✓ Old events with missing fields show as "not captured" in retro output
✓ New events with complete data show actual metrics

## Test Coverage

Verified that:
1. All four skill files now write the same AGENT_DONE schema
2. Schema matches the authoritative definition in events.py
3. eventlog.summary() function correctly reads these fields
4. No other skill files write AGENT_DONE
5. No adapter overrides exist that would bypass this schema

## Expected Results

After this fix:
1. New pipeline runs will write complete AGENT_DONE events with all fields
2. retro skill will read tokens_in, tokens_out, cost_usd, tool_uses, wall_seconds
3. 02-TOKEN-USAGE.md will show actual token metrics instead of "not captured"
4. Cost tracking and telemetry will be functional
5. No breaking changes to existing code

## Verification Method

To verify the fix works:
```bash
# Run a feature pipeline
/pathly-team test-feature

# Check EVENTS.jsonl for AGENT_DONE events
grep AGENT_DONE pathly/plans/test-feature/EVENTS.jsonl | head -1

# Expected output (with actual values):
{"type": "AGENT_DONE", "agent": "builder", "model": "claude-sonnet-4-6", "conversation": 1, "result": "DONE", "tokens_in": 15000, "tokens_out": 3000, "cost_usd": 0.0045, "tool_uses": 12, "wall_seconds": 45, "timestamp": "2026-05-14T..."}

# Check retro output for actual metrics
head -20 pipeline-walkthrough/test-feature/02-TOKEN-USAGE.md
# Should show token counts, not "not captured"
```

## Files Modified

1. C:/Users/Yafit/.claude/skills/pathly-build/SKILL.md
2. C:/Users/Yafit/.claude/skills/pathly-team/build/SKILL.md
3. C:/Users/Yafit/.claude/skills/pathly-team/review/SKILL.md
4. C:/Users/Yafit/.claude/skills/pathly-team/retro/SKILL.md

All changes are additive — adding required fields to event schema. No breaking changes to existing functionality.
