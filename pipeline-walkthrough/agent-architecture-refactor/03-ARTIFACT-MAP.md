# 03 — Artifact Map: agent-architecture-refactor

Every file produced or consumed during this pipeline run.

---

## Plan files (the FSM's persistent state)

### plans/agent-architecture-refactor/USER_STORIES.md
**Written by:** Planner  
**Read by:** Tester (acceptance criteria source)

Contains 7 user stories (S1.1–S1.2, S2.1–S2.5, S3.1–S3.2, S4.1–S4.2) covering
scout-path elimination, agent contract upgrades, explorer parity, and orchestrator conversion.

---

### plans/agent-architecture-refactor/FEATURE_INDEX.md
**Written by:** Planner  
**Read by:** Builder agents at the start of every conversation

Single orientation file listing all plan files and all codebase paths. Eliminated
orientation overhead across all 4 builder spawns.

---

### plans/agent-architecture-refactor/IMPLEMENTATION_PLAN.md
**Written by:** Planner  
**Read by:** Planner (when writing CONVERSATION_PROMPTS.md)

18 phases across 4 conversations. Phase 6.5 (team/plan.md) was identified here but
not wired into Conv 1's CONVERSATION_PROMPTS.md — caught by the tester in run 1.

---

### plans/agent-architecture-refactor/CONVERSATION_PROMPTS.md
**Written by:** Planner  
**Read by:** Builder agents (primary instruction source)

4 conversations with exact scope, file lists, phase-by-phase instructions, and
verify commands. Conv 1 listed 8 files but missed team/plan.md.

---

### plans/agent-architecture-refactor/PROGRESS.md
**Written by:** Orchestrator  
**Read by:** Orchestrator (pipeline recovery)

Tracks all 18 phases across 4 conversations. Status: COMPLETE.

---

### plans/agent-architecture-refactor/RETRO.md
**Written by:** Retro  
**Read by:** Humans, /lessons

Retrospective covering conversation sizing, test fix, and lessons for next time.

---

## Transient feedback files (deleted after resolution)

| File | Written by | Resolved by | Content |
|---|---|---|---|
| `feedback/TEST_FAILURES.md` | Tester run 1 | Builder test-fix (deleted) | team/plan.md had 4 residual scout-path refs; team/discover.md had 1 prose ref |

No REVIEW_FAILURES.md was ever written — all 4 reviewer passes were clean.

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/core/skills/build.md` | S1.1 | Phase 2 Scout: Call scout-path → spawn scout inline delegation block |
| `src/pathly_data/core/skills/review.md` | S1.1 | Phase 2 Scout: same pattern |
| `src/pathly_data/core/skills/test.md` | S1.1 | Step 2 Scout: same pattern |
| `src/pathly_data/core/skills/explore.md` | S1.1 | Step 3 Scout: inline spawn; Rules: scout agent only |
| `src/pathly_data/core/skills/scout-path.md` | S1.2 | Added standalone-only note at top |
| `src/pathly_data/core/skills/team/build.md` | S1.1 | Phase 2 Scout: same spawn pattern |
| `src/pathly_data/core/skills/team/test.md` | S1.1 | Phase 2 Scout + subagents table updated |
| `src/pathly_data/core/skills/team/discover.md` | S1.2 | Subagents table + prose reference updated |
| `src/pathly_data/core/skills/team/plan.md` | S1.1, S1.2 | Storm Phase 2 + Plan Phase 2 rewritten; subagents table updated (test-fix conv) |
| `src/pathly_data/core/agents/tester.md` | S2.1 | Scout delegation section added after Phase: analyze |
| `src/pathly_data/core/agents/builder.md` | S2.2 | Scout delegation section added with way of thinking + constraints |
| `src/pathly_data/core/agents/planner.md` | S2.3 | Scout delegation section added; no-scout rule removed |
| `src/pathly_data/adapters/claude/_meta/tester.yaml` | S2.4 | can_spawn: [builder] → [quick, scout, builder] |
| `src/pathly_data/adapters/codex/_meta/tester.yaml` | S2.4 | same |
| `src/pathly_data/adapters/claude/_meta/planner.yaml` | S2.5 | can_spawn: [quick, web-researcher] → [quick, scout, web-researcher] |
| `src/pathly_data/adapters/codex/_meta/planner.yaml` | S2.5 | same |
| `src/pathly_data/core/agents/explorer.md` | S3.1 | Scout delegation section added; Do NOT spawn rule removed |
| `src/pathly_data/adapters/claude/_meta/explorer.yaml` | S3.2 | can_spawn: [scout, quick] added |
| `src/pathly_data/adapters/codex/_meta/explorer.yaml` | S3.2 | same |
| `src/pathly_data/core/agents/orchestrator.md` | S4.1 | 4 sections added: routing table, responsibilities between stages, artifact archiving rule |
| `src/pathly_data/core/skills/team.md` | S4.2 | Converted to thin launcher; FSM/routing/commit logic moved to orchestrator.md |
| `pyproject.toml` | — | Version bumped 2.1.0 → 2.2.0 |

---

## How plan files relate to each other

```
USER_STORIES.md          ←── what to build (requirements)
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it (18 phases)
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact prompts to builders (4 conversations)
       │
       ▼
PROGRESS.md              ←── which conversations are done (state)
       │
       ▼
RETRO.md                 ←── what we learned (feedback to next feature)
```
