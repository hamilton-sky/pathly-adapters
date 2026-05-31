# Brightsky ↔ Pathly Integration — Full Specification

**Date:** 2026-05-31  
**Author:** Architecture review  
**Status:** Draft — awaiting implementation prioritization

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [What the Backend Expects](#3-what-the-backend-expects)
4. [Studio Frontend Gaps](#4-studio-frontend-gaps)
5. [Unified Message Contract](#5-unified-message-contract)
6. [Studio Analyzer — The Missing Pattern](#6-studio-analyzer--the-missing-pattern)
7. [Backend: PathlyModule](#7-backend-pathlymodule)
8. [System Prompt Architecture](#8-system-prompt-architecture)
9. [Product Vision — Cross-Surface Developer AI](#9-product-vision--cross-surface-developer-ai)
10. [Build Sequence](#10-build-sequence)
11. [Comparison to Existing Assessment](#11-comparison-to-existing-assessment)
12. [Open Questions](#12-open-questions)

---

## 1. Executive Summary

Pathly Studio can already connect to the Brightsky backend at the transport level (WebSocket + OAuth working). The gap is at the application layer: Studio sends only a bare text message with no workspace context, and the backend has no Pathly-specific routing module, system prompt builder, or tool definitions.

**Decision: one shared backend, multiple client adapters.**  
Do not clone Brightsky into a Pathly-only backend. The right architecture is:

```
Chrome Extension  ──┐
                    ├──▶  Brightsky Backend (NestJS, shared orchestration)
Pathly Studio     ──┘         ├── AgentsModule (existing)
                              ├── McpModule (existing)
                              ├── WorkflowModule (existing)
                              └── PathlyModule  ← NEW
```

This gives you one memory model, one agent pipeline, and a future path to cross-surface sessions where Chrome and Pathly share context.

---

## 2. Current State Analysis

### 2.1 What Pathly Studio sends today

```ts
// Session creation (first message)
{
  type: 'create_session_with_message',
  payload: {
    userMessage: { content: string, role: 'user' }
  }
}

// Subsequent messages
{
  type: 'user_message',
  content: string,
  sessionId: string
}
```

**Source files:**
- [`studio/src/renderer/src/lib/brightskyClient.ts`](studio/src/renderer/src/lib/brightskyClient.ts)
- [`studio/src/renderer/src/components/ChatPanel/index.tsx`](studio/src/renderer/src/components/ChatPanel/index.tsx)

**What is missing from every outbound message:**

| Field | Available in Studio? | Sent to backend? |
|---|---|---|
| `messageType` (routing hint) | No | No |
| `activeFeature` (current plan) | Yes — from FSM | No |
| `fsmStage` (STORM/BUILD/REVIEW…) | Yes — from FSM | No |
| `activePlan` (USER_STORIES, IMPL_PLAN) | Yes — filesystem | No |
| `availableSkills` | Yes — from pathlyContext | No |
| `studioSchema` (open panels, state) | Yes — from pathlyContext | No |
| `capabilities` (tool bridge support) | No | No |
| `customInstructions` | No | No |

**Key insight:** `pathlyContext` is built in `ChatPanel/index.tsx` (lines 296–313) and used only for local LLM system prompts. It is never forwarded to Brightsky.

### 2.2 Transport layer — what works

| Feature | Status |
|---|---|
| WebSocket connection | ✓ Working |
| Google OAuth + token exchange | ✓ Working |
| JWT auto-refresh (60s before expiry) | ✓ Working |
| `stream_chunk` accumulation and display | ✓ Working |
| `session_created` → sessionId storage | ✓ Working |
| Connection status badge | ✓ Working |
| Model selector with Brightsky option | ✓ Working |

Transport is solid. Everything above this layer needs work.

### 2.3 What the Chrome extension sends (for comparison)

```ts
{
  type: 'user_message',
  content: string,
  messageType: 'chat' | 'page_summary' | 'page_research' | 'workflow_generate',
  metadata: {
    pageUrl: string,
    pageTitle: string,
    pageText: string,
    semanticPage: { structure, regions, actionElements },
    userIntent?: string,
    selection?: { text, html, position },
    calendarToken?: string
  }
}
```

The extension sends rich context. Pathly sends bare text. Both hit the same `UnifiedChatGateway`.

---

## 3. What the Backend Expects

### 3.1 Routing fields (UnifiedChatGateway)

The backend's message router reads:
- `messageType` → selects agent (generic chat / page research / workflow / deep research)
- `currentUrl` / `pageTitle` → injects page awareness into system prompt
- `metadata.semanticPage` → DOM structure for tool-using agents
- `customInstructions` → per-session system prompt injection
- `conversationHistory` → multi-turn context

When none of these are present the backend falls back to the generic chat agent with an empty system prompt. That is why Brightsky feels generic in Studio today.

### 3.2 Backend → client message types (what Studio must handle)

| Message type | Backend sends it? | Studio handles it? |
|---|---|---|
| `stream_chunk` | Yes | ✓ Yes |
| `session_created` | Yes | ✓ Yes |
| `stream_end` | Yes | ✓ Yes |
| `typing_metadata` | Yes (`label`, `phase`) | ✗ Ignored |
| `tool_call` | Yes (`callId`, `toolName`, `parameters`) | ✗ No handler |
| `agent_response` with `metadata.sources` | Yes | ✗ Sources not rendered |
| `partial_response` | Yes (alias of stream_chunk) | ✗ No handler |
| `processing_status` | Yes | ✗ Ignored |

The most impactful single fix: handle `typing_metadata`. Backend already sends "Analyzing page…", "Searching the web…" etc. — Studio just drops them on the floor.

---

## 4. Studio Frontend Gaps

### 4.1 Gap inventory

| Gap | Impact | Effort |
|---|---|---|
| No `typing_metadata` handler | User sees silence while backend thinks | Low — 1 afternoon |
| No context forwarding | Backend has no workspace awareness | Medium — 1–2 days |
| No capability handshake | Backend can't adapt behavior per client | Low — half day |
| No `tool_call` / `tool_response` round-trip | Backend can't query Studio state | High — 3–4 days |
| No backend thinking indicator | No visibility into reasoning phases | Low-Medium — 1 day |
| No source citations rendering | Research results lose citations | Low-Medium — 1 day |
| No reconnect with backoff | Disconnect = dead session | Low-Medium — 1 day |

### 4.2 What the thinking indicator needs

Studio already has a thinking block component (used for local LLM `<think>` parsing). The same component should activate for Brightsky when:

```
{ type: 'typing_metadata', label: 'Analyzing your plan…', phase: 'planning' }
  → show thinking indicator with label
{ type: 'stream_chunk', chunk: '...' }
  → hide thinking indicator, start streaming
```

Zustand store needs one new field: `brightskyThinkingLabel: string | null`.

### 4.3 Tool call round-trip (the hard gap)

```
Backend sends:
  { type: 'tool_call', callId: 'abc', toolName: 'get_fsm_state', parameters: {} }

Studio must:
  1. Receive and parse tool_call
  2. Execute the tool locally (see StudioAnalyzer section)
  3. Send back:
     { type: 'tool_response', callId: 'abc', payload: { result, success } }

UI should show:
  "Using tool: get_fsm_state…" while waiting for local execution
```

This requires a `tool_call` handler in `brightskyClient.ts` and an IPC bridge to execute tools that need main-process access.

---

## 5. Unified Message Contract

Both Chrome extension and Pathly Studio should send this normalized envelope:

```ts
interface BrightskyClientMessage {
  type: 'user_message';
  requestId: string;           // client-generated UUID per message
  sessionId?: string;          // omit on first message
  content: string;             // user's text

  context: {
    source: 'chrome-extension' | 'pathly-studio';

    // Chrome extension fields
    currentUrl?: string;
    pageTitle?: string;
    pageText?: string;
    semanticPage?: {
      structure: unknown;
      regions: unknown[];
      actionElements: unknown[];
    };
    selection?: { text: string; html: string; position: unknown };

    // Pathly Studio fields
    appContext?: {
      projectPath?: string;
      activeFeature?: string;          // e.g. "payment-integration"
      fsmStage?: string;               // e.g. "BUILD"
      activeConversation?: number;     // e.g. 2
      totalConversations?: number;     // e.g. 3
      activePlan?: {
        userStories?: string;          // USER_STORIES.md contents (trimmed)
        implementationPlan?: string;   // IMPLEMENTATION_PLAN.md contents (trimmed)
        nextUncompletedStory?: string;
      };
      availableSkills?: string[];
      openPanels?: string[];
      selectedTab?: string;
    };
  };

  capabilities: {
    canAnalyzeDom: boolean;        // Chrome: true; Studio: false (Phase 1), true (Phase 3)
    canExecuteToolCalls: boolean;  // Chrome: true; Studio: false (Phase 1), true (Phase 3)
    canStreamThinking: boolean;
    supportedToolTypes?: string[]; // e.g. ['studio_analyzer']
  };

  messageType?: 'pathly_chat' | 'chat' | 'page_research' | 'workflow_generate';
  customInstructions?: string;
  metadata?: Record<string, unknown>;
}
```

### 5.1 Capability handshake

Send this once after WebSocket connection is established:

```ts
{
  type: 'client_capabilities',
  source: 'pathly-studio',
  capabilities: {
    canAnalyzeDom: false,
    canExecuteToolCalls: false,   // true in Phase 3
    canStreamThinking: true,
    supportedToolTypes: []        // ['studio_analyzer'] in Phase 3
  },
  version: '1.0'
}
```

Backend stores this against the session and adapts which tools it calls.

---

## 6. Studio Analyzer — The Missing Pattern

The Chrome extension has `PageAnalyzer`: a browser-side executor that lets the backend request DOM info via `tool_call` / `tool_response`. Pathly Studio needs the equivalent for the developer workspace.

### 6.1 Tool definitions

| Tool | Input | Output |
|---|---|---|
| `get_fsm_state` | `{}` | `{ stage, feature, rigor, conversationIndex, totalConversations }` |
| `get_feature_plan` | `{ sections?: string[] }` | `{ userStories, implementationPlan, progressTable }` |
| `get_active_conversations` | `{}` | `{ done: string[], todo: string[] }` |
| `get_available_skills` | `{}` | `{ skills: [{ name, description }] }` |
| `get_studio_schema` | `{}` | `{ openPanels, selectedTab, visibleFeatures, monitorState }` |
| `advance_fsm_stage` | `{}` | `{ previousStage, newStage, success }` |
| `run_skill` | `{ skillName: string, args?: string }` | `{ output: string, success: boolean }` |

### 6.2 Execution architecture

```
Backend sends:
  { type: 'tool_call', callId: 'xyz', toolName: 'get_fsm_state', parameters: {} }

StudioAnalyzer (renderer process):
  - receives tool_call via brightskyClient.ts handler
  - looks up toolName in StudioToolRegistry
  - executes locally:
      filesystem reads → via IPC ('pathly:get-fsm-state')
      UI state reads → directly from Zustand stores
  - sends:
    { type: 'tool_response', callId: 'xyz',
      payload: { result: { stage: 'BUILD', feature: 'payment-integration' }, success: true } }

IPC handlers needed in main process (brightsky.ts):
  'pathly:get-fsm-state'       → reads pathly/plans/<feature>/STATE.json
  'pathly:get-feature-plan'    → reads USER_STORIES.md, IMPLEMENTATION_PLAN.md
  'pathly:get-conversations'   → reads PROGRESS.md
  'pathly:advance-stage'       → calls pathly-ff CLI
  'pathly:run-skill'           → shells out to pathly skill
```

### 6.3 Why this matters

With StudioAnalyzer, a conversation like this becomes possible:

> User: "What should I do next?"  
> Backend: calls `get_fsm_state` → BUILD, conv 2  
> Backend: calls `get_feature_plan` → next uncompleted story is S-04  
> AI: "You're in BUILD stage, conversation 2 of 3. The next story is S-04: validate webhook signatures. Your IMPLEMENTATION_PLAN says to implement it in `src/payments/webhook.ts`. Want me to start?"

Without StudioAnalyzer, the AI guesses from plain text context.

---

## 7. Backend: PathlyModule

### 7.1 New module structure

```
backend/src/pathly/
  pathly.module.ts
  pathly-context-builder.service.ts   ← system prompt from Pathly envelope
  pathly-tools.registry.ts            ← StudioAnalyzer tool definitions
  pathly-router.service.ts            ← routes pathly-studio messages
  pathly-session.service.ts           ← Pathly-specific session state
```

### 7.2 Routing change in UnifiedChatGateway

```ts
// existing routing
if (messageType === 'page_research') → PageResearchStrategy
if (messageType === 'workflow_generate') → WorkflowStrategy

// add
if (context?.source === 'pathly-studio') → PathlyRouterService
```

### 7.3 PathlyRouterService logic

```
1. Receive user_message with source: 'pathly-studio'
2. Call PathlyContextBuilder.build(message.context.appContext)
   → produces system prompt with workspace context
3. Check client capabilities:
   - canExecuteToolCalls: true → register StudioAnalyzer tools in this session
   - canExecuteToolCalls: false → text-only responses, no tool calls
4. Route to agent (initially: existing ChatAgent with enriched system prompt)
5. Stream response back
```

### 7.4 StudioAnalyzer tools on backend (MCP-registered)

Mirror of the Studio-side tools — registered in `ToolRegistry` under namespace `studio`:

```ts
studio.get_fsm_state      → sends tool_call to Studio, waits for tool_response
studio.get_feature_plan   → sends tool_call to Studio, waits for tool_response
studio.advance_fsm_stage  → sends tool_call to Studio, waits for tool_response
studio.run_skill          → sends tool_call to Studio, waits for tool_response
```

Uses the same `PageAnalyzerBridgeTool` pattern already in `backend/src/mcp/`.

---

## 8. System Prompt Architecture

### 8.1 PathlyContextBuilder output

When `source === 'pathly-studio'`, replace the generic system prompt with:

```
You are an AI coding assistant integrated into Pathly Studio, a structured 
feature-development pipeline for software engineers.

## Current workspace state
Active feature: {{activeFeature}}
Pipeline stage: {{fsmStage}} (conversation {{activeConversation}} of {{totalConversations}})
Project path: {{projectPath}}

## Feature context
### Next uncompleted story
{{nextUncompletedStory}}

### Acceptance criteria (from USER_STORIES.md)
{{userStoriesSummary}}   ← trimmed to ~2000 tokens

### Implementation plan
{{implementationPlanSummary}}   ← trimmed to ~1500 tokens

## Available Pathly actions
{{#if canExecuteToolCalls}}
You have access to these Studio tools:
- get_fsm_state: check current pipeline stage
- get_feature_plan: read full plan files
- advance_fsm_stage: move to next pipeline stage
- run_skill: invoke a Pathly skill (e.g. pathly-build, pathly-review)
{{/if}}

## Instructions
- Answer questions about the codebase and feature plan directly
- Suggest next steps based on the current pipeline stage
- When the user asks "what next", call get_feature_plan to read the current plan
- Do not invent plan details — use the tool to read actual files
```

### 8.2 Token budget for context

Plan files can be large. Trim strategy:
- USER_STORIES.md: include all story titles, full text of uncompleted ones only
- IMPLEMENTATION_PLAN.md: include only the active conversation's tasks
- PROGRESS.md: include done/todo counts and the first 3 TODO items
- Total injected context target: ≤ 4000 tokens

---

## 9. Product Vision — Cross-Surface Developer AI

### 9.1 The core insight

| Surface | Lens | What it sees |
|---|---|---|
| Chrome extension | Browser | What the user is reading / browsing |
| Pathly Studio | Workspace | What the user is building |
| Brightsky backend | Brain | Both — one reasoning model across surfaces |

With a shared session, the AI can connect signals neither surface sees alone:

- "You're on the Stripe Webhooks docs (Chrome sees it). You're in BUILD stage of `payment-integration`, next story is webhook signature validation (Pathly sees it). Want me to implement it based on this page?"
- "You just pushed to review. The Stripe rate-limits page you had open might be relevant to the test failures — want me to factor that in?"
- "Welcome back — you closed your laptop yesterday mid-feature. Your next task is S-04, here's where you left off."

### 9.2 Shared session architecture

```
Chrome Extension ──┐   sessionId: "sess_abc"
                   ├──▶ Brightsky Backend ──▶ Shared session store
Pathly Studio    ──┘   sessionId: "sess_abc"      (Redis/Postgres)
                                                    ├── conversation history
                                                    ├── Chrome context (last page)
                                                    └── Pathly context (last feature state)
```

Linkage options (Phase 4 design decision):
- **Option A:** QR code / link from Studio that Chrome extension picks up
- **Option B:** Same Google account → auto-link latest Studio session to Chrome session
- **Option C:** Explicit "connect to Studio" button in Chrome extension

### 9.3 Why this is differentiated

No AI tool today bridges "what you're researching" and "what you're building" in real time. The closest is Copilot with browser context, but it's tab-scoped. A persistent cross-surface session with a structured pipeline (Pathly FSM) behind it is a qualitatively stronger product.

---

## 10. Build Sequence

### Phase 1 — Make Studio a proper Brightsky client (2–3 days)

Goal: backend becomes workspace-aware without any backend changes.

1. **Handle `typing_metadata`** in `brightskyClient.ts`  
   → Add `brightskyThinkingLabel: string | null` to brightskyStore  
   → Show labeled thinking indicator in ChatPanel while label is set  

2. **Forward `pathlyContext` in every `user_message`**  
   → Read FSM state + feature name from existing `pathlyContext` builder  
   → Add `context.appContext` to outbound envelope  
   → Add `messageType: 'pathly_chat'` to outbound messages  

3. **Capability handshake on connect**  
   → Send `client_capabilities` immediately after `session_created`  
   → Phase 1 values: `canExecuteToolCalls: false`, `canStreamThinking: true`  

4. **Reconnect with exponential backoff**  
   → On `ws.onclose`: attempt reconnect at 1s, 2s, 4s, 8s, 16s, then stop  
   → Restore `sessionId` from store on reconnect  

**Acceptance criteria:**
- Brightsky chat in Studio shows "Analyzing…" while backend is thinking
- Backend system logs show `appContext` present with feature + FSM stage
- Disconnect does not require app restart to reconnect

### Phase 2 — PathlyModule on backend (3–5 days)

Goal: backend routes Pathly messages to a workspace-aware agent.

1. Add `PathlyModule` to NestJS app  
2. `PathlyContextBuilder.build()` constructs system prompt from `appContext`  
3. `UnifiedChatGateway` routes `source === 'pathly-studio'` → PathlyRouterService  
4. PathlyRouterService passes enriched system prompt to existing ChatAgent  
5. Studio shows meaningfully different (plan-aware) responses  

**Acceptance criteria:**
- "What should I do next?" returns the actual next story from the plan
- System prompt contains active feature name and FSM stage
- Generic chat behavior still works when no `appContext` provided

### Phase 3 — Studio Analyzer + tool bridge (5–7 days)

Goal: backend can query and act on Studio state.

1. Add `StudioToolRegistry` in renderer with 7 tool implementations  
2. Add IPC handlers in main process for filesystem reads  
3. Add `tool_call` handler in `brightskyClient.ts`  
4. Add `tool_response` sender  
5. Update capability handshake: `canExecuteToolCalls: true`, `supportedToolTypes: ['studio_analyzer']`  
6. Register StudioAnalyzer bridge tools in backend `ToolRegistry`  
7. Add tool-call UI state in ChatPanel ("Using tool: get_feature_plan…")  

**Acceptance criteria:**
- Backend can call `get_fsm_state` and receive accurate response
- Backend can call `advance_fsm_stage` and Studio pipeline advances
- `run_skill` executes a pathly skill and returns output

### Phase 4 — Cross-surface sessions (design sprint first)

Goal: Chrome extension and Pathly Studio share a session.

1. Design shared session linkage UX (option A/B/C from section 9.2)
2. Backend `SessionService` supports multi-client attachment  
3. Backend `ContextMergeService` merges page context + workspace context  
4. Action routing: browser actions → Chrome, workspace actions → Studio  
5. "Continue where you left off" experience across surfaces  

**Before starting Phase 4:** validate Phase 3 with real usage. The StudioAnalyzer tool quality determines whether cross-surface context is worth merging.

---

## 11. Comparison to Existing Assessment

[BRIGHTSKY_PATHLY_ASSESSMENT.md](BRIGHTSKY_PATHLY_ASSESSMENT.md) — written 2026-05-31.

| Assessment point | Verdict |
|---|---|
| Shared backend recommendation | ✓ Correct — fully agree |
| Envelope schema proposal | ✓ Correct — this spec extends it |
| Studio gaps: context, tool bridge, thinking UI, session contract | ✓ Correct |
| "Pathly adapter in front of shared backend" framing | ✓ Correct direction |

**What this spec adds beyond the assessment:**

1. **StudioAnalyzer tool set** — the assessment says "tool bridge" but doesn't define what tools Pathly exposes. This spec defines 7 concrete tools with inputs, outputs, and execution architecture.

2. **PathlyContextBuilder system prompt design** — the assessment doesn't address how the backend constructs prompts for Pathly requests. This spec defines the template, the token budget strategy, and the conditional tool-call section.

3. **PathlyModule file structure** — the assessment says "add a Pathly adapter" but doesn't specify what backend code to write. This spec gives the module structure and service responsibilities.

4. **Product vision detail** — the assessment mentions "shared workspace intelligence" in one paragraph. This spec defines the shared session architecture, linkage options, and why it's differentiated.

5. **Sequenced build plan** — the assessment gives 5 steps in order. This spec expands to 4 phases with acceptance criteria per phase.

The assessment is correct at the transport layer. This spec is the application-layer design that sits on top of it.

---

## 12. Open Questions

| Question | Decision needed by |
|---|---|
| Which shared session linkage option (QR, auto-link, button)? | Before Phase 4 |
| Should PathlyModule read plan files directly (backend reads filesystem via SSH/API) or always via StudioAnalyzer tool calls? | Before Phase 2 |
| Token budget for plan files in system prompt — 4000 tokens enough? | Before Phase 2 |
| `run_skill` tool — should it be fire-and-forget or wait for completion? Skills can take minutes. | Before Phase 3 |
| Should Chrome extension and Studio share conversation history or just context state? | Before Phase 4 |
| Authentication: does the shared session require same Google account, or explicit linking? | Before Phase 4 |
