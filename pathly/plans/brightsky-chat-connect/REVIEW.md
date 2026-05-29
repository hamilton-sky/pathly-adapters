# Review — brightsky-chat-connect

## Conv 1 — PASS

All violations fixed: preload callback types, IPC handler OAuth edge cases, App.tsx guard.

## Conv 2 — PASS

Violations fixed:
- Token removed from WebSocket URL (security)
- `readyState` check before `ws.send()` 
- `BRIGHTSKY_BASE_URL` used directly in `maybeRefreshToken` (removed fragile `.replace`)
- `intentionalDisconnect` flag suppresses error on clean user-initiated disconnect
- Auth guard in `handleBrightskySend` prevents unauthenticated connect attempts

Known gap (per spec): sessions list passed as `[]` — no session list fetch endpoint wired yet.

## TypeScript gate

- `tsconfig.web.json` — zero errors (Brightsky files clean; pre-existing Sidebar.tsx error unrelated)
- `tsconfig.node.json` — zero errors
