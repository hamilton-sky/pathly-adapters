# AI-Assisted Flow Wizard - Progress

## Status: PLAN UPDATED - IMPLEMENTATION NOT STARTED

The previous Chat/Automate Playwright plan has been superseded after inspection of the live wizard and FlowEditor schema handling.

## Story status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | Wizard represents shipped Pathly flows | Conv 1-2 | TODO |
| S2 | Full-flow validation before save | Conv 1-2 | TODO |
| S3 | LLM creates structured drafts inside wizard | Conv 3 | TODO |
| S4 | Draft failure preserves user work | Conv 3 | TODO |
| S5 | Draft/review status is clear | Conv 4 | TODO |

## Conversation status

| Conv | Work package | Status | Verification focus |
|---|---|---|---|
| 1 | Canonical model, serialization, validation, LLM bridge prerequisite | TODO | Focused tests plus TypeScript baseline repair |
| 2 | Full-schema wizard fields and round-trip behavior | TODO | Representative shipped-flow round trip |
| 3 | AI draft panel and structured generation | TODO | Valid/invalid/abort generation tests |
| 4 | Review UX, integration verification, regression checks | TODO | Manual happy flow plus relevant automated suite |

## Verified baseline observations

- The existing wizard does not serialize all fields used by shipped flows.
- FlowEditor already handles `role_map` and `transition_actions` in graph/validation logic.
- Current TypeScript verification is not a clean zero-error baseline because `llmBridge.ts` passes a fourth argument to `ollamaChat` while its declared surface accepts three.

## Blocked by

Nothing for planning. Conversation 1 must resolve or accurately record the LLM bridge type contract before AI generation is accepted.
