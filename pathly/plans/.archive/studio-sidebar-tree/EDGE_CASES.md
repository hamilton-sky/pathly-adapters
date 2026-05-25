# studio-sidebar-tree — Edge Cases

## Category 1: Drag-and-drop conflicts

### EC-1.1: Dropping a file onto its own parent folder

- **Trigger:** User drags a file and drops it on the SubdirRow that already contains it.
- **Current behavior:** N/A (feature not yet built).
- **Expected behavior:** No-op — `sourcePath === targetPath` guard returns early; no file operations; no UI change.
- **Handled in:** Phase 10 (Sidebar.tsx `handleReorgDrop` no-op guard).

### EC-1.2: Cross-section drop attempt

- **Trigger:** User drags a skill file and drops it on a SubdirRow inside the "Agents" section.
- **Current behavior:** N/A.
- **Expected behavior:** Drop is rejected silently (`payload.section !== sectionId` guard). `dropEffect = 'none'` shows the "no drop" cursor to the user.
- **Handled in:** Phase 10 (WorkspacePanel cross-section guard).

### EC-1.3: Dragging a PROTECTED_FILENAMES file

- **Trigger:** User tries to drag `STATE.json` or `PROGRESS.md` from a plans folder.
- **Current behavior:** N/A.
- **Expected behavior:** `draggable` attribute is `false`; `onDragStart` calls `e.preventDefault()`; no drag ghost appears.
- **Handled in:** Phase 8 (WorkspaceItem `isProtectedFile` guard).

### EC-1.4: File read fails during move

- **Trigger:** Source file is deleted or locked by OS between drag start and drop.
- **Current behavior:** N/A.
- **Expected behavior:** `window.pathly.fs.read` throws; `.catch(() => '')` returns empty string; write still proceeds (empty file at target). This is acceptable since the move was user-initiated. `loadItems()` still fires to show the current state.
- **Handled in:** Phase 10 (`handleReorgDrop` read catch).

---

## Category 2: Lock state edge cases

### EC-2.1: `TemplateSubdir` has no `path` field

- **Trigger:** Builder finds that `TemplateSubdir` in `types/index.ts` doesn't have a `path` property when adding folder lock wiring.
- **Current behavior:** `userLockedFolders.has(subdir.path)` would be `has(undefined)` → always false.
- **Expected behavior:** Derive path as `${sectionBaseDir}/${subdir.name}` and use that as the lock key. Extend `TemplateSubdir` with `path?: string` in types.
- **Handled in:** Phase 3 (WorkspacePanel, fallback path derivation).

### EC-2.2: localStorage `QuotaExceededError` for locked folders

- **Trigger:** `localStorage.setItem('pathly:userLockedFolders', …)` throws when storage is full.
- **Current behavior:** N/A.
- **Expected behavior:** `try/catch` swallows the error — same pattern used by `userLockedPaths`. The in-memory Set still updates; only persistence fails silently.
- **Handled in:** Phase 2 (uiStore `toggleFolderLock` try/catch).

### EC-2.3: User locks a folder that later becomes a system folder

- **Trigger:** User locks `plans/my-plan/`; later Pathly writes `STATE.json` into it.
- **Current behavior:** N/A.
- **Expected behavior:** System protection (`isSystemFolder`) takes precedence over user lock (`isUserLocked`) in WorkspacePanel — render system lock icon, not cyan lock. User lock remains in localStorage but is visually overridden.
- **Handled in:** Phase 3 (WorkspacePanel prop derivation: `isSystemFolder` check first).

---

## Category 3: Context menu portal positioning

### EC-3.1: Row near the bottom of the viewport

- **Trigger:** User clicks ⋯ on a file row near the bottom edge of the screen.
- **Current behavior:** N/A (inline popovers scroll offscreen).
- **Expected behavior:** ContextMenu's `top` is clamped so the menu doesn't overflow the viewport bottom (`Math.min(anchor.top, window.innerHeight - menuHeight)`). Builder should implement this clamp in Phase 4.
- **Handled in:** Phase 4 (ContextMenu.tsx viewport clamp).

### EC-3.2: Sidebar is maximally wide (480px) and context menu clips the app content

- **Trigger:** User resizes sidebar to 480px; clicking ⋯ opens portal at `left: 484px`.
- **Current behavior:** N/A.
- **Expected behavior:** Portal renders at `left: sidebarWidth + 4` as designed. The app content area starts immediately after the sidebar — the menu overlaps it, which is the expected and desired behavior (it's a floating overlay, not pushed content).
- **Handled in:** Phase 4/5 (by design; no special case needed).

### EC-3.3: ContextMenu is dragged off-screen

- **Trigger:** User drags the menu far to the right or below the bottom edge.
- **Current behavior:** N/A.
- **Expected behavior:** No clamp applied to drag position — user is intentionally moving it. If they can't see it, reopening via ⋯ resets to default anchor position (because `anchor` is re-derived from `getBoundingClientRect()` each time the menu opens).
- **Handled in:** Phase 4 (each open resets position from `anchor`; no persistent drag position saved).

---

## Category 4: Dual create button edge cases

### EC-4.1: `window.pathly.fs.mkdir` is not available

- **Trigger:** Running on a version of the Electron bridge that doesn't expose `mkdir`.
- **Current behavior:** N/A.
- **Expected behavior:** Builder checks `typeof window.pathly.fs.mkdir === 'function'` before calling it. If unavailable, fall back to writing an empty placeholder file (`.gitkeep` or `README.md`) via `window.pathly.fs.write` to create the directory implicitly.
- **Handled in:** Phase 7 (Sidebar.tsx `handleInlineCreateFolder` with availability check).

### EC-4.2: User enters empty or whitespace folder name

- **Trigger:** `window.prompt('Folder name:')` returns `''` or only spaces.
- **Current behavior:** N/A.
- **Expected behavior:** Guard `if (!name?.trim()) return` — no folder created, no error shown.
- **Handled in:** Phase 7 (Sidebar.tsx guard).

---

## Known Limitations

- Folder rename is not included in this plan — only file rename is supported (existing `commitRename` flow). Folder rename would require recursive path rewriting and is planned separately.
- Drag-and-drop across sections (e.g., moving a skill file to become an agent) is intentionally out of scope — the file format contract differs per section type.
- Library tab sections do not get drag-and-drop or dual create buttons in this plan — Library items come from the user's global `pathlyUserHome`, not the project tree.
