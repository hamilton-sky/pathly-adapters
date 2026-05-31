# User Stories — brightsky-studio-wire

---

### S-01 — Typing metadata thinking indicator

**As a** Pathly Studio user
**I want** to see a labeled thinking indicator ("Analyzing your plan…") while the Brightsky backend is processing
**So that** I know the AI is working and what phase it is in, rather than seeing silence

**Acceptance criteria:**
- [ ] When the WebSocket receives `{ type: 'typing_metadata', label: '...' }`, the ChatPanel displays the label text in a visible status bar
- [ ] The thinking indicator is hidden when the first `stream_chunk` arrives
- [ ] The thinking indicator is hidden when `stream_end` arrives
- [ ] `brightskyStore` has a `thinkingLabel: string | null` field and `setThinkingLabel(label)` setter
- [ ] When `thinkingLabel` is non-null the ChatPanel renders it above the streaming area
- [ ] Setting `thinkingLabel` to null hides the indicator (no empty bar shown)

**Delivered in:** Conv 1

---

### S-02 — Context forwarding on every outbound message

**As a** Pathly Studio user
**I want** every message I send to carry the active feature name, FSM stage, and plan summary
**So that** Brightsky answers are grounded in what I am actually building right now

**Acceptance criteria:**
- [ ] Every `user_message` sent over WebSocket includes `context.source: 'pathly-studio'`
- [ ] Every `user_message` includes `context.appContext.activeFeature` (from FSM state)
- [ ] Every `user_message` includes `context.appContext.fsmStage` (from FSM state)
- [ ] Every `user_message` includes `context.appContext.nextUncompletedStory` (parsed from PROGRESS.md)
- [ ] Every `user_message` includes `context.appContext.userStoriesSummary` (trimmed to ≤ 2000 tokens)
- [ ] Every `user_message` includes `messageType: 'pathly_chat'`
- [ ] Every `user_message` includes `capabilities: { canExecuteToolCalls, canStreamThinking, supportedToolTypes }`
- [ ] If no active feature is set, `appContext` is sent as `{ source: 'pathly-studio', projectPath }` (no error thrown)
- [ ] `pathlyContextCollector.ts` is the single function responsible for building the appContext object
- [ ] Total injected context from plan files does not exceed 4000 tokens

**Delivered in:** Conv 1

---

### S-03 — Capability handshake on connect

**As a** Pathly Studio user
**I want** the Studio to announce its capabilities to the Brightsky backend immediately after connecting
**So that** the backend knows which tool types it can call and adapts its behavior accordingly

**Acceptance criteria:**
- [ ] After `session_created` is received, the client sends a `client_capabilities` message over WebSocket
- [ ] The `client_capabilities` message includes `type: 'client_capabilities'`, `source: 'pathly-studio'`, `version: '1.0'`
- [ ] After Conv 3 the handshake declares `canExecuteToolCalls: true`, `canStreamThinking: true`, and `supportedToolTypes: ['studio_analyzer', 'automation']`
- [ ] The handshake is sent exactly once per session (not repeated on subsequent messages)
- [ ] The handshake does not block or delay the session creation confirmation in the UI

**Delivered in:** Conv 1

---

### S-04 — Reconnect with exponential backoff

**As a** Pathly Studio user
**I want** the Studio to automatically reconnect to Brightsky after a network disconnect
**So that** I do not need to restart the app or manually reconnect when the connection drops

**Acceptance criteria:**
- [ ] When `ws.onclose` fires and the disconnect was not intentional, a reconnect is scheduled
- [ ] Reconnect attempts use delays of 1s, 2s, 4s, 8s, 16s (five attempts maximum)
- [ ] After 5 failed attempts, reconnect stops and the auth error state is set
- [ ] An intentional disconnect (user-initiated logout or explicit close) does not trigger reconnect
- [ ] `reconnectAttempts` counter is tracked on the client instance
- [ ] On a successful reconnect the session continues (sessionId restored from store)

**Delivered in:** Conv 1

---

### S-05 — Backend returns plan-aware answers (PathlyModule)

**As a** Pathly Studio user
**I want** Brightsky to answer questions about my plan using the actual USER_STORIES.md and IMPLEMENTATION_PLAN.md contents
**So that** when I ask "what should I do next?" the answer references real stories not generic advice

**Acceptance criteria:**
- [ ] A new NestJS module `PathlyModule` exists at `backend/src/pathly/`
- [ ] `PathlyContextBuilder.build(appContext)` produces a system prompt containing `activeFeature`, `fsmStage`, `nextUncompletedStory`, and `userStoriesSummary`
- [ ] `UnifiedChatGateway` routes messages with `context.source === 'pathly-studio'` to `PathlyRouterService`
- [ ] `UnifiedChatGateway` handles `type: 'client_capabilities'` and stores capabilities in session
- [ ] `PathlyRouterService.handle()` builds the system prompt and passes it to the existing ChatAgent
- [ ] Generic chat behavior (no `appContext`) is unchanged — existing tests still pass
- [ ] Asking "what should I do next?" returns a response that names the active feature and its current stage

**Delivered in:** Conv 2

---

### S-06 — tool_call round-trip (StudioAnalyzer)

**As a** Pathly Studio user
**I want** the Brightsky backend to be able to query my workspace state (FSM stage, plan files) mid-conversation
**So that** the AI can read up-to-date plan information instead of relying only on what was included in the initial message

