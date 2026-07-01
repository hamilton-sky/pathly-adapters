# Edge Cases — brightsky-chat-connect

---

## EC-01 — OAuth callback timeout

**Scenario:** The user clicks "Connect", the system browser opens, but the user closes the browser tab, gets distracted, or the network call to `/auth/exchange-code` fails silently. The `brightsky://` callback never arrives within the expected window.

**Defined boundary:** 60 seconds from when the main process opens the system browser.

**Failure mode:** The local HTTP server (or protocol handler) is still listening. The pending `brightsky:login` IPC invoke is unresolved. Studio appears frozen from the user's perspective.

**Required handling:**
- The main process `brightsky:login` handler starts a 60-second timer the moment `shell.openExternal` is called.
- If the timer fires before the callback arrives, the handler sends `win.webContents.send('brightsky:token', { error: 'Auth timed out. Please try again.' })` to the renderer and tears down the local listener.
- The IPC invoke resolves (does not reject) with an error-shaped payload so the renderer does not receive an unhandled promise rejection.
- The renderer dispatches `setAuthError('Auth timed out. Please try again.')` and renders the message inline in ModelSelector.
- The "Connect" button returns to its default state — the user can retry immediately.

**Builder note:** The one-pending-auth guard (IMPLEMENTATION_PLAN Conv 1 Phase 2, step 7) must be released when the timeout fires, otherwise a retry attempt will be silently swallowed.

---

## EC-02 — OAuth callback race (multiple Studio windows)

**Scenario:** The user has two Studio windows open simultaneously and clicks "Connect" in one. The `brightsky://` callback URL carries no window identity. Both windows may be registered to receive `open-url` / `second-instance` events (if using `app.setAsDefaultProtocolClient`) or both may have started local HTTP servers on different ports — but only one should claim the code.

**Failure mode (protocol handler path):** Both windows' `second-instance`/`open-url` listeners fire. Both attempt to call `POST /auth/exchange-code` with the same code. The second attempt returns a 4xx (code already consumed) and its window shows a spurious auth error.

**Failure mode (local HTTP server path):** Only the window that started the server on the advertised callback port receives the request. The second window's server (different port) never fires. No race, but only if the callback URL encodes the correct port.

**Required handling:**
- If using the local HTTP server approach: the port chosen must be included in the redirect URI sent to the backend in the initial `GET /auth/google` request. Only one auth flow may be in flight per application instance (not per window). Use a process-level singleton flag or a shared IPC channel routed through one window.
- If using `app.setAsDefaultProtocolClient`: the `open-url` / `second-instance` handler must check which window initiated the auth flow (tracked by window ID in the main process) and route the code only to that window. Other windows are ignored for this callback.
- The one-pending-auth guard (IMPLEMENTATION_PLAN Conv 1 Phase 2, step 7) applies process-wide, not per-window.

**Builder note:** This is an edge case for multi-window use. The most pragmatic resolution is to allow only one auth flow across all windows at once and return an error to any window that tries to start a second flow while one is pending.

---

## EC-03 — Access token expiry mid-conversation

**Scenario:** The user has been working for a while. The access token's expiry time is reached while the user is composing or has just sent a message. The WebSocket send (or the reconnect handshake) carries a now-expired bearer token and the server returns a 401 / closes the connection with an auth error code.

**Pre-send path:**
- `brightskyClient.sendMessage` decodes the JWT expiry (from the `exp` claim) before sending.
- If `now >= exp - buffer` (buffer: 60 seconds recommended), it calls `POST /auth/refresh` with the stored `refresh_token` first.
- On 2xx: updates `brightskyStore` with the new token pair, then sends the message. The user sees no interruption.
- On non-2xx: falls through to EC-04.

**Mid-stream path (401 on WS):**
- The server closes the WebSocket with a 4001 or similar close code indicating auth failure.
- `BrightskyClient`'s `close` handler inspects the close code.
- If it is an auth close code and a valid refresh token is available, it attempts one silent refresh, then reconnects and replays the last unsent message.
- The in-progress assistant message is marked "(incomplete)" during the reconnect window.
- If the replay succeeds, the "(incomplete)" marker is removed and streaming resumes.
- If the replay fails, it falls through to EC-04.

---

## EC-04 — Refresh token failure or revocation

**Scenario:** `POST /auth/refresh` returns a non-2xx response. This covers: the refresh token has expired (typically 30–90 days of inactivity), the user has revoked Studio's Google OAuth grant, or the backend has invalidated the session for security reasons.

**Failure mode:** Silent retry loops, storing a permanently invalid token, or silently discarding user messages.

**Required handling:**
- On any non-2xx from `/auth/refresh`, the handler must not retry. One attempt only.
- `brightskyStore.clearAuth()` is called immediately: clears `accessToken`, `refreshToken`, `userId`, `sessionId`, and sets `authenticated = false`.
- The active WebSocket is closed (`brightskyClient.disconnect()`).
- The ChatPanel surfaces an inline message: "Session expired — reconnect" with a "Reconnect" button. The button triggers `window.pathly.brightsky.login()` to restart the full OAuth flow.
- The user's unsent message (if any) is preserved in the chat input field — not silently dropped.
- Zustand persist will flush the cleared state to localStorage, preventing reuse of the invalid tokens after a restart.

---

## EC-05 — WebSocket disconnect mid-stream

**Scenario:** The WebSocket closes unexpectedly while the server is still emitting `stream_chunk` events. Causes include: network interruption, Render instance restart, idle timeout, or the backend process crashing.

