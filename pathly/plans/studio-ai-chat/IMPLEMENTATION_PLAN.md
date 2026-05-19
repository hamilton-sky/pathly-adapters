# Studio AI Chat — Implementation Plan

## Overview

Adds a local AI chat assistant to Pathly Studio (Electron). The assistant runs entirely offline via Ollama, is aware of the current pipeline stage and feature plan, and can propose terminal commands for the user to approve. Three layers: Python chat agent server, React + Zustand chat UI, Electron IPC bridge for terminal write.

## Pre-flight

Before Conversation 1, run the existing test suite and record any pre-existing failures as the known baseline. Do not attribute pre-existing failures to this feature.

```
cd studio && npm run typecheck
```

## Layer Architecture

```
Studio Renderer (React + Zustand)
     │  HTTP POST /chat (fetch + ReadableStream)
     ▼
Pathly Python Server (http_server.py :8765)
     │  chat_agent.py — ReAct loop
     ▼
Ollama (local, :11434)
     │  phi4-mini or configurable model
     ▼
Response streams back up through all layers

Renderer ──IPC──► Electron Main (ipc/chat.ts)
                       │  node-pty.write()
                       ▼
                  Shell Terminal
```

---

## Phase 1: Add Ollama dependency + /chat endpoint skeleton   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server.py` — MODIFY: add `POST /chat` route
**File:** `pyproject.toml` — MODIFY: add `ollama>=0.3` to dependencies
**Done when:** `curl -X POST http://127.0.0.1:8765/chat -H "Content-Type: application/json" -d '{"message":"hi","history":[]}' ` returns a 200 (even a static response)
**Delivers stories:** S1.1 (partial)
**Depends on:** nothing
**Enables:** Phase 2 (agent loop)
**Details:**
- Add route `/chat` accepting POST with JSON body `{ message: str, history: list }`
- Return chunked streaming response (`Content-Type: text/event-stream`)
- Static placeholder: `data: {"text": "chat endpoint ready"}\n\n`
- Add `ollama` to pyproject.toml dependencies list
**Verify:** `python -m pytest tests/ -x -q` (baseline check)

---

## Phase 2: ReAct agent loop + Ollama call   ← Conversation: 1

**File:** `src/pathly_orchestrator/chat_agent.py` — CREATE
**Done when:** `/chat` returns a real streamed response from the local Ollama model
**Delivers stories:** S1.1
**Depends on:** Phase 1
**Enables:** Phase 3 (context injection)
**Details:**
- `ChatAgent` class with `stream(message, history, context) -> AsyncGenerator[str]`
- Calls `ollama.AsyncClient().chat()` with model from env `PATHLY_CHAT_MODEL` (default `phi4-mini`)
- Streams response chunks back via async generator
- `http_server.py` `/chat` route calls `ChatAgent().stream()` and yields chunks as SSE: `data: {"text": "..."}\n\n`
- On `ollama.ResponseError` or connection refused: yield `data: {"error": "Ollama not available"}\n\n` then close with 503

---

## Phase 3: Pathly context injection   ← Conversation: 1

**File:** `src/pathly_orchestrator/chat_tools.py` — CREATE
**File:** `src/pathly_orchestrator/chat_agent.py` — MODIFY: inject context into system prompt
**Done when:** AI response references the active FSM stage by name when asked "what stage am I in?"
**Delivers stories:** S1.2
**Depends on:** Phase 2
**Enables:** Conversation 2 (UI can display meaningful responses)
**Details:**
- `chat_tools.py` exports three functions:
  - `get_fsm_state(project_root) -> dict` — reads FSM state file or calls `/next_action` internally
  - `read_plan_summary(project_root) -> str` — reads `plans/*/FEATURE_INDEX.md` for the active feature (most recently modified)
  - `list_skills() -> list[str]` — reads skill names from the installed skills manifest
- `chat_agent.py` calls these three before the Ollama call to build `system_prompt`:
  ```
  You are the Pathly Studio AI assistant. You help developers use the Pathly pipeline.

  ## Current State
  Stage: {fsm_stage}
  Feature: {feature_name}

  ## Active Plan
  {plan_summary}  (truncate to 800 tokens max)

  ## Available Skills
  {skills_list}

  Be concise. When suggesting commands, wrap them in a fenced code block starting with $.
  ```
- Total system prompt capped at 2,000 tokens (truncate plan summary if needed)

---

## Phase 4: Zustand chat store   ← Conversation: 2

