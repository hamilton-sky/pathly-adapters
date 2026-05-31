# Implementation Plan — brightsky-studio-wire

Rigor: lite | Conversations: 3 | Feature: brightsky-studio-wire

---

## Conv 1 — Frontend context + thinking indicator

**Goal:** Studio becomes a proper Brightsky client. Every message carries workspace context. The user sees a thinking indicator while the backend is processing. The connection recovers from drops automatically. No backend changes required.

**Stories delivered:** S-01, S-02, S-03, S-04

### Files to modify

| File | Change |
|---|---|
| `studio/src/renderer/src/store/brightskyStore.ts` | Add `thinkingLabel: string \| null` field and `setThinkingLabel(label)` setter |
| `studio/src/renderer/src/lib/brightskyClient.ts` | Add `typing_metadata` handler (B2b), context forwarding in sendMessage (B2c), capability handshake after session_created (B2d), reconnect backoff in ws.onclose (B2e) |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | Render thinkingLabel status bar above streaming area; hide on stream_chunk / stream_end |

### Files to create

| File | Purpose |
|---|---|
| `studio/src/renderer/src/lib/pathlyContextCollector.ts` | `collectPathlyContext()` — reads FSM state + plan files via IPC, returns appContext object trimmed to ≤ 4000 tokens |

### Key functions to add

**pathlyContextCollector.ts**
- `collectPathlyContext(): Promise<AppContext>` — guards on `activeTopic` being non-null/non-empty before calling `window.pathly.fsm.state()`; if no activeTopic returns `{ source: 'pathly-studio', projectPath }` immediately; otherwise reads PROGRESS.md and USER_STORIES.md via `window.pathly.fs.read()`, trims stories to 2000 chars (~500 tokens), returns structured appContext
- `safeRead(path, maxChars): Promise<string>` — reads file via IPC, trims to maxChars, returns empty string on any error (never throws)
- `parseNextTodo(progressMd): string` — extracts the first TODO row from PROGRESS.md table

**brightskyStore.ts additions**
- `thinkingLabel: string | null` — initial value null
- `setThinkingLabel(label: string | null): void` — plain setter

**brightskyClient.ts additions**
- Add instance fields: `private wsUrl: string = ''`, `private accessToken: string = ''`, `private reconnectAttempts: number = 0`
- `connect(wsUrl, accessToken)` — store `this.wsUrl = wsUrl`, `this.accessToken = accessToken`, `this.reconnectAttempts = 0` at the very top before existing logic
- `ws.onmessage` — add `typing_metadata` branch: calls `useBrightskyStore.getState().setThinkingLabel(data.label ?? null)`
- `ws.onmessage` — in `stream_chunk` and `stream_end` branches: call `setThinkingLabel(null)` to clear indicator
- `ws.onmessage` — `session_created` branch: after existing sessionId extraction, check `ws.readyState === WebSocket.OPEN` before sending `client_capabilities`
- `sendMessage(content, sessionId)` — keep existing shape (`payload.userMessage` for create_session, flat `content` for user_message); add `sharedFields` spread with `collectPathlyContext()`, `messageType: 'pathly_chat'`, `capabilities`, `requestId: crypto.randomUUID()`
- `ws.onclose` — replace `setAuthError` with reconnect logic using `this.connect(this.wsUrl, this.accessToken)`; also call `setThinkingLabel(null)` to clear stale label

**ChatPanel/index.tsx additions**
- Import `useBrightskyStore` and subscribe to `thinkingLabel`
- Render `{thinkingLabel && <div className={styles.thinkingBar}>{thinkingLabel}</div>}` above the message list or streaming area
- Clear thinkingLabel display on any stream activity (already handled by store)

### Acceptance test

1. Open Studio with a feature active (e.g. `brightsky-studio-wire`)
2. Open Brightsky chat, type any message
3. Observe: before any response text appears, the thinking bar shows a label (e.g. "Analyzing your plan…")
4. Observe: when streaming starts, the thinking bar disappears
5. In browser DevTools Network → WS frames: confirm outbound `user_message` contains `context.appContext.activeFeature` and `context.appContext.fsmStage`
6. Disconnect network, wait 2 seconds, reconnect — confirm the chat reconnects without app restart
7. Confirm no TypeScript errors: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from repo root

---

## Conv 2 — Backend PathlyModule

**Goal:** The Brightsky backend routes messages from Pathly Studio to a workspace-aware agent that uses the forwarded appContext to build a plan-specific system prompt. Generic chat for all other clients is unchanged.

**Stories delivered:** S-05

### Files to modify

