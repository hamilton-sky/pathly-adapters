# User Stories — brightsky-chat-connect

## S-01 — Backend selection persists across restarts
**Delivered by:** Conv 1

As a Studio user,
I want to pick "Brightsky" in the ModelSelector and have that choice survive a Studio restart,
so that I don't have to re-select my preferred backend every session.

**Acceptance criteria:**
- [ ] `modelStore` accepts `'brightsky'` as a valid backend value alongside `'ollama'` and `'llm'`.
- [ ] Selecting Brightsky in ModelSelector updates `modelStore` state immediately.
- [ ] After Studio quits and relaunches, `modelStore.backend` is still `'brightsky'` (persisted via Zustand persist).
- [ ] TypeScript compiles without errors after the `modelStore` change (`tsc --noEmit -p studio/tsconfig.web.json` passes).

---

## S-02 — Google OAuth round-trip via custom protocol
**Delivered by:** Conv 1

As a Studio user,
I want to click "Connect" when Brightsky is selected and complete Google OAuth in my system browser,
so that Studio receives a JWT without ever handling my Google password.

**Acceptance criteria:**
- [ ] Clicking "Connect" invokes `window.pathly.brightsky.login()` which triggers an IPC call to the main process.
- [ ] The main process opens `GET https://[backend]/auth/google` in the system browser (via `shell.openExternal`).
- [ ] The main process registers a local HTTP server (or `app.setAsDefaultProtocolClient`) to capture the `brightsky://auth?code=XXX` callback.
- [ ] The captured code is exchanged via `POST /auth/exchange-code` with body `{ code }` within 60 seconds of callback receipt.
- [ ] On success, `access_token`, `refresh_token`, and `user` fields are received from the backend and forwarded to the renderer via a `brightsky:token` push event.
- [ ] If the user closes the browser before the callback fires, the pending auth times out after 60 seconds and the renderer receives an error event — Studio does not hang indefinitely.
- [ ] Only the focused Studio window claims the `brightsky://` callback; a second open window does not race the exchange.

---

## S-03 — Auth state stored and reflected in UI
**Delivered by:** Conv 1

As a Studio user,
I want the auth dot in ModelSelector to accurately show whether I'm connected to Brightsky,
so that I always know my auth state at a glance without opening settings.

**Acceptance criteria:**
- [ ] `brightskyStore` holds `{ connected, authenticated, accessToken, refreshToken, userId, sessionId, wsUrl, authUrl }`.
- [ ] Tokens are persisted via Zustand `persist` (to localStorage) — not stored as plain environment variables or hardcoded.
- [ ] The auth dot in ModelSelector is green when `brightskyStore.authenticated === true`, and red/grey when false or when `accessToken` is absent.
- [ ] `brightskyStore.authenticated` updates in real time when the `brightsky:token` push event arrives from the main process.
- [ ] After a Studio restart with a stored token, `authenticated` is `true` without requiring a new OAuth flow (token is rehydrated from persist).
- [ ] TypeScript compiles without errors after all store and global type additions.

---

## S-04 — WebSocket connects and streams a first message
**Delivered by:** Conv 2

As a Studio user,
I want to type a message with Brightsky selected and see the response stream in real time,
so that the Brightsky chat experience matches the local LLM streaming experience.

**Acceptance criteria:**
- [ ] `brightskyClient.ts` opens `wss://[wsUrl]/ws` using the native browser WebSocket API when `connect()` is called.
- [ ] The first message from the user emits `{ type: 'create_session_with_message', payload: { userMessage: { content, role: 'user' } } }`.
- [ ] On `session_created` response, `brightskyStore.sessionId` is updated to the returned `metadata.sessionId`.
- [ ] Incoming `stream_chunk` events call `useChatStore.updateLastMessage({ content: prev + chunk })` — no new streaming primitive introduced.
- [ ] The assistant message renders incrementally in the ChatPanel as chunks arrive.
- [ ] `stream_end` finalizes the message (no further appends occur after it).
- [ ] Render cold-start delay (up to 60s) shows a "connecting…" status in the ChatPanel rather than an error state.

---

## S-05 — Follow-up turns reuse the active session
**Delivered by:** Conv 2

As a Studio user,
I want my second and subsequent messages in a conversation to continue the same Brightsky session,
so that the server retains conversation history without me managing session IDs manually.

