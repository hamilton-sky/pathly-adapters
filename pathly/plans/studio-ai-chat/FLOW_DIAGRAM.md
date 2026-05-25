# Studio AI Chat — Flow Diagram

## End-to-End Message Flow

```
USER                  RENDERER                    MAIN PROCESS         PYTHON SERVER        OLLAMA
 │                       │                              │                    │                 │
 │  types intent          │                              │                    │                 │
 │──────────────────────►│                              │                    │                 │
 │                       │  matchIntent(input)          │                    │                 │
 │                       │  MiniLM cosine sim (~22ms)   │                    │                 │
 │                       │  setMatch(top, alts)         │                    │                 │
 │  sees MatchCard < 50ms │  MatchCard renders instantly │                    │                 │
 │◄──────────────────────│                              │                    │                 │
 │                       │  POST /chat (async, parallel)│                    │                 │
 │                       │─────────────────────────────────────────────────►│                 │
 │                       │                              │                    │  chat(phi4-mini) │
 │                       │                              │                    │────────────────►│
 │                       │  ◄── SSE chunks ─────────────────────────────────│◄────────────────│
 │  sees explanation      │  appendToLastMessage()       │                    │                 │
 │◄──────────────────────│                              │                    │                 │
 │  clicks ▶ Run         │                              │                    │                 │
 │──────────────────────►│  ipcRenderer.invoke(         │                    │                 │
 │                       │    'chat:write-terminal',    │                    │                 │
 │                       │    { command, target } )     │                    │                 │
 │                       │─────────────────────────────►│                    │                 │
 │                       │                              │  sanitize(cmd)     │                 │
 │                       │                              │  activePtys        │                 │
 │                       │                              │    .get(target)    │                 │
 │                       │                              │    .write(cmd+\n)  │                 │
 │  sees cmd in terminal  │  OutputSnippet lines         │  PTY onData ──────►│                 │
 │◄──────────────────────│◄─────────────────────────────│                    │                 │
 │                       │  cmd completes → matchIntent │                    │                 │
 │  sees next suggestion  │  → new MatchCard appears     │                    │                 │
 │◄──────────────────────│                              │                    │                 │
```

## OLD DIAGRAM (replaced)

```
User types message + presses Enter
        │
        ▼
ChatInput.tsx (renderer)
        │  buildPathlyContext()
        ▼
pathlyContext.ts
        │  fetch GET :8765/next_action  ──► FSM stage
        │  analyzePageDirect()          ──► screen elements
        │  KNOWN_SKILLS list
        │  returns PathlyContext
        ▼
ChatInput.tsx
        │  fetch POST :8765/chat
        │  body: { message, history, context }
        ▼
http_server.py  POST /chat
        │  ChatAgent.stream(message, history, context)
        ▼
chat_agent.py
        │  chat_tools.get_fsm_state()   ──► stage string
        │  chat_tools.read_plan_summary()──► plan text
        │  chat_tools.list_skills()     ──► skill names
        │  build system_prompt (≤2000 tokens)
        │  ollama.AsyncClient().chat()  ──► stream
        ▼
Ollama :11434 (phi4-mini)
        │  token stream
        ▼
http_server.py SSE chunks
  data: {"text": "word "}\n\n ...
        │
        ▼
ChatPanel/index.tsx  ReadableStream reader
        │  appendToLastMessage(chunk)  per chunk
        ▼
chatStore.ts (Zustand)
        │  messages array updated
        ▼
MessageList.tsx
        │  renders streaming cursor ▋
        ▼
User sees response word by word
```

## Command Approval Flow

```
AI response contains fenced code block
  ``` $ /pathly build ```
        │
        ├─ autoApprove = false ──► TerminalApproval.tsx renders
        │                                │  Run clicked
        │                                ▼
        │                         ipcRenderer.invoke('chat:write-terminal')
        │                                │
        │                                ▼
        │                         ipc/chat.ts (Electron main)
        │                                │  activePtys.get(tabId).write(cmd+"\n")
        │                                ▼
        │                         node-pty → Shell
        │                         command executes in terminal
        │
        └─ autoApprove = true ───► skip banner
                                   ipcRenderer.invoke directly
                                   (after command sanitization)
```

## Error / Fallback Flow

```
fetch POST :8765/chat
        │
        ├─ Ollama offline ──► 503 {"error":"Ollama not available"}
        │                         │
        │                         ▼
        │                    MessageList shows inline error
        │                    "AI model offline — start Ollama"
        │
        ├─ FSM server down ──► buildPathlyContext() catches error
        │                         │
        │                         ▼
        │                    context.fsmStage = "unknown"
        │                    message sent anyway, AI notes unknown state
        │
        └─ Stream cancelled ──► abortController.abort()
                                    │
                                    ▼
                               setStreaming(false)
                               partial message frozen with [stopped]
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| ChatInput.tsx | User input bar; initiates send flow |
| pathlyContext.ts | Gathers FSM state + screen + skills before every send |
| http_server.py | Python Flask server; routes /chat to ChatAgent |
| chat_agent.py | Builds system prompt; calls Ollama; streams tokens |
| chat_tools.py | Reads FSM state, plan summary, skills from filesystem |
| Ollama :11434 | Local model inference — no internet required |
| chatStore.ts | Zustand store; source of truth for all chat state |
| MessageList.tsx | Renders messages; auto-scrolls; shows streaming cursor |
| TerminalApproval.tsx | Approval banner for AI-proposed commands |
| ipc/chat.ts | Electron main handler; writes to node-pty stdin |
