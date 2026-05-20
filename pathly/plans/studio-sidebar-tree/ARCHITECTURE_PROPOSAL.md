# studio-sidebar-tree — Architecture Proposal

## Problem Statement

The Workspace sidebar needs VS Code-style filesystem affordances: system folder protection, user-configurable locks on folders, a context menu that escapes the sidebar's overflow boundary, dual create buttons, and drag-and-drop reorg. The current implementation has file-level locks and a single `+` button, but no folder-level controls, no portal menu, and no drag support.

## Proposed Solution

Four isolated vertical slices, each buildable and testable in sequence:
1. **Store extension** — add `userLockedFolders` to uiStore (mirrors existing `userLockedPaths` pattern)
2. **SubdirRow upgrade** — add lock/system props to folder rows (mirrors existing WorkspaceItem pattern)
3. **ContextMenu portal** — new standalone component using `ReactDOM.createPortal` to `document.body`
4. **Drag-and-drop** — HTML5 native drag on WorkspaceItem + drop target on SubdirRow + fs move in Sidebar

## Layer Breakdown

```
uiStore.ts  (global state + localStorage persistence)
     │  userLockedFolders: Set<string>
     │  toggleFolderLock(path): void
     ▼
SubdirRow.tsx / WorkspaceItem.tsx  (row-level UI)
     │  isSystemFolder, isUserLocked, onToggleFolderLock
     │  draggable, onDragStart, onDragOver, onDrop
     ▼
ContextMenu.tsx  (portal — anchored to document.body)
     │  Fixed position, right of sidebar, draggable drag handle
     ▼
SectionHeader.tsx  (actionsLeft + actionsRight slots)
     │  dual create buttons
     ▼
WorkspacePanel.tsx  (section orchestration, drop state)
     │  derives isSystem from PROTECTED_FILENAMES check
     │  tracks dragOverSubdir state
     ▼
Sidebar.tsx  (top-level operations: fs.mkdir, handleReorgDrop)
```

## Key Design Decisions

### Decision 1: React portal for context menu

- **Options considered:** (A) inline div with overflow: visible override, (B) React portal to `document.body`, (C) Electron native context menu API
- **Chosen:** B — React portal
- **Rationale:** The sidebar tree container uses `overflow: hidden` for the drag-resize grip. Overriding overflow per-row would break the resize affordance. The Electron native context menu (option C) doesn't render in the React tree — styling, animation, and actions would be duplicated. A portal to `document.body` escapes all overflow boundaries and stays in the React component tree for props/callbacks.

### Decision 2: Separate `userLockedFolders` Set vs single `lockedPaths`

- **Options considered:** (A) single `lockedPaths: Set<string>` — distinguish files/folders by trailing `/`, (B) two Sets: `userLockedPaths` (files) + `userLockedFolders` (folders), (C) a Map with `{ type: 'file' | 'folder' }` values
- **Chosen:** B — two Sets
- **Rationale:** File locks and folder locks have different UI effects and different consumers. A single Set would require the consumers to re-check the path's type on every render. Two Sets are explicit and mirror the existing code (`userLockedPaths` already in uiStore). Option C adds complexity with no benefit for this use case.

### Decision 3: System folder detection at render time vs stored flag

- **Options considered:** (A) store system folder paths in uiStore or constants, (B) compute at render time from `subdir.files.some(f => PROTECTED_FILENAMES.has(f.name))`
- **Chosen:** B — compute at render time
- **Rationale:** `PROTECTED_FILENAMES` is the single source of truth. Storing paths separately would require keeping them in sync. Render-time computation is cheap (small arrays, one Set lookup per file) and always up to date.

### Decision 4: HTML5 native drag vs React DnD library

- **Options considered:** (A) `react-dnd` or `@dnd-kit/core`, (B) native HTML5 drag events
- **Chosen:** B — native HTML5
- **Rationale:** LibraryItem already uses native HTML5 drag for canvas drops (`e.dataTransfer.setData`). The `PathlyReorgDragItem` payload type and `PATHLY_DRAG_MIME` constant already exist in `types/index.ts`. Using the same system avoids a second DnD library and keeps drag payloads consistent. The scope is file→folder drops within one section — simple enough for native events.

### Decision 5: `TemplateSubdir.path` field

- **Options considered:** (A) add `path: string` to `TemplateSubdir`, (B) derive path on demand as `${sectionBaseDir}/${subdir.name}`
- **Chosen:** A (add optional `path?: string`) + B as runtime fallback
- **Rationale:** A stable path key is required for lock persistence. If the field doesn't exist in loaded data, derive from name as a fallback. Making it `path?: string` keeps the change backward-compatible with code that doesn't populate it yet.

## Key Components

| Component | New/Modified | Purpose |
|---|---|---|
| `ContextMenu.tsx` | NEW | Draggable portal context menu for file actions |
| `SubdirRow.tsx` | MODIFIED | Folder-level lock icon + system protection + drop target |
| `WorkspaceItem.tsx` | MODIFIED | Use ContextMenu portal; draggable with reorg payload |
| `SectionHeader.tsx` | MODIFIED | Dual action slots (actionsLeft + actionsRight) |
| `uiStore.ts` | MODIFIED | `userLockedFolders` Set + `toggleFolderLock` |
| `WorkspacePanel.tsx` | MODIFIED | Derive system folders; wire folder lock; drag state; drop handler |
| `Sidebar.tsx` | MODIFIED | `handleReorgDrop` (fs read+write+delete); `handleInlineCreateFolder` |

## Interface Design

```tsx
// ContextMenu
function ContextMenu(props: {
  anchor: DOMRect
  sidebarWidth: number
  onClose: () => void
  children: React.ReactNode
}): JSX.Element

// SubdirRow (new props only)
interface SubdirRowExtension {
  isSystemFolder?: boolean
  isUserLocked?: boolean
  onToggleFolderLock?: () => void
  onStartDeleteFolder?: () => void
  onDragOver?: (e: React.DragEvent) => void
  onDrop?: (e: React.DragEvent) => void
  isDragOver?: boolean
}

// SectionHeader (new prop only)
interface SectionHeaderExtension {
  actionsLeft?: React.ReactNode
}

// uiStore (new state slice)
interface UiStateFolderLock {
  userLockedFolders: Set<string>
  toggleFolderLock: (path: string) => void
}
```

## Risks

- **`window.pathly.fs.mkdir` not available:** Mitigation — check at runtime; fall back to writing a `.gitkeep` file to create the directory implicitly (same FS layer).
- **SubdirRow `path` field not populated in `useProjectFiles`:** Mitigation — derive from `${sectionBaseDir}/${subdir.name}` as a reliable fallback; document in Phase 3 prompt.
- **ContextMenu portal z-index conflicts with modal stack:** Mitigation — ContextMenu uses `z-index: 1000`; existing modals (DeleteConfirmModal, NewItemDialog) use standard stacking; ensure new portal CSS uses a distinct z-index level from app modals (typically 9000+) to avoid overlap. Set ContextMenu to z-index 500 (above sidebar, below modals).
