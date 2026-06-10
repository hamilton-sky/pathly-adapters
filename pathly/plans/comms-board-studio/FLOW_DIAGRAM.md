---
name: Flow Diagram
---
# Comms Board — Studio CommsPanel (Phase 2) — Flow Diagram

## Live update: agent posts → human sees it

```
agent (running)
      │  POST /comms/post
      ▼
FSM 8765 ──► comms_messages ──► _broadcast_comms(scope)
                                       │
                                       ▼  SSE COMMS_UPDATE
                       useHQ.tsx  EventSource('/events/comms?scope=<feature>')
                                       │  appendMessage(msg)   [dedup by id]
                                       ▼
                              store/commsStore
                                       │  subscribe
                                       ▼
                  CommsPanel ──► CommsMsgList ──► CommsMsgCard / CommsQuestionCard
                                 (decisions pinned)     (data-type variant)
```

## Human posts from the compose bar

```
CommsInput  (type defaults to "Note")
      │  Send
      ▼
commsApi.postMessage({feature, board, type, text, from:'human'})
      │  optimistic append → commsStore
      ▼
POST /comms/post ──► 200 {message_id}
      │
      └─ SSE COMMS_UPDATE echo ──► appendMessage  [dedup by id → reconciles optimistic copy]
```

## Board scope toggle

```
BoardToggle  [Feature ●] [Project ○] [Global ○]   (pill toggles)
      │  onSelect(board)
      ▼
useCommsPanel maps board → scope:
      feature → scope = activeTopic
      project → scope = projectRoot
      global  → scope = 'global'
      │
      ▼
commsApi.getMessages({feature, board, scope}) ──► setMessages + setBoard
```

## Fallback / error flow

```
server down OR fetch fails
      │
      ├─ commsApi.* .catch ──► returns {ok:false} / []
      │        │
      │        └─ CommsPanel shows empty/offline state (no crash)
      │
SSE drops
      │
      └─ EventSource auto-reconnects ──► effect re-runs getMessages ──► reconcile (dedup by id)
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `useHQ.tsx` | Hosts the 2nd EventSource to `/events/comms`; appends updates to the store |
| `commsApi` | `fetch` wrappers for `/comms/*`; errors non-blocking |
| `commsStore` | Zustand source of truth for the viewed board |
| `CommsPanel` | Docked shell: subtitle, BoardToggle, CommsMsgList, CommsInput |
| `CommsMsgCard` | One message; `data-type` drives the variant; 📌 on decisions |
| `CommsQuestionCard` | Question + option buttons; answer → `/comms/answer` |
| `BoardToggle` | Pill toggles Feature/Project/Global (not tabs) |
