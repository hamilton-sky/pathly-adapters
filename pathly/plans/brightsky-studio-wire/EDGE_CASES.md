# Edge Cases — brightsky-studio-wire

---

## Conv 1 edge cases

### EC-01 — WebSocket disconnects mid-stream

**Scenario:** The backend is actively streaming `stream_chunk` messages when the WebSocket closes.

**What happens today (without fix):** `ws.onclose` fires while the streaming message buffer is incomplete. The ChatPanel may display a partial message with no visual indication that it was cut off.

**Required behavior:**
- `brightskyClient.ts` `ws.onclose` handler detects that `streamingMessageId` is non-null (a stream was in progress).
- The store method that finalizes streaming is called immediately with a `[connection lost]` suffix appended to whatever partial content was received.
- The thinking indicator (`thinkingLabel`) is cleared to null so no stale label persists.
- The reconnect backoff sequence starts (EC-02 governs reconnect).
- The user sees the partial message, clearly terminated, and a status message indicating the connection dropped.

**What NOT to do:** Do not silently swallow `ws.onclose` while streaming. Do not leave `thinkingLabel` set to a stale value after disconnect.

---

### EC-02 — Reconnect race: session_created arrives, then disconnect fires before handshake completes

**Scenario:** `session_created` arrives, the client begins sending the `client_capabilities` handshake, but the socket closes in the same tick (flap).

**Required behavior:**
- The `session_created` handler checks `ws.readyState === WebSocket.OPEN` before sending `client_capabilities`.
- If the socket is already closing/closed, the handshake is skipped — it will be sent fresh after the reconnect establishes a new session.
- The `intentionalDisconnect` flag is false; reconnect backoff starts normally.

---

### EC-03 — Capability handshake sent to old backend that does not recognise `client_capabilities` message type

**Scenario:** The backend is a version that predates PathlyModule. It receives `{ type: 'client_capabilities', ... }` and either ignores it or responds with an error frame.

**Required behavior:**
- The Studio client treats `client_capabilities` as fire-and-forget. No response is expected and none is awaited.
- If the backend sends back an error frame (e.g. `{ type: 'error', code: 'unknown_message_type' }`), the existing error handler logs it and does nothing else — it does not crash the session.
- The `canExecuteToolCalls` flag declared in the handshake is `false` in Conv 1, so the backend skipping tool setup has no effect.

**What NOT to do:** Do not `await` a response to the handshake. Do not gate any session behavior on the backend acknowledging it.

---

### EC-04 — Context forwarding when no active feature

**Scenario:** `pathlyContextCollector.collectPathlyContext()` is called but `window.pathly.fsm.state()` returns null (no feature is active in the workspace).

**Required behavior:**
- `collectPathlyContext()` catches the null return and produces a minimal appContext: `{ source: 'pathly-studio', projectPath }`.
- `activeFeature`, `fsmStage`, `nextUncompletedStory`, and `userStoriesSummary` are omitted entirely from the object (not present as `null` or `undefined` keys).
- The outbound `user_message` envelope is still sent normally — only the appContext fields differ.
- No error is thrown. No error toast is shown to the user.

**Story reference:** S-02 acceptance criterion: "If no active feature is set, appContext is sent as `{ source: 'pathly-studio', projectPath }` (no error thrown)."

---

### EC-04b — fsm.state called with null or empty activeTopic crashes the FSM server

**Scenario:** `pathlyContextCollector.ts` calls `window.pathly.fsm.state(activeTopic)` but `activeTopic` is `null`, `undefined`, or `""`. The IPC handler calls `http://127.0.0.1:8765/next_action` with an empty topic, which the FSM server does not handle gracefully.

**Required behavior:**
- `collectPathlyContext()` checks `activeTopic` for null/undefined/empty string **before** calling `window.pathly.fsm.state()`.
- If the guard fails: return `{ source: 'pathly-studio', projectPath }` immediately without calling the FSM.
- This guard is distinct from EC-04 (which handles a valid call that returns null). This guard prevents the call entirely.
- Implementation:
  ```ts
  const { projectPath, activeTopic } = useWorkspaceStore.getState()
  if (!activeTopic) {
    return { source: 'pathly-studio', projectPath }
  }
  const fsmState = await window.pathly.fsm.state(activeTopic)
  ```

---

### EC-05 — pathlyContextCollector reads plan files that are missing or empty

**Scenario:** A feature was just created. The plan directory exists but `USER_STORIES.md` and/or `PROGRESS.md` have not been written yet (0 bytes or file-not-found).

