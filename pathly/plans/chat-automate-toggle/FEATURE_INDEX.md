# Chat/Automate Mode Toggle — Feature Index

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
| `EDGE_CASES.md` | Planner | Tester | Failure modes |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect | Design decisions |
| `FLOW_DIAGRAM.md` | Planner | Builder | ASCII flow of the new send path |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions |
| `EDGE_CASES.md` | yes | Failure modes and risk scenarios |
| `HAPPY_FLOW.md` | yes | Golden-path narrative |
| `FLOW_DIAGRAM.md` | yes | Multi-component interaction diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/store/chatStore.ts` | Conv 1 | Add `chatMode: 'chat' \| 'automate'` field and `setChatMode` action to `ChatState` |
| `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` | Conv 1 | Add mode toggle pill `[Chat \| Automate]` to footer row; reads `chatStore.chatMode` |
| `studio/src/renderer/src/components/ChatPanel/ChatInput.module.css` | Conv 1 | Add `.modeToggle`, `.modeBtn`, `.modeBtnActive` styles |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | Conv 2 | Replace unused `isAutomationIntent` regex with `chatMode` check; add automation system prompt branch; parse JSON response; call `updateLastMessage({ automationPlan })` and `automationStore.setSteps()` |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Store field + toggle pill UI | S1.1, S1.2 | TODO | `chatStore.ts`, `ChatInput.tsx`, `ChatInput.module.css` |
| 2 | Automation prompt + response wiring | S2.1, S2.2, S2.3, S2.4 | TODO | `ChatPanel/index.tsx` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/chat-automate-toggle/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
