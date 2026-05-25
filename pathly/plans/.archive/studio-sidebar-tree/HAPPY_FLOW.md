# studio-sidebar-tree — Happy Flow

## Overview

A studio user opens the Workspace tab, sees their project's folder tree, creates a new subfolder with a single click, drags an existing file into it, and right-clicks another file to lock it — all without leaving the sidebar and without any accidental deletion of state-machine files that run their agents.

## Step-by-Step Happy Flow

### Step 1: Open Workspace tab

- **User does:** Clicks the WORKSPACE tab in the sidebar tab bar.
- **System does:** Renders WorkspacePanel with all sections (Skills, Agents, Flows, Templates, Debugs, Explorations) and the Plan section.
- **State after:** Sidebar shows folder tree. Sections with PROTECTED_FILENAMES in their subdirs show a static muted Lock icon on the folder row.

### Step 2: Notice system-protected folders

- **User does:** Hovers over a `debugs/my-debug-run` folder row that contains `STATE.json`.
- **System does:** Renders no ⋯ button on hover — only the static Lock icon is visible.
- **State after:** User understands this folder is managed by Pathly and cannot be deleted.

### Step 3: Create a new subfolder

- **User does:** Clicks the FolderPlus icon (left `+`) on the "Skills" section header.
- **System does:** Prompts for a folder name; user types "utils"; `window.pathly.fs.mkdir` is called; `loadItems()` refreshes the section.
- **State after:** A new `skills/utils` SubdirRow appears in the Skills section.

### Step 4: Drag a file into the new folder

- **User does:** Grabs a file row (e.g. `my-helper.yaml`) in the Skills section and drags it toward the `utils` SubdirRow.
- **System does:** `utils` SubdirRow highlights with a dashed accent outline as the file hovers over it.
- **User does:** Drops the file.
- **System does:** Reads the file content, writes it to `skills/utils/my-helper.yaml`, deletes the original, calls `loadItems()`.
- **State after:** `my-helper.yaml` now appears inside `utils`; the source location is gone.

### Step 5: Open context menu portal

- **User does:** Clicks ⋯ on another skill file row.
- **System does:** Opens a floating ContextMenu panel to the right of the sidebar, vertically aligned with that row.
- **State after:** Menu shows Rename / Delete / (separator) / Lock file options.

### Step 6: Lock a file via the portal

- **User does:** Clicks "Lock file" in the context menu.
- **System does:** Calls `toggleUserLock(item.path)`, closes the menu, renders a cyan Lock icon on that file's row.
- **State after:** The file's ⋯ button is gone; cyan Lock icon visible. Lock persists after page reload.

### Step 7: Lock a folder

- **User does:** Hovers over the `utils` folder row; clicks ⋯; selects "Lock folder".
- **System does:** Calls `toggleFolderLock(folderPath)`, renders cyan Lock icon on the SubdirRow.
- **State after:** The folder's ⋯ button is gone; cyan Lock icon visible. Files inside are individually unaffected (each has its own lock state).

## End State

The user's workspace is organised with a new subfolder, a moved file, two locked items (one file, one folder), and all state-machine system folders visually distinct from user-managed folders. No critical files were accidentally deleted.

## Success Indicators

- [ ] System folders show static lock icon and no ⋯ button
- [ ] User-locked folders show cyan lock icon and no ⋯ button
- [ ] Context menu portal opens to the right of the sidebar, not clipped
- [ ] File drag-and-drop moves files on disk and refreshes the tree
- [ ] New folder prompt creates a real directory and shows immediately in the tree
- [ ] Lock state survives page reload (localStorage persistence)
