# Studio AI Chat — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> Maps every file in this folder so you can fetch only what you need in one read.
> **Also read DESIGN_SPEC.md** before writing any UI code — it contains ASCII layout, tokens, and component specs.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point |
| `DESIGN_SPEC.md` | Planner | Builder, Reviewer | UI layout, ASCII diagram, tokens, component specs — the visual contract |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Two-model system: MiniLM router + phi4-mini explainer |
| `EDGE_CASES.md` | yes | Failure modes — Ollama offline, low confidence, PTY race conditions |
| `HAPPY_FLOW.md` | yes | Golden-path narrative — user types intent, embedding matches, skill runs |
| `FLOW_DIAGRAM.md` | yes | End-to-end message flow across all layers |

---

## Feature Vision

The **Conductor** is a right-side chat panel in Pathly Studio. It has three capabilities:

**1. Skill Routing** — interprets plain-English intent and routes to the matching Pathly skill
using **embedding similarity** (MiniLM, ~22ms, zero hallucination). The matched command is
written to Claude Code or Codex terminal tab via Electron IPC after user approval.

**2. UI Automation** — the AI can read the live Studio UI (via a component registry) and execute
actions (click, fill, select) on behalf of the user. Two modes:
- **Staged**: AI shows each step and waits for user approval before executing
- **Auto**: AI executes the full action sequence without interruption

**3. Model Selector** — user picks their local AI model (Phi-4 Mini, Qwen3 4B, Qwen2.5 Coder 7B,
Llama 3.2 3B). The selected model downloads and caches via WebLLM (`@mlc-ai/web-llm`, WebGPU).
No Ollama required. Models data and engine ported from zakamurai.

### Two Build Tracks (parallel after Conv 5)

**Track A — UI Automation** (Convs 6–8)
- Conv 6: Page Analyzer (component registry + live element map)
- Conv 7: Action Executor (IPC click/fill/select)
- Conv 8: Staged/Auto mode in chat

**Track B — Model Selector** (Conv 9, independent)
- Port WebLLMModels + WebLLMAPI from zakamurai
- Build model selector UI
- Replace Ollama with WebLLM engine

---

## Codebase touchpoints

