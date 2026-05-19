# Studio AI Chat — Architecture Proposal

## Problem Statement

Pathly Studio users need in-app guidance that is aware of their current pipeline stage, active feature, and on-screen state. The guidance must be fully offline (no cloud API), integrated into the existing Electron + Python stack, and able to act on the user's behalf by typing commands into the terminal.

## Proposed Solution

A three-layer system: Python chat agent server (extends the existing FSM HTTP server), React + Zustand chat UI panel (new right sidebar in Studio renderer), and an Electron IPC bridge (one new handler for terminal write). All three layers communicate via existing transport mechanisms — HTTP and Electron IPC — so no new infrastructure is needed.

## Layer Breakdown

```
Studio Renderer (React 18 + Zustand + CSS Modules)
  ChatPanel component
     │  fetch POST /chat   (HTTP, ReadableStream for streaming)
     │  buildPathlyContext()  (DOM analysis + FSM state)
     ▼
Pathly Python Server  (http_server.py :8765 — already running)
  POST /chat  →  ChatAgent.stream()
     │  chat_tools.py  (get_fsm_state, read_plan, list_skills)
     ▼
Ollama  (:11434 — local system service)
  phi4-mini or env-configured model
     │  streams tokens back
     ▼
Response streams back through all layers to the MessageList

Renderer ──IPC 'chat:write-terminal'──► Electron Main
                                              │  node-pty.write()
                                              ▼
                                         Shell (PowerShell/bash)
```

## Key Design Decisions

### Decision 1: Ollama over web-llm
- **Options considered**: web-llm (in-browser WebGPU), Ollama (system service), llama.cpp (direct binary)
- **Chosen**: Ollama
- **Rationale**: Ollama survives page reloads, supports hot model switching, has a Python SDK, runs on CPU (no WebGPU required), and is already the standard local model runner on Windows. web-llm requires WebGPU which is not available in all Electron versions; llama.cpp requires compiling and managing binaries.

### Decision 2: Extend existing Python server vs. new Node.js server
- **Options considered**: Add /chat to http_server.py (Python), new NestJS server (port it from BrightSky), new Express server (Node.js in Studio main process)
- **Chosen**: Extend http_server.py
- **Rationale**: Everything is already Python. One less process to start. Ollama has a Python SDK. The existing server patterns (Flask routes, SSE streaming) map directly to what /chat needs. Porting BrightSky's NestJS backend to Python is the right call — same agent loop architecture, same tool system, but native to the existing stack.

### Decision 3: HTTP + ReadableStream over WebSocket for streaming
- **Options considered**: WebSocket (bidirectional), HTTP SSE, HTTP chunked transfer
- **Chosen**: HTTP SSE (Server-Sent Events via `text/event-stream`)
- **Rationale**: Studio already uses HTTP to talk to the FSM server. Adding WebSocket would require a new server listener. SSE is unidirectional (server → client) which is all chat streaming needs. fetch + ReadableStream handles it natively in Electron's Chromium renderer.

### Decision 4: CSS Modules over Tailwind for chat UI
- **Options considered**: Tailwind CSS, CSS Modules (existing Studio pattern), inline styles
- **Chosen**: CSS Modules
- **Rationale**: Studio already uses CSS Modules throughout. Adding Tailwind would require Vite config changes and a PostCSS setup. CSS Modules gives full control with zero new tooling. Design tokens from UI/UX Pro Max are applied as CSS custom properties.

### Decision 5: Context cap at 2,000 system-prompt tokens
- **Options considered**: Full plan injection (no cap), fixed 2,000 token cap, dynamic cap based on model context window
- **Chosen**: Fixed 2,000 token cap
- **Rationale**: phi4-mini has a 16k context window. 2,000 tokens for system context leaves 14k for conversation history — more than enough for a typical session. Fixed cap is simple and predictable. Dynamic cap adds complexity with no real benefit at this scale.

## Key Components

| Component | File | Description |
|---|---|---|
| `ChatAgent` | `chat_agent.py` | Builds system prompt from context, calls Ollama, streams response |
| `chat_tools` | `chat_tools.py` | Three functions that read Pathly state for context injection |
| `POST /chat` | `http_server.py` | HTTP endpoint, receives message + history + context, returns SSE stream |
| `chatStore` | `chatStore.ts` | Zustand store for all chat state — messages, streaming flag, approval state |
| `ChatPanel` | `ChatPanel/index.tsx` | Collapsible sidebar container, 32px ↔ 320px animated |
| `MessageList` | `ChatPanel/MessageList.tsx` | Scrollable message list with streaming cursor |
| `ChatInput` | `ChatPanel/ChatInput.tsx` | Textarea + Send/Stop buttons |
| `TerminalApproval` | `ChatPanel/TerminalApproval.tsx` | Command approval banner with Run/Dismiss |
| `chat IPC` | `ipc/chat.ts` | Electron main process handler for terminal write |
| `pathlyContext` | `lib/pathlyContext.ts` | Bundles FSM state + screen elements + skills into one object |
| `pageAnalyzer` | `lib/pageAnalyzer/` | BrightSky DOM analyzers (pure TS, no Chrome APIs) |

## Interface Design

```typescript
// POST /chat request body
{ message: string; history: Message[]; context?: PathlyContext }

// PathlyContext (from pathlyContext.ts)
{ fsmStage: string; featureName: string; screenElements: ScreenElements; skills: string[] }

// SSE chunk format
data: {"text": "..."}\n\n
data: {"error": "..."}\n\n  // terminal error

// IPC: chat:write-terminal
invoke('chat:write-terminal', command: string) → { ok: true } | { error: string }
```

## Risks

- **Ollama cold start**: First message after system restart may take 5–10 seconds while Ollama loads the model. Mitigation: show a "Loading model..." indicator in ChatPanel; start Ollama at Studio launch.
- **Context staleness**: FSM state is read at message-send time, not continuously. If the FSM advances mid-conversation, the AI's context is stale until the next message. Mitigation: accepted limitation for v1; a polling refresh can be added in a follow-up.
- **Shell injection via auto-approve**: If the AI hallucinates a destructive command and auto-approve is on, it executes immediately. Mitigation: sanitize command strings in Phase 9 (strip `;`, `&&`, `|`, `>`).
- **BrightSky PageAnalyzer coupling**: Copying source files creates a fork. If BrightSky updates its analyzers, Pathly Studio won't get the update automatically. Mitigation: document the copy in a comment; treat it as a vendored dependency.
