# 03 — Artifact Map: adapter-parity

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| TEST_FAILURES.md | Tester | Builder (deleted) | S1.4 dry-run criterion unverifiable; S3.1 wrong path + missing frontmatter |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/adapters/copilot/_meta/archive-artifacts_skill.yaml` | S1 | Created — 3-field skill YAML (archive-artifacts) |
| `src/pathly_data/adapters/copilot/_meta/commit_skill.yaml` | S2 | Created — 3-field skill YAML (commit) |
| `src/pathly_data/adapters/codex/_meta/commit_skill.yaml` | S2 | Created — 3-field skill YAML (commit) |
| `src/pathly_data/adapters/copilot/_meta/install.yaml` | S4 | Removed hooks: block (lines 10–14) |
| `src/pathly_data/core/agents/research/explorer.md` | S3 | Added YAML frontmatter (name + description) |
| `studio/src/renderer/src/components/TopBar.module.css` | S5 | 7 outline rules → var(--focus-ring) |
| `studio/src/renderer/src/components/sidebar/Sidebar.module.css` | S5 | 9 outline rules + .filterInput:focus-visible + .dropTarget tokens |

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
pipeline-walkthrough/adapter-parity/  ←── metrics record → this folder
```
