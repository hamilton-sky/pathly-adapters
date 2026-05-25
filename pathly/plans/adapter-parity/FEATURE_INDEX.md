---
name: Feature Index
---
# adapter-parity — Feature Index

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
| `EDGE_CASES.md` | Planner | Tester | Failure modes and risk scenarios |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Cross-layer design decisions |
| `FLOW_DIAGRAM.md` | Planner | Builder | Adapter system diagram |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Adapter schema contract and hooks architecture |
| `EDGE_CASES.md` | yes | Missing-file fallback, partial install |
| `HAPPY_FLOW.md` | yes | Copilot install + archive workflow |
| `FLOW_DIAGRAM.md` | yes | Adapter content pipeline diagram |

---

## Codebase touchpoints

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_data/adapters/copilot/_meta/archive_skill.yaml` | Conv 1 | CREATE — copy from claude adapter |
| `src/pathly_data/adapters/copilot/_meta/archive-artifacts_skill.yaml` | Conv 1 | CREATE — copy from claude adapter |
| `src/pathly_data/adapters/copilot/_meta/commit_skill.yaml` | Conv 1 | CREATE — copy from claude adapter |
| `src/pathly_data/adapters/codex/_meta/commit_skill.yaml` | Conv 1 | CREATE — copy from claude adapter |
| `src/pathly_data/core/agents/explorer.md` | Conv 1 | CREATE — behavioral contract for explorer agent |
| `src/pathly_data/adapters/copilot/_meta/install.yaml` | Conv 2 | MODIFY — remove dead `hooks:` block OR implement hooks installation |
| `src/install_cli/setup_command.py` | Conv 2 | MODIFY — add hooks materialization for copilot if implementing |
| `studio/src/renderer/src/styles/tokens.css` | Conv 3 | Verify — no changes needed (tokens are correct) |
| `studio/src/renderer/src/components/TopBar.module.css` | Conv 3 | MODIFY — replace 11× hardcoded `#89b4fa` with `var(--focus-ring)` |
| `studio/src/renderer/src/components/sidebar/Sidebar.module.css` | Conv 3 | MODIFY — replace hardcoded focus ring colors + fix filterInput outline |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Copilot/Codex skill parity + explorer contract | S1, S2, S3 | TODO | 5 new files |
| 2 | Copilot hooks — remove dead config | S4 | TODO | `install.yaml`, optionally `setup_command.py` |
| 3 | Studio accessibility token fixes | S5 | TODO | `TopBar.module.css`, `Sidebar.module.css` |

---

## Feedback files (transient — deleted after resolution)

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
