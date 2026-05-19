# Studio AI Chat — Conversation Guide

Split into 4 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Python Chat Agent Server (Phases 1–3)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Studio AI Chat Conversation 1 (Phases 1–3) from pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/http_server.py` — add POST /chat streaming endpoint
- `src/pathly_orchestrator/chat_agent.py` — CREATE: ReAct agent loop + Ollama streaming
- `src/pathly_orchestrator/chat_tools.py` — CREATE: get_fsm_state, read_plan_summary, list_skills
- `pyproject.toml` — add ollama>=0.3 dependency

Scope:
- Phase 1: Add `POST /chat` route to http_server.py returning chunked SSE. Add ollama to pyproject.toml.
- Phase 2: Create chat_agent.py with `ChatAgent.stream()` calling ollama.AsyncClient(). Handle Ollama unavailable → 503.
- Phase 3: Create chat_tools.py with the three context functions. Inject context into ChatAgent system prompt. Cap system prompt at 2,000 tokens.

Architectural rules:
- Do not modify any FSM logic, /next_action, /complete_stage, or /events/stream endpoints.
- System prompt template is in IMPLEMENTATION_PLAN.md Phase 3 — follow it exactly.
- PATHLY_CHAT_MODEL env var (default phi4-mini) must be respected.

Do NOT touch studio/ (frontend), IPC handlers, or anything outside the Python backend.

Verify: `curl -X POST http://127.0.0.1:8765/chat -H "Content-Type: application/json" -d '{"message":"what stage am I in?","history":[]}' --no-buffer`
Expected: streaming SSE response that references the current FSM stage.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 1–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `POST /chat` streams a real AI response that knows the current Pathly pipeline stage.
**Files touched:** `http_server.py`, `chat_agent.py`, `chat_tools.py`, `pyproject.toml`

---

## Conversation 2: Studio Chat UI (Phases 4–7)

