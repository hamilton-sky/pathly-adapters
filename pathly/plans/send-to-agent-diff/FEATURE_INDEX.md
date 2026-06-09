# Feature Index — send-to-agent-diff

## What this feature does
When the user clicks "Send to Agent" in the Studio notebook comment panel, instead of Claude overwriting the file directly, it writes a `.draft` alongside the original. The Studio then shows a section-level diff viewer where the user can toggle which changed sections to keep, then confirm (apply to original + delete draft) or reject (delete draft, nothing changes).

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| FEATURE_INDEX.md | planner | builder, reviewer | Entry point — all touchpoints and conversation map |
| USER_STORIES.md | planner | builder, reviewer, tester | Acceptance criteria |
| IMPLEMENTATION_PLAN.md | planner | builder | Phases, dependencies, done-when conditions |
| PROGRESS.md | planner | builder, orchestrator | Conversation status tracking |
| CONVERSATION_PROMPTS.md | planner | builder | Verbatim prompts for each conversation |
| HAPPY_FLOW.md | planner | designer, reviewer | Ideal user journey |
| EDGE_CASES.md | planner | builder, tester | Failure modes and edge conditions |
| ARCHITECTURE_PROPOSAL.md | planner | architect, builder | Design decisions |
| FLOW_DIAGRAM.md | planner | builder | ASCII flow showing data path |

---

## Codebase touchpoints

| File | Conv | Change |
|---|---|---|
| `studio/src/renderer/src/components/Editor/commentUtils.ts` | 1 | Change `buildSendPrompt` target from original path to `.draft` path |
| `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx` | 1 | Add `onDraftReady` prop; after spawn, register `terminal.onExit` listener that checks for draft and fires the prop |
| `studio/src/renderer/src/components/Editor/index.tsx` | 1 + 3 | Conv 1: add `draftPath` state + pass `onDraftReady` to CommentsPanel. Conv 3: mount DraftDiffViewer overlay, wire confirm/reject |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffViewer.tsx` | 2 | Modal shell: backdrop, header, orchestrates panels |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffViewer.module.css` | 2 | Shared modal shell styles |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftHunkList.tsx` | 2 | Left panel: section count header + hunk cards |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftHunkCard.tsx` | 2 | Single hunk card: type badge, toggle chip, collapsed/expanded text |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftPreviewPanel.tsx` | 2 | Right panel: Result / Changes toggle + MarkdownRenderer |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/DraftDiffFooter.tsx` | 2 | Footer: Discard (with inline confirm) / Close / Apply N of M |
| `studio/src/renderer/src/components/Editor/DraftDiffViewer/useDraftDiff.ts` | 2 | Hook — reads files, parses sections, computes hunks, tracks reviewed state |

---

## Conversation map

| # | Title | Status |
|---|---|---|
| 1 | Draft-mode wiring | TODO |
| 2 | DraftDiffViewer component | TODO |
| 3 | Mount overlay + confirm/reject handlers | TODO |
