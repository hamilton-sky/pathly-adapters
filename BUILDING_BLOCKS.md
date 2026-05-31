# Brightsky ↔ Pathly Studio — Building Blocks

**Date:** 2026-05-31  
**Companion docs:** BRIGHTSKY_PATHLY_ASSESSMENT.md · BRIGHTSKY_PATHLY_INTEGRATION_SPEC.md

---

## System map — one page

```
┌─────────────────────────────────────────────────────────────────────┐
│  PATHLY STUDIO (Electron)                                           │
│                                                                     │
│  ┌──────────────────┐    ┌─────────────────────────────────────┐   │
│  │  Renderer        │    │  Main Process                       │   │
│  │  (Chromium)      │    │  (Node.js)                          │   │
│  │                  │    │                                     │   │
│  │  [B1] ChatPanel  │    │  [B4] automation.ts IPC             │   │
│  │   └ thinkingLabel│    │   └ executeStep handler             │   │
│  │   └ tool status  │    │                                     │   │
│  │                  │    │  [B5] fsm.ts IPC                    │   │
│  │  [B2] brightsky  │IPC │   └ fsm:ping / fsm:state            │   │
│  │      Client.ts   │◄──►│                                     │   │
│  │   └ tool_call ✗  │    │  [B5] fs.ts IPC                     │   │
│  │   └ typing_meta ✗│    │   └ fs:read (plan files)            │   │
│  │   └ context fwd ✗│    │                                     │   │
│  │   └ handshake  ✗ │    │  fs.ts / fsm.ts / automation.ts    │   │
│  │                  │    │  all already exposed via preload ✓  │   │
│  │  [B3] Playwright │    │                                     │   │
│  │      Executor    │    │                                     │   │
│  │   └ navigate ✗   │    │                                     │   │
│  │   └ React fill ✗ │    │                                     │   │
│  │                  │    │                                     │   │
│  │  [B6] data-label │    │                                     │   │
│  │      on all UI   │    │                                     │   │
│  └──────────────────┘    └─────────────────────────────────────┘   │
│              │                          ▲                           │
│         WebSocket                   IPC Bridge                      │
│              │                          │                           │
└──────────────┼──────────────────────────┼───────────────────────── ┘
               │ WebSocket (port 3002)    │ (window.pathly.*)
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  BRIGHTSKY BACKEND (NestJS)                                      │
│                                                                  │
│  [B7] UnifiedChatGateway         ← route on source field        │
│   └ client_capabilities handler  ← NEW                          │
│   └ pathly-studio → PathlyRouter ← NEW                          │
│                                                                  │
│  [B8] PathlyModule               ← NEW NestJS module            │
│   └ PathlyContextBuilder         ← system prompt from appContext │
│   └ PathlyRouterService          ← agent selection              │
│   └ PathlySessionService         ← session state                │
│                                                                  │
│  [B9] ToolRegistry               ← add StudioAnalyzer tools     │
│   └ studio.get_fsm_state         ← sends tool_call to Studio    │
│   └ studio.get_feature_plan      ← sends tool_call to Studio    │
│   └ studio.automation.executeStep← sends tool_call to Studio    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
               ▲
               │
┌──────────────┴───────────────────────────────────────────────────┐
│  CHROME EXTENSION (existing, unchanged in this phase)            │
└──────────────────────────────────────────────────────────────────┘
```

Legend: ✗ = missing · ✓ = already exists

---

## Frontend blocks (Pathly Studio)

### B1 — ChatPanel UI additions
**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx`  
**Store:** `studio/src/renderer/src/store/brightskyStore.ts`

What to add:
- `thinkingLabel: string | null` field to `brightskyStore`
- A status bar in ChatPanel that shows `thinkingLabel` while it's set, hides when streaming starts
- A tool-call status row: "Using tool: get_feature_plan…" while backend waits for tool_response
- Citation renderer for `agent_response.metadata.sources` (list of title + url chips)

**Why it matters:**  
Right now the user sees silence while Brightsky thinks. Adding `thinkingLabel` turns "Analyzing your plan…" or "Searching the web…" into visible feedback. The backend already sends `typing_metadata` — Studio just ignores it today.

---

### B2 — BrightskyClient.ts — four additions
**File:** `studio/src/renderer/src/lib/brightskyClient.ts`

#### B2a — `tool_call` handler in `ws.onmessage`
```ts
} else if (type === 'tool_call') {
  const { callId, toolName, parameters } = data as ToolCallMessage
  try {
    const result = await window.pathly.automation.executeStep(parameters)
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
  }
}
```
`window.pathly.automation.executeStep` is **already exposed** in preload (line 88). This is one code block away.

#### B2b — `typing_metadata` handler in `ws.onmessage`
```ts
} else if (type === 'typing_metadata') {
  const label = (data.label as string) ?? null
  useBrightskyStore.getState().setThinkingLabel(label)
}
// also clear it at stream_end / stream_chunk start
```

#### B2c — Context forwarding in `sendMessage`
Replace the bare `user_message` with the full envelope:
```ts
const pathlyCtx = await collectPathlyContext()   // reads FSM + plan files via IPC

