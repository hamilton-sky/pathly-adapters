# Conversation Prompts — brightsky-chat-connect

---

## Conversation 1 — Auth layer

**Stories delivered:** S-01, S-02, S-03, S-08

### Context

You are implementing the authentication layer for the Brightsky chat backend integration in Pathly Studio. Do not implement WebSocket chat in this conversation — that is Conv 2. Leave the codebase TypeScript-clean and runnable after every phase.

**Backend contract (fixed — do not change):**
- Auth URL: `GET https://[backend]/auth/google` → opens browser
- Code exchange: `POST /auth/exchange-code` body `{ code: string }` → `{ access_token, refresh_token, user: { id, email, displayName } }`
- Code expires in 60 seconds, one-time use

**Codebase facts:**
- `electron-store` is NOT installed. Use Zustand `persist` to localStorage for token storage.
- IPC naming convention: `domain:action` (e.g. `brightsky:login`, `brightsky:token`)
- Preload: `studio/src/main/preload/index.ts` exposes `window.pathly.*` via contextBridge
- Main process: `studio/src/main/index.ts` calls `registerIpcHandlers()` which calls all `register*Handlers()`
- TypeScript check command (run from repo root): `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

### Phase 1 — Zustand store + global types

**Create** `studio/src/renderer/src/store/brightskyStore.ts`:
- Zustand store with `persist` middleware, localStorage key `'brightsky-store'`
- State: `connected: boolean`, `authenticated: boolean`, `accessToken: string | null`, `refreshToken: string | null`, `userId: string | null`, `sessionId: string | null`, `wsUrl: string`, `authUrl: string`, `authError: string | null`
- Default `wsUrl` and `authUrl` should reference the Brightsky Render deployment URL (use a placeholder constant `BRIGHTSKY_BASE_URL` at the top of the file so it is easy to change)
- Actions: `setTokens(access: string, refresh: string, user: { id: string; email: string; displayName: string }): void` — sets authenticated=true, connected=true, clears authError; `clearAuth(): void` — resets all auth fields, sets authenticated=false, connected=false, sessionId=null; `setSessionId(id: string | null): void`; `setConnected(val: boolean): void`; `setAuthError(msg: string | null): void`

**Modify** `studio/src/renderer/src/store/modelStore.ts`:
- Add `'brightsky'` to the backend type union and any arrays that enumerate valid backends
- Verify the store persists the selected backend

**Modify** `studio/src/renderer/src/types/global.d.ts`:
- Add to the `window.pathly` interface: `brightsky: { login(): Promise<void>; onToken(cb: (payload: BrightskyTokenPayload | BrightskyAuthError) => void): () => void }`
- Define in the same file: `interface BrightskyTokenPayload { access_token: string; refresh_token: string; user: { id: string; email: string; displayName: string } }` and `interface BrightskyAuthError { error: string }`

**Gate:** `tsc --noEmit` passes.

### Phase 2 — IPC handler (main process)

**Create** `studio/src/main/ipc/brightsky.ts`:

```typescript
// Registers brightsky:login IPC handler.
// Opens OAuth URL in system browser, captures brightsky:// callback,
// exchanges code for tokens, pushes result to renderer.
export function registerBrightskyHandlers(win: BrowserWindow): void
```

Implementation requirements:
1. `ipcMain.handle('brightsky:login', ...)` — async handler
2. Call `shell.openExternal(authUrl)` where authUrl comes from a config constant (same `BRIGHTSKY_BASE_URL` as in the store)
3. To capture the callback: spin a one-shot local HTTP server on a random free port, registering it as the redirect target — OR use `app.setAsDefaultProtocolClient('brightsky')` with the `open-url` (macOS) / `second-instance` (Windows) event. Choose the local HTTP server approach if `app.isPackaged` is false; document which approach is used and why in a code comment.
4. Resolve the captured code within 60 seconds. If no code arrives within 60s, close the server, reject/resolve with `{ error: 'Auth timed out' }`.
5. Call `POST /auth/exchange-code` with `{ code }`. On success, call `win.webContents.send('brightsky:token', { access_token, refresh_token, user })`. On HTTP error, call `win.webContents.send('brightsky:token', { error: '...' })`.
6. Guard: if a login flow is already in progress, return early without opening a second browser tab.

**Modify** `studio/src/main/index.ts`:
- Import `registerBrightskyHandlers` from `'./ipc/brightsky'`
- Call `registerBrightskyHandlers(win)` in the `registerIpcHandlers` function (or directly alongside the other `register*Handlers` calls — match the existing pattern)

**Gate:** `tsc --noEmit` passes. Main process TypeScript also compiles (use `tsconfig.node.json` if there is a separate check for main process files).

### Phase 3 — Preload bridge

**Modify** `studio/src/main/preload/index.ts`:

Add to the contextBridge object:
```typescript
brightsky: {
  login: () => ipcRenderer.invoke('brightsky:login'),
  onToken: (cb: (payload: unknown) => void) => {
    const handler = (_: unknown, payload: unknown) => cb(payload)
    ipcRenderer.on('brightsky:token', handler)
    return () => ipcRenderer.removeListener('brightsky:token', handler)
  },
},
```

**Gate:** `tsc --noEmit` passes.

### Phase 4 — Store wiring (renderer bootstrap)

Wire the `brightsky:token` push event into the store. The cleanest place is a `useEffect` in the root `App` component or a dedicated `useBrightskyAuth` hook:

```typescript
useEffect(() => {
  const cleanup = window.pathly.brightsky.onToken((payload) => {
    if ('error' in payload) {
      useBrightskyStore.getState().setAuthError(payload.error)
    } else {
      useBrightskyStore.getState().setTokens(
        payload.access_token,
        payload.refresh_token,
        payload.user,
      )
    }
  })
  return cleanup
}, [])
```

Place this where it runs exactly once across Studio's lifetime (not inside a component that remounts).

**Final gate:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes with zero errors. Mark S-01, S-02, S-03, S-08 as DONE in `pathly/plans/brightsky-chat-connect/PROGRESS.md`.

---

## Conversation 2 — WebSocket client + UI wiring

**Stories delivered:** S-04, S-05, S-06, S-07, S-09, S-10

**Prerequisite:** Conv 1 is complete. `brightskyStore`, IPC handler, preload bridge, and global types are all in place.

### Context

You are implementing the WebSocket client and all UI wiring for Brightsky chat in Pathly Studio. Auth is already done. Do not modify the IPC layer or preload — that is Conv 1 territory.

**Backend WebSocket contract (fixed):**
- WS URL: `wss://[app].onrender.com/ws`
- First message: `{ type: 'create_session_with_message', payload: { userMessage: { content: string, role: 'user' } } }`
- Server responds: `session_created` event with `metadata.sessionId`
- Subsequent messages: `{ type: 'user_message', content: string, sessionId: string }`
- Streaming: `stream_start` → `stream_chunk` (payload: `{ sessionId, messageId, chunk: string, isDone: boolean }`) → `stream_end`
- Stop: `{ type: 'stop_generation', sessionId: string }`
- Status: `{ type: 'processing_status', payload: { phase: string } }` (routing/tool_selecting/synthesizing)

