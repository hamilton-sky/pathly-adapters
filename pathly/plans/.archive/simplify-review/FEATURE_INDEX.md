# simplify-review — Feature Index

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
| `docs/ARCHITECTURE.md` | Conv 1 | Remove hardcoded "20" count; replace duplicated skill table with link to FLOW_DIAGRAM.md |
| `docs/PATHLY_ARCHITECTURE.md` | Conv 1 | Add scope header note; fix directory tree formatting; add team-flow entry-point comment; choose consistent annotation style; fix pip install command |
| `README.md` | Conv 1 | Trim quick-start block; add /pathly equivalence note; fix Supported Hosts table; restore `_meta/<name>.yaml` in How It Works; add Copilot skills destination |
| `docs/FLOW_DIAGRAM.md` | Conv 1 | Complete trailing "…"; add footnote for /pathly verify→verify-state; add Copilot to mermaid diagram; add Copilot invocation examples block |
| `schemas/pathly-meta.schema.json` | Conv 2 | Sync with src/ copy: add missing properties + constraints + descriptions |
| `src/pathly_data/schemas/pathly-meta.schema.json` | Conv 2 | Add `required`, `enum`, `minLength`, and `description` fields throughout |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Documentation fixes | S1.1, S1.2, S1.3 | TODO | `docs/ARCHITECTURE.md`, `docs/PATHLY_ARCHITECTURE.md`, `README.md`, `docs/FLOW_DIAGRAM.md` |
| 2 | Schema fixes | S2.1 | TODO | `schemas/pathly-meta.schema.json`, `src/pathly_data/schemas/pathly-meta.schema.json` |

---

## Feedback files (transient — deleted after resolution)

Live in `plans/simplify-review/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