this.ws?.send(JSON.stringify({
  type: sessionId === null ? 'create_session_with_message' : 'user_message',
  requestId: crypto.randomUUID(),
  sessionId: sessionId ?? undefined,
  content,
  messageType: 'pathly_chat',
  context: {
    source: 'pathly-studio',
    appContext: pathlyCtx          // stage, feature, plan summary, skills
  },
  capabilities: {
    canAnalyzeDom: false,
    canExecuteToolCalls: true,     // PlaywrightExecutor is ready
    canStreamThinking: true,
    supportedToolTypes: ['studio_analyzer', 'automation']
  }
}))
```

#### B2d — Capability handshake after `session_created`
```ts
if (type === 'session_created') {
  // ... existing sessionId extraction ...
  this.ws?.send(JSON.stringify({
    type: 'client_capabilities',
    source: 'pathly-studio',
    capabilities: { canExecuteToolCalls: true, canStreamThinking: true },
    version: '1.0'
  }))
}
```

#### B2e — Reconnect with backoff in `ws.onclose`
```ts
if (!this.intentionalDisconnect) {
  const delays = [1000, 2000, 4000, 8000, 16000]
  const attempt = this.reconnectAttempts++
  if (attempt < delays.length) {
    setTimeout(() => this.connect(wsUrl, accessToken), delays[attempt])
  }
}
```

**What B2 affects:**  
This is the central wire. Every other block depends on B2 being complete. Once B2 is done the backend can talk to the Studio and the Studio can talk back.

---

### B3 — PlaywrightExecutor — two fixes
**File:** `studio/src/main/automation/playwrightExecutor.ts`

#### B3a — React-compatible `fill`
The current `fill` sets `el.value = value` directly. React controlled inputs ignore this because React manages their state internally. Replace with the native setter approach:
```ts
case 'fill':
  await this.evalInPage(`
    (() => {
      const el = document.querySelector(${escaped});
      if (!el) return;
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
      ).set;
      nativeSetter.call(el, ${value});
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    })()
  `)
```

#### B3b — Implement `navigate`
Currently throws. Replace with panel navigation via Zustand:
```ts
case 'navigate':
  // step.value = panel name: 'monitor' | 'chat' | 'files' | 'terminal'
  await this.evalInPage(`
    window.__pathlyNavigate(${JSON.stringify(step.value ?? '')})
  `)
