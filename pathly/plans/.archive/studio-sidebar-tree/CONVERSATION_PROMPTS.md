# studio-sidebar-tree — Conversation Guide

Split into 4 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Folder locks + system protection (Phases 1–3)

**Stories delivered:** S1, S2

**Prompt to paste:**
```
Read pathly/plans/studio-sidebar-tree/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-sidebar-tree Conversation 1 (Phases 1–3) from pathly/plans/studio-sidebar-tree/IMPLEMENTATION_PLAN.md.

Pre-flight: before editing any file, run `cd studio && npx tsc --noEmit 2>&1 | head -40` and record any pre-existing errors. Do not fix pre-existing errors in this conversation.

**Before editing anything:** glob/read the live repo to confirm every file path in FEATURE_INDEX.md exists.

Scope:

Phase 1 — SubdirRow.tsx: Add optional props `isSystemFolder?`, `isUserLocked?`, `onToggleFolderLock?`, `onStartDeleteFolder?`. Render:
- When `isSystemFolder`: static muted Lock icon at row right (no click).
- When `isUserLocked`: cyan clickable Lock icon; clicking calls `onToggleFolderLock`.
- When neither: ⋯ button on hover → inline popover with "Lock folder" (always) + "Delete folder" (only if `onStartDeleteFolder` provided).
- Reuse existing `styles.rowActions`, `styles.rowAction`, `styles.rowActionLock` from Sidebar.module.css — these already exist.

Phase 2 — uiStore.ts: Add `userLockedFolders: Set<string>` + `toggleFolderLock(path: string)` to UiState. Pattern: identical to `userLockedPaths` / `toggleUserLock` already in the file. localStorage key: `pathly:userLockedFolders`. Do NOT add to zustand `partialize`.

Phase 3 — WorkspacePanel.tsx: Read `userLockedFolders` + `toggleFolderLock` from `useUiStore()`. For each subdir rendered in each section, compute:
- `isSystem = subdir.files.some(f => PROTECTED_FILENAMES.has(f.name))`
- Folder path key: if `TemplateSubdir` has no `path` field, derive it as `${sectionBaseDir}/${subdir.name}`. Extend `TemplateSubdir` in `types/index.ts` to add `path?: string` if needed.
- `isFolderLocked = userLockedFolders.has(folderPathKey)`
Pass `isSystemFolder`, `isUserLocked`, `onToggleFolderLock`, `onStartDeleteFolder` to each SubdirRow accordingly.

Architectural rules:
- All new state belongs in uiStore.ts. WorkspacePanel only derives UI props from it — no local state for locks.
- Only modify files listed in this conversation. Do NOT touch ContextMenu.tsx, SectionHeader.tsx, or drag logic yet.

Do NOT touch Conv 2–4 concerns (portal menu, dual buttons, drag-drop).
Verify: `cd studio && npx tsc --noEmit`
After done, update pathly/plans/studio-sidebar-tree/PROGRESS.md phases 1–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** System plan/debug/explore folder rows show static lock icons. Non-system folders show ⋯ on hover. Clicking ⋯ → "Lock folder" locks a folder (cyan lock appears, persists on reload). Clicking cyan lock unlocks.
**Files touched:** `SubdirRow.tsx`, `uiStore.ts`, `WorkspacePanel.tsx`, optionally `types/index.ts`

---

## Conversation 2: Context menu portal (Phases 4–5)

**Stories delivered:** S3

**Prompt to paste:**
```
Read pathly/plans/studio-sidebar-tree/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-sidebar-tree Conversation 2 (Phases 4–5) from pathly/plans/studio-sidebar-tree/IMPLEMENTATION_PLAN.md.

Conversation 1 must be committed before starting this conversation.

**Before editing anything:** glob/read the live repo to confirm every file path in FEATURE_INDEX.md exists.

Scope:

Phase 4 — CREATE studio/src/renderer/src/components/sidebar/ContextMenu.tsx:
- Props: `anchor: DOMRect`, `sidebarWidth: number`, `onClose: () => void`, `children: React.ReactNode`
- Render via `ReactDOM.createPortal(…, document.body)` — fixed position, z-index: 1000
- Default position: `left: sidebarWidth + 4`, `top: anchor.top`
- Draggable: mouse down on a drag handle div → track mouse move → update `{x, y}` local state
- Outside click: `document` mousedown listener → if not inside ref, call `onClose()`
- Escape key: `document` keydown listener
- Export: `export function ContextMenu(…)`
- Add CSS classes to Sidebar.module.css: `.contextMenuPortal` (fixed, z-index 1000, background var(--surface), border 1px solid var(--border), border-radius 6px, box-shadow), `.menuDragHandle` (cursor: move, padding 4px 8px, border-bottom 1px solid var(--border), user-select: none, color var(--text-muted), font-size 11px)

