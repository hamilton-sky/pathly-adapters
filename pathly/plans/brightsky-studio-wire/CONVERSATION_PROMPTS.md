# Conversation Prompts — brightsky-studio-wire

---

## Conv 1 — Frontend context + thinking indicator

### Background

Pathly Studio has a working WebSocket connection to the Brightsky AI backend (auth, streaming, session management all work). The problem: every outbound message is bare text with no workspace context. The backend receives no information about what feature is active, what pipeline stage the user is in, or what the plan files contain. As a result, Brightsky answers are generic.

Additionally, the backend already sends `typing_metadata` messages while it is thinking (e.g. `{ type: 'typing_metadata', label: 'Analyzing your plan…' }`), but the Studio ignores them — users see silence.

There is no reconnect logic: a dropped connection requires an app restart.

**What already exists (do not rebuild):**
- `studio/src/renderer/src/lib/brightskyClient.ts` — WebSocket client class with `connect()`, `sendMessage()`, `ws.onmessage` handler, `ws.onclose`
- `studio/src/renderer/src/store/brightskyStore.ts` — Zustand store with `connected`, `authenticated`, `accessToken`, `sessionId`, `authError` fields
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — chat UI with `handleBrightskySend(content)` which calls `brightskyClient.sendMessage(content, sessionId)`
- `window.pathly.fsm.state(topic)` — IPC call that returns FSM STATE.json for the given feature topic
- `window.pathly.fs.read(path)` — IPC call that reads a file at the given absolute path
- `window.pathly.automation.executeStep(params)` — IPC call for automation (not needed in Conv 1)
- `useWorkspaceStore` — has `projectPath` and `activeTopic` fields

**Nothing has been built for this feature yet.** This is the first conversation.

### What to build

**1. Create `studio/src/renderer/src/lib/pathlyContextCollector.ts`**

Export one main function:
```ts
export async function collectPathlyContext(): Promise<AppContext>
```

It must:
- Read `useWorkspaceStore.getState().projectPath` and `.activeTopic`
- **Guard before FSM call:** if `activeTopic` is null, empty, or undefined, return immediately: `{ source: 'pathly-studio', projectPath }`. Do NOT call `window.pathly.fsm.state()` with a null/empty topic — the FSM HTTP server will error.
- Call `window.pathly.fsm.state(activeTopic)` to get FSM state — only after the guard above passes
- Call `window.pathly.fs.read()` to read PROGRESS.md (trim to 500 chars) and USER_STORIES.md (trim to 2000 chars) from `${projectPath}/pathly/plans/${activeTopic}/`
- Parse PROGRESS.md for the first TODO row (the `parseNextTodo` helper)
- Return the full `appContext` object matching this shape:
```ts
{
  source: 'pathly-studio',
  projectPath,
  appContext: {
    activeFeature: activeTopic,
    fsmStage: fsmState?.stage,
    activeConversation: fsmState?.conversationIndex,
    totalConversations: fsmState?.totalConversations,
    nextUncompletedStory: parseNextTodo(progress),
    userStoriesSummary: stories,
  }
}
```
- Use a `safeRead(path, maxChars)` helper that returns `''` on any IPC error (do not throw)
- Total injected context must not exceed 4000 tokens — the trim limits enforce this

**2. Modify `studio/src/renderer/src/store/brightskyStore.ts`**

Add to the store state and actions:
```ts
thinkingLabel: string | null   // initial: null
setThinkingLabel: (label: string | null) => void
```

**3. Modify `studio/src/renderer/src/lib/brightskyClient.ts`**

Add four changes:

*Change A — `typing_metadata` handler in `ws.onmessage`:*
```ts
} else if (type === 'typing_metadata') {
  const label = (data.label as string) ?? null
  useBrightskyStore.getState().setThinkingLabel(label)
}
```
Also clear `thinkingLabel` at the start of `stream_chunk` handling and in `stream_end` handling:
```ts
useBrightskyStore.getState().setThinkingLabel(null)
```

*Change B — Capability handshake after `session_created`:*
After the existing sessionId extraction in the `session_created` branch, add:
```ts
this.ws?.send(JSON.stringify({
  type: 'client_capabilities',
  source: 'pathly-studio',
  capabilities: {
    canAnalyzeDom: false,
    canExecuteToolCalls: false,
    canStreamThinking: true,
    supportedToolTypes: []
  },
  version: '1.0'
}))
```

*Change C — Context forwarding in `sendMessage`:*