**Stories delivered:** S2.1, S2.2
**Requires:** Conversation 1 complete and FSM server running on port 8765.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Studio AI Chat Conversation 2 (Phases 4–7) from pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/store/chatStore.ts` — CREATE: Zustand store for messages + streaming
- `studio/src/renderer/src/store/uiStore.ts` — MODIFY: add chatOpen + toggleChat
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — CREATE: collapsible panel container
- `studio/src/renderer/src/components/ChatPanel/MessageList.tsx` — CREATE: message list
- `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` — CREATE: input bar
- `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` — CREATE: Dark OLED styles
- `studio/src/renderer/src/App.tsx` — MODIFY: add ChatPanel to body layout

Scope:
- Phase 4: Create chatStore.ts following uiStore.ts pattern (persist middleware). State shape in IMPLEMENTATION_PLAN.md Phase 4.
- Phase 5: Create ChatPanel/index.tsx — collapsible container, 32px collapsed / 320px expanded, CSS transition, toggle button uses lucide-react ChevronLeft/ChevronRight.
- Phase 6: Create MessageList.tsx (scroll to bottom on new message) and ChatInput.tsx (Enter sends, Shift+Enter newline, Stop button). Streaming via fetch + ReadableStream to http://127.0.0.1:8765/chat.
- Phase 7: Modify App.tsx to add <ChatPanel /> as third flex child after MainPanel. Modify uiStore.ts to add chatOpen.

Design system to apply (CSS Modules):
- Background: #0F172A, Surface: #1E293B, Surface2: #334155
- Accent: #22C55E, Foreground: #F8FAFC, Muted: #94A3B8, Border: #475569
- Font: Inter (system fallback stack: Inter, system-ui, sans-serif)
- Panel border-left: 1px solid #475569
- Message bubble border-radius: 8px, padding: 8px 12px
- All icon buttons: 44×44px touch target (per accessibility rules)
- Transition: width 200ms ease-out (transform only, no layout thrash)

Architectural rules:
- No Redux. No WebSocket. No Chrome extension APIs.
- Use Zustand for all state. Use fetch + ReadableStream for streaming.
- Follow existing CSS Modules pattern in studio/src/renderer/src/.
- Do not touch any IPC handlers, main process files, or Python backend.

Do NOT touch the terminal, sidebar, or any existing Studio components beyond App.tsx layout.

Verify: `cd studio && npm run typecheck`
Expected: zero TypeScript errors. Studio launches with ChatPanel visible on the right.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 4–7 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Studio has a working chat panel — user can send a message and see a streamed AI response.
**Files touched:** `chatStore.ts`, `uiStore.ts`, `ChatPanel/` (4 files), `App.tsx`

---

## Conversation 3: Terminal Write + Approval Flow (Phases 8–9)

**Stories delivered:** S3.1, S3.2
**Requires:** Conversation 2 complete (ChatPanel showing in Studio).

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Studio AI Chat Conversation 3 (Phases 8–9) from pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Specifically read studio/src/main/ipc/terminal.ts to understand how activePtys map and activeTabId are exported — match that pattern exactly.

**Codebase files this conversation touches:**
- `studio/src/main/ipc/chat.ts` — CREATE: IPC handler for terminal write
- `studio/src/main/index.ts` — MODIFY: register chat IPC handler
- `studio/src/renderer/src/components/ChatPanel/TerminalApproval.tsx` — CREATE: approval banner
- `studio/src/renderer/src/store/chatStore.ts` — MODIFY: add pendingCommand, autoApprove

Scope:
- Phase 8: Create ipc/chat.ts — ipcMain.handle('chat:write-terminal', ...) writes command+"\n" to active PTY. Register in index.ts. Expose as window.electronAPI.writeToTerminal on preload.
- Phase 9: Create TerminalApproval.tsx — parses AI message for fenced code blocks starting with $ or /pathly, shows Run/Dismiss banner. Add autoApprove toggle to ChatPanel header. Update chatStore with pendingCommand and autoApprove (persisted).

Styling for TerminalApproval:
- Background: #334155, border-left: 3px solid #22C55E, border-radius: 4px, padding: 8px 12px
- Run button: accent #22C55E text, Play icon (lucide-react)
- Dismiss button: muted #94A3B8 text, X icon (lucide-react)
- Both buttons: 44×44px minimum touch target

Architectural rules:
- Read terminal.ts before writing chat.ts — match the exact PTY write pattern.
- Preload must be updated if window.electronAPI doesn't already have writeToTerminal.
- Do not modify any FSM IPC handlers or Python backend.

Do NOT touch MessageList, ChatInput, or the Python chat agent.

Verify: `cd studio && npm run typecheck`
Expected: zero TypeScript errors. Sending a message like "/pathly build" as the AI response shows the approval banner.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 8–9 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** AI responses containing commands show an approval banner; Run writes to the terminal; Auto toggle bypasses banner.
**Files touched:** `ipc/chat.ts`, `main/index.ts`, `TerminalApproval.tsx`, `chatStore.ts`

---

## Conversation 4: PageAnalyzer + Context Injection (Phases 10–12)

**Stories delivered:** S4.1, S4.2
**Requires:** Conversation 3 complete.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Studio AI Chat Conversation 4 (Phases 10–12) from pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Also read the source files in C:\Users\Yafit\brightsky-ai\frontend\src\components\PageAnalyzer\ to understand what to copy.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/lib/pageAnalyzer/` — CREATE directory + copy pure TS analyzers from BrightSky
- `studio/src/renderer/src/lib/pathlyContext.ts` — CREATE: context builder
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: inject context per message
- `src/pathly_orchestrator/http_server.py` — MODIFY: pass context to ChatAgent
- `src/pathly_orchestrator/chat_agent.py` — MODIFY: append context to system prompt

Scope:
- Phase 10: Copy these files from BrightSky to studio/src/renderer/src/lib/pageAnalyzer/: analyzePageDirect.ts, CacheManager.ts, DOMAnalyzer2.ts, ButtonAnalyzer.ts, FormAnalyzer.ts, TextAnalyzer.ts, LinkAnalyzer.ts. Replace any @brightsky-ai/shared imports with inline type definitions.
- Phase 11: Create pathlyContext.ts — buildPathlyContext() fetches FSM state from port 8765, runs analyzePageDirect(), returns structured context object. KNOWN_SKILLS hardcoded list.
- Phase 12: Modify ChatPanel/index.tsx to call buildPathlyContext() before each send and include context in request body. Modify http_server.py to pass context to ChatAgent. Modify chat_agent.py to append ## Current Screen and ## Available Skills to system prompt (capped at 500 tokens for screen elements).

Architectural rules:
- Only copy pure TS files (no Chrome extension APIs, no Redux, no @brightsky-ai/shared).
- Screen context cap: 500 tokens max — truncate items list if exceeded.
- Do not add new IPC calls. Context is gathered in the renderer via fetch + DOM APIs only.

Do NOT touch TerminalApproval, chatStore approval logic, or any Conv 3 work.

Verify: `cd studio && npm run typecheck`
Expected: zero TypeScript errors. Ask the AI "what buttons do you see?" — it should list buttons currently visible in Studio.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 10–12 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** AI knows the current FSM stage, sees what buttons are on screen, and references available Pathly skills by name.
**Files touched:** `lib/pageAnalyzer/` (7 files), `pathlyContext.ts`, `ChatPanel/index.tsx`, `http_server.py`, `chat_agent.py`
