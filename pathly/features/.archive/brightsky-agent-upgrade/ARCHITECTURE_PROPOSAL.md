---
name: Architecture Proposal
---
# BrightSky Agent Upgrade — Architecture Proposal

## Problem Statement

BrightSky treats Pathly Studio as a generic chat source enriched with a system prompt. It cannot actively read plan state beyond the initial context envelope, cannot affect the workspace (create plans, run skills, navigate panels), and uses synthetic (fake) thinking steps instead of real reasoning. The HQ chat panel has a `ThinkingBlock` component already wired for Claude reasoning but BrightSky messages never populate it.

## Proposed Solution

Three parallel improvements that each stand alone and compose cleanly:

1. **Studio bridge expansion** — 6 new tool handlers in `studioAnalyzer.ts` using existing IPC channels; matching tool classes on the BrightSky backend
2. **Reasoning box integration** — one-line fix in `brightskyClient.ts` at `stream_end` to call `splitThinkingContent()`, matching how Conductor (Claude) already works
3. **Real extended thinking** — Pathly messages get `thinking: { type: 'enabled' }` on the Claude API call; thinking content blocks are routed to Studio as `<think>`-wrapped stream_chunks before visible text

## Layer Breakdown

```
BrightSky backend (brightsky-ai)
  PathlyRouterService             ← routes on context.source === 'pathly-studio'
       │
       ▼
  PathlyContextBuilderService     ← injects system prompt with stage/stories
       │
       ▼
  WsMessageHandler                ← processUserMessage() with customInstructions
       │
       ▼
  Claude API call                 ← CHANGE: add thinking:{type:'enabled'} for pathly_chat
       │  thinking content blocks ← stream as <think>...</think> stream_chunks (Phase 12)
       │  text content blocks     ← stream as regular stream_chunks
       ▼
  StudioBridgeTool subclasses     ← CHANGE: add 6 new classes (Phase 9)
       │  tool_call WebSocket     ← 30s timeout, same pattern as existing tools
       ▼
Pathly Studio (pathly-adapters)
  brightskyClient.ts              ← CHANGE: splitThinkingContent at stream_end (Phase 8)
       │
       ▼
  executeStudioTool()             ← studioAnalyzer.ts
       │  CHANGE: 6 new handlers  ← Phases 1-5, 7
       ▼
  window.pathly.fs.*              ← existing IPC — list, listDirs, read, write
  window.pathly.fsm.runSkill      ← NEW IPC channel (Phase 6-7) → POST /runner/start
  window.__pathlyNavigate         ← existing renderer function
       │
       ▼
  ThinkingBlock.tsx               ← no change needed; msg.thinking populated by Phase 8
```

## Key Design Decisions

### Decision 1: Extend the WebSocket tool bridge, not add a separate MCP server
- **Options**: A) Expand existing WebSocket tool bridge  B) Run a separate MCP server sidecar in Studio
- **Chosen**: A
- **Rationale**: The tool bridge is already working and tested. A sidecar adds process management, port allocation, and restart logic. The bridge pattern scales to any number of tools — just add a class on the backend and a handler on the Studio side. If other apps (Cursor, Codex) need the same tools, they can implement their own tool bridge with the same `toolName` strings.

### Decision 2: `splitThinkingContent` called only at stream end, not mid-stream
- **Options**: A) Parse `<think>` tags on every chunk  B) Parse only at stream_end/isDone
- **Chosen**: B
- **Rationale**: The `<think>` block may be split across multiple chunks. Parsing mid-stream would require a stateful parser. The existing `finishAssistantStream()` pattern for Conductor already works this way — accumulate full text, then split. Consistency matters here.

### Decision 3: `<think>` tag wrapping, not a new message type
- **Options**: A) New `thinking_chunk` WebSocket message type  B) Wrap in `<think>...</think>` tags inside `stream_chunk`
- **Chosen**: B
- **Rationale**: The Studio side already has `thinkingParser.ts` that handles `<think>` tags. Using the existing mechanism means zero UI changes — no new message type handler, no new store field. The thinking content arrives naturally in the existing stream and is extracted at the end.

### Decision 4: One new IPC channel only (`fsm:runSkill`)
- **Rationale**: All read/write tools (`list_plans`, `get_events`, `get_failures`, `create_plan`, `navigate_to`) work with the existing `window.pathly.fs.*` and `window.__pathlyNavigate` APIs. The only tool that requires main-process access (to avoid CORS on the FSM HTTP call) is `run_skill`. Keeping new IPC channels to a minimum reduces preload surface area.

## Key Components

| Component | New/Modified | What it does |
|---|---|---|
| `studioAnalyzer.ts` | Modified | +6 new tool handler functions; +6 entries in studioTools registry |
| `fsm.ts` (main IPC) | Modified | +1 new IPC handler `fsm:runSkill` |
| `preload/index.ts` | Modified | Exposes `window.pathly.fsm.runSkill` |
| `global.d.ts` | Modified | Types `window.pathly.fsm.runSkill` |
| `brightskyClient.ts` | Modified | `stream_end`/`isDone` calls `splitThinkingContent` |
| `studio-bridge-tool.ts` | Modified | +6 new StudioBridgeTool subclasses |
| `mcp.module.ts` | Modified | Registers 6 new tools |
| Claude API call file | Modified | Adds `thinking` param for pathly_chat |
| `reasoning-timer.service.ts` | Modified | Guard: skip synthetic steps for pathly_chat |

## Risks

- **`fs:write` parent mkdir**: The existing `window.pathly.fs.write` IPC may not create parent directories. This would silently fail for `studio.create_plan`. **Mitigation**: Phase 4 explicitly checks `fs.ts` and fixes if absent — low risk, easy to verify.
- **Extended thinking model support**: If the BrightSky backend is not using a Claude model that supports `thinking` (or using an older SDK version), Phase 11 will throw. **Mitigation**: Phase 11 wraps in try/catch and falls back to standard call — reasoning box simply won't appear.
- **Thinking block ordering**: If the backend sends text stream_chunks before `<think>` content, the ThinkingBlock will not appear (it requires thinking content to arrive before `stream_end`). **Mitigation**: Phase 12 explicitly sends the `<think>` chunk first, before any text content block.
