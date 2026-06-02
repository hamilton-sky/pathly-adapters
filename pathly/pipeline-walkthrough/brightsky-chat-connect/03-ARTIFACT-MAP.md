# Artifact Map — brightsky-chat-connect

## Feedback Files

| File | Written by | Resolved by | Notes |
|------|------------|-------------|-------|
| REVIEW_FAILURES.md (conv-1) | reviewer (inline) | builder (pass 3) | IPC/preload TypeScript failures |
| HUMAN_QUESTIONS.md | reviewer | human | Spec ambiguities resolved before TESTING gate |

## Source Files Changed

| Path | Story | What changed |
|------|-------|--------------|
| studio/src/main/ipc/brightsky.ts | S-02 | New: OAuth IPC handler, local HTTP server for code capture, 60s timeout |
| studio/src/main/preload/index.ts | S-02, S-03 | Added brightsky contextBridge (login, onToken) |
| studio/src/renderer/src/store/brightskyStore.ts | S-01, S-03 | New: Zustand persist store for auth state, tokens, sessionId |
| studio/src/renderer/src/store/modelStore.ts | S-01 | Added 'brightsky' to backend type union |
| studio/src/renderer/src/types/global.d.ts | S-02, S-03 | Added window.pathly.brightsky interface + token payload types |
| studio/src/renderer/src/App.tsx | S-03 | Wired useBrightskyAuth effect for token push events |
| studio/src/renderer/src/lib/brightskyClient.ts | S-04, S-05, S-06, S-09 | New: WebSocket client singleton, JWT refresh, cold-start timeout, disconnect handling |
| studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx | S-01, S-08 | Added Brightsky section with auth status dot, Connect/Disconnect buttons, error display |
| studio/src/renderer/src/components/sidebar/BrightskyProfile.tsx | S-03, S-07 | New: profile display component |
| studio/src/renderer/src/components/sidebar/Sidebar.tsx | S-07 | Integrated BrightskyProfile into sidebar |
| studio/src/renderer/src/components/sidebar/Sidebar.module.css | — | Sidebar style adjustments |
| studio/tsconfig.web.json | — | Config adjustments for new files |
| studio/package.json | — | Dependency updates |
