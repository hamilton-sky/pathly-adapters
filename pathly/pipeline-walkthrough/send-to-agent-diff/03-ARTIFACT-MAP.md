# Artifact Map — send-to-agent-diff

**Date:** 2026-06-10

---

## Feedback file archive

| File | Stage | Conv | Archived as |
|---|---|---|---|
| TEST_FAILURES.md | TESTING | 0 | `artifacts/TEST_FAILURES_conv1_attempt1.md` |

---

## Source files changed

### Feature code (committed during BUILD/REVIEW stage)

| File | Change |
|---|---|
| `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx` | Added onDraftReady wiring, terminal.onExit handler |
| `studio/src/renderer/src/components/Editor/commentUtils.ts` | buildSendPrompt writes to .draft instead of original |
| `studio/src/renderer/src/components/Editor/index.tsx` | draftPath state, DraftDiffViewer mount, handleDiffApply/Discard |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffViewer.tsx` | New component — overlay modal |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffViewer.module.css` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftHunkList.tsx` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftHunkList.module.css` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftHunkCard.tsx` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftHunkCard.module.css` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftPreviewPanel.tsx` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftPreviewPanel.module.css` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffFooter.tsx` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffFooter.module.css` | New |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/hooks/useDraftDiff.ts` | New — diff hook |
| `studio/src/main/preload/index.ts` | moveToParent already present |
| `studio/src/renderer/src/types/global.d.ts` | Type declarations for IPC bridge |
| `studio/src/main/ipc/fs.ts` | Atomic write + delete IPC handlers |

### Test-stage fixes (uncommitted working tree)

| File | Fix |
|---|---|
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftHunkCard.module.css` | border-left: 3px (was all-sides) |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffViewer.tsx` | Zero-diff: return null + dispatch toast |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/useDraftDiff.ts` | reconstruct() rejected-added fix + 3s poll watch |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffFooter.tsx` | Warning wording: "You have N unreviewed sections" |

---

## Plan files

| File | Purpose |
|---|---|
| `pathly/plans/send-to-agent-diff/STATE.json` | FSM state (current: RETRO) |
| `pathly/plans/send-to-agent-diff/PROGRESS.md` | 3 conversations, all DONE |
| `pathly/plans/send-to-agent-diff/USER_STORIES.md` | 4 user stories, 17 acceptance criteria |
| `pathly/plans/send-to-agent-diff/IMPLEMENTATION_PLAN.md` | 3-conversation breakdown |
| `pathly/plans/send-to-agent-diff/CONVERSATION_PROMPTS.md` | Per-conversation builder prompts |
| `pathly/plans/send-to-agent-diff/REVIEW.md` | Final review result: PASS |
| `pathly/plans/send-to-agent-diff/RETRO.md` | Retrospective |
| `pathly/plans/send-to-agent-diff/EVENTS.jsonl` | Append-only event log |
