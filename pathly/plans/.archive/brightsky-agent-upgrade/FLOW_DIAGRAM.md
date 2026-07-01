---
name: Flow Diagram
---
# BrightSky Agent Upgrade — Flow Diagram

## Happy Path: Tool call round-trip + Reasoning box

```
User sends message (HQ chat)
         │
         ▼
brightskyClient.ts
  assemble envelope:
  { messageType:'pathly_chat',
    context.appContext,
    capabilities }
         │  WebSocket send
         ▼
BrightSky backend
  UnifiedChatGateway
  (detects 'pathly-studio' source)
         │
         ▼
  PathlyRouterService
  → PathlyContextBuilderService
    (builds system prompt)
         │
         ▼
  WsMessageHandler
  .processUserMessage()
  (customInstructions injected)
         │
         ▼
  gemini.service.ts → Gemini 2.5 Flash
  ┌──────────────────────────────────────┐
  │ thinkingConfig: { thinkingBudget:    │  ← Phase 11 (pathly_chat only)
  │   8000 } (Gemini native thinking)    │  BrightSky uses Gemini, NOT Claude
  └──────────────────────────────────────┘
         │
         ├─ [tool_call event] ──────────────────────────┐
         │                                               │
         │                                        Studio (studioAnalyzer.ts)
         │                                        executeStudioTool()
         │                                               │
         │                          ┌────────────────────┤
         │                          │  studio.list_plans  │ Phase 1
         │                          │  studio.get_events  │ Phase 2
         │                          │  studio.get_failures│ Phase 3
         │                          │  studio.create_plan │ Phase 4
         │                          │  studio.navigate_to │ Phase 5
         │                          │  studio.run_skill   │ Phase 7
         │                          └────────────────────┘
         │                                               │
         │                                        tool_response ──┐
         │◄──────────────────────────────────────────────────────┘
         │
         ├─ [Gemini thinking content part]
         │   <think>reasoning...</think>
         │   stream_chunk (sent FIRST)      ← Phase 12
         │
         ├─ [text content blocks]
         │   stream_chunk, stream_chunk,
         │   ..., stream_end
         ▼
brightskyClient.ts
  stream_chunk: accumulate streamContent
  stream_end (or isDone:true):
    splitThinkingContent(streamContent)    ← Phase 8
    → { thinking: '...', content: '...' }
    updateLastMessage({
      content, thinking, status:'done'
    })
         │
         ▼
MessageList.tsx + ThinkingBlock.tsx
  msg.thinking → ThinkingBlock (collapsible)
  msg.content  → visible response
  (collapses 800ms after stream_end)
```

## Fallback: No thinking content

```
stream_end fires
         │
         ▼
splitThinkingContent(fullText)
  → { thinking: undefined, content: fullText }
         │
         ▼
updateLastMessage({ content: fullText, status:'done' })
  (thinking field absent → ThinkingBlock not rendered)
```

## New IPC channel: studio.run_skill

```
studio.run_skill tool_call
         │
         ▼
studioAnalyzer.ts
  runSkill(params)
  window.pathly.fsm.runSkill(feature, skill, projectPath)
         │  ipcRenderer.invoke('fsm:runSkill', ...)
         ▼
Main process (fsm.ts)
  ipcMain.handle('fsm:runSkill')
         │  POST http://127.0.0.1:8765/runner/start
         ▼
FSM HTTP server
         │
         ├─ 200 OK → { success: true, runId }
         └─ error  → { success: false, error }
```

## Component Legend

| Symbol / Name | Role in this feature |
|---|---|
| `brightskyClient.ts` | WebSocket client; stream accumulator; calls splitThinkingContent at end |
| `studioAnalyzer.ts` | Tool dispatcher; 6 new handlers added |
| `fsm.ts` (main) | IPC bridge to FSM HTTP server; 1 new channel |
| `ThinkingBlock.tsx` | Renders collapsible reasoning; reads `msg.thinking` — no changes |
| `splitThinkingContent` | Strips `<think>` tags, returns `{ thinking, content }` — no changes |
| `StudioBridgeTool subclasses` | Backend tool descriptors; send tool_call → wait for tool_response |
| `reasoning-timer.service.ts` | Synthetic thinking generator — guarded off for pathly_chat |
| `gemini.service.ts` | Gemini 2.5 Flash; thinkingConfig enabled per-message for pathly_chat only (BrightSky does NOT use Claude) |
