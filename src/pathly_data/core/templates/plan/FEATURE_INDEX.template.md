# [Feature Name] — Feature Index

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
| `ARCHITECTURE_PROPOSAL.md` | [yes/no] | Cross-layer design decisions |
| `EDGE_CASES.md` | [yes/no] | Failure modes and risk scenarios |
| `HAPPY_FLOW.md` | [yes/no] | Golden-path narrative |
| `FLOW_DIAGRAM.md` | [yes/no] | Multi-component interaction diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `[src/path/to/file.py]` | Conv 1 | [description] |
| `[src/path/to/other.py]` | Conv 2 | [description] |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | [Title] | S1, S2 | TODO | `[file]`, `[file]` |
| 2 | [Title] | S3 | TODO | `[file]` |

---

## Feedback files (transient — deleted after resolution)

Live in `plans/[feature]/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
