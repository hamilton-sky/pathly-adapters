# Chat/Automate Mode Toggle — Architecture Proposal

## Problem Statement

The `AutomationCard` + `StepQueue` + `automationStore` + Playwright executor are all built and
functional, but the pipeline that feeds them is missing. The chat flow never generates a
structured action plan — `isAutomationIntent` is defined but unused, and `automationStore.setSteps()`
is never called from `handleSend()`. The AutomationCard is an orphan UI.

This feature closes that gap with the simplest possible addition: an explicit mode toggle that
routes the LLM call and its response handling down the correct path.

## Proposed Solution

A `chatMode: 'chat' | 'automate'` field in `chatStore`. The toggle pill in `ChatInput` sets it.
`handleSend` branches on it. No new files, no new IPC, no new stores — just a new branch in
the existing send flow.

## Layer Breakdown

```
ChatInput (renderer — UI layer)
     │  onClick → chatStore.setChatMode('automate')
     ▼
chatStore.ts (renderer — state layer)
     │  chatMode: 'chat' | 'automate'
     ▼
ChatPanel/index.tsx (renderer — orchestration layer)
     │  handleSend reads chatMode once at start
     │
     ├─ chatMode === 'chat'  ──────────────────────────► existing flow (unchanged)
     │                                                   matchIntent → MatchCard
     │                                                   buildSystemPrompt → LLM → chat bubble
     │
     └─ chatMode === 'automate' ──────────────────────► new branch
          │  setCurrentMatch(null), setAltMatches([])
          │  buildAutomationPrompt(studioSchema)
          │  LLM call (Ollama or node-llama-cpp, same IPC)
          │  on done: parseAutomationResponse(fullText)
          │     ├─ success: automationStore.reset() + setSteps() + updateLastMessage({ automationPlan })
          │     └─ failure: updateLastMessage({ content: fullText })  [plain text fallback]
          ▼
     AutomationCard (existing) ← renders when msg.automationPlan exists
     StepQueue (existing) ← reads automationStore.steps
     PlaywrightExecutor (existing) ← executes approved steps
```

## Key Design Decisions

### Decision 1: Explicit toggle, not intent detection
- **Options considered**: regex detection (`isAutomationIntent`), LLM classification, explicit toggle
- **Chosen**: Explicit toggle
- **Rationale**: Regex fires on ambiguous phrases ("create a new step" in a planning conversation). LLM classification adds a round-trip. Explicit toggle is zero-latency, zero-false-positives, and immediately understandable to the user. The `isAutomationIntent` regex is removed.

### Decision 2: Mode read once at send, not reactive during stream
- **Options considered**: Read mode reactively via hook, read via `getState()` at send time
- **Chosen**: `useChatStore.getState().chatMode` read once at the start of `handleSend`
- **Rationale**: The mode that was active when the user pressed Send is the correct mode for that message. Reactive reading would allow the mode to change mid-stream, producing partially-handled responses.

### Decision 3: JSON fallback to chat, not crash
- **Options considered**: Show error, crash, show chat response
- **Chosen**: Show plain text as chat message
- **Rationale**: Small local models may not reliably follow JSON prompts 100% of the time. A safe fallback keeps the UX recoverable — user sees the response and can retry.

### Decision 4: No streaming JSON parsing
- **Options considered**: Parse incrementally as tokens arrive, parse only on done
- **Chosen**: Parse only on `done`
- **Rationale**: Partial JSON is unparseable. Attempting incremental parse would require a custom JSON streaming library. Parse-on-done is correct and simple. The streaming dots already indicate progress.

## Key Components

| Component | Status | Role in this feature |
|---|---|---|
| `chatStore.chatMode` | NEW | Source of truth for current mode |
| `ChatInput` toggle pill | NEW | User-facing mode switch |
| `buildAutomationPrompt()` | NEW | Constructs JSON-request system prompt with studioSchema |
| `parseAutomationResponse()` | NEW | Parses LLM JSON response, assigns step IDs |
| `AutomationCard` | EXISTING — no changes | Renders when `msg.automationPlan` is set |
| `StepQueue` | EXISTING — no changes | Reads `automationStore.steps` |
| `automationStore` | EXISTING — no changes | `setSteps()` + `reset()` called from new branch |
| `playwrightExecutor` | EXISTING — no changes | Executes steps on approval |

## Risks

- **Model JSON compliance**: Small models (phi-4-mini, deepseek-r1:1.5b) may not consistently follow the JSON schema. Mitigation: JSON fallback to chat display; user can retry or switch to a larger model (qwen3-4b is recommended for automation).
- **studioSchema staleness**: If Studio UI labels change, generated steps will use wrong labels. Mitigation: existing Playwright executor error handling; fix is to update `studioSchema.ts` (one file).
