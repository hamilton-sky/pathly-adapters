# studio-sidebar-tree — User Stories

## Context

The Pathly Studio sidebar has a Library tab (primary, already implemented) and a Workspace tab. The Workspace tab currently shows files and folders but lacks VS Code-style affordances: system folders can be accidentally renamed or deleted, users have no way to lock personal folders, the `+` create button has no folder option, the context menu is an inline popover that clips when the sidebar is narrow, and files cannot be reorganised by dragging.

This feature adds five capabilities: system folder protection, user-configurable folder locks, a draggable context menu portal, dual create buttons (file + folder), and drag-and-drop tree reorg within sections — bringing the Workspace tab to parity with VS Code's Explorer.

---

## Stories

### S1: System folder protection

**As a** studio user, **I want** plan/debug/explore folders that contain state-machine files to be protected from rename and delete, **so that** I cannot accidentally break a running agent by removing a critical file's parent.

**Acceptance Criteria:**
- [ ] A SubdirRow containing at least one file whose name is in `PROTECTED_FILENAMES` renders no Delete option (neither in context menu nor right-click).
- [ ] Protected SubdirRows still show "New file" and "New folder" create options.
- [ ] The system Lock icon (non-interactive) is visible on protected folder rows at all times, not just on hover.
- [ ] Unprotected SubdirRows in the same section show full delete + rename + lock options.

**Delivered by:** Phase 1 → Conversation 1

---

### S2: User folder lock

**As a** studio user, **I want** to lock any non-system folder so its rename and delete actions are hidden, **so that** I can protect folders I consider stable without relying on system rules.

**Acceptance Criteria:**
- [ ] A non-system SubdirRow shows a `⋯` button on hover that opens a menu with "Lock folder".
- [ ] After clicking "Lock folder", the `⋯` button is replaced by a cyan Lock icon on the row.
- [ ] Clicking the cyan Lock icon on a locked folder unlocks it (restores `⋯` button).
- [ ] Lock state for folders is persisted to localStorage under `pathly:userLockedFolders` and survives page reload.
- [ ] Locking a folder does NOT change the lock state of individual files inside it — file locks are independent.

**Delivered by:** Phase 2–3 → Conversation 1

---

### S3: Draggable context menu portal

**As a** studio user, **I want** the file action menu (Rename / Delete / Lock) to appear to the right of the sidebar rather than inside it, **so that** the menu is never clipped by the sidebar's overflow boundary and I can drag it to a convenient position.

**Acceptance Criteria:**
- [ ] Clicking `⋯` on a file row opens a context menu rendered via React portal outside the sidebar DOM node.
- [ ] The menu's default position is to the right of the sidebar, vertically aligned with the clicked row.
- [ ] The menu can be dragged to any screen position by its drag handle.
- [ ] Clicking anywhere outside the menu closes it without triggering underlying items.
- [ ] The menu is dismissed on Escape key.
- [ ] The menu contains: Rename, Delete (danger), separator, Lock file — same as the previous inline popover.

**Delivered by:** Phase 4–5 → Conversation 2

---

### S4: Dual create buttons on section headers

**As a** studio user, **I want** section headers in the Workspace to show two `+` icons — one for new file, one for new folder — **so that** I can create either without navigating a submenu.

**Acceptance Criteria:**
- [ ] Each section header in the Workspace tab shows two icon buttons side-by-side: a "new file" icon and a "new folder" icon.
- [ ] Clicking "new file" opens the existing NewItemDialog (or NewFolderInput for the folder variant) scoped to that section's base directory.
- [ ] Clicking "new folder" triggers an inline folder name input (or the existing InlineFolderInput component) within the section.
- [ ] Library tab section headers retain the existing single `+` behaviour (unchanged).
- [ ] Both buttons are hidden when the sidebar filter input has text (same rule as the existing single `+`).

**Delivered by:** Phase 6–7 → Conversation 3

---

### S5: Drag-and-drop file reorg within sections

**As a** studio user, **I want** to drag a file from one folder to another folder within the same section, **so that** I can organise my workspace without using rename/delete.

**Acceptance Criteria:**
- [ ] Dragging a `WorkspaceItem` row and dropping it onto a `SubdirRow` in the same section moves the file (read + write + delete original).
- [ ] A drop target SubdirRow shows a visible highlight when a draggable item is held over it.
- [ ] Dropping a file onto its own parent folder is a no-op (no error, no UI change).
- [ ] Files in `PROTECTED_FILENAMES` are not draggable — no drag handle and `draggable` attribute not set.
- [ ] After a successful drop the section reloads and the moved file is visible in its new location.
- [ ] Drag-and-drop only works within the same section — dropping onto a SubdirRow in a different section is rejected (effectAllowed = 'none').

**Delivered by:** Phase 8–10 → Conversation 4