**File:** `studio/src/renderer/src/store/chatStore.ts` — CREATE
**Done when:** `useChatStore()` returns `{ messages, isStreaming, sendMessage, stopStream }` without TypeScript errors
**Delivers stories:** S2.2 (partial)
**Depends on:** Phase 1–3 complete (server running)
**Enables:** Phase 5 (ChatPanel renders from store)
**Details:**
- Follow pattern from `studio/src/renderer/src/store/uiStore.ts` (create with persist)
- State shape:
  ```ts
  interface Message { id: string; role: 'user' | 'assistant'; content: string; timestamp: number }
  interface ChatStore {
    messages: Message[]
    isStreaming: boolean
    addMessage: (msg: Message) => void
    appendToLastMessage: (chunk: string) => void
    setStreaming: (v: boolean) => void
    clearMessages: () => void
  }
  ```
- Use `crypto.randomUUID()` for message IDs
- Persist messages in localStorage key `pathly-chat`

---

## Phase 5: ChatPanel collapsible container   ← Conversation: 2

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx` — CREATE
**File:** `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` — CREATE
**Done when:** ChatPanel renders in Studio, collapse toggle works, panel width animates between 32px and 320px
**Delivers stories:** S2.1
**Depends on:** Phase 4
**Enables:** Phase 6 (message list and input inside panel)
**Details:**
- Read `uiStore` for `chatOpen` state; toggle on button click
- CSS: `transition: width 200ms ease-out` — no layout thrashing, transform only
- Collapsed: 32px wide, shows only `<ChevronLeft />` from lucide-react
- Expanded: 320px wide, shows header + content area
- Colors from design system: background `#0F172A`, border-left `1px solid #475569`
- Panel sits as a flex sibling after MainPanel in App.tsx body row

---

## Phase 6: MessageList + ChatInput components   ← Conversation: 2

**File:** `studio/src/renderer/src/components/ChatPanel/MessageList.tsx` — CREATE
**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` — CREATE
**Done when:** User can type a message, press Enter or click Send, see their message appear, then see streamed AI response appear word by word
**Delivers stories:** S2.2
**Depends on:** Phase 5
**Enables:** Phase 7 (wired into App)
**Details:**
- `MessageList`: maps `messages` from chatStore; user messages right-aligned (surface `#1E293B`), AI messages left-aligned; streaming message shows blinking `▋` cursor appended to content; scroll to bottom on new message (`useEffect` + `ref.scrollIntoView`)
- `ChatInput`: textarea (1–4 rows auto-resize); Send button (`<Send />` icon, accent `#22C55E`); Stop button (`<StopCircle />`) visible only when `isStreaming`; Enter submits, Shift+Enter newline
- `sendMessage` flow: add user Message to store → `fetch('http://127.0.0.1:8765/chat', { method: 'POST', body: JSON.stringify({message, history}) })` → `ReadableStream` reader → call `appendToLastMessage` per chunk → `setStreaming(false)` on done
- Stop: call `reader.cancel()` → `setStreaming(false)`

---

## Phase 7: Wire ChatPanel into App layout   ← Conversation: 2

**File:** `studio/src/renderer/src/App.tsx` — MODIFY
**File:** `studio/src/renderer/src/store/uiStore.ts` — MODIFY
**Done when:** Studio launches with ChatPanel visible on the right; toggling collapse works
**Delivers stories:** S2.1 (complete)
**Depends on:** Phase 5, 6
**Enables:** Conversation 3
**Details:**
- `uiStore.ts`: add `chatOpen: boolean` (default `true`) and `toggleChat: () => void`
- `App.tsx`: import `ChatPanel`, add `<ChatPanel />` after `<MainPanel />` inside the body flex row
- No changes to Sidebar, TopBar, or Terminal

---

## Phase 8: Electron IPC terminal-write handler   ← Conversation: 3

**File:** `studio/src/main/ipc/chat.ts` — CREATE
**File:** `studio/src/main/index.ts` — MODIFY
**Done when:** Calling `ipcRenderer.invoke('chat:write-terminal', 'echo hello')` writes `echo hello\n` to the active PTY tab and it executes in the terminal
**Delivers stories:** S3.1 (partial)
**Depends on:** Phase 7 (app running)
**Enables:** Phase 9 (approval UI calls this)
**Details:**
- `chat.ts`: `ipcMain.handle('chat:write-terminal', (event, command: string) => { activePtys.get(activeTabId)?.write(command + '\n') })`
- Import `activePtys` map from `terminal.ts` (check exact export name)
- Register in `index.ts` alongside other IPC handlers
- Expose on preload as `window.electronAPI.writeToTerminal(cmd: string): Promise<void>`

---

## Phase 9: Approval flow UI + configurable setting   ← Conversation: 3

