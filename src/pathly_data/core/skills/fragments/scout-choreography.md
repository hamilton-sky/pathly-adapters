## Scout choreography (analyze → scout → compress)

The stage agent (builder / reviewer / tester) declares what context it needs *before* doing the
work, scouts gather that context in parallel, and the findings are compressed into the work prompt.

### Phase 1 — Analyze

Spawn the stage agent with `phase: analyze`. It outputs a `## NEEDS_CONTEXT` block **only** —
the list of things it must know before implementing / reviewing / testing.

NEEDS_CONTEXT format (one entry per line):
```
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
```

Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2 (or use only the stage's
default scout entry, where one is defined).

### Phase 2 — Scout (parallel, max 4)

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: <stage agent>` + the question
- `type: scout` → spawn `scout` with `ROLE: <stage agent>` + scope + question

After each scout/quick returns, parse its `<usage>` block (`subagent_tokens`, `tool_uses`) and
record it immediately — non-blocking, skip if server unavailable:

```bash
# For each scout that returned — replace placeholders with actual values from <usage> block
# model is claude-haiku-4-5-20251001 for scout/quick agents
pathly-fsm-call record-activity \
  --agent "scout" \
  --feature "<feature>" \
  --summary "<question truncated to 80 chars>" \
  --conversation N \
  --model "claude-haiku-4-5-20251001" \
  --total-tokens SCOUT_TOKENS \
  --tool-uses SCOUT_TOOL_USES \
  --wall-seconds 0 \
  --cost-usd SCOUT_COST_USD
```

Compute `SCOUT_COST_USD` using haiku rates (input $0.80/MTok, output $4.00/MTok) with 80/20 split.
Add each scout's `SCOUT_TOKENS` to the stage running total for the final AGENT_DONE.

Compress all returned findings into a short summary and inject it into the Phase 3 work prompt
as the stage's findings section.