Import `collectPathlyContext` from `pathlyContextCollector.ts`. `sendMessage` is already `async` — keep the signature unchanged and insert context collection before the send.

**Important:** the backend expects different payload shapes for session creation vs. continuation. Preserve the existing shapes and add context fields alongside them:

```ts
async sendMessage(content: string, sessionId: string | null): Promise<void> {
  await this.maybeRefreshToken()   // existing — keep at top

  if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
    useBrightskyStore.getState().setAuthError('Not connected — please wait for the connection to open.')
    return
  }

  useChatStore.getState().addMessage({
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    status: 'streaming',
  })
  this.streamContent = ''
  this.streamInProgress = true

  const pathlyCtx = await collectPathlyContext()   // ← new

  const sharedFields = {                           // ← new
    requestId: crypto.randomUUID(),
    messageType: 'pathly_chat',
    context: { source: 'pathly-studio', appContext: pathlyCtx.appContext },
    capabilities: {
      canAnalyzeDom: false,
      canExecuteToolCalls: false,
      canStreamThinking: true,
      supportedToolTypes: [] as string[]
    }
  }

  if (sessionId === null) {
    // Preserve the nested payload.userMessage shape the backend expects for session creation
    this.ws?.send(JSON.stringify({
      type: 'create_session_with_message',
      payload: { userMessage: { content, role: 'user' } },
      ...sharedFields
    }))
  } else {
    // Preserve the flat shape for continuation messages
    this.ws?.send(JSON.stringify({
      type: 'user_message',
      content,
      sessionId,
      ...sharedFields
    }))
  }
}
```

*Change D — Reconnect with backoff in `ws.onclose`:*

Add these instance fields to `BrightskyClient` (alongside the existing `ws`, `streamInProgress` etc.):
```ts
private wsUrl: string = ''
private accessToken: string = ''
private reconnectAttempts: number = 0
```

At the very top of `connect(wsUrl, accessToken)` — before any other logic — store the parameters:
```ts
connect(wsUrl: string, accessToken: string): void {
  this.wsUrl = wsUrl           // ← add this
  this.accessToken = accessToken  // ← add this
  this.reconnectAttempts = 0   // ← reset on fresh connect
  // ... rest of existing connect logic unchanged
}
```

Then in `ws.onclose`, replace the existing `setAuthError('Disconnected from Brightsky.')` block with:
```ts
ws.onclose = () => {
  useBrightskyStore.getState().setConnected(false)
  if (this.streamInProgress) {
    // existing incomplete-stream logic unchanged
    const current = useChatStore.getState().messages
    const last = current[current.length - 1]
    const prev = (last?.content as string | undefined) ?? ''
    useChatStore.getState().updateLastMessage({
      content: prev + '\n\n_(incomplete — connection lost)_',
    })
  }
  useBrightskyStore.getState().setThinkingLabel(null)  // clear stale label
  this.streamInProgress = false
  this.streamContent = ''

  if (!this.intentionalDisconnect) {
    const delays = [1000, 2000, 4000, 8000, 16000]
    const attempt = this.reconnectAttempts++
    if (attempt < delays.length) {
      setTimeout(() => this.connect(this.wsUrl, this.accessToken), delays[attempt])
    } else {
      useBrightskyStore.getState().setAuthError('Connection lost after 5 attempts — please sign in again.')
    }
  }
  this.intentionalDisconnect = false
  this.ws = null
}
```

Note: `this.wsUrl` and `this.accessToken` are now instance fields set at the start of `connect()`, so they are always in scope inside the `ws.onclose` closure.

**4. Modify `studio/src/renderer/src/components/ChatPanel/index.tsx`**

Subscribe to `thinkingLabel` from brightskyStore:
```ts
const thinkingLabel = useBrightskyStore(s => s.thinkingLabel)
```

Render a status bar above the message area (or above the input bar) when it is non-null:
```tsx
{thinkingLabel && (
  <div className={styles.thinkingBar}>
    <span className={styles.thinkingDot} />
    {thinkingLabel}
  </div>
)}
```
Add minimal CSS for `.thinkingBar` — small italic text, muted color, visible but not intrusive.

### Acceptance test — verify before declaring done

1. Open Studio. Activate a feature (set `activeTopic` to any existing plan).
2. Open Brightsky chat. Type "hello". Send.
3. Check: thinking bar appears with a label before any response text streams in.
4. Check: thinking bar disappears when streaming begins.
5. Open browser DevTools → Network → WS. Find the outbound `user_message` frame. Confirm it contains:
   - `context.appContext.activeFeature` (non-empty string)
   - `context.appContext.fsmStage` (non-empty string)
   - `messageType: 'pathly_chat'`
   - `capabilities.canStreamThinking: true`