**Required behavior:**
- `safeRead(path, maxChars)` catches file-not-found errors (IPC returns null or throws) and returns an empty string `""`.
- `parseNextTodo("")` returns `""` — no crash on empty input.
- `userStoriesSummary` is set to `""` — the field is included in the context object but its value is an empty string.
- The backend receives a valid context object with empty plan fields. PathlyContextBuilder handles empty fields without crashing — it omits those sections from the system prompt.

---

### EC-06 — Brightsky `session_created` message is delayed

**Scenario:** The user opens the chat panel and types a message before `session_created` has arrived (WebSocket connected but session not yet established).

**Required behavior:**
- `brightskyClient.sendMessage()` checks that `sessionId` is non-null before sending.
- If `sessionId` is null, the message is queued in a `pendingMessages: string[]` array on the client instance.
- When `session_created` arrives, the client drains the pending queue in order, sending each message.
- The user sees no error. The message appears to send normally once the session is established.
- Queue depth: maximum 10 messages. If the queue is full and the session has not arrived within 30 seconds, the pending messages are dropped and a status message is shown: "Session could not be established."

---

### EC-07 — Token expiry during a tool_call round-trip

**Scenario:** The backend sends a `tool_call` message. While the Studio is executing the tool and preparing the `tool_response`, the OAuth token expires and the WebSocket reconnects (new session).

**What happens:** The pending `callId` from the original session is no longer valid on the new session. Sending `tool_response` with the old `callId` over the new socket will either be ignored by the backend or produce a stale-call error.

**Required behavior:**
- When `ws.onclose` fires and `pendingToolCalls: Map<callId, ...>` is non-empty, each pending call is abandoned.
- For each abandoned call, the renderer logs a warning: `[studioAnalyzer] tool call <callId> abandoned — session reset`.
- The `toolCallInProgress` store state is cleared to null.
- The ChatPanel tool-call status row is hidden.
- No `tool_response` is sent on the new session for the stale `callId`.
- The backend's `StudioBridgeTool` has its own timeout (see EC-08). When it fires, it sends a `{ success: false, error: 'timeout' }` synthetic result to the agent so the agent can recover gracefully.

---

## Conv 2 edge cases

### EC-07b — AppContext fields arrive as undefined on the backend

**Scenario:** Studio sends a message where `context.appContext.activeFeature` or other fields are `undefined` because the collector returned a minimal context (no active feature). `PathlyContextBuilderService.build()` receives a partially populated AppContext and tries to use `${appContext?.appContext?.activeFeature}` in a template string, producing `"undefined"` literal in the system prompt.

**Required behavior:**
- `PathlyContextBuilderService.build()` checks each field with a fallback:
  ```ts
  const feature = appContext?.appContext?.activeFeature ?? '(no active feature)'
  const stage   = appContext?.appContext?.fsmStage ?? '(unknown stage)'
  ```
- Template sections that depend on a missing field are omitted entirely, not rendered as `"undefined"`.
- If `appContext` itself is null/undefined, `build()` returns the generic fallback prompt (not an error).
- The `AppContext` and `ClientCapabilities` types live in `backend/src/pathly/types.ts` — no `any` types are used in PathlyModule services.

---

### EC-08 — tool_call timeout: backend sends tool_call but Studio never responds

**Scenario:** The backend's `StudioBridgeTool` sends a `tool_call` WebSocket message but the Studio client crashes, loses connection, or is stuck before sending `tool_response`.

**What the backend must do:**
- `StudioBridgeTool` sets a timeout of **15 seconds** after sending the `tool_call`.
- If no `tool_response` with the matching `callId` arrives within 15 seconds, the tool resolves with `{ success: false, error: 'Studio tool call timed out after 15s', callId }`.
- The agent receives the timeout error as the tool result and can decide whether to retry, ask the user, or continue without the data.
- The timeout is cancelled if a `tool_response` arrives within the window.

**What the Studio should show:**
- The tool-call status row remains visible ("Using tool: [toolName]…") until a `tool_response` is sent or the session resets (EC-07).
- If the socket reconnects and no tool_response was sent, the status row is cleared (EC-07 governs this).

---

### EC-09 — `client_capabilities` received by backend running a version that predates PathlyModule

**Scenario:** Same as EC-03 from the Studio side, but described from the backend perspective.

