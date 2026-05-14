# orchestrator-skill-delegation — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Builder, Tester | Failure modes and guard conditions |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Builder, Reviewer | Design decisions and dispatch model |
| `FLOW_DIAGRAM.md` | Planner | Builder | Before/after orchestrator dispatch diagram |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions — new skill dispatch model |
| `EDGE_CASES.md` | yes | Guard conditions for commit skill |
| `HAPPY_FLOW.md` | yes | End-to-end delegation narrative |
| `FLOW_DIAGRAM.md` | yes | Before/after transition_actions dispatch |

---

## Codebase touchpoints

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_data/core/skills/commit.md` | Conv 1 | CREATE — new skill: stage + commit with guard |
| `src/pathly_data/core/skills/archive-artifacts.md` | Conv 1 | CREATE — new skill: copy feedback files to pipeline-walkthrough/artifacts/ |
| `src/pathly_data/adapters/claude/_meta/commit_skill.yaml` | Conv 1 | CREATE — adapter meta for commit skill |
| `src/pathly_data/adapters/claude/_meta/archive-artifacts_skill.yaml` | Conv 1 | CREATE — adapter meta for archive-artifacts skill |
| `src/pathly_data/core/agents/orchestrator.md` | Conv 2 | MODIFY — shrink Execute transition_actions to pure delegation (5 lines) |
| `C:/Users/Yafit/.claude/agents/orchestrator.md` | Conv 2 | MODIFY — sync installed copy |
| `src/pathly_data/core/flows/team.flow.yaml` | Conv 3 | MODIFY — type: git_commit → skill: commit, type: archive_artifacts → skill: archive-artifacts |
| `src/pathly_data/core/flows/debug.flow.yaml` | Conv 3 | MODIFY — fix FIXING: tester → builder; add transition_actions with skill: syntax |
| `src/pathly_data/core/flows/explore.flow.yaml` | Conv 3 | MODIFY — add transition_actions with skill: syntax |
| `C:/Users/Yafit/.claude/agents/team.flow.yaml` | Conv 3 | MODIFY — sync installed copy |
| `C:/Users/Yafit/.claude/agents/debug.flow.yaml` | Conv 3 | MODIFY — sync installed copy |
| `C:/Users/Yafit/.claude/agents/explore.flow.yaml` | Conv 3 | MODIFY — sync installed copy |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Create commit and archive-artifacts skills | S1, S2 | TODO | `commit.md`, `archive-artifacts.md`, 2× meta YAMLs |
| 2 | Shrink orchestrator to pure delegation | S3 | TODO | `orchestrator.md` (source + installed) |
| 3 | Update flow YAMLs + fix debug bug | S4, S5 | TODO | `team.flow.yaml`, `debug.flow.yaml`, `explore.flow.yaml` (source + installed) |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/orchestrator-skill-delegation/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `HUMAN_QUESTIONS.md` | Any agent | User |