| File | Change |
|---|---|
| `backend/src/chat/gateways/core/unified-chat.gateway.ts` | Handle `client_capabilities` message type (store in session); add routing branch for `context.source === 'pathly-studio'` → PathlyRouterService |
| `backend/src/app.module.ts` (or equivalent root module) | Import and register PathlyModule |

### Files to create

| File | Purpose |
|---|---|
| `backend/src/pathly/pathly.module.ts` | NestJS module declaration — imports, providers, exports |
| `backend/src/pathly/pathly-context-builder.service.ts` | `build(appContext): string` — constructs system prompt template |
| `backend/src/pathly/pathly-router.service.ts` | `handle(client, message)` — gets capabilities, builds prompt, calls ChatAgent |
| `backend/src/pathly/pathly-session.service.ts` | `storeCapabilities(sessionId, caps)` and `getCapabilities(sessionId)` — in-memory map |

### Key functions to add

**pathly-context-builder.service.ts**
- `build(appContext: AppContext): string` — fills the system prompt template (see BRIGHTSKY_PATHLY_INTEGRATION_SPEC.md §8.1) with activeFeature, fsmStage, activeConversation, totalConversations, nextUncompletedStory, userStoriesSummary; includes tool section if appContext.capabilities.canExecuteToolCalls
- Token-safe: does not re-read plan files — uses what was forwarded in appContext

**pathly-router.service.ts**
- `handle(client: WsClient, message: BrightskyClientMessage): Observable<void>` — reads session capabilities from PathlySessionService, calls `contextBuilder.build()`, assembles tool list (empty in Phase 2), delegates to existing `ChatAgent.run({ systemPrompt, message, tools })`

**pathly-session.service.ts**
- `storeCapabilities(sessionId: string, caps: ClientCapabilities): void`
- `getCapabilities(sessionId: string): ClientCapabilities | undefined`
- Private `Map<string, ClientCapabilities>` — no persistence needed for Phase 2

**unified-chat.gateway.ts additions**
- In the message handler switch/if chain: add case for `type === 'client_capabilities'` → `pathlySessionService.storeCapabilities(client.sessionId, message.capabilities)`
- Add routing condition: `if (message.context?.source === 'pathly-studio' || message.messageType === 'pathly_chat')` → `return this.pathlyRouter.handle(client, message)`
- Inject `PathlyRouterService` and `PathlySessionService` into gateway constructor

### Acceptance test

1. Send a message from Studio chat with an active feature
2. In backend logs confirm: routing branch `pathly-studio` is entered, system prompt is logged containing the feature name and FSM stage
3. In Studio chat: type "what should I do next?" and confirm the response names the actual active feature and current stage (not generic advice)
4. Without appContext (generic chat client): confirm existing behavior is unaffected — send a plain `user_message` with no context field and confirm it routes to the generic handler
5. Confirm no NestJS compilation errors: `nest build` or TypeScript check passes

---

## Conv 3 — Tool bridge + Studio Analyzer + data-label audit

**Goal:** The backend can query and act on Studio state mid-conversation via tool_call / tool_response round-trips. The AI can fill wizard inputs and click buttons. All interactive UI components have data-label attributes for reliable element resolution.

**Stories delivered:** S-06, S-07, S-08, S-09, S-10

### Files to modify

| File | Change |
|---|---|
| `studio/src/renderer/src/lib/brightskyClient.ts` | Add `tool_call` handler — routes to `studioAnalyzer`, sends `tool_response` |
| `studio/src/main/automation/playwrightExecutor.ts` | Fix fill action (native setter, B3a); implement navigate action (window.__pathlyNavigate, B3b) |
| `studio/src/renderer/src/App.tsx` | Register `window.__pathlyNavigate` in renderer root pointing to navigation store action |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | Add tool-call status row ("Using tool: [toolName]…") |
| `studio/src/renderer/src/components/sidebar/shared/InlineCreateInput.tsx` | Primary feature-creation input — `data-label="New Plan Name"` |
| Sidebar PlanSection "New plan folder" button | `data-label="New Plan Folder"` — what AI clicks to open inline input |
| `studio/src/renderer/src/components/FlowWizard/Step1Name.tsx` | Flow editing wizard — `data-label="Flow Name"`, `data-label="Flow Description"` (not for feature creation) |
| `studio/src/renderer/src/components/FlowWizard/` (Step2–Step6) | Add data-label to all interactive inputs, selects, and buttons |
| `studio/src/renderer/src/components/NewItemDialog.tsx` | Library items (skills, agents, templates) — add data-label to name, description, subdirectory inputs and confirm button |
| `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` | Add `data-label="Chat Input"` to textarea |
| `studio/src/renderer/src/components/Editor/ConfigForm.tsx` | Add data-label to name, description, adapter toggles, model/category selects |
| `studio/src/renderer/src/components/sidebar/shared/InlineCreateInput.tsx` | Add data-label |
| `studio/src/renderer/src/components/sidebar/shared/InlineFolderInput.tsx` | Add data-label |
| `studio/src/renderer/src/components/sidebar/shared/RenameInput.tsx` | Add data-label |
| App-level nav panel triggers (Monitor, Chat, Files, Terminal) | Add `data-label` matching panel name |
| `backend/src/mcp/tool-registry.ts` | Register `studio.get_fsm_state`, `studio.get_feature_plan`, `studio.automation.executeStep` using StudioBridgeTool |