**Required behavior:**
- If `PathlySessionService` is not registered (old backend), the `UnifiedChatGateway` message handler has no branch for `type === 'client_capabilities'` and falls through to the default/unknown handler.
- The default handler logs an unknown message type warning and does nothing.
- The session continues. The Studio receives no error frame for this.
- This is a safe degradation: the backend simply treats the Studio as a generic chat client.

---

## Conv 3 edge cases

### EC-10 — tool_call arrives with unrecognised toolName in studioAnalyzer registry

**Scenario:** The backend sends `{ type: 'tool_call', callId: 'abc', toolName: 'studio.do_something_new', parameters: {} }`. The `studioTools` map in `studioAnalyzer.ts` has no key for `'studio.do_something_new'`.

**Required behavior:**
- `executeStudioTool()` checks `toolName` against the registry before calling.
- If not found, it does not throw — it returns `{ success: false, error: 'Unknown tool: studio.do_something_new' }`.
- `brightskyClient.ts` sends `{ type: 'tool_response', callId: 'abc', payload: { success: false, error: 'Unknown tool: studio.do_something_new' } }`.
- The backend agent receives the error as the tool result and handles it (log + continue).
- No unhandled promise rejection occurs in the renderer.

---

### EC-11 — React fill on a component that is not mounted or is off-screen

**Scenario:** `automation:executeStep` with `action: 'fill'` and `label: 'New Plan Name'` is called, but the `InlineCreateInput` is not currently visible in the Sidebar (the user hasn't clicked "New Plan Folder" yet, so the input hasn't been rendered).

**Required behavior:**
- `playwrightExecutor.ts` `fill` action resolves the selector via tier 1/2/3 resolution.
- If no element is found, the action returns `{ success: false, error: 'Element not found: New Plan Name' }`.
- The `tool_response` carries this error. The backend agent receives it and can decide to first click "New Plan Folder" (using `{ action: 'click', label: 'New Plan Folder' }`) to open the input, then retry the fill.
- No exception propagates to the IPC handler. The IPC handler always returns a structured response.

**Note:** Elements that exist in the DOM but are scrolled off-screen are still reachable via `querySelector` — this is not a failure case. Only truly unmounted components (not in the DOM at all) trigger the "not found" path.

---

### EC-12 — navigate action targets a panel that does not exist or is already active

**Scenario A — Unknown panel name:** `automation:executeStep` is called with `{ action: 'navigate', value: 'dashboard' }`. `'dashboard'` is not a valid panel name.

**Required behavior:**
- `window.__pathlyNavigate('dashboard')` is called via `evalInPage`.
- The renderer-side `__pathlyNavigate` implementation checks the value against the known set: `['monitor', 'chat', 'files', 'terminal']`.
- If not in the set, it throws `new Error('Unknown panel: dashboard')`.
- `evalInPage` propagates the error to the IPC handler, which returns `{ success: false, error: 'Unknown panel: dashboard' }`.
- The `tool_response` carries this error.

**Scenario B — Panel already active:** The `navigate` action is called for the panel that is already visible.

**Required behavior:**
- `useLayoutStore.getState().setActivePanel(panelName)` is called unconditionally.
- Setting the already-active panel to itself is idempotent — no visual flicker, no error.
- `tool_response` is `{ success: true }`.

---

### EC-13 — studioAnalyzer `get_feature_plan` called for a feature with no plan directory

**Scenario:** `get_feature_plan` is called. `window.pathly.fs.read()` is called for `USER_STORIES.md`, but the file path resolves to a directory that does not exist.

**Required behavior:**
- Each `window.pathly.fs.read()` call is wrapped individually in try/catch inside `get_feature_plan`.
- Files that cannot be read return `""` for that field.
- The tool returns `{ userStories: "", implementationPlan: "", progress: "", success: true }`.
- This is considered a successful (non-error) tool result — the content is simply empty.
- The backend agent receives the empty content and can inform the user that no plan has been written yet.

---

### EC-14 — `get_studio_schema` called when layout store has not been initialised

**Scenario:** `studioAnalyzer` calls `get_studio_schema` before the Zustand `layoutStore` has been populated (app still initialising).

**Required behavior:**
- `get_studio_schema` reads the store state with `useLayoutStore.getState()`. Zustand stores always return their initial state even before any action has run.
- The initial state must define sensible defaults for `openPanels` (empty array or default panel list) and `activeTab` (a string, possibly `''`).
- The tool returns the initial state values without error.
- No null-pointer exception occurs accessing store state.
