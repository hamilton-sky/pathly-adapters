# studio-monitor-live — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | FSM topology rail with sliding dot | Conv 1 | TODO |
| S2 | Execution trace below rail | Conv 1 | TODO |
| S3 | SSE live source badge | Conv 1 | TODO |
| S4 | Monitor tabs for concurrent flows | Conv 2 | TODO |
| S5 | Running-flow entry banner | Conv 2 | TODO |
| S6 | Plan conversation card enhancements | Conv 2 | TODO |
| S7 | Last-used flow on open + auto-open Monitor | Conv 2 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1, 2, 3 | S1, S2, S3 | TODO | `cd studio; npm run typecheck` |
| 2 | 4, 5, 6, 7 | S4, S5, S6, S7 | TODO | `cd studio; npm run typecheck` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File(s) | Description | Done when | Status |
|------|-------|---------|-------------|-----------|--------|
| 1 | 1 | `Monitor/FsmView.tsx`, `theme.ts` | Connected rail + CSS dot; confirm `t.runtime` | Dot slides to active state, loop snap-back works | TODO |
| 1 | 2 | `Monitor/FsmView.tsx`, `Monitor/utils.ts` | Execution trace + `formatRelativeTime` | Chronological visits, loop re-visits as extra rows | TODO |
| 1 | 3 | `Monitor/index.tsx` | SSE source badge (live/polling/—) | Old label removed; null→`—` works | TODO |
| 2 | 4 | `store/uiStore.ts`, `Monitor/index.tsx` | Multi-flow store + tab bar + SSE re-key | ≥2 sessions → tab bar; tab switch re-keys SSE | TODO |
| 2 | 5 | `FlowEditor/VisualView/index.tsx` | Running-flow banner + `setActivePanel` | Banner shows when 1 flow running; auto-dismisses 8s | TODO |
| 2 | 6 | `PlanBoard.tsx`, `types/index.ts`, `usePlanConversations.ts` | Plan card enhancements | Pulsing active, red failed, hover/selected, cost rows | TODO |
| 2 | 7 | `store/uiStore.ts`, `App.tsx` | Last-used flow + auto-open Monitor | Reopens to last flow; Monitor auto-opens if running | TODO |

## Prerequisites

- `studio-visual-flow-builder` Phase 7b complete (`FlowEditor/zIndex.ts` exists)
- `t.runtime` in `theme.ts` (add if missing — Phase 1 checks)
- `conversation` field in EVENTS.jsonl confirmed (Phase 6 checks before filtering)

## Blocked By

- `studio-visual-flow-builder` Phase 7b (for Phase 5 z-index)
