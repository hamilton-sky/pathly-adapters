# studio-sidebar-tree — Implementation Plan

## Overview

Adds five VS Code-style capabilities to the Pathly Studio Workspace sidebar: system folder protection (folders containing state-machine files cannot be deleted/renamed), user-configurable folder locks, a draggable React portal context menu positioned right of the sidebar, dual file+folder create buttons on section headers, and HTML5 drag-and-drop tree reorg within sections.

## Layer Architecture

```
uiStore.ts  (state + persistence)
      │  userLockedFolders Set<string>
      ▼
SubdirRow / WorkspaceItem  (row UI + action triggers)
      │  lock icon, ⋯ menu, draggable
      ▼
ContextMenu.tsx  (React portal — outside sidebar DOM)
      │  portal anchored at sidebar right edge
      ▼
WorkspacePanel / LibraryPanel  (section orchestration)
      │  passes handlers down + handles drops
      ▼
Sidebar.tsx  (top-level wiring + fs operations)
```

## Prerequisites

- Pre-flight: run `cd studio && npx tsc --noEmit 2>&1 | head -40` and record any pre-existing errors before starting Conv 1 so they are not attributed to this feature.
- `PROTECTED_FILENAMES` Set already exists in `constants.ts`.
- `userLockedPaths` Set + `toggleUserLock` already implemented in `uiStore.ts` (file-level locks).
- Library tab is already the default. File-level lock icon on `WorkspaceItem` already renders.

---

## Conversation 1: Folder locks + system protection   ← Conversation: 1

### Phase 1: System folder protection in SubdirRow   ← Conversation: 1

**File:** `studio/src/renderer/src/components/sidebar/SubdirRow.tsx` — MODIFY: add `isSystemFolder?`, `isUserLocked?`, `onToggleFolderLock?` props; render lock icon and conditional `⋯` button
**Done when:** A SubdirRow with `isSystemFolder={true}` shows a static Lock icon, no ⋯ button, no delete option; a SubdirRow with `isUserLocked={true}` shows a cyan clickable Lock icon; a normal SubdirRow shows a `⋯` on hover.
**Delivers stories:** S1, S2
**Depends on:** nothing (props added conservatively; all new props optional)
**Enables:** Phase 2 (folder lock state), Phase 3 (WorkspacePanel wiring)
**Details:**
```tsx
interface SubdirRowProps {
  name: string
  open: boolean
  onToggle: () => void
  depth?: number
  isSystemFolder?: boolean    // new — no delete/rename, static lock icon
  isUserLocked?: boolean      // new — cyan lock icon, click=unlock
  onToggleFolderLock?: () => void  // new — called when ⋯ → Lock folder or lock icon clicked
  onStartDeleteFolder?: () => void // new — called when ⋯ → Delete (only for non-system, non-locked)
}
```
- Render a `⋯` button on hover only when `!isSystemFolder && !isUserLocked`
- ⋯ popover menu items: "Lock folder" (always) + "Delete folder" (only if `onStartDeleteFolder` is provided)
- When `isUserLocked`: render cyan Lock icon at right; clicking calls `onToggleFolderLock`
- When `isSystemFolder`: render muted static Lock icon at right (no onClick)
- Reuse `styles.rowActions`, `styles.rowAction`, `styles.rowActionLock` classes from Sidebar.module.css — those already exist from file-level locks
**Verify:** `cd studio && npx tsc --noEmit`

---

### Phase 2: Extend uiStore with folder locks   ← Conversation: 1

**File:** `studio/src/renderer/src/store/uiStore.ts` — MODIFY: add `userLockedFolders: Set<string>` + `toggleFolderLock(path: string)`
**Done when:** `useUiStore().toggleFolderLock('/some/path')` adds/removes the path from `userLockedFolders`; the set is persisted to `localStorage` under key `pathly:userLockedFolders` as a JSON array; reloading the page restores the set.
**Delivers stories:** S2
**Depends on:** nothing (mirrors existing `userLockedPaths` pattern)
**Enables:** Phase 3
**Details:**
- Add `loadUserLockedFolders()` helper (same pattern as `loadUserLockedPaths()`)
- Add to `UiState` interface: `userLockedFolders: Set<string>` + `toggleFolderLock: (path: string) => void`
- Implement `toggleFolderLock` identically to `toggleUserLock` but using `pathly:userLockedFolders` key
- Do NOT add `userLockedFolders` to zustand `partialize` — it is managed via localStorage directly (same as `userLockedPaths`)
**Verify:** `cd studio && npx tsc --noEmit`