Phase 5 — MODIFY studio/src/renderer/src/components/sidebar/WorkspaceItem.tsx:
- Add `rowRef = useRef<HTMLDivElement>(null)` on the outer div.
- Add optional `sidebarWidth?: number` prop (read from `localStorage.getItem('sidebar-width')` as fallback if not passed).
- When `menuOpen` is true: instead of the inline `<div className={styles.itemMenu}>`, render `<ContextMenu anchor={rowRef.current!.getBoundingClientRect()} sidebarWidth={sidebarWidth ?? 240} onClose={() => setMenuOpen(false)}>` with the same Rename/Delete/separator/Lock buttons as children.
- Remove the old `styles.itemMenu` div and the `menuRef` / `onOutside` useEffect (ContextMenu handles its own outside-click).
- Keep all button handlers (`handleMenuAction`, etc.) unchanged — they still call the same callbacks.

Architectural rules:
- ContextMenu must be a pure presentational component — no knowledge of file paths, rename, or delete logic.
- WorkspaceItem passes callbacks as children; ContextMenu just renders them.
- Do NOT modify LibraryItem or LibraryPanel.

Do NOT touch Conv 3–4 concerns (dual buttons, drag-drop).
Verify: `cd studio && npx tsc --noEmit`
After done, update pathly/plans/studio-sidebar-tree/PROGRESS.md phases 4–5 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Clicking ⋯ on any WorkspaceItem opens a floating panel to the right of the sidebar that can be dragged. Actions (Rename/Delete/Lock) still work. Outside click and Escape close it.
**Files touched:** `ContextMenu.tsx` (new), `WorkspaceItem.tsx`, `Sidebar.module.css`

---

## Conversation 3: Dual create buttons (Phases 6–7)

**Stories delivered:** S4

**Prompt to paste:**
```
Read pathly/plans/studio-sidebar-tree/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-sidebar-tree Conversation 3 (Phases 6–7) from pathly/plans/studio-sidebar-tree/IMPLEMENTATION_PLAN.md.

Conversations 1–2 must be committed before starting this conversation.

**Before editing anything:** glob/read the live repo to confirm every file path in FEATURE_INDEX.md exists.

Scope:

Phase 6 — MODIFY studio/src/renderer/src/components/sidebar/SectionHeader.tsx:
- Keep the existing `actions?: ReactNode` prop — it remains the "right" slot for backward compat.
- Add `actionsLeft?: ReactNode` — renders to the LEFT of `actions`.
- Inside the sectionActions container, render: `{actionsLeft}{actions}` side by side.
- Update `.sectionActions` in Sidebar.module.css to `display: flex; gap: 2px; align-items: center`.
- No other changes to SectionHeader.

Phase 7 — MODIFY studio/src/renderer/src/components/sidebar/WorkspacePanel.tsx:
- Add `onInlineCreateFolder: (section: Section, e: React.MouseEvent<HTMLButtonElement>) => void` to WorkspacePanel props.
- For each section that already has a `+` button (currently via `onWorkspaceCreate` or `onInlineCreate`), now pass TWO buttons:
  - `actionsLeft={<IconButton onClick={(e) => onInlineCreateFolder(section, e)} title="New folder"><FolderPlus size={12} /></IconButton>}`
  - `actions={<IconButton onClick={(e) => onWorkspaceCreate(section, e) OR onInlineCreate(section, e)} title="New file"><FilePlus size={12} /></IconButton>}`
- Import `FolderPlus`, `FilePlus` from `lucide-react`.

MODIFY studio/src/renderer/src/components/sidebar/Sidebar.tsx:
- Add `handleInlineCreateFolder(section: Section, e: React.MouseEvent<HTMLButtonElement>)`:
  - Call `e.stopPropagation()`.
  - Prompt: `const name = window.prompt('Folder name:')` (simple for now — same pattern as `handleInlineCreatePlan`).
  - Call `await window.pathly.fs.mkdir(`${sectionBaseDir}/${name.trim()}`)` (or `write` with empty index if mkdir not available — check window.pathly.fs API).
  - Then `await loadItems()`.
- Pass `onInlineCreateFolder={handleInlineCreateFolder}` to WorkspacePanel.

KEEP studio/src/renderer/src/components/sidebar/LibraryPanel.tsx unchanged — Library sections retain their single `actions` node. Do NOT touch LibraryPanel.

Architectural rules:
- SectionHeader changes must be backward-compatible (all callers that only pass `actions` still work).
- Check `window.pathly.fs` for mkdir availability — fall back gracefully if not present.

Do NOT touch Conv 4 concerns (drag-drop).
Verify: `cd studio && npx tsc --noEmit`
After done, update pathly/plans/studio-sidebar-tree/PROGRESS.md phases 6–7 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Workspace section headers show two icons (folder + file). Clicking folder icon prompts for name and creates the folder. Library tab headers unchanged (single `+`).
**Files touched:** `SectionHeader.tsx`, `WorkspacePanel.tsx`, `LibraryPanel.tsx` (verify no change), `Sidebar.tsx`, `Sidebar.module.css`

---

## Conversation 4: Drag-and-drop reorg (Phases 8–10)

**Stories delivered:** S5

**Prompt to paste:**
```
Read pathly/plans/studio-sidebar-tree/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-sidebar-tree Conversation 4 (Phases 8–10) from pathly/plans/studio-sidebar-tree/IMPLEMENTATION_PLAN.md.

