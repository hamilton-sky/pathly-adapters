# Conv 1 Review Failures — studio-sidebar-tree

Reviewed: 2026-05-20
Reviewer: reviewer agent

---

## Violations

### V1 — `studio/.../sidebar/Sidebar.module.css:429` — CSS contract — `.rowActionsLocked` is structurally incomplete

`.rowActionsLocked` only sets `opacity: 1` but inherits none of the layout properties defined on `.rowActions` (`display: flex`, `align-items: center`, `flex-shrink: 0`, `margin-left: auto`). Both are used as sibling container divs in SubdirRow. The locked state row actions will not align correctly because the container has no flex layout.

Fix: Either extend `.rowActionsLocked` with the same layout properties as `.rowActions`, or compose both classes on the element (`className={`${styles.rowActions} ${styles.rowActionsLocked}`}`).

---

### V2 — `studio/.../sidebar/SubdirRow.tsx:50,51` — CSS Modules contract (no inline styles) — Two inline `style` props used for non-exceptional layout

Line 50: `<Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />`
Line 51: `<span style={{ flex: 1, textAlign: 'left' }}>`

Architecture contract: "CSS Modules pattern (no inline styles except where unavoidable)." These values are static layout/theme properties that belong in `.subdirFolderIcon` and `.subdirLabel` CSS classes respectively. Neither is dynamically computed, so inline style is not justified.

---

### V3 — `studio/.../sidebar/SubdirRow.tsx:9` + `studio/.../sidebar/WorkspacePanel.tsx:91-98,197-203` — Incomplete Phase 3 implementation — `onStartDeleteFolder` declared but never passed from WorkspacePanel

`SubdirRow` Props declares `onStartDeleteFolder?: () => void` and gates the Delete menu item on it. Both SubdirRow call sites in WorkspacePanel omit this prop entirely, so the Delete folder action is silently unavailable in the UI. The ARCHITECTURE_PROPOSAL lists `onStartDeleteFolder` as part of the Conv 1 interface contract for SubdirRow. The prop being optional means no TypeScript error is raised, but the feature is unimplemented.

---

## Warnings (non-blocking)

### W1 — `studio/.../sidebar/SubdirRow.tsx:9` — Declared but unused prop — `depth?: number`

`depth` is declared in the Props interface but is not destructured in the function signature and never referenced. Should be removed to avoid confusion, or used if indentation is intended.

### W2 — `studio/.../sidebar/SubdirRow.tsx:87-108` — No Escape key handler on inline menu

The menu opened by the `MoreHorizontal` button only closes via outside-click (`mousedown` listener). There is no `keydown` handler for Escape. This is a usability gap; keyboard users cannot dismiss the menu without clicking away.

### W3 — `studio/.../sidebar/Sidebar.module.css:451` — `.itemMenu` z-index 100 lower than architectural target

The architecture decision specifies the context menu should be z-index 500 (above sidebar, below modals at 9000+). The inline `.itemMenu` popover uses z-index 100. This is the non-portal inline menu used in Conv 1, not the ContextMenu portal (later phase), but the value should be raised to 500 for consistency with the stated contract.

---

## Pass

- uiStore: `userLockedFolders: Set<string>` and `toggleFolderLock` added following exact `userLockedPaths` pattern. Pass.
- uiStore `partialize`: unchanged — includes only `sidebarCollapsed` and `theme`. Pass.
- localStorage keys: `pathly:userLockedPaths` and `pathly:userLockedFolders`. Pass.
- System folder detection: render-time `subdir.files.some(f => PROTECTED_FILENAMES.has(f.name))` — not stored. Pass.
- All CSS classes referenced by SubdirRow (`subdirHeader`, `chevron`, `rowActions`, `rowActionsLocked`, `rowAction`, `rowActionLock`, `itemMenu`, `itemMenuItem`, `itemMenuSep`, `itemMenuItemDelete`) exist in Sidebar.module.css. Pass.
- WorkspacePanel derives `isSystemFolder` and wires `userLockedFolders` / `toggleFolderLock` at both SubdirRow call sites. Pass.
- Lucide React icons used throughout (ChevronRight, ChevronDown, Folder, Lock, MoreHorizontal). Pass.
- No hardcoded credentials or secrets. Pass.
- Dependency direction: SubdirRow → uiStore is indirect (WorkspacePanel passes callbacks); WorkspacePanel imports uiStore directly. Both are renderer-layer components importing renderer-layer store. No upward dependency violations. Pass.