6. Find the `session_created` response, then confirm the next outbound frame is `client_capabilities`.
7. In DevTools: manually close the WS connection. Wait 1–2 seconds. Confirm the WS reconnects automatically without any user action.
8. Run TypeScript check from repo root: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`. Zero errors.

---

## Conv 2 — Backend PathlyModule

### Background

Conv 1 is complete. Pathly Studio now sends every message with a full workspace context envelope: `context.appContext` contains `activeFeature`, `fsmStage`, `nextUncompletedStory`, and `userStoriesSummary`. A capability handshake is sent after connection. Reconnect backoff is working.

The backend problem: the Brightsky NestJS backend's `UnifiedChatGateway` receives these enriched messages but falls through to the generic chat handler because there is no routing for `source: 'pathly-studio'`. The system prompt is empty. The backend has no knowledge of Pathly plans.

**What already exists (do not rebuild):**
- `backend/src/chat/gateways/core/unified-chat.gateway.ts` — routes `messageType === 'page_research'` and `messageType === 'workflow_generate'` to existing strategies. You will add a routing branch here.
- Existing `ChatAgent` (or equivalent) — takes `{ systemPrompt, message, tools }` and streams a response. Your new PathlyRouterService calls this.
- Existing `SessionService` (or equivalent) — manages per-session state. Your PathlySessionService is a simple in-memory supplement, not a replacement.
- `PageAnalyzerBridgeTool` pattern in `backend/src/mcp/` — you will reference this pattern in Conv 3 but do not need to touch it in Conv 2.

**Conv 1 output that is now live:**
- Studio sends `type: 'client_capabilities'` after session_created — your gateway must handle this message type
- Studio sends all messages with `context.source: 'pathly-studio'` and `messageType: 'pathly_chat'`

**Nothing has been built for the backend part of this feature yet.** Conv 2 is the first backend conversation.

### What to build

**1. Create `backend/src/pathly/types.ts`**

Define the shared types the backend needs. Do NOT import from the Studio frontend — backend must not depend on Studio source files.

```ts
export interface AppContext {
  source: 'pathly-studio'
  projectPath?: string
  appContext?: {
    activeFeature?: string
    fsmStage?: string
    activeConversation?: number
    totalConversations?: number
    nextUncompletedStory?: string
    userStoriesSummary?: string
  }
}

export interface ClientCapabilities {
  canAnalyzeDom: boolean
  canExecuteToolCalls: boolean
  canStreamThinking: boolean
  supportedToolTypes: string[]
}

export interface BrightskyClientMessage {
  type: string
  requestId?: string
  sessionId?: string
  content?: string
  messageType?: string
  context?: AppContext
  capabilities?: ClientCapabilities
  [key: string]: unknown
}
```

Import these types in `PathlyContextBuilderService`, `PathlyRouterService`, and `PathlySessionService` — never use `any` for these shapes.

---

**2. Create `backend/src/pathly/pathly.module.ts`**

Standard NestJS module. Provides: PathlyContextBuilderService, PathlyRouterService, PathlySessionService. Exports all three (gateway needs them injected).

**2. Create `backend/src/pathly/pathly-session.service.ts`**

Injectable service. Private `Map<string, ClientCapabilities>`. Methods:
- `storeCapabilities(sessionId: string, caps: ClientCapabilities): void`
- `getCapabilities(sessionId: string): ClientCapabilities | undefined`

No persistence — in-memory only.

**3. Create `backend/src/pathly/pathly-context-builder.service.ts`**

Injectable service. One public method:
```ts
build(appContext: AppContext, capabilities?: ClientCapabilities): string
```

Returns a string system prompt using this template (fill in values from appContext):
```
You are an AI coding assistant integrated into Pathly Studio, a structured
feature-development pipeline for software engineers.

## Current workspace state
Active feature: ${activeFeature}
Pipeline stage: ${fsmStage} (conversation ${activeConversation} of ${totalConversations})

## Next task
${nextUncompletedStory}

## Acceptance criteria (USER_STORIES.md)
${userStoriesSummary}

