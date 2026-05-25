# studio-sidebar-tree — Flow Diagram

## Happy Path: File drag-and-drop reorg

```
WorkspaceItem (draggable)
        │
        │  dragstart → PathlyReorgDragItem payload
        │  e.dataTransfer.setData(PATHLY_DRAG_MIME, …)
        ▼
SubdirRow (drop target)
        │
        ├─ dragover ──► setDragOverSubdir(folderPath)
        │               e.dataTransfer.dropEffect = 'move'
        │               (highlight row)
        │
        └─ drop ──────► onReorgDrop(e, sectionId, targetDir)
                                │
                                ▼
                        WorkspacePanel
                                │
                                │  parse PATHLY_DRAG_MIME
                                │  guard: same section?
                                ▼
                        Sidebar.ts handleReorgDrop
                                │
                                ├─ same path? ──► no-op
                                │
                                ▼
                        fs.read(sourcePath)
                                │
                                ▼
                        fs.write(targetPath, content)
                                │
                                ▼
                        fs.delete(sourcePath)
                                │
                                ▼
                        loadItems() ──► sidebar refresh
```

## Happy Path: Context menu portal open/close

```
WorkspaceItem row
        │
        │  click ⋯ button
        ▼
menuOpen = true
rowRef.getBoundingClientRect() → anchor: DOMRect
        │
        ▼
ContextMenu (ReactDOM.createPortal → document.body)
        │
        │  fixed position: left = sidebarWidth + 4, top = anchor.top
        │  renders: Rename / Delete / --- / Lock file
        │
        ├─ click action ──► handleMenuAction(callback)
        │                    setMenuOpen(false)
        │
        ├─ outside click ─► setMenuOpen(false)
        │
        └─ Escape key ────► setMenuOpen(false)
```

## Happy Path: Folder lock toggle

```
SubdirRow (non-system, !isUserLocked)
        │
        │  hover → ⋯ button appears
        ▼
⋯ popover
        │
        └─ click "Lock folder"
                │
                ▼
        toggleFolderLock(folderPath)   [uiStore]
                │
                ├─ next = new Set(userLockedFolders)
                ├─ next.add(folderPath)
                ├─ localStorage.setItem('pathly:userLockedFolders', JSON.stringify([...next]))
                └─ setState({ userLockedFolders: next })
                │
                ▼
        SubdirRow re-renders
        isUserLocked = true → cyan Lock icon, no ⋯
```

## Fallback Flow: Cross-section drop rejected

```
WorkspaceItem drag (sectionId = 'skills')
        │
        │  drop on SubdirRow in 'agents' section
        ▼
WorkspacePanel onReorgDrop(e, 'agents', targetDir)
        │
        │  parse payload: payload.section = 'skills'
        │  guard: 'skills' !== 'agents'
        │
        └─ return early (no-op)
           dropEffect already 'none' for user
```

## Component Legend

| Component | Role in this feature |
|---|---|
| `WorkspaceItem` | Drag source; opens ContextMenu portal on ⋯ click |
| `SubdirRow` | Drop target for drag reorg; shows lock state |
| `ContextMenu` | Portal rendered to `document.body`; draggable; escapes sidebar overflow |
| `SectionHeader` | Renders dual create buttons (FolderPlus + FilePlus) |
| `WorkspacePanel` | Derives `isSystem` from PROTECTED_FILENAMES; tracks `dragOverSubdir` |
| `uiStore` | Holds `userLockedFolders` Set; persists to localStorage |
| `Sidebar.tsx` | Executes fs operations: `handleReorgDrop`, `handleInlineCreateFolder` |
