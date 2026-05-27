# Chat/Automate Mode Toggle — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | Mode toggle pill in footer | Conv 1 | TODO |
| S1.2 | chatMode field in chatStore | Conv 1 | TODO |
| S2.1 | Automation system prompt with studioSchema | Conv 2 | TODO |
| S2.2 | JSON response parsed into AutomationCard | Conv 2 | TODO |
| S2.3 | Parsed steps wired to automationStore | Conv 2 | TODO |
| S2.4 | Chat mode unaffected (no regression) | Conv 2 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | Pre-flight, 1, 2 | S1.1, S1.2 | TODO | `cd studio && npx tsc --noEmit` |
| 2 | 3, 4 | S2.1, S2.2, S2.3, S2.4 | TODO | `cd studio && npx tsc --noEmit` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | Pre-flight | `ChatPanel/index.tsx` | Verify isAutomationIntent unused, baseline TS check | 0 TS errors recorded | TODO |
| 1 | 1 | `store/chatStore.ts` | Add chatMode field + setChatMode action | useChatStore returns chatMode without TS errors | TODO |
| 1 | 2 | `ChatInput.tsx` + `ChatInput.module.css` | Mode toggle pill in footer | Pill renders, clicking updates store, active styling works | TODO |
| 2 | 3 | `ChatPanel/index.tsx` | Automation system prompt branch | Automate mode sends different prompt; chat mode unchanged | TODO |
| 2 | 4 | `ChatPanel/index.tsx` | Parse JSON response + wire stores | AutomationCard appears; automationStore.steps populated | TODO |

## Prerequisites
- [x] `automationStore.ts` exists with `setSteps` and `reset`
- [x] `AutomationCard` renders when `msg.automationPlan` is set
- [x] `buildPathlyContext()` returns `studioSchema`
- [ ] Baseline TS errors recorded (run in pre-flight)

## Blocked By
- Nothing
