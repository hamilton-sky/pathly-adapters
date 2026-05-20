# studio-monitor-live — Progress

## Status: COMPLETE

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | FSM topology rail with sliding dot | Conv 1 | DONE |
| S2 | Execution trace below rail | Conv 1 | DONE |
| S3 | SSE live source badge | Conv 1 | DONE |
| S4 | Monitor tabs for concurrent flows | Conv 2 | DONE |
| S5 | Running-flow entry banner | Conv 2 | DONE |
| S6 | Plan conversation card enhancements | Conv 2 | DONE |
| S7 | Last-used flow on open + auto-open Monitor | Conv 2 | DONE |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1, 2, 3 | S1, S2, S3 | DONE | `cd studio; npm run typecheck` — passes (pre-existing errors in App.tsx and sidebar are out of scope) |
| 2 | 4, 5, 6, 7 | S4, S5, S6, S7 | DONE | `cd studio; npm run typecheck` — passes (only pre-existing errors remain) |

See **CONVERSATION_PROMPTS.md** for exact prompts.
See **DESIGN.md** for all token values, color constants, spacing, and accessibility specs.
See **EDGE_CASES.md** for edge case handling per story.

## Phase Detail

| Conv | Phase | File(s) | Description | Done when | Status |
|------|-------|---------|-------------|-----------|--------|
| 1 | 1 | `theme.ts`, `Monitor/FsmView.tsx` | Token additions + connected rail + CSS dot + prefers-reduced-motion | `t.runtime`/`fontFamilyMono` in theme; dot slides; COMPLETED_GREEN used; motion gated | DONE |
| 1 | 2 | `Monitor/FsmView.tsx`, `Monitor/utils.ts` | Execution trace + formatRelativeTime + aria-live | Chronological visits, aria-live polite, sorted by ts | DONE |
| 1 | 3 | `Monitor/index.tsx` | SSE badge (live/polling/—) | Old label removed; null→`—` correct | DONE |
| 2 | 4 | `store/uiStore.ts`, `Monitor/index.tsx` | Multi-flow store + ARIA tab bar + SSE re-key | ≥2 sessions → tab bar; Arrow key nav; tab switch re-keys SSE; ◐ NOT rendered | DONE |
| 2 | 5 | `FlowEditor/VisualView/index.tsx` | Running banner + setActivePanel + hover-to-pause + aria | Banner shows; 8s dismiss pauses on hover; setActivePanel not bottomPanel | DONE |
| 2 | 6 | `PlanBoard.tsx`, `types/index.ts`, `usePlanConversations.ts` | Card enhancements: t.runtime (not t.blue), pulsing color-only, role=button, cost, hover/selected | All active status uses t.runtime; pulsing width never changes; cards focusable | DONE |
| 2 | 7 | `store/uiStore.ts`, `App.tsx` | Last-used flow + auto-open Monitor | Reopens to last flow; Monitor auto-opens if running | DONE |

## Plan Files

| File | Purpose |
|---|---|
| USER_STORIES.md | Stories + acceptance criteria (includes EDGE_CASES.md references) |
| IMPLEMENTATION_PLAN.md | Phase-by-phase technical spec |
| PROGRESS.md | This file — status tracking |
| CONVERSATION_PROMPTS.md | Exact prompts to paste per conversation |
| DESIGN.md | Design reference: tokens, colors, spacing, animation, accessibility |
| EDGE_CASES.md | All edge cases with trigger, expected behavior, and handling phase |

## Prerequisites

- `studio-visual-flow-builder` Phase 7b complete (`FlowEditor/zIndex.ts` exists — required for Phase 5)
- Conv 1 complete before starting Conv 2 (`Monitor/utils.ts` + `t.runtime` token needed by Conv 2)

## Post-MVP (not in this plan)

- `isCli` signal and `>_` badge (CLI session discovery via pid/lock file watcher)
- `isPaused` signal and `◐` tab indicator
- EVENTS.jsonl / SSE race fix (merge strategy)
- `formatRelativeTime` auto-refresh without re-render
