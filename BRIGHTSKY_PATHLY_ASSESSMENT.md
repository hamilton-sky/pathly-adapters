# Bright Sky and Pathly Integration Assessment

Date: 2026-05-31

## Summary

Pathly Studio can already connect to the Bright Sky backend at the transport level, but it is not yet sending the richer context that the backend was designed to use. The current Pathly client behaves like a minimal chat sender, while the Bright Sky backend expects a session-aware, context-rich message envelope and supports additional event types such as tool calls and reasoning/status updates.

My recommendation is to **keep one shared Bright Sky backend** and build a **Pathly adapter** for it, rather than creating a separate Pathly-only backend. A second backend would duplicate the parts you most want to unify later: session management, agent orchestration, tool execution, and streaming semantics.

## What Pathly Sends Today

Pathly Studio currently sends only a small message payload:

- `create_session_with_message` with `payload.userMessage.content` and `role`
- `user_message` with `content` and `sessionId`

Relevant code:

- [studio/src/renderer/src/lib/brightskyClient.ts](C:/Users/Yafit/pathly-adapters/studio/src/renderer/src/lib/brightskyClient.ts)
- [studio/src/renderer/src/components/ChatPanel/index.tsx](C:/Users/Yafit/pathly-adapters/studio/src/renderer/src/components/ChatPanel/index.tsx)

What is missing from Pathly's outbound message today:

- current URL
- page title
- page DOM / interactive elements
- app/workspace context
- workflow or feature context
- client capability info
- structured request metadata

## What the Bright Sky Backend Expects

The Bright Sky WebSocket gateway authenticates the client and then routes messages into a richer orchestration pipeline.

Relevant code:

- [unified-chat.gateway.ts](C:/Users/Yafit/brightsky-ai/backend/src/chat/gateways/core/unified-chat.gateway.ts)
- [message-routing.service.ts](C:/Users/Yafit/brightsky-ai/backend/src/chat/gateways/session/services/message-routing.service.ts)
- [response-delivery.service.ts](C:/Users/Yafit/brightsky-ai/backend/src/chat/gateways/session/services/response-delivery.service.ts)

Key backend behavior:

- accepts a WebSocket connection with a JWT token
- creates a connection/session mapping
- routes `user_message` and related message types into the agent pipeline
- forwards context to `AgentOrchestratorService`
- can stream responses back in chunks
- can send tool calls to the frontend and wait for tool responses

The routing layer already passes these kinds of fields to the orchestrator:

- `message`
- `sessionId`
- `currentUrl`
- `pageTitle`
- `pageElements`
- `conversationHistory`
- `customInstructions`
- `metadata`
- `messageType`

## What Is Missing in Pathly Studio

### 1. Structured context forwarding

Pathly builds local Studio context for its own UI/LLM logic, but does not forward that context to Bright Sky. That means the backend cannot reason over the current app state, DOM, or workflow state.

### 2. Tool bridge support

Bright Sky can emit `tool_call` messages and expects a `tool_response` reply. Pathly Studio does not yet implement that round trip.

### 3. Backend thinking / progress UI

Pathly has a local loading indicator for its own routing/model state, but it does not yet expose a dedicated backend reasoning/progress indicator for Bright Sky events such as:

- thinking started
- tool requested
- tool completed
- response streaming

### 4. Session contract alignment

Pathly currently treats the Bright Sky connection as a generic chat socket. To make it compatible long term, it should carry a stable session/request identity and a capability handshake.

## Recommendation

### Best option

Build **one shared backend** and add a **Pathly adapter** in front of it.

That means:

- Bright Sky remains the orchestration core
- Chrome extension becomes one client adapter
- Pathly Studio becomes another client adapter
- both clients speak a shared message schema

### Why this is better than a Pathly-only backend

- avoids duplicated orchestration logic
- keeps tool handling consistent
- makes future shared sessions possible
- lowers maintenance cost
- makes Chrome and Pathly interoperable later

## Proposed Architecture

### Client layer

Each client should send a normalized envelope such as:

```ts
{
  type: 'user_message',
  requestId: string,
  sessionId?: string,
  content: string,
  context: {
    source: 'chrome-extension' | 'pathly-studio',
    currentUrl?: string,
    pageTitle?: string,
    pageElements?: unknown[],
    appContext?: {
      projectPath?: string,
      activeFeature?: string,
      activePlan?: string,
      selectedTab?: string,
      studioSchema?: unknown[]
    }
  },
  capabilities: {
    canAnalyzeDom: boolean,
    canExecuteToolCalls: boolean,
    canStreamThinking: boolean
  },
  metadata: Record<string, unknown>
}
```

### Backend layer

The backend should:

- normalize all client payloads into one internal request model
- decide whether DOM/page context is needed
- stream progress/reasoning to the client
- call frontend tools when supported
- fall back cleanly when a client does not support a capability

### Pathly Studio adapter

Pathly Studio should add:

- context collection before send
- capability handshake after connect
- `tool_call` / `tool_response` handling
- backend thinking indicator
- richer error and reconnect handling

## Product Idea

This can become a shared “workspace intelligence” platform:

- Chrome extension is the browser lens
- Pathly Studio is the workspace lens
- Bright Sky is the reasoning/orchestration brain
- both clients can share sessions, context, and action history

That is a stronger product than two separate backends because it creates one memory model and one action model across surfaces.

## Practical Next Step

If you want to move forward safely, I would do this in order:

1. Define the shared message contract
2. Add a capability handshake to Pathly Studio
3. Add tool-call support in Pathly Studio
4. Add structured context forwarding from Pathly Studio
5. Keep the Bright Sky backend as the shared orchestrator

## Final Recommendation

Do **not** clone Bright Sky into a Pathly-only backend unless you discover a hard blocker. The better architecture is one shared backend, multiple adapters, shared session semantics, and explicit capability negotiation.
