# Flow Diagrams — brightsky-studio-wire

Legend:
  [R]  = Renderer layer (Chromium, React, Zustand, lib/)
  [IPC]= IPC boundary (preload contextBridge)
  [M]  = Main process layer (Node.js, Electron)
  [WS] = WebSocket boundary (port 3002)
  [B]  = Backend layer (NestJS, Brightsky)

---

## Path A — Normal chat with context (Conv 1 result)

User types message in ChatPanel and presses Send.

```
[R]  ChatPanel.handleBrightskySend(content)
      |
      v
[R]  pathlyContextCollector.collectPathlyContext()
      |
      |-- window.pathly.fsm.state(activeTopic)
      |    |
      |   [IPC] ipcRenderer.invoke('fsm:state', activeTopic)
      |    |
      |   [M]  fsm IPC handler
      |         reads pathly/plans/<topic>/STATE.json
      |         returns { stage, feature, rigor }
      |    |
      |    <-- { stage, feature, rigor }
      |
      |-- window.pathly.fs.read(PROGRESS.md path)
      |    |
      |   [IPC] ipcRenderer.invoke('fs:read', path)
      |    |
      |   [M]  fs IPC handler  →  fs.readFile(path)
      |    |
      |    <-- file contents string (or "" on error)
      |
      |-- window.pathly.fs.read(USER_STORIES.md path)
      |    |
      |   [IPC] ipcRenderer.invoke('fs:read', path)
      |    |
      |   [M]  fs IPC handler  →  fs.readFile(path)
      |    |
      |    <-- file contents string trimmed to ≤2000 tokens
      |
      v
      returns AppContext {
        source: 'pathly-studio',
        projectPath,
        activeFeature,
        fsmStage,
        nextUncompletedStory,  // parsed from PROGRESS.md
        userStoriesSummary,    // trimmed ≤2000 tokens
      }
      |
      v
[R]  brightskyClient.sendMessage(content, sessionId)
      builds outbound envelope:
      {
        type: 'user_message',
        messageType: 'pathly_chat',
        content,
        sessionId,
        requestId: crypto.randomUUID(),
        context: { appContext },
        capabilities: {
          canExecuteToolCalls: false,   // Conv 1
          canStreamThinking: true,
          supportedToolTypes: []
        }
      }
      |
      v
[R]  ws.send(JSON.stringify(envelope))
      |
     [WS] ---------- WebSocket frame (user_message) ---------->
      |
[B]  UnifiedChatGateway.onMessage(client, message)
      checks: message.context?.source === 'pathly-studio'
                  OR message.messageType === 'pathly_chat'
      → routes to PathlyRouterService.handle(client, message)
      |
      v
[B]  PathlyRouterService.handle(client, message)
      |
      |-- PathlySessionService.getCapabilities(client.sessionId)
      |    returns { canExecuteToolCalls, canStreamThinking, ... }
      |
      |-- PathlyContextBuilderService.build(message.context.appContext)
      |    fills system prompt template with:
      |      activeFeature, fsmStage, nextUncompletedStory,
      |      userStoriesSummary
      |    (tool section omitted — canExecuteToolCalls: false)
      |    returns systemPrompt string
      |
      v
[B]  ChatAgent.run({ systemPrompt, message, tools: [] })
      LLM begins inference
      |
      v
[B]  (typing_metadata — thinking phase)
      ChatAgent emits { type: 'typing_metadata', label: 'Analyzing your plan…' }
      |
     [WS] <--------- typing_metadata frame ----------------
      |
[R]  brightskyClient ws.onmessage
      branch: type === 'typing_metadata'
      useBrightskyStore.getState().setThinkingLabel(data.label)
      |
      v
[R]  ChatPanel re-renders
      thinkingLabel is non-null
      renders: <div className={styles.thinkingBar}>Analyzing your plan…</div>
      (above the message list)
      |
      |   (LLM continues generating response tokens)
      |
      v
[B]  ChatAgent emits first { type: 'stream_chunk', delta: '...' }
      |
     [WS] <--------- stream_chunk frame -----------------
      |
[R]  brightskyClient ws.onmessage
      branch: type === 'stream_chunk'
      setThinkingLabel(null)          ← thinking bar cleared
      appends delta to streaming message in store
      |
      v
[R]  ChatPanel re-renders
      thinkingLabel is null → thinking bar hidden
      streaming message text visible and growing
      |
      |   (more stream_chunk frames arrive)
      |
      v
[B]  ChatAgent emits { type: 'stream_end' }
      |
     [WS] <--------- stream_end frame -------------------
      |
[R]  brightskyClient ws.onmessage
      branch: type === 'stream_end'
      setThinkingLabel(null)          ← ensure cleared (defensive)
      finalises streaming message → committed to message list
      |
      v
[R]  ChatPanel re-renders
      complete assistant message visible
      input re-enabled
```