**Codebase facts:**
- Existing streaming primitive: `useChatStore.updateLastMessage({ content: prev + chunk })` — reuse exactly, do not invent a new one
- `ConductorHeader` already accepts `sessions?: SessionSummary[]` and `onSelectSession?: (id: string) => void` — no changes to that component needed
- WebSocket opens directly from renderer using native browser WebSocket API — no IPC bridge for chat traffic
- Token refresh endpoint: `POST /auth/refresh` body `{ refresh_token }` → `{ access_token, refresh_token, user }`

### Phase 1 — WebSocket client

**Create** `studio/src/renderer/src/lib/brightskyClient.ts`:

```typescript
export class BrightskyClient {
  connect(wsUrl: string, accessToken: string): void
  sendMessage(content: string, sessionId: string | null): void
  stopGeneration(sessionId: string): void
  disconnect(): void
  // private: onMessage, onClose, onError
}
```

Implementation requirements:
1. `connect()`: opens `new WebSocket(wsUrl)`. Sets `brightskyStore.setConnected(true)` on `ws.onopen`. Sets a 90-second connection timeout that shows "connecting…" state (set `brightskyStore.setConnected(false)` and `setAuthError('Connection timed out — the backend may be starting up. Try again in a moment.')` if no `onopen` fires within 90s). This handles Render cold-start without showing a hard error.
2. `sendMessage()`: before sending, call `maybeRefreshToken()` (see below). If `sessionId` is null, send `create_session_with_message`; else send `user_message`. Append a pending assistant message to `useChatStore` before sending (so the streaming bubble appears immediately).
3. `maybeRefreshToken()`: decode JWT expiry from `accessToken` (base64 decode the payload). If expiry is within 60 seconds, call `POST /auth/refresh` with `{ refresh_token }`. On success, call `brightskyStore.setTokens(...)`. On failure, call `brightskyStore.clearAuth()` and throw so the send is aborted with a visible error.
4. `onMessage` handler — dispatch by `event.type`:
   - `session_created`: call `brightskyStore.setSessionId(metadata.sessionId)`
   - `stream_chunk`: call `useChatStore.updateLastMessage({ content: prev + payload.chunk })`. If `payload.isDone` is true, finalize.
   - `stream_end`: finalize the message if not already done
   - `processing_status`: update a status label (store it in `brightskyStore` or local component state — your call, but make it visible in ChatPanel)
