# Progress — brightsky-chat-connect

| Story | Title | Conv | Status |
|---|---|---|---|
| S-01 | Backend selection persists across restarts | Conv 1 | DONE |
| S-02 | Google OAuth round-trip via custom protocol | Conv 1 | DONE |
| S-03 | Auth state stored and reflected in UI | Conv 1 | DONE |
| S-08 | Graceful auth failure and error surfacing | Conv 1 | DONE |
| S-04 | WebSocket connects and streams a first message | Conv 2 | DONE |
| S-05 | Follow-up turns reuse the active session | Conv 2 | DONE |
| S-06 | Token auto-refresh without user interruption | Conv 2 | DONE |
| S-07 | Sessions dropdown lists Brightsky sessions | Conv 2 | DONE |
| S-09 | WebSocket disconnect is surfaced and recoverable | Conv 2 | DONE |
| S-10 | Session ownership invalidated on account change | Conv 2 | DONE |

## Conversation status

| Conv | Title | Status |
|---|---|---|
| Conv 1 | Auth layer (store, IPC, preload, types) | DONE |
| Conv 2 | WebSocket client + ModelSelector + ChatPanel wiring | DONE |
