# studio-monitor-live — Artifact Map

**Date:** 2026-05-25

---

## Feedback Files

| File | Written by | Resolved by | Notes |
|------|------------|-------------|-------|
| —    | —          | —           | No feedback files — feature completed without retries |

---

## Source Files Changed

| Path | Story | What changed |
|------|-------|--------------|
| studio/src/renderer/src/theme.ts | S1 | Added `runtime` and `fontFamilyMono` tokens |
| studio/src/renderer/src/components/Monitor/FsmView.tsx | S1, S2 | Connected FSM rail with sliding dot, execution trace, aria-live |
| studio/src/renderer/src/components/Monitor/index.tsx | S3, S4 | SSE live/polling badge, multi-flow tab bar, SSE re-key |
| studio/src/renderer/src/components/Monitor/utils.ts | S2 | New file — `formatRelativeTime` helper |
| studio/src/renderer/src/store/uiStore.ts | S4, S7 | `activeFlowSessions`, `activeMonitorTab`, `lastUsedFlowPath` |
| studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx | S5 | Running-flow banner with hover-to-pause |
| studio/src/renderer/src/components/PlanBoard.tsx | S6 | Card enhancements: t.runtime color, pulsing border, cost row, role=button |
| studio/src/renderer/src/types/index.ts | S6 | Added `phases?: string` to ConvRow |
| studio/src/renderer/src/hooks/usePlanConversations.ts | S6 | Parse phase range from PROGRESS.md table |
| studio/src/renderer/src/App.tsx | S7 | Auto-open Monitor if flow running on startup |