---

### Phase 3: Wire folder lock + system protection in WorkspacePanel   ← Conversation: 1

**File:** `studio/src/renderer/src/components/sidebar/WorkspacePanel.tsx` — MODIFY: read `userLockedFolders` + `toggleFolderLock` from uiStore; compute `isSystemFolder` per SubdirRow; pass new props
**Done when:** SubdirRows in WorkspacePanel receive correct `isSystemFolder`, `isUserLocked`, `onToggleFolderLock`, `onStartDeleteFolder` props; system subdir rows (those with any PROTECTED_FILENAMES file) show static lock; user-locked subdirs show cyan lock.
**Delivers stories:** S1, S2
**Depends on:** Phase 1 (SubdirRow new props), Phase 2 (uiStore)
**Enables:** S1 and S2 acceptance criteria now visually satisfied
**Details:**
- In WorkspacePanel, read `const { userLockedFolders, toggleFolderLock } = useUiStore()`
- For each `subdir` in a section: `const isSystem = subdir.files.some(f => PROTECTED_FILENAMES.has(f.name))`
- `const isFolderLocked = userLockedFolders.has(subdir.path ?? '')`
  - Note: `TemplateSubdir` currently has `{ name, open, files }` — no `path`. Extend `TemplateSubdir` in `types/index.ts` to include `path?: string`, and populate it in `useProjectFiles` hook.
  - If `subdir.path` is not yet populated, use `${sectionBaseDir}/${subdir.name}` as the folder path key.
- Pass `isSystemFolder={isSystem}`, `isUserLocked={isFolderLocked}`, `onToggleFolderLock={() => toggleFolderLock(folderPath)}` to each SubdirRow
- Pass `onStartDeleteFolder` only when `!isSystem && !isFolderLocked` (and only if a delete handler exists)
**Verify:** `cd studio && npx tsc --noEmit`

---

## Conversation 2: Context menu portal   ← Conversation: 2

### Phase 4: Create ContextMenu portal component   ← Conversation: 2

**File:** `studio/src/renderer/src/components/sidebar/ContextMenu.tsx` — CREATE: draggable React portal context menu
**Done when:** `<ContextMenu anchor={rect} onClose={fn}>` renders a `<ul>` via `ReactDOM.createPortal(…, document.body)` positioned to the right of the sidebar, dismisses on outside click or Escape, and can be dragged by a drag handle to any screen position.
**Delivers stories:** S3
**Depends on:** nothing (standalone component)
**Enables:** Phase 5
**Details:**
```tsx
interface ContextMenuProps {
  anchor: DOMRect      // getBoundingClientRect() of the row that opened it
  sidebarWidth: number // so we can position to the right of the sidebar
  onClose: () => void
  children: React.ReactNode
}
```
- Default position: `left: sidebarWidth + 4px`, `top: anchor.top`
- Draggable: mouse down on `.menuDragHandle` (the title bar area) → mouse move updates local `{x, y}` state
- Portal: `ReactDOM.createPortal(<div className={styles.contextMenuPortal}>…</div>, document.body)`
- Outside click: `mousedown` on `document` → if not inside `menuRef`, call `onClose()`
- Escape key: `keydown` listener on `document`
- CSS: fixed position, z-index 1000, `styles.contextMenuPortal`, `styles.menuDragHandle`
- Add these class names to `Sidebar.module.css`
**Verify:** `cd studio && npx tsc --noEmit`

---

### Phase 5: Wire WorkspaceItem to use ContextMenu portal   ← Conversation: 2

**File:** `studio/src/renderer/src/components/sidebar/WorkspaceItem.tsx` — MODIFY: replace inline `styles.itemMenu` div with `<ContextMenu>` portal
**Done when:** Clicking `⋯` on a WorkspaceItem opens `ContextMenu` portal at the sidebar's right edge aligned to the row; the menu contains Rename / Delete / Lock actions; closing the menu works via outside click, Escape, and action selection.
**Delivers stories:** S3
**Depends on:** Phase 4 (ContextMenu component)
**Enables:** S3 acceptance criteria satisfied
**Details:**
- WorkspaceItem needs to know `sidebarWidth` — add it as a prop (optional, default 240)
- `rowRef = useRef<HTMLDivElement>(null)` on the root div
- When `menuOpen` is true: pass `anchor={rowRef.current!.getBoundingClientRect()}` and `sidebarWidth` to `<ContextMenu>`
- Remove the old inline `<div className={styles.itemMenu}>` block; render `<ContextMenu>` in its place
- Keep Rename / Delete / separator / Lock actions as `<button>` children inside `<ContextMenu>`
- WorkspacePanel and LibraryPanel must pass `sidebarWidth` down through the chain if needed, OR WorkspaceItem reads sidebar width from a React context / localStorage directly (prefer localStorage read to avoid prop-drilling: `parseInt(localStorage.getItem('sidebar-width') ?? '240', 10)`)
**Verify:** `cd studio && npx tsc --noEmit`

