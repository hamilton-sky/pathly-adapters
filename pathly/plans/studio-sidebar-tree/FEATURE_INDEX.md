# studio-sidebar-tree — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions |
| `EDGE_CASES.md` | yes | Failure modes and risk scenarios |
| `HAPPY_FLOW.md` | yes | Golden-path narrative |
| `FLOW_DIAGRAM.md` | yes | Multi-component interaction diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/store/uiStore.ts` | Conv 1 | Add `userLockedFolders: Set<string>` + `toggleFolderLock(path)` |
| `studio/src/renderer/src/components/sidebar/SubdirRow.tsx` | Conv 1 | Add lock icon, `onToggleFolderLock?`, `isSystemFolder?`, `isUserLocked?` props |
| `studio/src/renderer/src/components/sidebar/WorkspacePanel.tsx` | Conv 1, 3, 4 | Pass folder lock handlers; split create handlers; wire reorg drop |
| `studio/src/renderer/src/components/sidebar/Sidebar.tsx` | Conv 1, 4 | Pass folder lock; wire reorg drop handler |
| `studio/src/renderer/src/components/sidebar/ContextMenu.tsx` | Conv 2 | CREATE: React portal context menu, draggable, positioned right of sidebar |
| `studio/src/renderer/src/components/sidebar/WorkspaceItem.tsx` | Conv 2 | Replace inline `itemMenu` popover with `ContextMenu` portal |
| `studio/src/renderer/src/components/sidebar/Sidebar.module.css` | Conv 2, 3 | Portal positioning styles; dual button styles |
| `studio/src/renderer/src/components/sidebar/SectionHeader.tsx` | Conv 3 | Accept `actionsLeft?: ReactNode` (folder create) + keep `actions?: ReactNode` (file create) |
| `studio/src/renderer/src/components/sidebar/LibraryPanel.tsx` | Conv 3 | Pass two action nodes to SectionHeader |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Folder locks + system protection | S1, S2 | TODO | `uiStore.ts`, `SubdirRow.tsx`, `WorkspacePanel.tsx`, `Sidebar.tsx` |
| 2 | Context menu portal | S3 | TODO | `ContextMenu.tsx` (new), `WorkspaceItem.tsx`, `Sidebar.module.css` |
| 3 | Dual create buttons | S4 | TODO | `SectionHeader.tsx`, `WorkspacePanel.tsx`, `LibraryPanel.tsx`, `Sidebar.module.css` |
| 4 | Drag-and-drop reorg | S5 | TODO | `WorkspaceItem.tsx`, `SubdirRow.tsx`, `WorkspacePanel.tsx`, `Sidebar.tsx` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/studio-sidebar-tree/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