```
Register `window.__pathlyNavigate` in the renderer root — it calls the navigation Zustand store action.

**What B3 affects:**  
Without B3a, `fill` silently fails on any React controlled input (feature name wizard, chat input, etc.). Without B3b, the AI cannot switch panels. Both are needed for the wizard flow.

---

### B4 — StudioAnalyzer tools (renderer side)
**New file:** `studio/src/renderer/src/lib/studioAnalyzer.ts`

These are the local tool implementations the backend can request via `tool_call`. They use existing IPC channels — no new IPC handlers needed.

```ts
export const studioTools: Record<string, (params: unknown) => Promise<unknown>> = {

  'get_fsm_state': async () => {
    const state = await window.pathly.fsm.state(activeFeature)
    return { stage: state.stage, feature: state.topic, rigor: state.rigor }
  },

  'get_feature_plan': async ({ sections }) => {
    const base = `${projectPath}/pathly/plans/${activeFeature}`
    const stories   = await window.pathly.fs.read(`${base}/USER_STORIES.md`)
    const implPlan  = await window.pathly.fs.read(`${base}/IMPLEMENTATION_PLAN.md`)
    const progress  = await window.pathly.fs.read(`${base}/PROGRESS.md`)
    return { stories, implPlan, progress }
  },

  'get_available_skills': async () => {
    // reads from pathly_data context already loaded in store
    return { skills: usePathlyStore.getState().availableSkills }
  },

  'get_studio_schema': async () => {
    return {
      openPanels: useLayoutStore.getState().openPanels,
      selectedTab: useLayoutStore.getState().activeTab,
    }
  },

  'automation:executeStep': async (params) => {
    return window.pathly.automation.executeStep(params)
  }
}
```

Update B2's `tool_call` handler to route through this registry:
```ts
const handler = studioTools[toolName]
if (handler) {
  const result = await handler(parameters)
  // send tool_response ...
}
```

**What B4 affects:**  
This is what gives the AI workspace intelligence. With these tools the backend goes from generic chat to "you're in BUILD stage, next story is S-04, here's the implementation plan."

---

### B5 — context collector
**New file:** `studio/src/renderer/src/lib/pathlyContextCollector.ts`

Collects the `appContext` object to attach to every outbound message. Uses existing IPC:

```ts
export async function collectPathlyContext(): Promise<AppContext> {
  const projectPath  = useWorkspaceStore.getState().projectPath
  const activeFeature = useWorkspaceStore.getState().activeTopic

  if (!activeFeature) return { source: 'pathly-studio', projectPath }

  const fsmState = await window.pathly.fsm.state(activeFeature)
  const base     = `${projectPath}/pathly/plans/${activeFeature}`

  // Read plan files but trim to stay within token budget
  const stories  = await safeRead(`${base}/USER_STORIES.md`, 2000)
  const progress = await safeRead(`${base}/PROGRESS.md`, 500)

  return {
    source: 'pathly-studio',
    projectPath,
    appContext: {
      activeFeature,
      fsmStage:             fsmState?.stage,
      activeConversation:   fsmState?.conversationIndex,
      totalConversations:   fsmState?.totalConversations,
      nextUncompletedStory: parseNextTodo(progress),
      userStoriesSummary:   stories,
    }
  }
}
```

**What B5 affects:**  
Every message sent to Brightsky will carry workspace context from this point on. The backend immediately has what it needs to build a Pathly-aware system prompt without any backend work being required first.

---

### B6 — `data-label` on interactive components

Every button, input, select, and nav item that the AI should be able to control needs a `data-label` attribute matching what a human would call it.

**Priority order:**

| Component | Label examples |
|---|---|
| New Feature wizard — name input | `data-label="Feature Name"` |
| New Feature wizard — rigor selector | `data-label="Rigor Level"` |
| New Feature wizard — confirm button | `data-label="Create Feature"` |
| ChatPanel send button | `data-label="Send Message"` |
| ChatPanel input | `data-label="Chat Input"` |
| Model selector | `data-label="Model Selector"` |
| Nav: Monitor panel | `data-label="Monitor"` |
| Nav: Chat panel | `data-label="Chat"` |
| Nav: Files panel | `data-label="Files"` |
| Advance stage button | `data-label="Next Stage"` |

Without `data-label`, Tier 1 resolution falls through to Tier 2 (fuzzy) which is less reliable. Tier 1 is instant and exact — it's the right target.

**What B6 affects:**  
Everything the AI can click or fill. Without labels, automation works unreliably. With labels, it's rock solid.

---

## Backend blocks (Brightsky NestJS)

### B7 — UnifiedChatGateway — routing update
**File:** `backend/src/chat/gateways/core/unified-chat.gateway.ts`

Two changes:

#### B7a — Handle `client_capabilities`
```ts
case 'client_capabilities':
  await this.sessionService.storeCapabilities(client.sessionId, message.capabilities)
  break
```

#### B7b — Route `pathly-studio` source
```ts
// Existing routing:
if (messageType === 'page_research') → PageResearchStrategy
if (messageType === 'workflow_generate') → WorkflowStrategy

// Add:
if (context?.source === 'pathly-studio' || messageType === 'pathly_chat') {
  return this.pathlyRouter.handle(client, message)
}
```

**What B7 affects:**  
Without this, all Pathly messages fall through to the generic chat handler with no workspace awareness. This is the routing gate.

---

### B8 — PathlyModule (new NestJS module)
**New directory:** `backend/src/pathly/`

**`pathly-context-builder.service.ts`** — builds the system prompt:
```ts
build(appContext: AppContext): string {
  return `
You are an AI coding assistant in Pathly Studio.

Active feature: ${appContext.activeFeature}
Pipeline stage: ${appContext.fsmStage}
Conversation: ${appContext.activeConversation} of ${appContext.totalConversations}

Next task: ${appContext.nextUncompletedStory}

Acceptance criteria:
${appContext.userStoriesSummary}

${capabilities.canExecuteToolCalls ? `
Available tools:
- get_fsm_state: check current pipeline stage
- get_feature_plan: read full plan files  
- automation:executeStep: click or fill any Studio UI element
` : ''}
`
}
```

**`pathly-router.service.ts`** — selects agent:
```ts
handle(client, message) {
  const systemPrompt = this.contextBuilder.build(message.context.appContext)
  const caps = this.sessionService.getCapabilities(client.sessionId)

  const tools = caps?.canExecuteToolCalls
    ? this.toolRegistry.getStudioTools()
    : []

  return this.chatAgent.run({ systemPrompt, message, tools })
}
```

**What B8 affects:**  
This transforms Brightsky from a generic chat backend into a Pathly-aware agent. The system prompt built here is what makes answers plan-specific instead of generic.

---

### B9 — ToolRegistry — StudioAnalyzer tools
**File:** `backend/src/mcp/tool-registry.ts`

Register three bridge tools that use the existing `PageAnalyzerBridgeTool` pattern (already used by Chrome extension tools):

```ts
// These send tool_call to Studio and wait for tool_response
registry.register('studio.get_fsm_state', new StudioBridgeTool('get_fsm_state'))
registry.register('studio.get_feature_plan', new StudioBridgeTool('get_feature_plan'))
registry.register('studio.automation.executeStep', new StudioBridgeTool('automation:executeStep'))
```

`StudioBridgeTool` is identical to `PageAnalyzerBridgeTool` — only the `clientType` filter changes from `chrome-extension` to `pathly-studio`.

**What B9 affects:**  
Without this, the backend cannot query Studio state on demand. With it, the agent can call `get_feature_plan` mid-conversation and read the actual plan files rather than relying on what the user included in the message context.

---

## The wire — how the blocks connect

```
User types message in ChatPanel
  │
  ▼