---

## Path B — AI-driven tool call to read workspace state (Conv 3 result)

User asks "what should I do next?" — backend needs live plan data, uses tool call.

```
[R]  User types "what should I do next?" → ChatPanel sends message
      (follows Path A steps up to ChatAgent.run — omitted for brevity)
      |
      v
[B]  ChatAgent.run({ systemPrompt, message, tools: [studio.get_feature_plan, ...] })
      LLM decides it needs current plan content
      calls tool: studio.get_feature_plan
      |
      v
[B]  StudioBridgeTool.execute({ toolName: 'get_feature_plan', parameters: {} })
      looks up connected client with clientType === 'pathly-studio'
      generates callId = uuid()
      starts 15-second timeout
      sends tool_call frame
      |
     [WS] <--------- tool_call frame ---------------------
      {
        type: 'tool_call',
        callId: '<uuid>',
        toolName: 'get_feature_plan',
        parameters: {}
      }
      |
[R]  brightskyClient ws.onmessage
      branch: type === 'tool_call'
      useBrightskyStore.getState().setActiveToolCall({ toolName: 'get_feature_plan' })
      calls: executeStudioTool('get_feature_plan', {})
      |
      v
[R]  ChatPanel re-renders
      toolCallInProgress is set
      renders: <div className={styles.toolCallBar}>Using tool: get_feature_plan…</div>
      |
      v
[R]  studioAnalyzer.executeStudioTool('get_feature_plan', {})
      looks up 'get_feature_plan' in studioTools registry
      calls get_feature_plan handler
      |
      v
[R]  get_feature_plan handler
      |
      |-- window.pathly.fs.read(USER_STORIES.md path)
      |    |
      |   [IPC] ipcRenderer.invoke('fs:read', path)
      |    |
      |   [M]  fs IPC handler  →  fs.readFile(path)
      |    |
      |    <-- USER_STORIES.md contents
      |
      |-- window.pathly.fs.read(IMPLEMENTATION_PLAN.md path)
      |    |
      |   [IPC] ipcRenderer.invoke('fs:read', path)
      |    |
      |   [M]  fs IPC handler  →  fs.readFile(path)
      |    |
      |    <-- IMPLEMENTATION_PLAN.md contents
      |
      |-- window.pathly.fs.read(PROGRESS.md path)
      |    |
      |   [IPC] ipcRenderer.invoke('fs:read', path)
      |    |
      |   [M]  fs IPC handler  →  fs.readFile(path)
      |    |
      |    <-- PROGRESS.md contents
      |
      returns {
        userStories: '...',
        implementationPlan: '...',
        progress: '...'
      }
      |
      v
[R]  executeStudioTool returns result
      |
[R]  brightskyClient (tool_call handler continuation)
      useBrightskyStore.getState().setActiveToolCall(null)   ← clear status bar
      ws.send(JSON.stringify({
        type: 'tool_response',
        callId: '<uuid>',
        payload: { result, success: true }
      }))
      |
     [WS] ---------- tool_response frame ---------------->
      {
        type: 'tool_response',
        callId: '<uuid>',
        payload: {
          success: true,
          result: {
            userStories: '...',
            implementationPlan: '...',
            progress: '...'
          }
        }
      }
      |
[R]  ChatPanel re-renders
      toolCallInProgress is null → tool-call status bar hidden
      |
[B]  StudioBridgeTool.execute resolves with tool result
      15-second timeout cancelled
      |
      v
[B]  ChatAgent receives tool result
      LLM continues with plan content in context
      generates answer: "Based on your PROGRESS.md, the next story is S-05 (PathlyModule)…"
      emits stream_chunk frames
      |
     [WS] <--------- stream_chunk (answer text) ---------
      |
[R]  (follows Path A stream handling — thinkingLabel cleared, message displayed)
```

