# 03 — Artifact Map: orchestrator-skill-delegation

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Builder agents | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| — | — | — | No feedback files were written — zero review failures, zero retries |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/core/agents/orchestrator.md` | S3 | `Execute transition_actions` replaced with pure skill delegation (10 lines, no shell commands) |
| `src/pathly_data/core/flows/debug.flow.yaml` | S4, S5 | `agent_map.FIXING`: tester → builder; `transition_actions: {}` replaced with skill: syntax |
| `src/pathly_data/core/flows/explore.flow.yaml` | S4 | `transition_actions: {}` replaced with skill: syntax |
| `src/pathly_data/core/flows/team.flow.yaml` | S4 | `type: git_commit` / `type: archive_artifacts` replaced with `skill:` syntax |

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
pipeline-walkthrough/orchestrator-skill-delegation/  ←── metrics record → this folder
```
