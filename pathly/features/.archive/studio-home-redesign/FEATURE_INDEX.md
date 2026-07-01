# studio-home-redesign — Feature Index

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
| `DESIGN.md` | Designer | Builder | Full visual spec — layout, card spec, header controls, colors |
| `PO_NOTES.md` | PO | Builder, Reviewer | Requirements and scope boundaries |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | no | merged into IMPLEMENTATION_PLAN.md |
| `EDGE_CASES.md` | no | merged into USER_STORIES.md |
| `HAPPY_FLOW.md` | no | merged into IMPLEMENTATION_PLAN.md |
| `FLOW_DIAGRAM.md` | no | N/A — single-component UI change |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/types/index.ts` | Conv 1 | Add `pinned?: boolean` to `ProjectEntry` interface |
| `studio/src/renderer/src/components/HomeScreen.tsx` | Conv 1 | Add dark mode + view toggles to drag strip; welcome subtitle; grid layout |
| `studio/src/renderer/src/components/HomeScreen.tsx` | Conv 2 | Richer project cards; pin/star; empty state |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Layout, header controls, grid view | S1, S2, S3 | TODO | `types/index.ts`, `HomeScreen.tsx` |
| 2 | Richer cards, pinning, empty state | S4, S5, S6 | TODO | `HomeScreen.tsx` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/studio-home-redesign/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `HUMAN_QUESTIONS.md` | Any agent | User |