### Files to create

| File | Purpose |
|---|---|
| `studio/src/renderer/src/lib/studioAnalyzer.ts` | Tool registry: `studioTools` map from toolName → async handler; implements get_fsm_state, get_feature_plan, get_studio_schema, automation:executeStep |
| `backend/src/pathly/types.ts` | Shared TypeScript interfaces: AppContext, ClientCapabilities, BrightskyClientMessage — used by PathlyModule services |
| `backend/src/mcp/studio-bridge-tool.ts` | `StudioBridgeTool` class — identical to PageAnalyzerBridgeTool with clientType = 'pathly-studio' |

### Key functions to add

**studioAnalyzer.ts**
- `studioTools: Record<string, (params: unknown) => Promise<unknown>>` — tool registry map
- `get_fsm_state`: calls `window.pathly.fsm.state(activeFeature)`, returns `{ stage, feature, rigor }`
- `get_feature_plan`: reads USER_STORIES.md, IMPLEMENTATION_PLAN.md, PROGRESS.md via `window.pathly.fs.read()`, returns all three
- `get_studio_schema`: reads `openPanels` and `activeTab` from layout Zustand store
- `automation:executeStep`: delegates to `window.pathly.automation.executeStep(params)`
- `executeStudioTool(toolName, parameters)` — exported function called from brightskyClient

**brightskyClient.ts `tool_call` handler**
```
} else if (type === 'tool_call') {
  const { callId, toolName, parameters } = data
  try {
    const result = await executeStudioTool(toolName, parameters)
    this.ws?.send(JSON.stringify({ type: 'tool_response', callId, payload: { result, success: true } }))
  } catch (err) {
    this.ws?.send(JSON.stringify({ type: 'tool_response', callId, payload: { success: false, error: String(err) } }))
  }
}
```

Also: set a `toolCallInProgress: { toolName }` state in store when tool_call received, clear it when tool_response sent.

**playwrightExecutor.ts fill fix (B3a)**
Replace direct `el.value = value` with:
```
const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
nativeSetter.call(el, value);
el.dispatchEvent(new Event('input', { bubbles: true }));
el.dispatchEvent(new Event('change', { bubbles: true }));
```

**playwrightExecutor.ts navigate action (B3b)**
```
case 'navigate':
  await this.evalInPage(`window.__pathlyNavigate(${JSON.stringify(step.value ?? '')})`)
  break
```

**App.tsx `window.__pathlyNavigate` registration**
In the renderer root (before return), register:
```
window.__pathlyNavigate = (panelName: string) => {
  useLayoutStore.getState().setActivePanel(panelName)
}
```

**StudioBridgeTool (backend)**
- Copy structure from `PageAnalyzerBridgeTool`
- Change `clientType` filter from `'chrome-extension'` to `'pathly-studio'`
- Constructor accepts `toolName: string` — the Studio-side tool to call

### Acceptance test

1. In Studio with feature active, ask Brightsky: "What is my current FSM stage?"
2. Observe in browser DevTools WS frames: backend sends `tool_call` with `toolName: 'get_fsm_state'`, Studio sends `tool_response` with actual stage value
3. Observe in Studio chat: "Using tool: get_fsm_state…" appears while call is in progress
4. In automation test or console: call `window.pathly.automation.executeStep({ action: 'fill', selector: '[data-label="Feature Name"]', value: 'test-feature' })` — confirm the FlowWizard input shows "test-feature"
5. Call `window.pathly.automation.executeStep({ action: 'navigate', value: 'monitor' })` — confirm Studio switches to Monitor panel
6. Inspect DOM in browser DevTools: confirm all FlowWizard inputs, ChatPanel input, ConfigForm fields, and nav panels have `data-label` attributes
7. Confirm no TypeScript errors: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from repo root
