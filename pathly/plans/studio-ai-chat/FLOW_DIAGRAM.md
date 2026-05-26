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

## UI Automation Flow (Conv 6–8)

```
User: "create a checkout flow"
        │
        ▼
AI reads studioSchema (injected in system prompt)
→ knows FlowEditor has "New Flow" button
→ knows StepEditor has step type selector
        │
        ▼
POST /chat (mode: 'automation', studioSchema in context)
AI returns: { type:'automation', steps:[{ type:'click', label:'New Flow', screen:'FlowEditor' },...] }
        │
        ▼
AutomationCard shows full plan — user sees all steps before execution
[▶ Run All] or [Step by Step]
        │
        ▼  (on approval)
ipcRenderer.invoke('automation:execute-step', step)
        │
        ▼  (Electron main)
PlaywrightExecutor.executeStep(step)
→ getByRole / getByLabel / getByPlaceholder / getByText cascade
→ Playwright click/fill/select on live Electron window
        │
        ▼
StepResult { ok: true } → advance to next step
```

**Staged mode detail:**
```
USER                  RENDERER                     MAIN PROCESS
 │                       │                              │
 │  sees AutomationCard   │  setSteps(steps)             │
 │  "5 steps planned"     │  render AutomationCard       │
 │◄──────────────────────│                              │
 │                       │                              │
 │  [Step by Step]        │                              │
 │──────────────────────►│  show StepQueue              │
 │  sees step 1 card      │  current step highlighted    │
 │◄──────────────────────│                              │
 │  [✓ Approve]          │                              │
 │──────────────────────►│  executeAutomationStep(step) │
 │                       │─────────────────────────────►│
 │                       │  ipc: automation:execute-step │
 │                       │  PlaywrightExecutor.executeStep
 │                       │  → semantic cascade finds el  │
 │                       │  → Playwright .click()        │
 │  sees step execute     │◄─────────────────────────────│
 │  in live Studio app    │  { ok: true }                │
 │◄──────────────────────│  advance to step 2           │
 │  ...repeats per step   │                              │
 │                       │                              │
 │  sees "Flow created —  │  AI sends summary message    │
 │  5 steps executed"     │                              │
 │◄──────────────────────│                              │
```

## Model Selection Flow (Conv 9)

```
USER                  RENDERER (WebLLM)
 │                       │
 │  opens ModelSelector   │
 │──────────────────────►│  getCachedWebLLMModelIds()
 │                       │  checks browser cache storage
 │  sees model cards      │  badges: Cached / Recommended
 │◄──────────────────────│
 │                       │
 │  toggles Cache on      │
 │  "Qwen3 4B"            │
 │──────────────────────►│  cacheWebLLMModel(id, onProgress)
 │                       │  @mlc-ai/web-llm → WebGPU download
 │  sees progress bar     │  modelStore.setProgress(id, pct)
 │  "Downloading 34%"     │
 │◄──────────────────────│
 │                       │  download complete
 │  sees "Cached" badge   │  modelStore.setCached([...ids])
 │◄──────────────────────│
 │                       │
 │  selects "Qwen3 4B"    │
 │──────────────────────►│  modelStore.setSelectedModel(id)
 │                       │  getEngine(id) → CreateMLCEngine
 │                       │  (replaces phi4-mini singleton)
 │  next message uses     │
 │  Qwen3 4B              │
 │                       │  askWebLLM(prompt, system, onChunk)
 │  sees response stream  │  → streams via modelStore callback
 │◄──────────────────────│
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| ChatInput.tsx | User input bar; initiates send flow |
| pathlyContext.ts | Gathers FSM state + studioSchema + skills before every send |
| studioSchema.ts | Static typed constant — describes all key Studio UI elements by screen |
| playwrightExecutor.ts | Main process — connects via CDP, resolves elements semantically, executes steps |
| ipc/automation.ts | Electron main handler; delegates step execution to playwrightExecutor |
| automationStore.ts | Step queue state for staged and auto modes |
| StepQueue.tsx | Per-step approval UI (staged) or progress bar (auto) |
| AutomationCard.tsx | AI action plan summary — shows intent + step count, mode buttons |
| webLLMEngine.ts | WebLLM singleton engine — download, cache, stream |
| modelStore.ts | Selected model, cached model IDs, download progress |
| ModelSelector.tsx | Model picker UI with spec cards and cache toggles |
| http_server.py | Python server (optional legacy backend for Ollama users) |
| chat_agent.py | Explainer + automation step generator |
| chatStore.ts | Zustand store; source of truth for all chat state |
| MessageList.tsx | Renders messages; auto-scrolls; shows streaming cursor |
| ipc/chat.ts | Electron main handler; writes to node-pty stdin |
