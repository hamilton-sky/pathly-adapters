# studio-sidebar-tree — Progress

## Status: IN PROGRESS (Conv 1 DONE)

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | System folder protection | Conv 1 | DONE |
| S2 | User folder lock | Conv 1 | DONE |
| S3 | Draggable context menu portal | Conv 2 | TODO |
| S4 | Dual create buttons | Conv 3 | TODO |
| S5 | Drag-and-drop reorg | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1–3 | S1, S2 | DONE | `cd studio && npx tsc --noEmit` |
| 2 | 4–5 | S3 | TODO | `cd studio && npx tsc --noEmit` |
| 3 | 6–7 | S4 | TODO | `cd studio && npx tsc --noEmit` |
| 4 | 8–10 | S5 | TODO | `cd studio && npx tsc --noEmit` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | Phase 1 | `sidebar/SubdirRow.tsx` | Add lock/system props + ⋯ popover | System/locked rows show correct icons, unprotected shows ⋯ | DONE |
| 1 | Phase 2 | `store/uiStore.ts` | Add `userLockedFolders` + `toggleFolderLock` | Toggle persists to localStorage and survives reload | DONE |
| 1 | Phase 3 | `sidebar/WorkspacePanel.tsx` | Wire folder lock + system detection | SubdirRows get correct props derived from file contents | DONE |
| 2 | Phase 4 | `sidebar/ContextMenu.tsx` (new) | Draggable React portal context menu | Portal renders right of sidebar, draggable, closes on outside click/Escape | TODO |
| 2 | Phase 5 | `sidebar/WorkspaceItem.tsx` | Replace inline popover with ContextMenu portal | ⋯ opens portal at sidebar right edge, all actions work | TODO |
| 3 | Phase 6 | `sidebar/SectionHeader.tsx` | Dual action slots (actionsLeft + actionsRight) | Two ReactNode slots render side-by-side without breaking Library | TODO |
| 3 | Phase 7 | `sidebar/WorkspacePanel.tsx` + `LibraryPanel.tsx` | Pass dual buttons to Workspace, keep single for Library | Workspace shows FolderPlus + FilePlus; Library unchanged | TODO |
| 4 | Phase 8 | `sidebar/WorkspaceItem.tsx` | Add draggable + PayloadReorgDragItem | Non-protected files draggable; protected files not draggable | TODO |
| 4 | Phase 9 | `sidebar/SubdirRow.tsx` | Add drop target + highlight | Drag-over shows highlight; onDrop called | TODO |
| 4 | Phase 10 | `sidebar/WorkspacePanel.tsx` + `Sidebar.tsx` | Wire drop handler + fs move | File moves on disk; sidebar refreshes | TODO |

## Prerequisites

- Pre-existing TS errors recorded (pre-flight run done before Conv 1)
- `PROTECTED_FILENAMES` Set in `constants.ts` already populated
- File-level user lock (`userLockedPaths`, `toggleUserLock`) already in uiStore

## Blocked By

- Nothing
