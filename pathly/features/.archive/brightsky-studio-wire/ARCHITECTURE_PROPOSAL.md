# Architecture Proposal — brightsky-studio-wire

---

## Layer diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RENDERER LAYER (Chromium — no Node.js APIs)                                 │
│                                                                              │
│  React Components                  Zustand Stores          lib/              │
│  ─────────────────                 ──────────────          ────              │
│  ChatPanel/index.tsx               brightskyStore          brightskyClient   │
│    └ thinkingBar (S-01)              └ thinkingLabel          └ sendMessage  │
│    └ toolCallBar (S-06)              └ activeToolCall          └ ws.onmessage│
│    └ handleBrightskySend             └ setThinkingLabel        └ tool_call   │
│                                      └ setActiveToolCall       └ reconnect   │
│  FlowWizard/Step1Name (S-08)       workspaceStore           pathlyContext    │
│  FlowWizard/StepN     (S-08)         └ activeTopic          Collector        │
│  NewItemDialog        (S-08)         └ projectPath            └ collect      │
│  Editor/ConfigForm    (S-08)       layoutStore                 PathlyContext │
│  ChatPanel/ChatInput  (S-08)         └ setActivePanel        studioAnalyzer  │
│  Sidebar inline inputs(S-08)                                   └ studioTools │
│  App.tsx nav panels   (S-08 S-10)                              └ execute     │
│    └ window.__pathlyNavigate (S-10)                            StudioTool    │
│                                                                              │
└───────────────────────────┬──────────────────────────────────────────────────┘
                            │  window.pathly.*  (preload bridge — already built)
┌───────────────────────────▼──────────────────────────────────────────────────┐
│  IPC BOUNDARY (preload.ts — contextBridge)                                   │
│                                                                              │
│  window.pathly.fsm.state(topic)         → ipcRenderer.invoke('fsm:state')   │
│  window.pathly.fs.read(path)            → ipcRenderer.invoke('fs:read')      │
│  window.pathly.automation.executeStep  → ipcRenderer.invoke('auto:step')    │
│                                                                              │
└───────────────────────────┬──────────────────────────────────────────────────┘
                            │  ipcMain.handle
┌───────────────────────────▼──────────────────────────────────────────────────┐
│  MAIN PROCESS LAYER (Node.js — full filesystem + process access)             │
│                                                                              │
│  fsm.ts IPC handlers                                                         │
│    └ fsm:state → reads pathly/plans/<topic>/STATE.json                       │
│  fs.ts IPC handlers                                                          │
│    └ fs:read  → reads any file at given absolute path                        │
│  automation.ts IPC handlers                                                  │
│    └ auto:step → calls playwrightExecutor.performAction()                    │
│                                                                              │
│  playwrightExecutor.ts  (Electron BrowserWindow.webContents)                 │
│    └ fill:     native setter trick (S-09)                                    │
│    └ navigate: evalInPage window.__pathlyNavigate (S-10)                     │
│    └ click, select: unchanged                                                │
│                                                                              │
└───────────────────────────┬──────────────────────────────────────────────────┘
                            │
                            │  (no direct connection — all traffic goes through
                            │   renderer brightskyClient.ts WebSocket)
                            │
┌───────────────────────────▼──────────────────────────────────────────────────┐
│  WEBSOCKET BOUNDARY (port 3002)                                              │
│                                                                              │
│  Outbound (Studio → Backend):                                                │
│    user_message with context.appContext + capabilities (S-02)                │
│    client_capabilities handshake (S-03)                                      │
│    tool_response after tool execution (S-06)                                 │
│                                                                              │
│  Inbound (Backend → Studio):                                                 │
│    session_created, stream_chunk, stream_end  (already handled)             │
│    typing_metadata → thinkingLabel (S-01)                                   │
│    tool_call → studioAnalyzer dispatch (S-06)                               │
│                                                                              │
└───────────────────────────┬──────────────────────────────────────────────────┘
                            │  NestJS WebSocket Gateway
