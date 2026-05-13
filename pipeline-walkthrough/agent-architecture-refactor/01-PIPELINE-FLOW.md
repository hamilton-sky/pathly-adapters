# 01 — Pipeline Flow: agent-architecture-refactor

This documents every agent spawn, every feedback loop, and every gate in the
agent-architecture-refactor run. Read top to bottom — it is in execution order.

---

## Pipeline map

```
User: "/pathly team agent-architecture-refactor fast"
│
│  [Entry — autoFlow = true, rigor = lite]
│
│  [Stage 1 — Build: Conversation 1 — Scout-pattern migration]
├─► Builder agent (Conv 1)
│   Reads:  FEATURE_INDEX.md, CONVERSATION_PROMPTS.md, 8 skill files
│   Writes: src/pathly_data/core/skills/build.md       (scout-path → spawn scout)
│           src/pathly_data/core/skills/review.md      (scout-path → spawn scout)
│           src/pathly_data/core/skills/test.md        (scout-path → spawn scout)
│           src/pathly_data/core/skills/explore.md     (two-line update)
│           src/pathly_data/core/skills/scout-path.md  (standalone-only note)
│           src/pathly_data/core/skills/team/build.md  (scout-path → spawn scout)
│           src/pathly_data/core/skills/team/test.md   (scout-path → spawn scout)
│           src/pathly_data/core/skills/team/discover.md (subagents table update)
│
│  [Stage 2 — Review: Conversation 1]
├─► Reviewer agent (Conv 1)
│   Result: PASS — no feedback file written → pipeline advances
│
│  [Stage 1 — Build: Conversation 2 — Worker agent contracts + YAML]
├─► Builder agent (Conv 2)
│   Reads:  FEATURE_INDEX.md, CONVERSATION_PROMPTS.md, tester.md, builder.md,
│           planner.md, reviewer.md (reference), architect.md (reference), 4 YAML files
│   Writes: src/pathly_data/core/agents/tester.md      (scout delegation section added)
│           src/pathly_data/core/agents/builder.md     (way of thinking + constraints added)
│           src/pathly_data/core/agents/planner.md     (scout section added, no-scout rule removed)
│           src/pathly_data/adapters/claude/_meta/tester.yaml   (can_spawn updated)
│           src/pathly_data/adapters/codex/_meta/tester.yaml    (can_spawn updated)
│           src/pathly_data/adapters/claude/_meta/planner.yaml  (can_spawn updated)
│           src/pathly_data/adapters/codex/_meta/planner.yaml   (can_spawn updated)
│
│  [Stage 2 — Review: Conversation 2]
├─► Reviewer agent (Conv 2)
│   Result: PASS — no feedback file written → pipeline advances
│
│  [Stage 1 — Build: Conversation 3 — Explorer agent parity]
├─► Builder agent (Conv 3)
│   Reads:  FEATURE_INDEX.md, CONVERSATION_PROMPTS.md, explorer.md, 2 YAML files
│   Writes: src/pathly_data/core/agents/explorer.md              (scout section, no-spawn rule removed)
│           src/pathly_data/adapters/claude/_meta/explorer.yaml  (can_spawn: [scout, quick])
│           src/pathly_data/adapters/codex/_meta/explorer.yaml   (can_spawn: [scout, quick])
│
│  [Stage 2 — Review: Conversation 3]
├─► Reviewer agent (Conv 3)
│   Result: PASS — no feedback file written → pipeline advances
│
│  [Stage 1 — Build: Conversation 4 — Orchestrator conversion]
├─► Builder agent (Conv 4)
│   Reads:  FEATURE_INDEX.md, CONVERSATION_PROMPTS.md, orchestrator.md, team.md
│   Writes: src/pathly_data/core/agents/orchestrator.md  (4 FSM sections added)
│           src/pathly_data/core/skills/team.md           (converted to thin launcher)
│
│  [Stage 2 — Review: Conversation 4]
├─► Reviewer agent (Conv 4)
│   Result: PASS — no feedback file written → pipeline advances
│
│  [IMPLEMENT_COMPLETE]
│
│  [Stage 3 — Test: Run 1]
├─► Tester agent (run 1)
│   Reads: USER_STORIES.md, all modified skill/agent files
│   Result:
│     S1.1 → PASS, S1.2 → FAIL (team/plan.md — 4 residual scout-path refs)
│     S2.1–S2.5 → PASS
│     S3.1–S3.2 → PASS
│     S4.1–S4.2 → PASS
│   Produces: plans/agent-architecture-refactor/feedback/TEST_FAILURES.md
│
│  [Stage 1 — Build: Test fix]
├─► Builder agent (test fix)
│   Reads:  TEST_FAILURES.md, src/pathly_data/core/skills/team/plan.md
│   Writes: src/pathly_data/core/skills/team/plan.md  (scout-path refs replaced;
│           also fixes team/discover.md line 127 prose reference)
│   Deletes: TEST_FAILURES.md
│
│  [Stage 3 — Test: Run 2]
├─► Tester agent (run 2)
│   All 35 acceptance criteria → PASS
│   No TEST_FAILURES.md written
│
│  [Stage 4 — Retro]
└─► Retro
    Writes: plans/agent-architecture-refactor/RETRO.md
    STATE.json → DONE
```

---

## How agents communicate

Agents never call each other. The orchestrator (main assistant) is the only router.
Communication happens in two ways:

### 1. Plan files (sequential hand-off)

Each agent reads the plan files the previous stage wrote. The builder reads
CONVERSATION_PROMPTS.md to know exactly what to implement. The reviewer reads
git diff. The tester reads USER_STORIES.md for acceptance criteria.

### 2. Feedback files (blocking gates)

A feedback file in `plans/<feature>/feedback/` means "blocked — action required."

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes it) | Implementation must change |
| `TEST_FAILURES.md` | Tester | Builder (deletes it) | Stories not satisfied |

---

## FSM states traversed (agent-architecture-refactor)

```
→ BUILDING          (Conv 1 builder spawned)
→ REVIEWING         (Conv 1 reviewer spawned)
→ BUILDING          (Conv 2 builder spawned)
→ REVIEWING         (Conv 2 reviewer spawned)
→ BUILDING          (Conv 3 builder spawned)
→ REVIEWING         (Conv 3 reviewer spawned)
→ BUILDING          (Conv 4 builder spawned)
→ REVIEWING         (Conv 4 reviewer spawned)
→ TESTING           (tester spawned — run 1, TEST_FAILURES.md written)
→ BUILDING          (builder fix spawned)
→ TESTING           (tester spawned — run 2, all PASS)
→ RETRO
→ DONE
```

---

## Feedback loop summary

| Stage | Loops | Cause | Resolution |
|---|---|---|---|
| Review Conv 1–4 | 0 | — | All 4 reviews passed first attempt |
| Test run 1 | 1 loop | team/plan.md not in Conv 1 scope — 4 residual scout-path refs | Builder fix + team/discover.md prose fix |