## Instructions
- Answer questions about the codebase and feature plan directly
- Suggest next steps based on the current pipeline stage
- When the user asks "what next", use the plan context above to answer with the specific story
- Do not invent plan details
```

If `appContext` is null/undefined, return a sensible generic fallback rather than throwing.

**4. Create `backend/src/pathly/pathly-router.service.ts`**

Injectable service. Inject: PathlyContextBuilderService, PathlySessionService, and the existing ChatAgent (or whatever streaming agent the gateway uses).

One public method:
```ts
handle(client: WsClient, message: BrightskyClientMessage): Observable<void>
```

Logic:
1. Extract `appContext` from `message.context?.appContext`
2. Get capabilities from `pathlySessionService.getCapabilities(client.sessionId)` — may be undefined
3. Build system prompt: `contextBuilder.build(appContext, capabilities)`
4. Assemble tools list — empty array in Conv 2 (tool bridge is Conv 3)
5. Delegate to ChatAgent with the enriched system prompt: `return this.chatAgent.run({ systemPrompt, message, tools: [] })`

**5. Modify `backend/src/chat/gateways/core/unified-chat.gateway.ts`**

Two additions only — do not refactor existing routing logic:

*Addition A — handle `client_capabilities`:*
In the existing message-type dispatch, add:
```ts
if (message.type === 'client_capabilities') {
  await this.pathlySessionService.storeCapabilities(client.sessionId, message.capabilities)
  return
}
```

*Addition B — route pathly-studio source:*
Before the existing `page_research` / `workflow_generate` branches (or after, as long as it does not shadow them):
```ts
if (message.context?.source === 'pathly-studio' || message.messageType === 'pathly_chat') {
  return this.pathlyRouter.handle(client, message)
}
```

Inject `PathlyRouterService` and `PathlySessionService` into the gateway constructor.

**6. Register PathlyModule in the root app module**

Import `PathlyModule` in `backend/src/app.module.ts` (or wherever the root module is). No other changes to the root module.

### Acceptance test — verify before declaring done

1. Start the Brightsky backend with the new module.
2. Connect Studio, activate a feature with a PROGRESS.md that has a TODO story.
3. In Studio Brightsky chat type: "What should I do next?"
4. Confirm: the response names the actual active feature (e.g. "brightsky-studio-wire") and the current FSM stage (e.g. "PLANNING").
5. Confirm: the response references the actual next uncompleted story (not a generic placeholder).
6. In backend logs (or add a temporary log): confirm `PathlyRouterService.handle` was entered for the message.
7. Confirm generic chat still works: send a plain message without `context.source` — confirm it routes to the existing generic handler and returns a normal response.
8. `nest build` (or TypeScript check) passes with zero errors.

---

## Conv 3 — Tool bridge + Studio Analyzer + data-label audit

### Background

Conv 1 and Conv 2 are complete:
- Studio sends every message with full workspace context (activeFeature, fsmStage, plan summary)
- Backend routes `source: 'pathly-studio'` messages to PathlyRouterService with a plan-aware system prompt
- Users see a thinking indicator while the backend is processing
- Connection reconnects automatically on drop

The remaining gap: the backend cannot query Studio state mid-conversation. If the user's message context is stale or incomplete, the AI cannot fetch updated plan data. Also, the AI cannot perform UI actions (fill wizard inputs, click buttons, navigate panels).

Additionally, `playwrightExecutor.ts` has two known bugs: `fill` sets `el.value` directly (breaks React controlled inputs), and `navigate` throws (not implemented).

**What already exists:**
- `studio/src/renderer/src/lib/brightskyClient.ts` — has `typing_metadata`, context forwarding, capability handshake, reconnect from Conv 1. Missing: `tool_call` handler.
- `window.pathly.automation.executeStep` — exposed in preload, line 88. Works.
- `window.pathly.fsm.state(topic)` and `window.pathly.fs.read(path)` — exposed in preload. Work.
- `studio/src/main/automation/playwrightExecutor.ts` — 3-tier element resolver, click/select work, fill broken for React inputs, navigate not implemented.
- `backend/src/mcp/tool-registry.ts` — existing registry. `PageAnalyzerBridgeTool` pattern already exists for Chrome extension.
- Conv 2 built: PathlyModule, PathlyContextBuilder, PathlyRouterService, PathlySessionService, UnifiedChatGateway routing.
- `App.tsx` layout: TopBar → Sidebar → MainPanel (PlanBoard | Editor | FlowEditor | Monitor | Settings) → ChatPanel → Terminal. Navigation state is in a layout/navigation Zustand store.

**Nothing has been built for Phase 3 yet.** This is the first conversation for the tool bridge.

### What to build

**1. Create `studio/src/renderer/src/lib/studioAnalyzer.ts`**

Export a tool registry and a dispatch function:

```ts
import { useWorkspaceStore } from '../store/workspaceStore'
// import layout store — whatever store manages active panel / open panels