**Acceptance criteria:**
- [ ] `brightskyClient.ts` handles `{ type: 'tool_call', callId, toolName, parameters }` messages
- [ ] The handler routes to `studioAnalyzer.ts` tool registry by `toolName`
- [ ] A successful tool call sends `{ type: 'tool_response', callId, payload: { result, success: true } }` back over WebSocket
- [ ] A failed tool call sends `{ type: 'tool_response', callId, payload: { success: false, error: '...' } }` back over WebSocket
- [ ] `studioAnalyzer.ts` implements `get_fsm_state`: returns stage, feature, rigor via `window.pathly.fsm.state()`
- [ ] `studioAnalyzer.ts` implements `get_feature_plan`: returns USER_STORIES.md, IMPLEMENTATION_PLAN.md, PROGRESS.md via `window.pathly.fs.read()`
- [ ] `studioAnalyzer.ts` implements `get_studio_schema`: returns open panels and active tab from Zustand stores
- [ ] `studioAnalyzer.ts` implements `automation:executeStep`: delegates to `window.pathly.automation.executeStep()`
- [ ] Backend `ToolRegistry` registers `studio.get_fsm_state`, `studio.get_feature_plan`, `studio.automation.executeStep` using `StudioBridgeTool`
- [ ] ChatPanel shows "Using tool: [toolName]…" while a tool call is in progress

**Delivered in:** Conv 3

---

### S-07 — AI can create a new feature plan via automation:executeStep tool call

**As a** Pathly Studio user
**I want** the AI to be able to click "New plan folder" and type a feature name into the inline input on my behalf
**So that** I can say "create a feature called payment-integration" and the AI creates the plan directory

> **Note:** Feature plans are created via Sidebar → PlanSection → "New plan folder" button → `InlineCreateInput`.
> This is NOT the FlowWizard (that is for flow.yaml definitions) and NOT `NewItemDialog` (that creates library items).

**Acceptance criteria:**
- [ ] A `tool_call` of type `automation:executeStep` with `{ action: 'click', label: 'New Plan Folder' }` opens the inline plan name input in the Sidebar
- [ ] A `tool_call` of type `automation:executeStep` with `{ action: 'fill', label: 'New Plan Name', value: 'payment-integration' }` fills the inline input
- [ ] The fill action uses the native setter approach so the React controlled input registers the change
- [ ] The automation step sends a `tool_response` with `{ success: true }` after execution
- [ ] If the target element is not found the response is `{ success: false, error: 'Element not found: [label]' }`

**Delivered in:** Conv 3

---

### S-08 — data-label on all interactive components

**As a** Pathly Studio user
**I want** every interactive wizard input, form field, button, and navigation item to have a `data-label` attribute
**So that** the AI's Tier 1 element resolver can find them instantly without fuzzy matching

**Acceptance criteria:**
- [ ] `sidebar/shared/InlineCreateInput.tsx` — plan name input has `data-label="New Plan Name"` (primary feature-creation target)
- [ ] Sidebar PlanSection "New plan folder" button has `data-label="New Plan Folder"` (what AI clicks to open the input)
- [ ] `FlowWizard/Step1Name.tsx` — flow name input has `data-label="Flow Name"`, description has `data-label="Flow Description"` (flow editing, not feature creation)
- [ ] `FlowWizard` confirm/submit button has `data-label="Create Flow"`
- [ ] `NewItemDialog.tsx` — name, description, subdirectory inputs and confirm button have `data-label` (for library item creation)
- [ ] `ChatPanel/ChatInput.tsx` — message textarea has `data-label="Chat Input"`
- [ ] `ChatPanel` — send button has `data-label="Send Message"`
- [ ] `Editor/ConfigForm.tsx` — name input, description input, and adapter toggle chips have `data-label`
- [ ] Sidebar inline inputs (InlineFolderInput, RenameInput) have `data-label`
- [ ] App-level navigation panels (Monitor, Chat, Files, Terminal) have `data-label` matching panel name
- [ ] No `data-label` value is duplicated on the same page — each label is unique

**Delivered in:** Conv 3

---

### S-09 — React-compatible fill in PlaywrightExecutor

**As a** Pathly Studio user
**I want** the automation fill action to correctly update React controlled inputs
**So that** when the AI fills a form field, the React component state updates and the value persists

**Acceptance criteria:**
- [ ] `playwrightExecutor.ts` fill action uses `Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set` to set the value
- [ ] After setting the value, the fill action dispatches both `input` and `change` events with `bubbles: true`
- [ ] Filling the FlowWizard Feature Name input via `automation:executeStep` results in the input showing the value and the Next button becoming enabled (if applicable)
- [ ] The old direct `el.value =` assignment is removed

**Delivered in:** Conv 3

---

### S-10 — navigate action in PlaywrightExecutor

**As a** Pathly Studio user
**I want** the AI to be able to switch between Studio panels (Monitor, Chat, Files, Terminal) programmatically
**So that** the AI can direct my attention to the relevant panel as part of a workflow

**Acceptance criteria:**
- [ ] `playwrightExecutor.ts` implements a `navigate` action case
- [ ] The navigate action calls `window.__pathlyNavigate(panelName)` via `evalInPage`
- [ ] `window.__pathlyNavigate` is registered in the renderer root and calls the navigation Zustand store action
- [ ] Valid panel names are: `'monitor'`, `'chat'`, `'files'`, `'terminal'`
- [ ] Navigating to `'monitor'` switches the main panel to the Monitor view
- [ ] An invalid panel name results in a `tool_response` with `{ success: false, error: 'Unknown panel: ...' }`

**Delivered in:** Conv 3