**File:** `studio/src/renderer/src/components/ChatPanel/TerminalApproval.tsx` — CREATE
**File:** `studio/src/renderer/src/store/chatStore.ts` — MODIFY: add `pendingCommand`, `autoApprove`
**Done when:** When AI responds with a fenced code block starting with `$` or `/pathly`, approval banner appears; Run executes it in terminal; Auto toggle in panel header bypasses banner
**Delivers stories:** S3.1, S3.2
**Depends on:** Phase 8
**Enables:** Conversation 4
**Details:**
- Parse AI message content for ` ```\n$... ``` ` or ` ```\n/pathly... ``` ` pattern (simple regex, no AST)
- `TerminalApproval`: shows command text + `<Play /> Run` (accent green) + `<X /> Dismiss` (muted) buttons
- `chatStore`: add `pendingCommand: string | null`, `autoApprove: boolean` (persisted)
- When `autoApprove` is true, skip the banner and call `writeToTerminal` immediately after message completes
- ChatPanel header: `<Toggle>` label "Auto" / "Manual" reading from `chatStore.autoApprove`
- Approval banner styling: surface `#334155`, border-left `3px solid #22C55E`, border-radius 4px

---

## Phase 10: Copy PageAnalyzer pure TS analyzers   ← Conversation: 4

**File:** `studio/src/renderer/src/lib/pageAnalyzer/` — CREATE directory
**Done when:** `import { analyzePageDirect } from '../lib/pageAnalyzer/utils/analyzePageDirect'` compiles without errors in Studio renderer
**Delivers stories:** S4.1 (partial)
**Depends on:** Phase 9 (app stable)
**Enables:** Phase 11 (context builder uses it)
**Details:**
- Copy these files verbatim from `C:\Users\Yafit\brightsky-ai\frontend\src\components\PageAnalyzer\`:
  - `utils/analyzePageDirect.ts`
  - `utils/CacheManager.ts`
  - `DOMAnalyzer2.ts`
  - `ButtonAnalyzer.ts`
  - `FormAnalyzer.ts`
  - `TextAnalyzer.ts`
  - `LinkAnalyzer.ts`
- Fix any imports that reference `@brightsky-ai/shared` — replace with inline type definitions
- Do NOT copy Redux-dependent or Chrome-extension-dependent files

---

## Phase 11: pathlyContext builder   ← Conversation: 4

**File:** `studio/src/renderer/src/lib/pathlyContext.ts` — CREATE
**Done when:** `buildPathlyContext()` returns a JSON-serializable object with `fsmStage`, `featureName`, `planSummary`, `screenElements`, `skills` fields
**Delivers stories:** S4.1, S4.2
**Depends on:** Phase 10
**Enables:** Phase 12 (ChatPanel injects this)
**Details:**
- `buildPathlyContext()` async function:
  1. Calls `fetch('http://127.0.0.1:8765/next_action')` → extracts current stage name
  2. Calls `analyzePageDirect()` → extracts `buttons`, `forms`, `textBlocks` (cap at 20 items each)
  3. Returns `{ fsmStage, featureName: 'unknown', planSummary: '', screenElements: {...}, skills: KNOWN_SKILLS }`
- `KNOWN_SKILLS`: hardcoded list of pathly skill names (plan, build, review, test, etc.) — no filesystem read from renderer

---

## Phase 12: Inject context into chat messages   ← Conversation: 4

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY
**Done when:** AI response correctly references a button visible on the current screen and the current FSM stage
**Delivers stories:** S4.1, S4.2 (complete)
**Depends on:** Phase 11
**Enables:** feature complete
**Details:**
- Before calling `fetch('/chat')`, call `buildPathlyContext()`
- Add `context` field to request body: `{ message, history, context }`
- `http_server.py` `/chat` route passes `context` to `ChatAgent.stream()`
- `chat_agent.py` appends context to system prompt under `## Current Screen` and `## Available Skills`
- Screen elements capped at 500 tokens; truncate oldest items first if over limit

---

## Prerequisites
- Ollama installed locally (`winget install Ollama.Ollama` or https://ollama.com)
- `ollama pull phi4-mini` run once before Conv 1
- Pathly FSM server running on port 8765 before testing Conv 1

## Key Decisions
- **Ollama over web-llm**: Ollama runs as a system service, survives page reloads, supports model switching without browser download. web-llm requires WebGPU and is harder to update.
- **HTTP over WebSocket for chat**: Studio already uses HTTP to the FSM server. Adding WebSocket would require a new server. HTTP + ReadableStream gives streaming at no extra cost.
- **CSS Modules over Tailwind**: Studio already uses CSS Modules. Adding Tailwind is out of scope.
- **No Redux**: Studio uses Zustand. ChatPanel state lives in a new `chatStore`, same pattern as `uiStore`.
- **Context cap at 2,000 tokens**: Phi4-mini has 16k context. 2,000 for system prompt leaves plenty for conversation history.