export const studioTools: Record<string, (params: unknown) => Promise<unknown>> = {

  'get_fsm_state': async () => {
    const { activeTopic, projectPath } = useWorkspaceStore.getState()
    const state = await window.pathly.fsm.state(activeTopic ?? '')
    return { stage: state?.stage, feature: activeTopic, rigor: state?.rigor }
  },

  'get_feature_plan': async (params: unknown) => {
    const { activeTopic, projectPath } = useWorkspaceStore.getState()
    const base = `${projectPath}/pathly/plans/${activeTopic}`
    const stories    = await window.pathly.fs.read(`${base}/USER_STORIES.md`)
    const implPlan   = await window.pathly.fs.read(`${base}/IMPLEMENTATION_PLAN.md`)
    const progress   = await window.pathly.fs.read(`${base}/PROGRESS.md`)
    return { stories, implPlan, progress }
  },

  'get_studio_schema': async () => {
    // read from whatever layout/navigation Zustand store exists
    return { openPanels: [], selectedTab: null }  // fill from actual store
  },

  'automation:executeStep': async (params: unknown) => {
    return window.pathly.automation.executeStep(params as any)
  }
}

export async function executeStudioTool(toolName: string, parameters: unknown): Promise<unknown> {
  const handler = studioTools[toolName]
  if (!handler) throw new Error(`Unknown studio tool: ${toolName}`)
  return handler(parameters)
}
```

**2. Modify `studio/src/renderer/src/lib/brightskyClient.ts`**

Add `tool_call` handler in `ws.onmessage`. Import `executeStudioTool` from `studioAnalyzer.ts`. Also add tool-call state tracking in the store (see below):

```ts
} else if (type === 'tool_call') {
  const { callId, toolName, parameters } = data as ToolCallMessage
  useBrightskyStore.getState().setActiveToolCall(toolName)
  try {
    const result = await executeStudioTool(toolName, parameters)
    this.ws?.send(JSON.stringify({
      type: 'tool_response',
      callId,
      payload: { result, success: true }
    }))
  } catch (err) {
    this.ws?.send(JSON.stringify({
      type: 'tool_response',
      callId,
      payload: { success: false, error: String(err) }
    }))
  } finally {
    useBrightskyStore.getState().setActiveToolCall(null)
  }
}
```

Also update the Conv 1 capability handshake and `sendMessage` capabilities to reflect Phase 3 capabilities:
```ts
canExecuteToolCalls: true,
supportedToolTypes: ['studio_analyzer', 'automation']
```

Add to brightskyStore: `activeToolCall: string | null` and `setActiveToolCall(name: string | null): void`.

**3. Modify `studio/src/renderer/src/components/ChatPanel/index.tsx`**

Add tool-call status row. Subscribe to `activeToolCall`:
```ts
const activeToolCall = useBrightskyStore(s => s.activeToolCall)
```
Render below the thinkingBar (or in the same status area):
```tsx
{activeToolCall && (
  <div className={styles.toolCallBar}>
    Using tool: {activeToolCall}…
  </div>
)}
```

**4. Modify `studio/src/main/automation/playwrightExecutor.ts`**

*Fix A — React-compatible fill:*
Find the `fill` case (or wherever `el.value = value` is set). Replace with:
```ts
case 'fill':
  await this.evalInPage(`
    (() => {
      const el = document.querySelector(${escaped});
      if (!el) return;
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
      ).set;
      nativeSetter.call(el, ${JSON.stringify(step.value ?? '')});
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    })()
  `)
  break
```

*Fix B — navigate action:*
Add `navigate` case:
```ts
case 'navigate':
  await this.evalInPage(
    `window.__pathlyNavigate(${JSON.stringify(step.value ?? '')})`
  )
  break