Conversations 1–3 must be committed before starting this conversation.

**Before editing anything:** glob/read the live repo to confirm every file path in FEATURE_INDEX.md exists.

Scope:

Phase 8 — MODIFY studio/src/renderer/src/components/sidebar/WorkspaceItem.tsx:
- Add props: `sectionId: string`, `isProtectedFile?: boolean`.
- Add `draggable={!isProtectedFile && !isRenaming}` to the root div.
- `onDragStart`: if `isProtectedFile`, call `e.preventDefault(); return`.
  Otherwise build `PathlyReorgDragItem` (from types/index.ts) with `{ dragType: 'reorg', name: item.name, section: sectionId as any, path: [item.name], type: 'file', sourcePath: item.path }`.
  Call `e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))`, set `e.dataTransfer.effectAllowed = 'move'`.
- Add `cursor: grab` to the root div when draggable (via CSS or inline — prefer a CSS class in Sidebar.module.css).

Phase 9 — MODIFY studio/src/renderer/src/components/sidebar/SubdirRow.tsx:
- Add optional props: `onDragOver?: (e: React.DragEvent) => void`, `onDrop?: (e: React.DragEvent) => void`, `isDragOver?: boolean`.
- `onDragOver` handler: call `e.preventDefault(); e.dataTransfer.dropEffect = 'move'` then call the prop callback.
- `onDrop` handler: call `e.preventDefault()` then call the prop callback.
- When `isDragOver={true}`, apply `styles.subdirRowDragOver` class.
- Add to Sidebar.module.css: `.subdirRowDragOver { background: var(--accent-subtle, rgba(100,200,255,0.08)); outline: 1px dashed var(--accent); }`

Phase 10 — MODIFY studio/src/renderer/src/components/sidebar/WorkspacePanel.tsx:
- Add `dragOverSubdir` state: `const [dragOverSubdir, setDragOverSubdir] = useState<string | null>(null)`.
- For each SubdirRow, pass:
  - `isDragOver={dragOverSubdir === folderPath}`
  - `onDragOver={(e) => { /* handled inside SubdirRow */ setDragOverSubdir(folderPath) }}`
  - `onDrop={(e) => { setDragOverSubdir(null); onReorgDrop?.(e, sectionId, folderPath) }}`
- Add `onDragLeave` on the SubdirRow container to clear `dragOverSubdir`.
- Add `onReorgDrop?: (e: React.DragEvent, sectionId: string, targetDir: string) => void` to WorkspacePanel props.

MODIFY studio/src/renderer/src/components/sidebar/Sidebar.tsx:
- Add `handleReorgDrop(e: React.DragEvent, sectionId: string, targetDir: string)`:
  ```ts
  const raw = e.dataTransfer.getData(PATHLY_DRAG_MIME)
  if (!raw) return
  const payload = JSON.parse(raw) as PathlyReorgDragItem
  if (payload.dragType !== 'reorg') return
  if (payload.section !== sectionId) return  // cross-section guard
  const sourcePath = payload.sourcePath
  const fileName = sourcePath.split('/').pop() ?? ''
  const targetPath = `${targetDir}/${fileName}`
  if (sourcePath === targetPath) return
  const content = await window.pathly.fs.read(sourcePath).catch(() => '')
  await window.pathly.fs.write(targetPath, content ?? '')
  await window.pathly.fs.delete(sourcePath)
  await loadItems()
  ```
- Pass `onReorgDrop={(e, sid, dir) => { void handleReorgDrop(e, sid, dir) }}` to WorkspacePanel.

Also in WorkspacePanel — pass `sectionId` and `isProtectedFile` to each WorkspaceItem:
- `sectionId={section.type}`
- `isProtectedFile={PROTECTED_FILENAMES.has(item.name)}`

Architectural rules:
- Cross-section drops must be rejected silently (return early, no error).
- Dropping on the file's own parent folder is a no-op (same path guard).
- `window.pathly.fs.read` + `write` + `delete` is the established pattern for move (no atomic rename API).
- Only WorkspacePanel receives drag state — LibraryItem canvas-drag is unrelated and must not be broken.

Do NOT change LibraryItem, LibraryPanel, or PlanSection drag behaviour.
Verify: `cd studio && npx tsc --noEmit`
After done, update pathly/plans/studio-sidebar-tree/PROGRESS.md phases 8–10 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Workspace files are draggable (except PROTECTED_FILENAMES). Dropping on a SubdirRow moves the file on disk and reloads the section. Drop target shows highlight. Cross-section and same-folder drops are no-ops.
**Files touched:** `WorkspaceItem.tsx`, `SubdirRow.tsx`, `WorkspacePanel.tsx`, `Sidebar.tsx`, `Sidebar.module.css`
