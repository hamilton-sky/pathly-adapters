# hq-panel — Code Review

**Date:** 2026-06-01  
**Rigor:** standard  
**Reviewer:** pathly-review  
**Final result: PASS (after fixes)**

---

## Round 1 — FAIL (9 violations)

Full findings in `pathly/pipeline-walkthrough/hq-panel/artifacts/REVIEW_FAILURES_conv2_attempt1.md`.

| # | Type | File | Issue |
|---|---|---|---|
| 1 | ARCH | `useHQ.tsx` | EventSource never closed on unmount (scope bug) |
| 2 | ARCH | `useHQ.tsx` | STAGE_CHANGE missing `adapter` + `status` dispatch |
| 3 | ARCH | `useHQ.tsx` | DECISION_MENU missing `status = 'blocked'` |
| 4 | ARCH | `useHQ.tsx` | RUNNER_ERROR missing `status = 'error'` |
| 5 | IMPL | `AutomationCard.tsx` | CSS import pointed to stale `ChatPanel.module.css` |
| 6 | IMPL | `FlowControlBar.tsx` | Abort button missing `disabled`/`aria-disabled` |
| 7 | IMPL | `FlowControlBar.tsx` | Reroute condition conflicted with S1 AC |
| 8 | IMPL | `useHQ.tsx` | Inline `import()` type casts bypassed barrel |
| 9 | IMPL | `FlowControlBar.tsx` | `aria-disabled` boolean instead of string-spread |

## Round 1 fixes — applied by builder

- `useHQ.tsx`: hoisted `es` outside `connect()`, added exponential backoff (3s→30s cap), fixed STAGE_CHANGE/DECISION_MENU/RUNNER_ERROR dispatches, added named type imports
- `FlowControlBar.tsx`: `rerouteEnabled = status === 'blocked'`, `abortEnabled = status !== 'idle'`, all `aria-disabled` use spread pattern
- `AutomationCard.tsx`: CSS import updated to `../index.module.css`
- Runtime: EventSource reconnect storm resolved (backoff prevents 404 hammering)

## Round 2 — PASS

`npm run typecheck` exits 0. No violations remaining.
