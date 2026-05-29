# Architecture Proposal — brightsky-chat-connect

---

## Layer diagram

```
┌─────────────────────────────────────────────────────────┐
│  Brightsky Backend (Render, NestJS)                     │
│  • REST: /auth/google, /auth/exchange-code, /auth/refresh│
│  • WebSocket: wss://[host]/ws                            │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTPS + WSS (internet)
┌──────────────────────────▼──────────────────────────────┐
│  Renderer process (Chromium / React + Vite)             │
│  • brightskyStore (Zustand persist → localStorage)      │
│  • BrightskyClient (native browser WebSocket)           │
│  • ChatPanel, ModelSelector (React components)          │
│  • useChatStore (existing streaming primitive)          │
└──────────────────────────┬──────────────────────────────┘
       window.pathly.brightsky.*  (contextBridge)
┌──────────────────────────▼──────────────────────────────┐
│  Preload script                                         │
│  • ipcRenderer.invoke('brightsky:login')                │
│  • ipcRenderer.on('brightsky:token', cb)                │
└──────────────────────────┬──────────────────────────────┘
                      IPC (invoke / send)
┌──────────────────────────▼──────────────────────────────┐
│  Main process (Node.js)                                 │
│  • registerBrightskyHandlers(win: BrowserWindow)        │
│  • brightsky:login handler                              │
│    – shell.openExternal → system browser                │
│    – local HTTP server OR app.setAsDefaultProtocolClient│
│    – POST /auth/exchange-code                           │
│    – win.webContents.send('brightsky:token', payload)   │
└─────────────────────────────────────────────────────────┘
```

---

## Why WebSocket lives in the renderer

1. **Browser API availability.** The renderer runs in a Chromium context, which provides the native `WebSocket` constructor. Node.js also has WebSocket support (via `ws` or native in Node 22+), but using the browser-native API in the renderer means zero additional dependencies and consistent behavior with the existing Vite/React bundle.

2. **No IPC serialization overhead.** Streaming responses can produce hundreds of small `stream_chunk` events per second. Routing each chunk through an IPC bridge (main → preload → renderer) would add per-message serialization cost and IPC queue contention. A direct renderer WebSocket eliminates that entirely.

3. **Lifecycle alignment.** The WebSocket connection is scoped to the lifetime of the authenticated renderer session. When the user switches backends, reloads the chat, or logs out, the React component tree naturally tears down the client. Managing that lifecycle from the main process would require explicit coordination signals that add complexity without benefit.

4. **Existing streaming pattern.** `useChatStore.updateLastMessage` is already the established primitive for streaming content into the chat UI. BrightskyClient calling it directly keeps the streaming path consistent with the local LLM path — no new rendering primitives are introduced.

---

## Why OAuth lives in the main process

1. **Custom protocol registration requires Node/OS access.** `app.setAsDefaultProtocolClient('brightsky')` is an Electron main-process API. There is no equivalent in the renderer. The `brightsky://` URI scheme must be registered at the OS level so the system browser can redirect back to Studio.

2. **`shell.openExternal` is main-process only.** Opening the user's system browser is a privileged operation. It is available via `shell` in the main process and is not exposed to the renderer by default (and should not be — it is a potential open-redirect vector if renderer code could invoke it directly).

3. **One handler owns the pending auth state.** The code-exchange step (`POST /auth/exchange-code`) must happen exactly once per OAuth flow. Centralizing it in the main process makes it straightforward to enforce the "only one pending auth at a time" guard and to route the result back to the correct `BrowserWindow` via `win.webContents.send`.

4. **Renderer isolation.** The renderer should never hold the raw authorization code. The code arrives at the main process (via local HTTP server or protocol handler), is exchanged immediately, and only the resulting token payload is forwarded to the renderer. This keeps the OAuth secret out of the Chromium context.

---

## Token storage decision

Tokens are stored via Zustand `persist` middleware writing to `localStorage` under the key `brightsky-store`.

**Rationale:**

- This is the established pattern in the Studio codebase — `modelStore` and other stores already use Zustand persist to localStorage. Adding `electron-store` would introduce a new dependency, a separate IPC read path on startup, and a second place where application state lives.
- `localStorage` in Electron is sandwiched within the app's Chromium profile directory, which is user-account-scoped and not accessible by other OS processes in normal operation.
- The token is already short-lived (access token) or only useful in conjunction with the backend's refresh endpoint (refresh token). The security posture of localStorage is acceptable for this use case given the existing project pattern.
- No `electron-store` dependency is added.

---

## Data flow: OAuth to streamed response

```
User clicks "Connect"
  → renderer: window.pathly.brightsky.login()
  → IPC invoke: brightsky:login
  → main: shell.openExternal(authUrl)           # system browser opens
  → [user completes Google OAuth in browser]
  → main: local HTTP server receives brightsky://auth?code=XXX
  → main: POST /auth/exchange-code { code }
  → main: win.webContents.send('brightsky:token', { access_token, refresh_token, user })
  → preload: ipcRenderer.on forwards to renderer callback
  → renderer: brightskyStore.setTokens(access, refresh, user)
              brightskyStore.authenticated = true

User types a message (first turn)
  → renderer: handleBrightskySend(content)
  → renderer: brightskyClient.connect(wsUrl, accessToken)   # if not already connected
  → renderer: WS opens to wss://[host]/ws
  → renderer: brightskyClient.sendMessage(content, sessionId=null)
  → WS emit: { type: 'create_session_with_message', payload: { userMessage: { content, role: 'user' } } }
  → server: creates session, returns session_created event
  → renderer: brightskyStore.setSessionId(metadata.sessionId)
  → server: emits stream_chunk events
  → renderer: useChatStore.updateLastMessage({ content: prev + chunk })
  → server: emits stream_end
  → renderer: message finalized

User types a follow-up message (subsequent turn)
  → renderer: brightskyClient.sendMessage(content, brightskyStore.sessionId)
  → WS emit: { type: 'user_message', content, sessionId }
  → [streaming repeats]
```

---

## Dependency direction rules

1. **Renderer never imports main-process code.** Files under `studio/src/main/` must not be imported by files under `studio/src/renderer/`. The boundary is enforced by the fact that Vite only bundles the renderer tree.

2. **IPC is the only cross-boundary call.** The renderer reaches the main process exclusively through `window.pathly.*` (the contextBridge surface). The main process reaches the renderer exclusively through `win.webContents.send(channel, payload)`. No shared in-memory objects cross this boundary.

3. **Preload is a thin bridge, not logic.** The preload script (`preload/index.ts`) only translates between `ipcRenderer` calls and `window.pathly.*` methods. It contains no business logic, no token handling, and no state.

4. **brightskyStore is renderer-only.** The main process does not read from or write to `brightskyStore` directly. It forwards the token payload once; the renderer stores it. Subsequent reads (e.g., to get `accessToken` for WebSocket auth) happen entirely within the renderer.

5. **BrightskyClient depends on brightskyStore, not vice versa.** The client reads token state from the store and writes session/connection state back to it. The store has no reference to the client instance. Component code holds the client instance (or accesses it via a module singleton) and calls store actions as side effects.