[B5] collectPathlyContext()
  reads FSM state via window.pathly.fsm.state()
  reads plan files via window.pathly.fs.read()
  builds appContext object
  │
  ▼
[B2c] sendMessage() attaches appContext + capabilities
  sends enriched user_message over WebSocket
  │
  ▼ (WebSocket)
[B7b] UnifiedChatGateway routes source=pathly-studio
  │
  ▼
[B8] PathlyContextBuilder builds system prompt
  │
  ▼
ChatAgent runs with workspace-aware system prompt
  │
  ├──▶ needs more info? calls [B9] StudioBridgeTool
  │      │
  │      ▼ (WebSocket tool_call)
  │    [B2a] brightskyClient receives tool_call
  │      │
  │      ▼
  │    [B4] studioAnalyzer routes to handler
  │      reads FSM/plan/schema via existing IPC
  │      OR calls [B3] PlaywrightExecutor for UI actions
  │      │
  │      ▼ (WebSocket tool_response)
  │    Agent receives result, continues
  │
  ├──▶ thinking? sends typing_metadata
  │      │
  │      ▼ (WebSocket)
  │    [B2b] → brightskyStore.thinkingLabel = "Analyzing plan…"
  │    [B1]  → ChatPanel shows status bar
  │
  └──▶ streams answer
       [B2] stream_chunk → updateLastMessage (already works)
       [B1] thinkingLabel clears, message appears
```

---

## Build order — what unlocks what

```
Phase 1 — Backend gets context, Studio gets feedback (3 days, no backend changes needed)
  B5  context collector          ← standalone, no deps
  B2c attach context to send     ← needs B5
  B2b typing_metadata handler    ← standalone
  B1  thinking indicator in UI   ← needs B2b store change
  B2d capability handshake       ← standalone
  B2e reconnect with backoff     ← standalone

  After Phase 1: backend is workspace-aware on every message.
  Brightsky shows "Analyzing…" status. No backend code written yet.

Phase 2 — Backend routes Pathly properly (3-4 days, backend work)
  B7  gateway routing update     ← backend, standalone
  B8  PathlyModule + context builder ← needs B7
  
  After Phase 2: Brightsky gives plan-aware answers.
  "What next?" → returns actual next story from USER_STORIES.md.

Phase 3 — Tool bridge: AI can query and act on Studio (4-5 days)
  B3a React fill fix             ← standalone, small
  B3b navigate action            ← standalone, small
  B6  data-label on components   ← systematic, component by component
  B4  studioAnalyzer registry    ← needs B3
  B2a tool_call handler          ← needs B4
  B9  backend ToolRegistry tools ← needs B7/B8

  After Phase 3: AI can read plan files on demand, click wizard buttons,
  fill inputs, advance the FSM stage — all triggered by conversation.
```

---

## What stays unchanged

| Item | Why untouched |
|---|---|
| Chrome extension | Different client, same backend — no changes needed |
| `brightskyClient.connect()` | Transport works, only message handling changes |
| `PlaywrightExecutor` tier 1/2 resolution | Already correct — only performAction changes |
| FSM HTTP server | Already running, already correct |
| `window.pathly.automation.executeStep` | Already exposed in preload |
| `window.pathly.fsm.*` | Already exposed in preload |
| `window.pathly.fs.*` | Already exposed in preload |
| Auth + token refresh | Already working |
| Streaming display | Already working |

The IPC bridge is already fully built. The automation executor is already built. The WebSocket transport is already built. What's missing is the message content going through the wire and the backend knowing what to do with it.
