# Chat/Automate Mode Toggle — Architecture Proposal

## Problem Statement

The `AutomationCard` + `StepQueue` + `automationStore` + Playwright executor are all built and
functional, but the pipeline that feeds them is missing. The chat flow never generates a
structured action plan — `isAutomationIntent` is defined but unused, and `automationStore.setSteps()`
is never called from `handleSend()`. The AutomationCard is an orphan UI.

This feature closes that gap with the simplest possible addition: an explicit mode toggle that
routes the LLM call and its response handling down the correct path. A named action registry
(Conv 3) then lifts the step vocabulary from brittle raw labels to stable, parameterized action names.

## Proposed Solution

A `chatMode: 'chat' | 'automate'` field in `chatStore`. The toggle pill in `ChatInput` sets it.
`handleSend` branches on it. A `pathlyActionRegistry.ts` maps named actions to concrete Playwright
steps so the LLM picks from a stable vocabulary instead of inventing raw element labels.

## Layer Breakdown

```
ChatInput (renderer — UI layer)
     |  onClick -> chatStore.setChatMode('automate')
     v
chatStore.ts (renderer — state layer)
     |  chatMode: 'chat' | 'automate'
     v
ChatPanel/index.tsx (renderer — orchestration layer)
     |  handleSend reads chatMode once at start
     |
     +-- chatMode === 'chat'  -> existing flow (unchanged)
     |                          matchIntent -> MatchCard
     |                          buildSystemPrompt -> LLM -> chat bubble
     |
     +-- chatMode === 'automate' -> new branch
          |  setCurrentMatch(null), setAltMatches([])
          |  buildAutomationPrompt()   [uses REGISTRY_PROMPT_BLOCK]
          |  LLM call (Ollama or node-llama-cpp, same IPC)
          |  on done: parseAutomationResponse(fullText)
          |     +-- success: expandAction() per step -> concrete AutomationStep[]
          |     |            automationStore.reset() + setSteps()
          |     |            updateLastMessage({ automationPlan })
          |     +-- failure: updateLastMessage({ content: fullText })  [chat fallback]
          v
     AutomationCard (existing) <- renders when msg.automationPlan exists
     StepQueue (existing) <- reads automationStore.steps
     PlaywrightExecutor (existing) <- executes approved steps

pathlyActionRegistry.ts (new — Conv 3)
     PATHLY_ACTIONS[]     -> named action defs with {{param}} templates
     expandAction(name, params) -> concrete step array
     REGISTRY_PROMPT_BLOCK -> LLM vocabulary string injected into buildAutomationPrompt
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

### Decision 5: Named action registry over raw click/fill/select (Conv 3)
- **Options considered**: Keep raw `{ type: "click", label: "Run Storm" }` steps; introduce a registry
- **Chosen**: Named action registry (`pathlyActionRegistry.ts`)
- **Rationale**: Raw label steps are brittle — a single label rename in Studio breaks every past automation. The registry decouples the LLM vocabulary (stable action names like `pathly_run_storm`) from the Playwright implementation (editable step arrays in one file). The LLM picks from a documented, constrained list; `expandAction` resolves params and produces the concrete steps. Inspired by the stepper framework's pattern of named compound actions backed by Page Object methods.

### Decision 6: Template params in registry steps
- **Options considered**: Separate step array per param combination; `{{param}}` templates
- **Chosen**: `{{paramName}}` template strings in step `value` fields
- **Rationale**: Allows parameterized actions (e.g., `pathly_plan_feature(featureName)`) without duplicating step definitions. `expandAction` resolves them at parse time before steps reach the executor.

## Key Components

| Component | Status | Role in this feature |
|---|---|---|
| `chatStore.chatMode` | NEW — Conv 1 | Source of truth for current mode |
| `ChatInput` toggle pill | NEW — Conv 1 | User-facing mode switch |
| `pathlyActionRegistry.ts` | NEW — Conv 3 | Named action defs, param templates, expandAction |
| `buildAutomationPrompt()` | NEW — Conv 2, updated Conv 3 | Prompt with registry vocabulary |
| `parseAutomationResponse()` | NEW — Conv 2, updated Conv 3 | JSON parser + expandAction per step |
| `AutomationCard` | EXISTING — no changes | Renders when `msg.automationPlan` is set |
| `StepQueue` | EXISTING — no changes | Reads `automationStore.steps` |
| `automationStore` | EXISTING — no changes | `setSteps()` + `reset()` called from new branch |
| `playwrightExecutor` | EXISTING — no changes | Executes steps on approval |

## Risks

- **Model JSON compliance**: Small models (phi-4-mini, deepseek-r1:1.5b) may not consistently follow the JSON schema. Mitigation: JSON fallback to chat display; user can retry or switch to a larger model (qwen3-4b is recommended for automation).
- **Registry coverage gaps**: If a user asks for a flow that has no matching named action, `expandAction` returns null and the step is silently skipped, producing an empty plan (fallback to chat). Mitigation: expand the registry as new flows are needed — one entry per action.
- **studioSchema staleness (Conv 2 only)**: Raw labels in the Conv 2 prompt can drift if Studio UI changes. Fully resolved in Conv 3 when the registry becomes the single source of truth for labels.
