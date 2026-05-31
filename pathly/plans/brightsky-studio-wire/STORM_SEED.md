# Storm Seed — brightsky-studio-wire

Architecture pre-decided from session research. Full specs in:
- `BUILDING_BLOCKS.md` — 9 blocks, exact files, code snippets
- `BRIGHTSKY_PATHLY_INTEGRATION_SPEC.md` — full system design
- `BRIGHTSKY_PATHLY_ASSESSMENT.md` — current state analysis

## Key architectural decisions

### What already exists (do not re-build)

- `studio/src/main/automation/playwrightExecutor.ts` — 3-tier element resolver, click/fill/select
- `studio/src/renderer/src/store/automationStore.ts` — staged/auto mode, step lifecycle
- `window.pathly.automation.executeStep` — already in preload (line 88)
- `window.pathly.fsm.state(topic)` — already in preload
- `window.pathly.fs.read(path)` — already in preload
- WebSocket transport, auth, streaming — all working in brightskyClient.ts

### Frontend layer (Electron renderer + main process)

**File: `studio/src/renderer/src/lib/brightskyClient.ts`**
Four additions to `ws.onmessage` + `sendMessage` + `ws.onopen` + `ws.onclose`:
1. `tool_call` handler → `window.pathly.automation.executeStep()` or studioAnalyzer tool
2. `typing_metadata` handler → `brightskyStore.setThinkingLabel(label)`
3. Context forwarding: attach appContext + capabilities to every outbound message
4. Capability handshake after session_created
5. Reconnect with backoff in ws.onclose

**New file: `studio/src/renderer/src/lib/pathlyContextCollector.ts`**
Collects FSM state + plan file snippets via existing IPC.
Token budget: ≤ 4000 tokens total injected per message.

**New file: `studio/src/renderer/src/lib/studioAnalyzer.ts`**
Tool registry for backend-requested tools.
Tools: get_fsm_state, get_feature_plan, get_studio_schema, automation:executeStep
Routes tool_call by toolName → correct IPC handler.

**File: `studio/src/main/automation/playwrightExecutor.ts`**
Two fixes:
- `fill`: replace `el.value =` with native setter for React compatibility
- `navigate`: implement using `window.__pathlyNavigate(panelName)` eval

**File: `studio/src/renderer/src/store/brightskyStore.ts`**
Add: `thinkingLabel: string | null`, `setThinkingLabel(label)`

**Files: wizard + form components**
Add `data-label` attributes to all interactive elements.
Priority: New Feature wizard (name, rigor, confirm), ChatPanel input/send, nav panels.

### Backend layer (NestJS)

**New module: `backend/src/pathly/`**
- `pathly.module.ts`
- `pathly-context-builder.service.ts` — builds system prompt from appContext
- `pathly-router.service.ts` — selects agent for pathly-studio source
- `pathly-session.service.ts` — stores capabilities per session

**Modified file: `backend/src/chat/gateways/core/unified-chat.gateway.ts`**
- Handle `client_capabilities` message type → store in session
- Route `source === 'pathly-studio'` → PathlyRouterService

**Modified file: `backend/src/mcp/tool-registry.ts`**
- Register `studio.get_fsm_state`, `studio.get_feature_plan`, `studio.automation.executeStep`
- Use existing PageAnalyzerBridgeTool pattern with clientType filter = 'pathly-studio'

### Message contract

Outbound (Studio → Backend):
```ts
{
  type: 'user_message',
  requestId: string,
  sessionId?: string,
  content: string,
  messageType: 'pathly_chat',
  context: {
    source: 'pathly-studio',
    appContext: {
      activeFeature, fsmStage, activeConversation,
      totalConversations, nextUncompletedStory, userStoriesSummary
    }
  },
  capabilities: {
    canExecuteToolCalls: true,
    canStreamThinking: true,
    supportedToolTypes: ['studio_analyzer', 'automation']
  }
}
```

Backend → Studio tool_call:
```ts
{ type: 'tool_call', callId: string, toolName: string, parameters: unknown }
```

Studio → Backend tool_response:
```ts
{ type: 'tool_response', callId: string, payload: { result, success, error? } }
```

### Build order

Phase 1 (frontend only, 2–3 days):
  pathlyContextCollector → brightskyClient context + handshake → brightskyStore thinkingLabel →
  brightskyClient typing_metadata → ChatPanel UI indicator → reconnect backoff

Phase 2 (backend, 3–4 days):
  PathlyModule → PathlyContextBuilder → UnifiedChatGateway routing

Phase 3 (tool bridge, 4–5 days):
  playwrightExecutor fixes → studioAnalyzer registry → brightskyClient tool_call handler →
  backend ToolRegistry StudioAnalyzer tools → data-label audit

## Risks

- React fill: native setter pattern tested and works in Chromium; risk is low
- Token budget: plan files can be large — trim to section summaries; USER_STORIES all stories + IMPL_PLAN active conv only
- navigate action: needs `window.__pathlyNavigate` registration in renderer root — must not conflict with React Router
