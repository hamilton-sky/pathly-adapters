# Feature: pathly-observability

## What this is

Add structured phase-level observability to the Pathly framework. Today, EVENTS.jsonl records
only `AGENT_DONE` events. There is no way to see which internal phase (analyze, scout, implement,
review, test) an agent was in when it ran, how long each phase took, or how many scouts were
spawned per phase. Rigor levels exist as a concept but are not enforced or recorded anywhere in
the agent or skill layer.

This feature delivers:
1. A `/record_phase` HTTP endpoint and `PHASE_START`/`PHASE_DONE` event schema
2. Phase-boundary logging calls added to all six development skills
3. Three-phase structure enforced in `design.md` and `storm.md`
4. `rigor_contract` tables embedded in all six agent contracts, plus `stage_brief` sections

## Who benefits

- **Pipeline operators** — can see where time is spent and whether scout counts match rigor level
- **Planner/architect** — can verify phases completed before promoting a feature
- **Builder** — has explicit rigor guidance per phase so they know what "enough" looks like

## Rigor

standard

## Pipeline status

PLAN phase — plan files written, not yet built.

## Conversations

| # | Title | Stories | Status |
|---|---|---|---|
| 1 | Python infrastructure | S-01, S-02, S-03 | TODO |
| 2 | Skill phase logging | S-04, S-05, S-06 | TODO |
| 3 | design.md + storm.md phases | S-07 | TODO |
| 4 | Agent contracts + adapter propagation | S-08, S-09 | TODO |

## File map

```
pathly/plans/pathly-observability/
  FEATURE_INDEX.md          this file
  USER_STORIES.md           acceptance criteria
  IMPLEMENTATION_PLAN.md    technical scope, event schema, file list
  PROGRESS.md               conversation status table
  CONVERSATION_PROMPTS.md   self-contained builder prompts
  HAPPY_FLOW.md             end-to-end success walkthrough
  EDGE_CASES.md             failure modes and expected behavior
  ARCHITECTURE_PROPOSAL.md  design decisions and rationale
  FLOW_DIAGRAM.md           ASCII phase event flow
```

## Dependencies

- No external dependencies
- Requires Python tests to pass before Conv 2 begins (gate: `python -m pytest tests/ -q`)
- Conv 4 requires pathly-setup to be installed and functional
