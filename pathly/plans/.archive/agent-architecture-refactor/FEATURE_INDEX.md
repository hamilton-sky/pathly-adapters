# agent-architecture-refactor — Feature Index

## What this feature is

Refactor the pathly pipeline agent architecture to:
1. Eliminate all `Call scout-path` skill-in-skill invocations — replace with direct `Spawn scout agent` calls.
2. Bring all five worker agents (builder, tester, planner, reviewer, architect) to full scout spawn parity — consistent `way of thinking` + `constraints` delegation pattern.
3. Give explorer agent scout spawn capability (remove the hard no-spawn rule).
4. Update all adapter YAML `can_spawn` fields for affected agents (claude + codex).
5. Convert `team.md` from full-FSM-inline to a thin launcher that spawns the orchestrator agent.

## Why it matters

- Skill-in-skill calls accumulate sub-skill text into the main context window on every pipeline run.
- tester, planner, and explorer had no scout access — plans were written blind to existing architecture; tests had no context-gathering path.
- builder.md's delegation pattern lacked `way of thinking` and `constraints`, giving scouts weaker guidance than reviewer/architect scouts get.
- `team.md` runs the full FSM inline — context grows with every conversation in a long feature run.

## Conversation map

| Conv | Scope | Stories | Files |
|---|---|---|---|
| 1 | Scout-pattern migration | S1.1, S1.2 | 8 skill files |
| 2 | Worker agent contracts + YAML | S2.1–S2.5 | 3 agent .md + 4 YAML |
| 3 | Explorer parity | S3.1, S3.2 | 1 agent .md + 2 YAML |
| 4 | Orchestrator conversion | S4.1, S4.2 | 2 files |

## Key file paths

### Skills (Conv 1)
- `src/pathly_data/core/skills/build.md` — line ~54: Call scout-path → Spawn scout agent
- `src/pathly_data/core/skills/review.md` — line ~24: call scout-path → Spawn scout agent
- `src/pathly_data/core/skills/test.md` — line ~66: call scout-path → Spawn scout agent
- `src/pathly_data/core/skills/explore.md` — lines ~83, ~166: scout-path → scout agent
- `src/pathly_data/core/skills/scout-path.md` — add standalone-only note
- `src/pathly_data/core/skills/team/build.md` — line ~77: Call scout-path → Spawn scout agent
- `src/pathly_data/core/skills/team/test.md` — line ~65: Call scout-path → Spawn scout agent
- `src/pathly_data/core/skills/team/discover.md` — subagents table: doc update only

### Agent contracts (Conv 2)
- `src/pathly_data/core/agents/tester.md` — add scout spawn section
- `src/pathly_data/core/agents/builder.md` — upgrade delegation pattern (add way of thinking + constraints)
- `src/pathly_data/core/agents/planner.md` — add scout spawn section, remove no-scout rule

### YAML adapters (Conv 2)
- `src/pathly_data/adapters/claude/_meta/tester.yaml` — can_spawn: [builder] → [quick, scout, builder]
- `src/pathly_data/adapters/codex/_meta/tester.yaml` — same
- `src/pathly_data/adapters/claude/_meta/planner.yaml` — can_spawn: [quick, web-researcher] → [quick, scout, web-researcher]
- `src/pathly_data/adapters/codex/_meta/planner.yaml` — same

### Explorer (Conv 3)
- `src/pathly_data/core/agents/explorer.md` — add scout spawn section, remove "Do NOT spawn additional agents"
- `src/pathly_data/adapters/claude/_meta/explorer.yaml` — add can_spawn: [scout, quick]
- `src/pathly_data/adapters/codex/_meta/explorer.yaml` — add can_spawn: [scout, quick]

### Orchestrator (Conv 4)
- `src/pathly_data/core/agents/orchestrator.md` — add git commit + PROGRESS.md update + routing table + dual-write rule
- `src/pathly_data/core/skills/team.md` — convert to thin launcher

### Reference (already correct — do not change)
- `src/pathly_data/core/agents/reviewer.md` — already has full delegation pattern ✓
- `src/pathly_data/core/agents/architect.md` — already has full delegation pattern ✓
- `src/pathly_data/core/agents/po.md` — intentionally NO scout/quick (PO already has web-researcher; scout excluded by design)
- `src/pathly_data/core/skills/team/review.md` — already uses new spawn pattern ✓

## Verify command

```
git diff --stat
```

No test suite exists for skill/agent .md files; correctness is verified by content inspection (grep) after each conversation.
