# studio-ui-fixes — Artifact Map

Date: 2026-05-18

## Feedback Artifacts

| File | Stage | Conv | Outcome |
|---|---|---|---|
| REVIEW_FAILURES.md | REVIEWING | 3 | Fixed (1 cycle): unsafe cast, "new template" label, parseProgressMd duplication |
| TEST_FAILURES.md | TESTING | — | Fixed (1 cycle): S4.4 empty-directory visibility |

## Source Files Changed

| File | Conversations |
|---|---|
| `studio/src/renderer/src/types/index.ts` | Conv 1 (FsmEvent), Conv 3 (PathlyItemType, SectionState) |
| `studio/src/renderer/src/components/Monitor/index.tsx` | Conv 1 (.slice(-50)), Conv 2 (flow YAML loader) |
| `studio/src/renderer/src/components/Monitor/EventLog.tsx` | Conv 1 (formatTime, eventDetail) |
| `studio/src/renderer/src/store/projectStore.ts` | Conv 2 (pipelineStates) |
| `studio/src/renderer/src/components/Monitor/FsmView.tsx` | Conv 2 (dynamic PIPELINE) |
| `studio/src/renderer/src/hooks/useProjectFiles.ts` | Conv 3 (Debugs/Explorations sections) |
| `studio/src/renderer/src/components/Sidebar.tsx` | Conv 3 (render, type guard, button fix) |
| `studio/src/renderer/src/hooks/usePlanConversations.ts` | Conv 3 (parseProgressMd scoped + exported) |
| `studio/src/renderer/src/components/PlanBoard.tsx` | Conv 3 (parser import, flat event list) |

## Plan Artifacts

| File | Status |
|---|---|
| `pathly/plans/studio-ui-fixes/IMPLEMENTATION_PLAN.md` | Existing (pre-built) |
| `pathly/plans/studio-ui-fixes/PROGRESS.md` | All 3 convs DONE |
| `pathly/plans/studio-ui-fixes/RETRO.md` | Written |
| `pathly/plans/studio-ui-fixes/EVENTS.jsonl` | 25 events logged |
| `pathly/plans/studio-ui-fixes/STATE.json` | DONE |