```

**5. Modify `studio/src/renderer/src/App.tsx`**

Register `window.__pathlyNavigate` before the component return. Use whatever navigation action your layout/navigation store provides to switch main panels:
```ts
// In App component body, after store imports:
React.useEffect(() => {
  (window as any).__pathlyNavigate = (panelName: string) => {
    // call the store action to switch active panel
    // e.g.: useLayoutStore.getState().setActivePanel(panelName)
  }
}, [])
```

Declare the global type in a `.d.ts` or inline:
```ts
declare global {
  interface Window { __pathlyNavigate: (panel: string) => void }
}
```

**6. Add data-label attributes — systematic audit**

> **Critical note on feature creation:** The wizard for creating a new Pathly feature/plan is NOT
> `FlowWizard` (that is for flow.yaml definitions) and NOT `NewItemDialog` (that creates library
> items: skills, agents, templates). The actual feature creation flow is:
> `Sidebar.tsx → PlanSection → "New plan folder" button → InlineCreateInput`.
> S-07 targets this flow. FlowWizard still gets data-labels for its own form fields (flow editing),
> but it is NOT the target for "create a feature called X" automation.

For each file below, add `data-label` to the listed elements. Use the label text a human would use to refer to that element:

| File | Elements to label |
|---|---|
| **`sidebar/shared/InlineCreateInput.tsx`** | input → `data-label="New Plan Name"` (this is what the AI fills when creating a new feature) |
| `sidebar/shared/InlineFolderInput.tsx` | input → `data-label="New Folder Name"` |
| `sidebar/shared/RenameInput.tsx` | input → `data-label="Rename Input"` |
| `components/sidebar/` — PlanSection "New plan folder" button | `data-label="New Plan Folder"` (this is what the AI clicks to open the inline input) |
| `NewItemDialog.tsx` | name input → `data-label="Item Name"`, description → `data-label="Item Description"`, subdirectory → `data-label="Subdirectory"`, confirm button → `data-label="Confirm"` |
| `ChatPanel/ChatInput.tsx` | textarea → `data-label="Chat Input"`, send button → `data-label="Send Message"` |
| `Editor/ConfigForm.tsx` | name → `data-label="Config Name"`, description → `data-label="Config Description"`, adapter toggles → `data-label="[adapter name] Toggle"`, model select → `data-label="Model Selector"`, category select → `data-label="Category Selector"` |
| `FlowWizard/Step1Name.tsx` | flow name input → `data-label="Flow Name"`, description → `data-label="Flow Description"` (for flow editing, not feature creation) |
| FlowWizard confirm/submit button | `data-label="Create Flow"` |
| App-level Monitor nav | `data-label="Monitor"` |
| App-level Chat nav | `data-label="Chat"` |
| App-level Files nav | `data-label="Files"` |
| App-level Terminal nav | `data-label="Terminal"` |

**7. Create `backend/src/mcp/studio-bridge-tool.ts`**

Copy the structure from `PageAnalyzerBridgeTool` (find it in `backend/src/mcp/`). The only differences:
- `clientType` filter = `'pathly-studio'` (not `'chrome-extension'`)
- Constructor takes `toolName: string` — stored as the tool name to send in the `tool_call` message

**8. Modify `backend/src/mcp/tool-registry.ts`**

Register three StudioBridgeTool instances:
```ts
registry.register('studio.get_fsm_state',           new StudioBridgeTool('get_fsm_state'))
registry.register('studio.get_feature_plan',         new StudioBridgeTool('get_feature_plan'))
registry.register('studio.automation.executeStep',   new StudioBridgeTool('automation:executeStep'))
```

Also update PathlyRouterService (from Conv 2) to pass these tools when `capabilities.canExecuteToolCalls` is true:
```ts
const tools = capabilities?.canExecuteToolCalls
  ? this.toolRegistry.getByPrefix('studio.')
  : []
```

### Acceptance test — verify before declaring done

1. In Studio with feature active, ask Brightsky: "What is my current FSM stage?"
2. Observe in browser DevTools WS: backend sends `{ type: 'tool_call', toolName: 'get_fsm_state' }`, Studio sends `{ type: 'tool_response', payload: { result: { stage: '...', feature: '...' } } }`
3. Observe in Studio chat: "Using tool: get_fsm_state…" text appears while call is in progress, disappears when done.
4. Click the "New plan folder" button in the Sidebar PlanSection to open the inline input. In browser console run:
   ```js
   window.pathly.automation.executeStep({ action: 'fill', selector: '[data-label="New Plan Name"]', value: 'test-feature-123' })
   ```
   Confirm the inline input shows `test-feature-123` and the React state updates (Next/Enter should be enabled).
5. In browser console run:
   ```js
   window.pathly.automation.executeStep({ action: 'navigate', value: 'monitor' })
   ```
   Confirm Studio switches to Monitor panel.
6. Open DevTools Elements panel, filter for `data-label`. Confirm all FlowWizard inputs, ChatPanel input, ConfigForm fields, sidebar inputs, and navigation items have `data-label`.
7. Run TypeScript check from repo root: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`. Zero errors.
8. Backend: `nest build` passes. Zero errors.