---

## Conversation 3: Dual create buttons   ← Conversation: 3

### Phase 6: Extend SectionHeader to accept two action slots   ← Conversation: 3

**File:** `studio/src/renderer/src/components/sidebar/SectionHeader.tsx` — MODIFY: rename `actions` prop to `actionsRight?` (backward compat alias) and add `actionsLeft?: ReactNode`
**Done when:** SectionHeader renders `actionsLeft` (new folder icon) then `actionsRight` (new file icon) side-by-side in the header actions area without breaking existing Library tab sections that still pass a single `actions` node.
**Delivers stories:** S4
**Depends on:** nothing
**Enables:** Phase 7
**Details:**
- Keep `actions?: ReactNode` as a backward-compat alias for `actionsRight`
- Add `actionsLeft?: ReactNode`
- Render: `{actionsLeft}{actionsRight ?? actions}` inside `styles.sectionActions`
- Update CSS in `Sidebar.module.css` so `.sectionActions` has `display: flex; gap: 2px; align-items: center`
**Verify:** `cd studio && npx tsc --noEmit`

---

### Phase 7: Workspace + Library pass dual buttons   ← Conversation: 3

**File:** `studio/src/renderer/src/components/sidebar/WorkspacePanel.tsx` — MODIFY: pass separate "new file" IconButton as `actions` and "new folder" IconButton as `actionsLeft` to SectionHeader for Workspace sections
**File:** `studio/src/renderer/src/components/sidebar/LibraryPanel.tsx` — MODIFY: keep existing single `actions` node (no change to Library behaviour)
**Done when:** Each Workspace section header shows two `+`-style icons side by side: FolderPlus (left, for new folder) and FilePlus (right, for new file); Library headers still show one `+`.
**Delivers stories:** S4
**Depends on:** Phase 6 (SectionHeader dual slots)
**Enables:** S4 acceptance criteria satisfied
**Details:**
- WorkspacePanel: for each section, compose:
  ```tsx
  actionsLeft={<IconButton onClick={(e) => onInlineCreateFolder(section, e)} title="New folder"><FolderPlus size={12} /></IconButton>}
  actions={<IconButton onClick={(e) => onWorkspaceCreate(section, e)} title="New file"><FilePlus size={12} /></IconButton>}
  ```
- Add `onInlineCreateFolder` prop to WorkspacePanel + wire to Sidebar.tsx handler that prompts for a folder name and calls `window.pathly.fs.mkdir`
- LibraryPanel: no change to `actions` usage — leave as-is
- Import `FolderPlus`, `FilePlus` from `lucide-react`
**Verify:** `cd studio && npx tsc --noEmit`

---

## Conversation 4: Drag-and-drop reorg   ← Conversation: 4

### Phase 8: Make WorkspaceItem draggable   ← Conversation: 4

**File:** `studio/src/renderer/src/components/sidebar/WorkspaceItem.tsx` — MODIFY: add `draggable` + `onDragStart` for non-protected files; add `sectionId` prop to scope drops
**Done when:** A non-protected WorkspaceItem row can be dragged; a protected file (name in `PROTECTED_FILENAMES`) has `draggable={false}` and no drag cursor; the drag payload uses the existing `PathlyReorgDragItem` shape from `types/index.ts`.
**Delivers stories:** S5
**Depends on:** Conv 1–3 must be committed (WorkspaceItem already updated)
**Enables:** Phase 9
**Details:**
- Add props: `sectionId: string` (e.g. section.type), `isProtectedFile?: boolean`
- `draggable={!isProtectedFile && !isRenaming}`
- `onDragStart`: build `PathlyReorgDragItem` payload `{ dragType: 'reorg', name, section, path, type: 'file', sourcePath: item.path }`, set `e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))`, `effectAllowed = 'move'`
- CSS: add `cursor: grab` when draggable; `cursor: default` when not
**Verify:** `cd studio && npx tsc --noEmit`

