# Architecture Proposal — chat-stop-proxy

## Feature summary

Two independent enhancements to the chat panel:

1. **Stop button** — the send button becomes a stop button during streaming; pressing it aborts the in-flight LLM request.
2. **Claude Code proxy mode** — a mode toggle routes chat messages to a Claude Code PTY session instead of the local LLM.

---

## Layer map

```
Renderer (React)
  ChatInput.tsx
  ChatPanel/index.tsx
  chatStore.ts
        |
        | window.pathly.*   (contextBridge — preload)
        |
IPC boundary
        |
        | ipcRenderer ↔ ipcMain
        |
Main process
  studio/src/main/ipc/terminal.ts   (already exists — no changes)
  [llm abort handler]               (already exists — no changes)
```

All new code lives in `studio/src/renderer/src/`. No main process changes are required.

---

## IPC path 1 — Abort (stop button)

```
ChatPanel calls abortLlm()
  → llmBridge.ts: window.pathly.llm.abort()
    → preload: ipcRenderer.send('llm:abort')
      → main: kills in-flight Ollama / llama.cpp request
```

**Key decision:** `abortLlm()` is a stateless fire-and-forget call. No AbortController is threaded through component props or function signatures. The existing `abortLlm` export already handles the IPC send; ChatPanel simply calls it on stop.

No abort state is stored in chatStore — the loading flag (`isLoading`) that drives the button swap already resets when the stream ends or is aborted.

---

## IPC path 2 — PTY write/read (Claude proxy mode)

### Sending a message to Claude Code

```
ChatPanel.handleSend() (when chatMode === 'claude')
  → writeToTerminal(tabId, message + '\n')
    → window.pathly.terminal.write(tabId, data)
      → preload: ipcRenderer.send('terminal:write', tabId, data)
        → main/ipc/terminal.ts: pty.write(data)
```

### Receiving PTY output into the chat bubble

```
main/ipc/terminal.ts: pty.onData → ipcMain sends 'terminal:data:<tabId>'
  → preload: ipcRenderer.on('terminal:data:<tabId>', cb)
    → window.pathly.terminal.onData(tabId, cb)
      → ChatPanel useEffect: accumulates data into chat message bubble
```

Subscription is established inside a `useEffect` that runs when `chatMode` changes to `'claude'`. The cleanup function (`return () => unsubscribe()`) fires on mode change back to `'llm'` or on component unmount, preventing ghost listeners.

---

## Renderer component changes

### ChatInput.tsx

| Addition | Purpose |
|---|---|
| `isLoading: boolean` prop | drives button icon swap |
| `onStop: () => void` prop | called when stop button is pressed |
| Square icon rendered when `isLoading` | visible stop affordance |
| Stop button is **active**, not disabled | must be clickable during streaming |

### ChatPanel/index.tsx

| Addition | Purpose |
|---|---|
| `abortLlm()` wired to `onStop` | cancels in-flight LLM stream |
| `chatMode` read from chatStore | branch between LLM and proxy handleSend |
| `handleSend` proxy branch | calls `writeToTerminal` instead of `sendMessage` |
| `useEffect` PTY subscription | collects PTY output into chat bubble when in proxy mode |

### chatStore.ts

| Addition | Purpose |
|---|---|
| `chatMode: 'llm' \| 'claude'` field | persists mode across re-renders and component remounts |
| `setChatMode(mode)` action | toggled by the mode control in ChatPanel |

**Key decision:** `chatMode` lives in the Zustand store, not local component state. Local state would reset on component remount (e.g., tab switch), losing the user's chosen mode silently.

---

## What is explicitly out of scope

- No new main process IPC handlers.
- No changes to the terminal PTY infrastructure.
- No changes to the existing LLM streaming pipeline (only the abort call is wired in).
- No persistence of `chatMode` across app restarts (store is in-memory).

---

## Open questions

None. All architectural decisions are resolved above.
