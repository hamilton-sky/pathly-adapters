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

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1, 2, 3 | S1, S2, S3 | TODO | `cd studio; npm run typecheck` |
| 2 | 4, 5, 6 | S4, S5, S6 | TODO | `cd studio; npm run typecheck` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1 | `studio/src/renderer/src/components/Monitor/FsmView.tsx` | Connected rail with CSS dot | Dot slides to active state, loop snap-back works | TODO |
| 1 | 2 | `studio/src/renderer/src/components/Monitor/FsmView.tsx` | Execution trace below rail | Chronological state visits, loop re-visits appear as extra rows | TODO |
| 1 | 3 | `studio/src/renderer/src/components/Monitor/index.tsx` | SSE source badge | `● live` / `○ polling` in header | TODO |
| 2 | 4 | `studio/src/renderer/src/store/uiStore.ts`, `Monitor/index.tsx` | Multi-flow store + tab bar | Tab bar appears for >1 session, switching works | TODO |
| 2 | 5 | `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Running-flow banner | Banner shows when flow running, auto-dismisses 8s | TODO |
| 2 | 6 | `studio/src/renderer/src/components/PlanBoard.tsx` | Plan card enhancements | Pulsing active, red failed, cost row, timestamps | TODO |

## Prerequisites

- `studio-visual-flow-builder` Conv 1 complete (graph rendering fix)
- `monitorSource`, `fsmState`, `events`, `pipelineStates` in store (confirmed present)

## Blocked By

- Nothing