**Failure mode:** The assistant message bubble stops updating mid-sentence with no indication to the user. The user may not notice the response is incomplete.

**Required handling:**
- `BrightskyClient.close` handler checks whether there is an in-flight message (i.e., a `stream_chunk` sequence that has not yet received `stream_end`).
- If yes: appends an "(incomplete)" indicator to the last message content and calls `useChatStore.updateLastMessage` to make it visible.
- `brightskyStore.connected` is set to `false`.
- The ChatPanel renders an inline "Disconnected — reconnect" action beneath the incomplete message.
- Clicking "Reconnect" calls `brightskyClient.connect(wsUrl, accessToken)`. It does NOT automatically resend the last message — the user decides whether to retry.
- Completed messages (those that received `stream_end`) are unaffected and remain visible.
- Studio must not crash. All disconnect paths are caught in try/finally or via the WS `error` + `close` event pair.

**Reconnect sequencing:** `connect()` is idempotent — if the WebSocket is already open or connecting, a second call does nothing. The existing `connected` state in the store is the guard.

---

## EC-06 — Render cold-start (free-tier 30–60 second spin-up)

**Scenario:** The Brightsky backend is hosted on Render's free tier and has spun down due to inactivity. The first `wss://[host]/ws` connection attempt or the first `POST /auth/exchange-code` call will block for 30–60 seconds before the instance wakes.

**Failure mode (without handling):** The WebSocket connection attempt times out (default browser timeout is much shorter than 60s in some environments, or the user assumes the app is broken and closes it).

**Required handling (WebSocket path):**
- `BrightskyClient.connect()` sets a 90-second connection timeout — long enough to survive a cold start with margin.
- While the connection is pending (WS readyState is CONNECTING), `brightskyStore` exposes a `connecting: boolean` flag.
- The ChatPanel renders a "Connecting to Brightsky..." status indicator (spinner or subtle text) whenever `connecting === true`. This is NOT shown as an error state.
- After 90 seconds with no `open` event, the connection attempt is aborted and the user is shown "Could not connect — Brightsky may be unavailable. Retry?" — a distinct message from a mid-session disconnect.

**Required handling (OAuth path):**
- The `/auth/exchange-code` call is also subject to cold-start delay. The 60-second exchange timeout defined in EC-01 is measured from callback receipt (i.e., after the browser redirects back), not from when the user started the browser flow. The cold-start delay at the backend happens during the HTTP POST, which should complete within the 60-second window if the cold start is under 30 seconds.
- If the POST takes longer than 30 seconds (edge case of severe cold start), the error message should read "Taking longer than expected — please wait" rather than failing immediately.

**Do not show:** A red error state, a crash, or a "Disconnected" indicator during the connecting window.

---

## EC-07 — Multiple Studio windows sharing the same session

**Scenario:** The user opens two Studio windows. Both are authenticated as the same user. One window sends a message and receives `session_created` with `sessionId: "abc123"`. The second window also has `brightskyStore.sessionId === null` (it has not sent a message yet). When the second window sends a message, it creates a new session — that is the correct behavior. But if both windows somehow obtain the same `sessionId` (e.g., via persist rehydration from localStorage), they could both send `user_message` events to the same session, interleaving their content on the server.

**Failure mode:** Two users (or two windows of the same user) appending messages to one conversation thread, producing a corrupted session transcript on the backend.

**Required handling:**
- `sessionId` in `brightskyStore` is set only by a `session_created` event received on the local WebSocket connection — not inherited from another window via localStorage rehydration.
- The `sessionId` field must be excluded from Zustand `persist`'s storage, or cleared on mount before rehydration is applied. Session ownership is per-window, per-connection, not per-user across windows.
- On window load, `sessionId` is always initialized to `null` regardless of what is in localStorage. This is the simplest safe default.
- `accessToken`, `refreshToken`, and `userId` are shared across windows via persist (same user, same credentials). `sessionId`, `connected`, and `connecting` are ephemeral and must not be persisted.

---

## EC-08 — Logout then re-login (account change or token refresh)

**Scenario:** The user clicks "Disconnect" in ModelSelector (or is force-logged-out by EC-04), then clicks "Connect" again — either as the same account or a different Google account.

**Failure mode:** The old `sessionId` is still in store. The new login produces a new `userId`. The user's sessions dropdown shows sessions belonging to the previous `userId`. A new message might be sent to a session owned by the old account.

**Required handling (on logout / clearAuth):**
- `brightskyStore.clearAuth()` must reset ALL of: `accessToken`, `refreshToken`, `userId`, `sessionId`, `connected`, `connecting`, `authError`.
- Any locally cached session list (if fetched and held in store) must be cleared at the same time.
- The WebSocket is closed before `clearAuth` is called to ensure no in-flight events attempt to update a cleared store.

**Required handling (on re-login):**
- The `brightsky:token` push event delivers a new `userId`.
- If `userId` in the incoming payload differs from the previously stored `userId`, `sessionId` is confirmed null (it was cleared on logout) and the sessions list is fetched fresh for the new `userId`.
- If the same `userId` re-authenticates (token refresh via full OAuth rather than silent refresh), `sessionId` may be restored from the server-side session list — but only after a fresh fetch, never from localStorage.
- The "Disconnect" button must be reachable from the ModelSelector whenever `brightskyStore.authenticated === true`. It is the primary logout affordance.
