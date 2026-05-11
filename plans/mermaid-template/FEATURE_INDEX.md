# mermaid-template — Feature Index

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

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | no | Cross-layer design decisions |
| `EDGE_CASES.md` | no | Failure modes and risk scenarios |
| `HAPPY_FLOW.md` | no | Golden-path narrative |
| `FLOW_DIAGRAM.md` | no | Multi-component interaction diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_data/core/templates/plan/MERMAID_DIAGRAM.template.md` | Conv 1 | CREATE — new Mermaid diagram template alongside existing ASCII FLOW_DIAGRAM.template.md |
| `src/pathly_data/core/skills/plan.md` | Conv 2 | MODIFY Section 4i — add Mermaid as diagram option alongside ASCII; update when-to-offer rule |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Create Mermaid diagram template | S1.1 | TODO | `src/pathly_data/core/templates/plan/MERMAID_DIAGRAM.template.md` |
| 2 | Wire template into plan skill | S1.2 | TODO | `src/pathly_data/core/skills/plan.md` |

---

## Feedback files (transient — deleted after resolution)

Live in `plans/mermaid-template/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