5. `onClose` / `onError`: set `brightskyStore.setConnected(false)`. If a stream was in progress, mark the last message with "(incomplete — connection lost)". Set `brightskyStore.setAuthError('Disconnected from Brightsky.')`.
6. `disconnect()`: closes WebSocket cleanly, sets `connected = false`.

Export a singleton: `export const brightskyClient = new BrightskyClient()`

### Phase 2 — ModelSelector Brightsky section

**Modify** `studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx`:

Add a Brightsky option alongside the existing backend options. When `modelStore.backend === 'brightsky'`:
- Show an auth status indicator dot: green (`#22c55e`) when `brightskyStore.authenticated`, grey (`#6b7280`) when not
- Show a "Connect" button (calls `window.pathly.brightsky.login()`) when `!brightskyStore.authenticated`
- Show a "Disconnect" button (calls `brightskyStore.clearAuth()` then `brightskyClient.disconnect()`) when authenticated
- Show `brightskyStore.authError` as an inline error string beneath the auth controls when non-null
- Render cold-start / connection status: show `brightskyStore.connected ? 'Connected' : 'Disconnected'` as a small status line

Keep all existing local-LLM sections intact and unmodified.

### Phase 3 — ChatPanel send path

**Modify** `studio/src/renderer/src/components/ChatPanel/index.tsx`:

Add `handleBrightskySend`:
```typescript
async function handleBrightskySend(content: string) {
  if (!brightskyStore.connected) {
    brightskyClient.connect(brightskyStore.wsUrl, brightskyStore.accessToken!)
  }
  brightskyClient.sendMessage(content, brightskyStore.sessionId)
}
```

In the existing send handler, gate on `modelStore.backend`:
- `'brightsky'` → `handleBrightskySend(content)`
- everything else → existing path (unchanged)

Pass to `ConductorHeader`:
```typescript
sessions={brightskyStore.authenticated ? brightskySessionList : undefined}
onSelectSession={(id) => brightskyStore.setSessionId(id)}
```

Where `brightskySessionList` is whatever session summary data is available from the store. If no session list fetch is implemented yet, pass an empty array `[]` — the ConductorHeader will still render its placeholder. Document this as a known gap.

### Phase 4 — Session ownership + disconnect cleanup

Verify in `brightskyStore.clearAuth()` (should already be from Conv 1):
- `sessionId` is reset to `null`
- `authenticated` is `false`
- `connected` is `false`

Add a `userId`-change watcher: if `userId` changes on a new login (token payload `user.id` differs from stored `userId`), reset `sessionId` to null and clear session list (S-10).

### Phase 5 — TypeScript gate

Run: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

Zero errors required before marking done.

**Final gate checklist:**
- [ ] `tsc --noEmit` passes
- [ ] Selecting Brightsky in ModelSelector persists after reload (S-01)
- [ ] Clicking Connect opens system browser (S-02)
- [ ] Auth dot turns green after successful token receipt (S-03)
- [ ] First message creates a session and streams chunks into the chat (S-04)
- [ ] Second message reuses sessionId (S-05)
- [ ] Token near expiry triggers refresh before send (S-06)
- [ ] Sessions list passed to ConductorHeader (S-07)
- [ ] Auth errors render inline (S-08)
- [ ] WebSocket drop marks in-flight message incomplete and shows reconnect action (S-09)
- [ ] clearAuth() resets sessionId (S-10)

Mark S-04 through S-10 as DONE in `pathly/plans/brightsky-chat-connect/PROGRESS.md`.
