---
name: Architecture Proposal
---
# Comms Board — Studio CommsPanel (Phase 2) — Architecture Proposal

## Problem Statement

The Phase 1 board is headless. We need a Studio UI that shows a feature's board live, lets the
human post and answer, and follows the strict Studio UI conventions — without coupling to the
runner lifecycle or duplicating the existing SSE/HTTP patterns.

## Proposed Solution

A thin three-layer slice that mirrors existing Studio patterns: a `commsApi` fetch service, a
`commsStore` Zustand store, and a docked `CommsPanel` component tree fed by a second SSE
subscription added in `useHQ`.

## Layer Breakdown

```
services/commsApi.ts        raw fetch → http://127.0.0.1:8765/comms/*       (no abstraction; .catch errors)
        │
store/commsStore.ts         Zustand: messages, board, scope, pendingCount   (chatStore pattern)
        │   ▲
        │   └── useHQ.tsx: EventSource('/events/comms?scope=<feature>') → appendMessage
        ▼
components/HQ/CommsPanel/    CommsPanel → BoardToggle + CommsMsgList → CommsMsgCard / CommsQuestionCard
                            + CommsInput   (CSS modules, data-type variants)
```

## Key Design Decisions

### Decision 1: Second EventSource, not a merged one
- **Options considered:** (A) add `/events/comms` as a separate `useEffect` EventSource, (B) multiplex comms events through the existing `/events/runner` stream
- **Chosen:** A
- **Rationale:** The runner stream is topic-scoped to the run lifecycle; the board is feature-scoped and outlives any single run. A separate subscription keyed on the active feature is cleaner and won't destabilize the existing runner handler chain (useHQ lines ~219–379).

### Decision 2: Raw fetch service, no IPC
- **Options considered:** (A) raw `fetch` to 127.0.0.1:8765 (the existing pattern), (B) a new `window.pathly` IPC channel
- **Chosen:** A
- **Rationale:** Studio already calls the FSM directly via `fetch` (`handleAgentAnswer`, terminal/started). The comms endpoints are plain HTTP; IPC would add main-process plumbing for no benefit.

### Decision 3: One store, board toggle drives queries
- **Options considered:** (A) single `commsStore` holding the currently-viewed board's messages, (B) three stores or a nested map per board
- **Chosen:** A
- **Rationale:** Phase 2 shows one board at a time. The toggle re-queries and replaces `messages`. Multi-board-at-once is Phase 4's command center, which can introduce a richer store then.

### Decision 4: Reuse AgentQuestionCard pattern
- **Options considered:** (A) a `CommsQuestionCard` mirroring `AgentQuestionCard`, (B) a brand-new question UI
- **Chosen:** A
- **Rationale:** The agent-question card already solves option rendering + answer callback with the project's CSS-module/data-attribute conventions. Mirroring it keeps the UI consistent and small.

### Decision 5: data-type variant styling
- **Options considered:** (A) `data-type={msg.type}` + CSS module attribute selectors, (B) conditional className cascades
- **Chosen:** A
- **Rationale:** Studio's own rule prefers `data-*` attributes for 3+ mutually-exclusive states; message types are an enum — a perfect fit.

## Key Components
- `services/commsApi.ts` — `postMessage`, `getMessages`, `searchMessages`, `answerQuestion`, `acknowledgeMessage`
- `store/commsStore.ts` — `messages`, `board`, `scope`, `pendingCount`; `appendMessage`/`setMessages`/`markRead`/`setBoard`/`clear`
- `components/HQ/CommsPanel/` — `CommsPanel`, `CommsMsgList`, `CommsMsgCard`, `BoardToggle`, `CommsInput`, `CommsQuestionCard`, `hooks/useCommsPanel`

## Interface Design
```ts
// commsApi.ts
postMessage(input: { feature: string; board?: Board; scope?: string; type: string; text: string; options?: Opt[] }): Promise<{ok: boolean; id?: string}>
getMessages(input: { feature: string; board?: Board; scope?: string }): Promise<CommsMessage[]>
answerQuestion(input: { question_id: string; answer: string; option_id?: string }): Promise<{ok: boolean}>

// commsStore.ts
type Board = 'feature' | 'project' | 'global'
interface CommsState { messages: CommsMessage[]; board: Board; scope: string; pendingCount: number; loading: boolean;
  appendMessage(m: CommsMessage): void; setMessages(m: CommsMessage[]): void; markRead(id: string): void; setBoard(b: Board, scope: string): void; clear(): void }
```

## Risks
- **Risk: SSE leak on topic change** → effect returns a cleanup that closes the EventSource; keyed on `activeTopic`.
- **Risk: optimistic + echo duplication** → `appendMessage` dedups by `id`; optimistic message uses the server id once the POST returns.
- **Risk: component bloat** → enforce the ~150-line cap; extract banners/ack into sub-components.
- **Risk: reintroducing the board/scope inversion** → the UI maps the toggle to `board` ∈ {feature,project,global} + the correct `scope`; never send the feature name as `board`.