---

## Path C — AI drives wizard to create a feature (Conv 3 result)

User says "create a feature called auth-flow" — AI executes three sequential tool calls.

```
[R]  User types "create a feature called auth-flow"
      (follows Path A steps up to ChatAgent.run — omitted for brevity)
      |
      v
[B]  ChatAgent.run({ systemPrompt, message, tools: [studio.automation.executeStep, ...] })
      LLM plans: open wizard → fill name → click create
      |
      |============================================================
      | STEP 1: click "New Feature" to open wizard
      |============================================================
      |
      v
[B]  StudioBridgeTool.execute({
        toolName: 'automation.executeStep',
        parameters: { action: 'click', selector: '[data-label="New Feature"]' }
      })
      generates callId-1
      |
     [WS] <--------- tool_call (callId-1) ----------------
      { type: 'tool_call', callId: 'callId-1',
        toolName: 'automation:executeStep',
        parameters: { action: 'click', selector: '[data-label="New Feature"]' } }
      |
[R]  brightskyClient
      setActiveToolCall({ toolName: 'automation:executeStep' })
      calls executeStudioTool('automation:executeStep', { action: 'click', ... })
      |
      v
[R]  studioAnalyzer — automation:executeStep handler
      calls window.pathly.automation.executeStep({ action: 'click', selector: '[data-label="New Feature"]' })
      |
     [IPC] ipcRenderer.invoke('auto:step', { action: 'click', selector: '[data-label="New Feature"]' })
      |
[M]  automation IPC handler
      calls playwrightExecutor.performAction({ action: 'click', selector: '[data-label="New Feature"]' })
      |
      v
[M]  playwrightExecutor — click case
      BrowserWindow.webContents.executeJavaScript(
        'document.querySelector(\'[data-label="New Feature"]\').click()'
      )
      element found (data-label added in Conv 3 data-label audit)
      click fires
      |
     [IPC] <-- { success: true }
      |
[R]  studioAnalyzer returns { success: true }
      |
[R]  brightskyClient
      setActiveToolCall(null)
      ws.send({ type: 'tool_response', callId: 'callId-1',
                payload: { success: true } })
      |
     [WS] ---------- tool_response (callId-1) success ---->
      |
[B]  StudioBridgeTool resolves callId-1  ← LLM receives: click succeeded
      |
      |   (FlowWizard Step1Name is now mounted in the renderer DOM)
      |
      |============================================================
      | STEP 2: fill "Feature Name" input with "auth-flow"
      |============================================================
      |
      v
[B]  StudioBridgeTool.execute({
        toolName: 'automation.executeStep',
        parameters: { action: 'fill', selector: '[data-label="Feature Name"]', value: 'auth-flow' }
      })
      generates callId-2
      |
     [WS] <--------- tool_call (callId-2) ----------------
      { type: 'tool_call', callId: 'callId-2',
        toolName: 'automation:executeStep',
        parameters: { action: 'fill', selector: '[data-label="Feature Name"]', value: 'auth-flow' } }
      |
[R]  brightskyClient
      setActiveToolCall({ toolName: 'automation:executeStep' })
      calls executeStudioTool(...)
      |
     [IPC] ipcRenderer.invoke('auto:step', { action: 'fill', ... })
      |
[M]  automation IPC handler
      calls playwrightExecutor.performAction({ action: 'fill', selector: '...', value: 'auth-flow' })
      |
      v
[M]  playwrightExecutor — fill case (React-compatible, S-09)
      BrowserWindow.webContents.executeJavaScript(`
        (function() {
          const el = document.querySelector('[data-label="Feature Name"]');
          const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
          nativeSetter.call(el, 'auth-flow');
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        })()
      `)
      React controlled input receives synthetic events
      React state updates → input shows "auth-flow"
      Next button becomes enabled (if gated on non-empty name)
      |
     [IPC] <-- { success: true }
      |
[R]  studioAnalyzer returns { success: true }
      |
[R]  brightskyClient
      setActiveToolCall(null)
      ws.send({ type: 'tool_response', callId: 'callId-2',
                payload: { success: true } })
      |
     [WS] ---------- tool_response (callId-2) success ---->
      |
[B]  StudioBridgeTool resolves callId-2  ← LLM receives: fill succeeded
      |
      |============================================================
      | STEP 3: click "Create Feature" to submit wizard
      |============================================================
      |
      v
[B]  StudioBridgeTool.execute({
        toolName: 'automation.executeStep',
        parameters: { action: 'click', selector: '[data-label="Create Feature"]' }
      })
      generates callId-3
      |
     [WS] <--------- tool_call (callId-3) ----------------
      { type: 'tool_call', callId: 'callId-3',
        toolName: 'automation:executeStep',
        parameters: { action: 'click', selector: '[data-label="Create Feature"]' } }
      |
[R]  brightskyClient
      setActiveToolCall({ toolName: 'automation:executeStep' })
      calls executeStudioTool(...)
      |
     [IPC] ipcRenderer.invoke('auto:step', { action: 'click', ... })
      |
[M]  automation IPC handler
      calls playwrightExecutor.performAction({ action: 'click', selector: '[data-label="Create Feature"]' })
      |
      v
[M]  playwrightExecutor — click case
      BrowserWindow.webContents.executeJavaScript(
        'document.querySelector(\'[data-label="Create Feature"]\').click()'
      )
      click fires → wizard submit handler runs
      FlowWizard closes, feature 'auth-flow' created in workspace
      |
     [IPC] <-- { success: true }
      |
[R]  studioAnalyzer returns { success: true }
      |
[R]  brightskyClient
      setActiveToolCall(null)
      ws.send({ type: 'tool_response', callId: 'callId-3',
                payload: { success: true } })
      |
     [WS] ---------- tool_response (callId-3) success ---->
      |
[B]  StudioBridgeTool resolves callId-3  ← LLM receives: click succeeded
      |
      v
[B]  ChatAgent — all tool calls resolved
      LLM generates summary response:
      "Done. I've created the feature 'auth-flow' for you."
      emits stream_chunk frames
      |
     [WS] <--------- stream_chunk (summary text) --------
      |
[R]  (follows Path A stream handling — message displayed, input re-enabled)
```

---

## Layer boundary summary

| Boundary | What crosses it | Direction |
|---|---|---|
| Renderer → IPC | `window.pathly.fsm.state()`, `window.pathly.fs.read()`, `window.pathly.automation.executeStep()` | Request / response |
| IPC → Main | `ipcRenderer.invoke()` → `ipcMain.handle()` | Request / response |
| Main → Renderer (automation) | `BrowserWindow.webContents.executeJavaScript()` | Main pushes, renderer executes in page |
| Renderer → WebSocket | `user_message`, `client_capabilities`, `tool_response` | Renderer → Backend |
| WebSocket → Renderer | `session_created`, `typing_metadata`, `stream_chunk`, `stream_end`, `tool_call` | Backend → Renderer |
| Backend internal | `UnifiedChatGateway` → `PathlyRouterService` → `PathlyContextBuilderService` → `ChatAgent` | Sequential call chain |
| Backend internal | `ChatAgent` tool call → `StudioBridgeTool` → waits on WebSocket response | Async round-trip |
