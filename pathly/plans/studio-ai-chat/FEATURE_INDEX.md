# Studio AI Chat — Feature Index

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
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions (3 layers: Python backend, Electron IPC, React UI) |
| `EDGE_CASES.md` | yes | Failure modes — Ollama offline, context overflow, PTY write race conditions |
| `HAPPY_FLOW.md` | yes | Golden-path narrative — user asks AI for help, AI types a command |
| `FLOW_DIAGRAM.md` | yes | End-to-end message flow across all 3 layers |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | Conv 1 | Add `POST /chat` streaming endpoint |
| `src/pathly_orchestrator/chat_agent.py` | Conv 1 | CREATE — ReAct agent loop, Ollama call, context injection |
| `src/pathly_orchestrator/chat_tools.py` | Conv 1 | CREATE — Pathly tools: get_fsm_state, read_plan, list_skills |
| `pyproject.toml` | Conv 1 | Add `ollama` Python dependency |
| `studio/src/renderer/src/store/chatStore.ts` | Conv 2 | CREATE — Zustand store: messages, streaming state |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | Conv 2 | CREATE — collapsible right sidebar panel |
| `studio/src/renderer/src/components/ChatPanel/MessageList.tsx` | Conv 2 | CREATE — virtualized message list with streaming |
| `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` | Conv 2 | CREATE — input bar, send/stop buttons |
| `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` | Conv 2 | CREATE — Dark OLED styles (CSS Modules) |
| `studio/src/renderer/src/App.tsx` | Conv 2 | MODIFY — add ChatPanel as third flex child in body layout |
| `studio/src/renderer/src/store/uiStore.ts` | Conv 2 | MODIFY — add `chatOpen: boolean` state |
| `studio/src/main/ipc/chat.ts` | Conv 3 | CREATE — IPC handler for terminal write + approval |
| `studio/src/main/index.ts` | Conv 3 | MODIFY — register chat IPC handler |
| `studio/src/renderer/src/components/ChatPanel/TerminalApproval.tsx` | Conv 3 | CREATE — approval banner UI |
| `studio/src/renderer/src/store/chatStore.ts` | Conv 3 | MODIFY — add pendingCommand + autoApprove state |
| `studio/src/renderer/src/lib/pageAnalyzer/` | Conv 4 | CREATE — copy pure TS analyzers from BrightSky |
| `studio/src/renderer/src/lib/pathlyContext.ts` | Conv 4 | CREATE — bundles FSM state + plan + screen into prompt context |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | Conv 4 | MODIFY — inject pathlyContext into every message |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Python Chat Agent Server | S1.1, S1.2 | TODO | `http_server.py`, `chat_agent.py`, `chat_tools.py` |
| 2 | Studio Chat UI | S2.1, S2.2 | TODO | `chatStore.ts`, `ChatPanel/`, `App.tsx` |
| 3 | Terminal Write + Approval | S3.1, S3.2 | TODO | `ipc/chat.ts`, `TerminalApproval.tsx`, `chatStore.ts` |
| 4 | PageAnalyzer + Context Injection | S4.1, S4.2 | TODO | `lib/pageAnalyzer/`, `pathlyContext.ts`, `ChatPanel/index.tsx` |

---

## Design system (from UI/UX Pro Max)

| Token | Value | Use |
|---|---|---|
| Background | `#0F172A` | Panel background |
| Surface | `#1E293B` | Message bubbles, input area |
| Surface 2 | `#334155` | Hover states, secondary surfaces |
| Accent | `#22C55E` | Send button, AI indicator, streaming cursor |
| Foreground | `#F8FAFC` | Primary text |
| Muted | `#94A3B8` | Timestamps, secondary text |
| Border | `#475569` | Panel borders, dividers |
| Destructive | `#EF4444` | Approval danger state |
| Font | Inter (system fallback) | All text |
| Style | Dark Mode OLED | Cohesive with Studio's dark theme |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/studio-ai-chat/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