┌───────────────────────────▼──────────────────────────────────────────────────┐
│  BACKEND LAYER (NestJS — shared Brightsky backend)                           │
│                                                                              │
│  UnifiedChatGateway (modified)                                               │
│    └ client_capabilities → PathlySessionService.storeCapabilities (S-03 S-05│
│    └ source=pathly-studio → PathlyRouterService.handle (S-05)                │
│    └ all other sources → existing routing unchanged                          │
│                                                                              │
│  PathlyModule (new)                                                          │
│    └ PathlyContextBuilderService.build(appContext) → system prompt (S-05)    │
│    └ PathlyRouterService.handle → ChatAgent with enriched prompt (S-05)      │
│    └ PathlySessionService → in-memory capabilities map (S-03 S-05)           │
│                                                                              │
│  ToolRegistry (modified)                                                     │
│    └ studio.get_fsm_state   → StudioBridgeTool (S-06)                       │
│    └ studio.get_feature_plan → StudioBridgeTool (S-06)                      │
│    └ studio.automation.executeStep → StudioBridgeTool (S-06 S-07)           │
│                                                                              │
│  StudioBridgeTool (new)                                                      │
│    └ mirrors PageAnalyzerBridgeTool, clientType='pathly-studio' (S-06)       │
│    └ sends tool_call over WS, waits for tool_response                        │
│                                                                              │
│  Chrome extension routing — UNCHANGED                                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Dependency direction rules

**Rule 1: Renderer never calls main-process APIs directly.**
All filesystem reads, FSM state lookups, and automation actions in the renderer must go through `window.pathly.*` (the contextBridge). Direct Node.js imports (`fs`, `path`, `child_process`) are forbidden in renderer code.

**Rule 2: Backend never knows about Electron.**
The Brightsky NestJS backend communicates only through WebSocket messages. It never imports Electron types, never references the preload API, and never assumes it is running in the same process as the Studio app.

**Rule 3: Data flows in one direction per boundary.**
- Renderer reads state via IPC calls (request → response)
- Backend sends tool_call requests; renderer executes and responds (request → response)
- Neither side maintains a persistent callback reference across the WebSocket boundary

**Rule 4: Tool routing lives in studioAnalyzer.ts (renderer), not in brightskyClient.ts.**
`brightskyClient.ts` is transport-only — it dispatches tool calls to `studioAnalyzer.executeStudioTool()`. The tool implementations are in `studioAnalyzer.ts`. This keeps transport concerns separate from tool logic.

**Rule 5: Context collection is the responsibility of pathlyContextCollector.ts.**
No other file reads FSM state or plan files for the purpose of outbound message enrichment. All callers use `collectPathlyContext()`.

**Rule 6: PathlyModule is additive — it does not modify existing backend modules.**
`UnifiedChatGateway` gets two new lines only (capability handler + routing branch). All Pathly logic lives in `backend/src/pathly/`. Existing Chrome extension behavior is not touched.

---

## New files summary

| File | Layer | Conv |
|---|---|---|
| `studio/src/renderer/src/lib/pathlyContextCollector.ts` | Renderer | 1 |
| `studio/src/renderer/src/lib/studioAnalyzer.ts` | Renderer | 3 |
| `backend/src/pathly/pathly.module.ts` | Backend | 2 |
| `backend/src/pathly/pathly-context-builder.service.ts` | Backend | 2 |
| `backend/src/pathly/pathly-router.service.ts` | Backend | 2 |
| `backend/src/pathly/pathly-session.service.ts` | Backend | 2 |
| `backend/src/mcp/studio-bridge-tool.ts` | Backend | 3 |

## Modified files summary

| File | Layer | Conv |
|---|---|---|
| `studio/src/renderer/src/store/brightskyStore.ts` | Renderer | 1 |
| `studio/src/renderer/src/lib/brightskyClient.ts` | Renderer | 1, 3 |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | Renderer | 1, 3 |
| `studio/src/renderer/src/App.tsx` | Renderer | 3 |
| `studio/src/main/automation/playwrightExecutor.ts` | Main process | 3 |
| All wizard/form/nav components with data-label | Renderer | 3 |
| `backend/src/chat/gateways/core/unified-chat.gateway.ts` | Backend | 2 |
| `backend/src/app.module.ts` | Backend | 2 |
| `backend/src/mcp/tool-registry.ts` | Backend | 3 |
