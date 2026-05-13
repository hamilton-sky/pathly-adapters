# 03 — Artifact Map: agent-architecture-refactor

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| FEATURE_INDEX.md | Planner | Builder agents | Orientation — all paths and roles in one place |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact changes — the design (18 phases) |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| `feedback/TEST_FAILURES.md` | Tester run 1 | Builder test-fix (deleted) | team/plan.md — 4 scout-path refs remaining; team/discover.md — 1 prose ref |

No REVIEW_FAILURES.md was written — all 4 reviewer passes were clean.

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/core/skills/build.md` | S1.1 | Phase 2 Scout: Call scout-path → spawn scout inline delegation block |
| `src/pathly_data/core/skills/review.md` | S1.1 | Phase 2 Scout: same pattern |
| `src/pathly_data/core/skills/test.md` | S1.1 | Step 2 Scout: same pattern |
| `src/pathly_data/core/skills/explore.md` | S1.1 | Step 3 Scout: inline spawn; Rules: scout agent only |
| `src/pathly_data/core/skills/scout-path.md` | S1.2 | Standalone-only note added at top |
| `src/pathly_data/core/skills/team/build.md` | S1.1 | Phase 2 Scout: same spawn pattern |
| `src/pathly_data/core/skills/team/test.md` | S1.1 | Phase 2 Scout + subagents table updated |
| `src/pathly_data/core/skills/team/discover.md` | S1.2 | Subagents table + prose reference updated |
| `src/pathly_data/core/skills/team/plan.md` | S1.1, S1.2 | Storm Phase 2 + Plan Phase 2 rewritten; subagents table updated (test-fix) |
| `src/pathly_data/core/agents/tester.md` | S2.1 | Scout delegation section added after Phase: analyze |
| `src/pathly_data/core/agents/builder.md` | S2.2 | Scout delegation section with way of thinking + constraints |
| `src/pathly_data/core/agents/planner.md` | S2.3 | Scout delegation section added; no-scout rule removed |
| `src/pathly_data/adapters/claude/_meta/tester.yaml` | S2.4 | can_spawn: [builder] → [quick, scout, builder] |
| `src/pathly_data/adapters/codex/_meta/tester.yaml` | S2.4 | same |
| `src/pathly_data/adapters/claude/_meta/planner.yaml` | S2.5 | can_spawn: [quick, web-researcher] → [quick, scout, web-researcher] |
| `src/pathly_data/adapters/codex/_meta/planner.yaml` | S2.5 | same |
| `src/pathly_data/core/agents/explorer.md` | S3.1 | Scout delegation section added; Do NOT spawn rule removed |
| `src/pathly_data/adapters/claude/_meta/explorer.yaml` | S3.2 | can_spawn: [scout, quick] added |
| `src/pathly_data/adapters/codex/_meta/explorer.yaml` | S3.2 | same |
| `src/pathly_data/core/agents/orchestrator.md` | S4.1 | 4 FSM sections added: routing table, stage responsibilities, artifact archiving |
| `src/pathly_data/core/skills/team.md` | S4.2 | Converted to thin launcher; FSM/routing/commit logic moved to orchestrator.md |
| `pyproject.toml` | — | Version bumped 2.1.0 → 2.2.0 |

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to build
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompts
       │
       ▼
PROGRESS.md              ←── which conversations done
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS.md       ←── promoted patterns → next planner
pipeline-walkthrough/agent-architecture-refactor/  ←── metrics record → this folder
```