| Codebase file | Conv | What changes |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | 1 | Add `POST /chat` SSE endpoint |
| `src/pathly_orchestrator/chat_agent.py` | 1 | CREATE — phi4-mini explainer (NOT router) |
| `src/pathly_orchestrator/chat_tools.py` | 1 | CREATE — get_fsm_state, read_plan_summary |
| `pyproject.toml` | 1 | Add `ollama>=0.3` |
| `studio/src/renderer/src/store/chatStore.ts` | 2 | CREATE — messages, streaming, match state |
| `studio/src/renderer/src/store/uiStore.ts` | 2 | MODIFY — add chatOpen, skillsPanelOpen |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | 2 | CREATE — panel container |
| `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` | 2 | CREATE — header + CLI status pills |
| `studio/src/renderer/src/components/ChatPanel/SkillsPanel.tsx` | 2 | CREATE — skill chips grid |
| `studio/src/renderer/src/components/ChatPanel/MessageList.tsx` | 2 | CREATE — scrollable messages |
| `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` | 2 | CREATE — input + model pills |
| `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` | 2 | CREATE — all chat styles |
| `studio/src/renderer/src/App.tsx` | 2 | MODIFY — add ChatPanel as flex child |
| `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` | 3 | CREATE — match result + approval |
| `studio/src/renderer/src/components/ChatPanel/OutputSnippet.tsx` | 3 | CREATE — live PTY output reader |
| `studio/src/main/ipc/chat.ts` | 3 | CREATE — IPC handler for terminal write |
| `studio/src/main/index.ts` | 3 | MODIFY — register chat IPC handler |
| `studio/src/renderer/src/lib/pathlyContext.ts` | 4 | CREATE — FSM + screen context builder |
| `studio/src/renderer/src/lib/embedRouter.ts` | 5 | CREATE — MiniLM wrapper + matchIntent() |
| `studio/src/renderer/src/lib/skillsManifest.ts` | 5 | CREATE — typed skills.json loader |
| `studio/src/renderer/src/data/skills.json` | 5 | CREATE — 14 skills with descriptions |
| `studio/src/renderer/src/hooks/usePageAnalyzer.ts` | 6 | CREATE — component self-registration hook |
| `studio/src/renderer/src/store/pageAnalyzerStore.ts` | 6 | CREATE — live element registry |
| `studio/src/renderer/src/lib/pageAnalyzer/index.ts` | 6 | CREATE — getPageContext() for AI consumption |
| `studio/src/renderer/src/lib/actionExecutor.ts` | 7 | CREATE — renderer-side action dispatch |
| `studio/src/main/ipc/uiActions.ts` | 7 | CREATE — IPC handler for click/fill/select |
| `studio/src/main/index.ts` | 7 | MODIFY — register uiActions IPC handler |
| `studio/src/renderer/src/store/automationStore.ts` | 8 | CREATE — step queue, staged/auto state |
| `studio/src/renderer/src/components/ChatPanel/StepQueue.tsx` | 8 | CREATE — staged step UI with approve/skip |
| `studio/src/renderer/src/components/ChatPanel/AutomationCard.tsx` | 8 | CREATE — AI action plan display |
| `studio/src/renderer/src/data/models.ts` | 9 | CREATE — model definitions (ported from zakamurai) |
| `studio/src/renderer/src/lib/webLLMEngine.ts` | 9 | CREATE — WebLLM engine wrapper (ported from zakamurai) |
| `studio/src/renderer/src/store/modelStore.ts` | 9 | CREATE — selected model, download progress, cache state |
| `studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx` | 9 | CREATE — model picker UI with system req cards |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Track | Stories | Status | Key files touched |
|---|---|---|---|---|---|
| 1 | Python Chat Agent Server | Core | S1.1, S1.2 | TODO | `http_server.py`, `chat_agent.py`, `chat_tools.py` |
| 2 | Studio Chat UI + Skills Panel | Core | S2.1, S2.2, S2.3 | TODO | `chatStore.ts`, `ChatPanel/`, `App.tsx` |
| 3 | MatchCard + IPC Terminal Write | Core | S3.1, S3.2 | TODO | `MatchCard.tsx`, `OutputSnippet.tsx`, `ipc/chat.ts` |
| 4 | Context Injection | Core | S4.1, S4.2 | TODO | `pathlyContext.ts`, `ChatPanel/index.tsx` |
| 5 | Embedding Router | Core | S5.1, S5.2, S5.3 | TODO | `embedRouter.ts`, `skillsManifest.ts`, `skills.json` |
| 6 | Page Analyzer | Track A | S6.1, S6.2, S6.3 | TODO | `usePageAnalyzer.ts`, `pageAnalyzerStore.ts`, `pageAnalyzer/index.ts` |
| 7 | Action Executor | Track A | S7.1, S7.2, S7.3 | TODO | `actionExecutor.ts`, `ipc/uiActions.ts` |
| 8 | Staged / Auto Automation Mode | Track A | S8.1, S8.2, S8.3, S8.4 | TODO | `automationStore.ts`, `StepQueue.tsx`, `AutomationCard.tsx` |
| 9 | Model Selector + WebLLM | Track B | S9.1, S9.2, S9.3, S9.4 | TODO | `models.ts`, `webLLMEngine.ts`, `modelStore.ts`, `ModelSelector.tsx` |

---

## Design tokens (summary — full spec in DESIGN_SPEC.md)

| Token | Value | Use |
|---|---|---|
| Background | `#0F172A` | Panel background |
| Surface | `#1E293B` | Cards, AI message bubbles |
| Surface 2 | `#334155` | User messages, hover |
| Accent | `#22C55E` | Run button, success, Pathly |
| Claude Blue | `#38BDF8` | Claude Code CLI indicator |
| Codex Amber | `#F59E0B` | Codex CLI indicator |
| Embed Purple | `#C084FC` | MiniLM / embedding indicator |
| Foreground | `#F8FAFC` | Primary text |
| Muted | `#94A3B8` | Secondary text, timestamps |
| Border | `#475569` | All borders |
| Destructive | `#EF4444` | Stop button, error |
| Font (mono) | JetBrains Mono | Commands, skill names, chips, headers |
| Font (sans) | Inter | Message text, descriptions |

---

## Feedback files

Live in `pathly/plans/studio-ai-chat/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