---

### Phase 9: Make SubdirRow a drop target   ← Conversation: 4

**File:** `studio/src/renderer/src/components/sidebar/SubdirRow.tsx` — MODIFY: add `onDragOver?`, `onDrop?`, `isDragOver?` props; style drop target highlight
**Done when:** Dragging a WorkspaceItem over a SubdirRow highlights it; dropping calls `onDrop` with the drag event; dragging over the source folder's own SubdirRow shows no highlight.
**Delivers stories:** S5
**Depends on:** Phase 8 (draggable items)
**Enables:** Phase 10
**Details:**
- Add props: `onDragOver?: (e: React.DragEvent) => void`, `onDrop?: (e: React.DragEvent) => void`, `isDragOver?: boolean`
- `onDragOver`: call `e.preventDefault(); e.dataTransfer.dropEffect = 'move'`; parent sets `isDragOver` state
- Apply `styles.subdirRowDragOver` class when `isDragOver` — add to `Sidebar.module.css`: `background: var(--accent-subtle); outline: 1px dashed var(--accent)`
**Verify:** `cd studio && npx tsc --noEmit`

---

### Phase 10: Wire drop handler in WorkspacePanel and Sidebar   ← Conversation: 4

**File:** `studio/src/renderer/src/components/sidebar/WorkspacePanel.tsx` — MODIFY: track `dragOverSubdir` state; pass `onDragOver`/`onDrop` to SubdirRow; call `onReorgDrop` prop
**File:** `studio/src/renderer/src/components/sidebar/Sidebar.tsx` — MODIFY: add `handleReorgDrop(sourcePath, targetDir)` that reads source file, writes to target dir, deletes original, then calls `loadItems()`
**Done when:** Dragging a file from one subdir and dropping on another subdir moves the file on disk and the sidebar refreshes with the file in its new location.
**Delivers stories:** S5
**Depends on:** Phase 8 (drag payload), Phase 9 (drop target)
**Enables:** S5 acceptance criteria satisfied
**Details:**
- WorkspacePanel: `const [dragOverSubdir, setDragOverSubdir] = useState<string | null>(null)` (keyed by folder path)
- On SubdirRow `onDrop`: parse `PATHLY_DRAG_MIME` payload, verify `sectionId` matches current section (reject cross-section drops by not calling handler), call `onReorgDrop(sourcePath, targetDirPath)`
- Sidebar `handleReorgDrop`:
  ```ts
  async function handleReorgDrop(sourcePath: string, targetDir: string): Promise<void> {
    const fileName = sourcePath.split('/').pop() ?? ''
    const targetPath = `${targetDir}/${fileName}`
    if (sourcePath === targetPath) return  // no-op: same folder
    const content = await window.pathly.fs.read(sourcePath).catch(() => '')
    await window.pathly.fs.write(targetPath, content ?? '')
    await window.pathly.fs.delete(sourcePath)
    await loadItems()
  }
  ```
- Cross-section guard: check that `payload.section` matches the section being dropped into before calling handler; if mismatch, `e.dataTransfer.dropEffect = 'none'` and return
**Verify:** `cd studio && npx tsc --noEmit`

---

## Key Decisions

- **Portal vs inline for context menu:** Sidebar has `overflow: hidden` on the tree container for proper resize behavior. An inline popover is always clipped. React portal to `document.body` is the only way to render to the right of the sidebar. (S3)
- **Separate `userLockedFolders` vs augmenting `userLockedPaths`:** Different semantics — file lock hides per-file actions; folder lock hides SubdirRow delete. Keep separate Sets for clarity; both use the same localStorage-manual pattern (Zustand persist doesn't handle Sets).
- **`TemplateSubdir` needs a `path` field:** Folder locks require a stable key. Since `TemplateSubdir.name` is not unique across sections, populate `path` in `useProjectFiles` as `${sectionBaseDir}/${subdir.name}`. Add `path?: string` to the interface (optional for backward compat).
- **Drag scope: within-section only.** Cross-section moves would require format conversion (e.g., agent file moved to skills dir breaks the type contract). Reject cross-section drops at the drop handler level.
- **PROTECTED_FILENAMES check at SubdirRow level:** A folder is "system" if ANY of its files are in `PROTECTED_FILENAMES`. This is computed in WorkspacePanel at render time — no store change needed.