**Acceptance criteria:**
- [ ] When `brightskyStore.sessionId` is non-null, subsequent user messages emit `{ type: 'user_message', content, sessionId }` (not `create_session_with_message`).
- [ ] `brightskyStore.sessionId` is NOT reset between messages within the same conversation window.
- [ ] Starting a new conversation (new chat button or explicit session clear) resets `sessionId` to null, and the next send emits `create_session_with_message` again.

---

## S-06 — Token auto-refresh without user interruption
**Delivered by:** Conv 2

As a Studio user,
I want my Brightsky JWT to refresh automatically before it expires,
so that long working sessions never break mid-conversation with a forced re-login.

**Acceptance criteria:**
- [ ] `brightskyClient` (or store) checks token expiry before each send; if within a defined buffer window it calls `POST /auth/refresh` with the stored `refresh_token` first.
- [ ] A successful refresh updates `accessToken` and `refresh_token` in `brightskyStore` without triggering a re-render of the chat history.
- [ ] If `POST /auth/refresh` returns a non-2xx response, `brightskyStore.authenticated` is set to `false`, the WebSocket is closed, and the ChatPanel surfaces an inline "Session expired — reconnect" message with a "Reconnect" button.
- [ ] The user is not prompted to re-run full OAuth unless `refresh_token` itself is invalid or absent.

---

## S-07 — Sessions dropdown lists Brightsky sessions
**Delivered by:** Conv 2

As a Studio user,
I want the ConductorHeader sessions dropdown to list my Brightsky conversation sessions,
so that I can resume a previous conversation without leaving Studio.

**Acceptance criteria:**
- [ ] When `brightskyStore.authenticated === true`, `ChatPanel/index.tsx` passes a `sessions` prop (array of `SessionSummary`) to `ConductorHeader`.
- [ ] Selecting a session from the dropdown sets `brightskyStore.sessionId` to the selected session's ID.
- [ ] The sessions list is populated from the Brightsky store or client; the `ConductorHeader` component itself is not modified.
- [ ] When not authenticated or Brightsky is not selected, `ConductorHeader` retains its existing "Connect Brightsky to see history" placeholder (no regression).

---

## S-08 — Graceful auth failure and error surfacing
**Delivered by:** Conv 1

As a Studio user,
I want clear inline errors when auth fails at any step,
so that I know what went wrong and can act without Studio crashing or silently dropping my input.

**Acceptance criteria:**
- [ ] Auth timeout (60s no callback) renders an inline error in the ChatPanel area or ModelSelector, not a thrown unhandled exception.
- [ ] `POST /auth/exchange-code` returning a server error surfaces an inline "Auth failed — try again" message with a retry affordance.
- [ ] All error states are represented as typed values in `brightskyStore` (e.g., `authError: string | null`), not as console-only logs.
- [ ] Studio does not crash (no unhandled promise rejection, no white screen) for any of the above failure paths.

---

## S-09 — WebSocket disconnect is surfaced and recoverable
**Delivered by:** Conv 2

As a Studio user,
I want a clear error when the WebSocket drops mid-stream,
so that I know the response is incomplete and can retry without confusion.

**Acceptance criteria:**
- [ ] A WebSocket `close` or `error` event during an active `stream_chunk` sequence marks the in-flight message with an "(incomplete)" or similar indicator.
- [ ] `brightskyStore.connected` is set to `false` on disconnect.
- [ ] The ChatPanel surfaces a "Disconnected — reconnect" inline action; clicking it calls `brightskyClient.connect()`.
- [ ] Studio does not crash and existing (completed) chat messages remain visible after a disconnect.

---

## S-10 — Session ownership invalidated on account change
**Delivered by:** Conv 2

As a Studio user,
I want the local session cache cleared when I log out and log back in as a different account,
so that I never see a previous user's sessions or accidentally continue their conversation.

**Acceptance criteria:**
- [ ] On logout (or when `userId` changes in `brightskyStore`), `sessionId` is set to null and any locally cached session list is cleared.
- [ ] After a new login, the sessions dropdown shows only sessions for the newly authenticated `userId`.
- [ ] Logout is reachable from the ModelSelector "Disconnect" button when Brightsky is selected and authenticated.
