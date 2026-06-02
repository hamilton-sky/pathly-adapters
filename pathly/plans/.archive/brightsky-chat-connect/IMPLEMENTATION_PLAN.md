# Implementation Plan — brightsky-chat-connect

**Rigor:** lite  
**Conversations:** 2  
**Stories delivered:** S-01, S-02, S-03, S-04, S-05, S-06, S-07, S-08, S-09, S-10

---

## Conversation 1 — Auth layer

**Stories:** S-01, S-02, S-03, S-08  
**Leaves codebase in:** TypeScript-compiling state with auth flow end-to-end wired; no WebSocket chat yet.

### Phase 1 — Zustand store + global types

Files:
- Create `studio/src/renderer/src/store/brightskyStore.ts`
  - State shape: `{ connected, authenticated, accessToken, refreshToken, userId, sessionId, wsUrl, authUrl, authError }`
  - Zustand `persist` middleware writing to localStorage key `brightsky-store`
  - Actions: `setTokens(access, refresh, user)`, `clearAuth()`, `setSessionId(id)`, `setConnected(bool)`, `setAuthError(msg | null)`
- Modify `studio/src/renderer/src/store/modelStore.ts`
  - Add `'brightsky'` to the backend union type and any backend value lists
- Modify `studio/src/renderer/src/types/global.d.ts`
  - Extend `window.pathly` with `brightsky: { login(): Promise<void>; onToken(cb: (payload: TokenPayload) => void): () => void }`
  - Define `TokenPayload` type: `{ access_token: string; refresh_token: string; user: { id: string; email: string; displayName: string } }`

### Phase 2 — IPC handler (main process)

Files:
- Create `studio/src/main/ipc/brightsky.ts`
  - Export `registerBrightskyHandlers(win: BrowserWindow): void`
  - Handler `brightsky:login`:
    1. Derives auth URL from store/config (`/auth/google` endpoint)
    2. Calls `shell.openExternal(authUrl)`
    3. Spins a one-shot local HTTP server on a free port to capture the `brightsky://auth?code=XXX` redirect (OR uses `app.setAsDefaultProtocolClient('brightsky')` + `second-instance` / `open-url` listener — choose whichever avoids OS-level protocol registration side effects for now; document the choice in a comment)
    4. On callback receipt (≤60s), calls `POST /auth/exchange-code` with `{ code }`
    5. On success, sends `{ channel: 'brightsky:token', payload }` to renderer via `win.webContents.send`
    6. On timeout or error, sends `{ channel: 'brightsky:token', error: '...' }` to renderer
    7. Ensures only one pending auth flow at a time (guard against concurrent calls)
- Modify `studio/src/main/index.ts`
  - Import `registerBrightskyHandlers` from `./ipc/brightsky`
  - Call `registerBrightskyHandlers(win)` inside `registerIpcHandlers(win)`

### Phase 3 — Preload bridge

Files:
- Modify `studio/src/main/preload/index.ts`
  - Add to `contextBridge.exposeInMainWorld('pathly', { ... })`:
    - `brightsky.login()` → `ipcRenderer.invoke('brightsky:login')`
    - `brightsky.onToken(cb)` → registers `ipcRenderer.on('brightsky:token', (_, payload) => cb(payload))`, returns cleanup function

### Phase 4 — Store wiring and error handling

Files:
- Modify `studio/src/renderer/src/store/brightskyStore.ts`
  - On app init (or a `useEffect` in a top-level component), call `window.pathly.brightsky.onToken(...)` and dispatch `setTokens` or `setAuthError` depending on payload shape
- Acceptance gate: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes with zero errors

---

## Conversation 2 — WebSocket client + UI wiring

**Stories:** S-04, S-05, S-06, S-07, S-09, S-10  
**Depends on:** Conv 1 merged (brightskyStore and IPC layer in place)  
**Leaves codebase in:** Fully functional Brightsky chat, session history, and error recovery.

### Phase 1 — WebSocket client library

Files:
- Create `studio/src/renderer/src/lib/brightskyClient.ts`
  - Class `BrightskyClient` with:
    - `connect(wsUrl: string, accessToken: string): void` — opens WebSocket, attaches listeners
    - `sendMessage(content: string, sessionId: string | null): void` — emits `create_session_with_message` if `sessionId` null, else `user_message`
    - `stopGeneration(sessionId: string): void` — emits `{ type: 'stop_generation', sessionId }`
    - `disconnect(): void` — closes WebSocket cleanly
    - Private event handlers for: `session_created` (updates store sessionId), `stream_chunk` (calls `useChatStore.updateLastMessage`), `stream_end`, `processing_status` (updates a status string in store or local state), `close`/`error`
  - Token refresh hook: before `sendMessage`, check JWT expiry; if within buffer call `POST /auth/refresh`; on refresh failure call `brightskyStore.clearAuth()` and surface error
  - Cold-start tolerance: set a 90s connection timeout, during which the UI shows "connecting…" not "failed"

### Phase 2 — ModelSelector Brightsky section

Files:
- Modify `studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx`
  - Add a "Brightsky" section rendered when `modelStore.backend === 'brightsky'` (or always visible as a selectable option)
  - Auth status dot: green circle when `brightskyStore.authenticated`, red/grey otherwise
  - "Connect" button: calls `window.pathly.brightsky.login()` when not authenticated
  - "Disconnect" button: calls `brightskyStore.clearAuth()` + `brightskyClient.disconnect()` when authenticated
  - Inline auth error display: shows `brightskyStore.authError` when non-null

### Phase 3 — ChatPanel send path

Files:
- Modify `studio/src/renderer/src/components/ChatPanel/index.tsx`
  - Add `handleBrightskySend(content: string)` function:
    1. If not connected, calls `brightskyClient.connect(wsUrl, accessToken)`
    2. Calls `brightskyClient.sendMessage(content, brightskyStore.sessionId)`
    3. Appends a pending assistant message bubble to trigger streaming render
  - Gate: only invoke `handleBrightskySend` when `modelStore.backend === 'brightsky'`; existing local LLM send path is untouched
  - Pass `sessions` prop to `ConductorHeader` when authenticated (populated from `brightskyStore` session list or a fetch)
  - Wire `onSelectSession` callback to `brightskyStore.setSessionId`

### Phase 4 — Disconnect, session ownership, error recovery

Files:
- Ensure `brightskyStore.clearAuth()` also resets `sessionId` and `connected` (S-10)
- Add WebSocket `close` / `error` handler in `BrightskyClient` that:
  - Marks in-flight message as incomplete (S-09)
  - Sets `brightskyStore.connected = false`
  - Surfaces inline "Disconnected — reconnect" action in ChatPanel (via store error field)

### Phase 5 — TypeScript gate

- `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` must pass with zero errors
- Verify: selecting Brightsky → Connect → OAuth → stream a message → follow-up turn reuses session
