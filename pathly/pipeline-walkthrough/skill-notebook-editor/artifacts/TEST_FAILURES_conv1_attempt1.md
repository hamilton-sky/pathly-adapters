## TEST_FAILURES

### [US-01] Open skill in notebook mode

**Criterion**: Clicking a skill file in the sidebar sets `activePanel: 'skill-notebook'`
**Found**: `handleItemClick` in `Sidebar.tsx` (line 151-157) routes to `'flow'` or `'editor'` only. There is no code path that sets `activePanel: 'skill-notebook'` or calls `setSkillNotebookPath` when a skill `.md` file is clicked. The store action `setSkillNotebookPath` exists in `uiStore.ts` but is never called from the sidebar.
**Fix**: `handleItemClick` needs to detect `.md` skill files and call `setActivePanel('skill-notebook')` + `setSkillNotebookPath(item.path)` instead of `setActivePanel('editor')`.

---

**Criterion**: Fragments listed in `composition.yaml` for that skill appear as FragmentCells below their insertion point
**Found**: `loadSkill` in `skillNotebookStore.ts` (line 70-88) only maps `body_cells` from `POST /skills/parse`. The API response type is typed as `{ body_cells: ...; composition_key: string }` — there is no `fragment_cells` field parsed. FragmentCells from `composition.yaml` are never loaded into the notebook on open.
**Fix**: The `/skills/parse` response must include fragment cells from `composition.yaml`, and `loadSkill` must map them into `FragmentCell` objects and interleave them with body cells.

---

### [US-03] Drag fragment from catalog into notebook

**Criterion**: Drop triggers a 150ms `scale(1.0→1.02→1.0)` pop animation on the new cell
**Found**: No `@keyframes` animation or `animation` property referencing a scale transform exists anywhere in the SkillNotebook CSS modules. The `InsertZone.module.css` uses only `height` and `background` transitions. `FragmentCell.module.css` has a `background` transition but no pop animation.
**Fix**: Add a `@keyframes popIn` rule (e.g. `0%,100% { transform: scale(1) } 50% { transform: scale(1.02) }` over 150ms) and apply it to newly inserted `FragmentCell` nodes.

---

### [US-03] Drag fragment from catalog into notebook

**Criterion**: InsertZone slots appear between cells when a drag is active
**Found**: InsertZones are always rendered in the DOM (one before each cell and one after). They only visually expand when `activeZone === cell.id`. However, the `activeZone` state in `NotebookCanvas` is set via `onDragOver` on each InsertZone — which only fires when the cursor is directly over that zone, not when any drag is active globally. When a drag starts from `FragmentCard`, no zone becomes active until the user hovers over it; all zones remain as 6px-tall invisible slivers. The story requires zones to become visible as soon as a drag is active.
**Fix**: Track a global `isDragging` boolean (e.g. via `onDragEnter` on the canvas, or listening for `dragstart`/`dragend` events) and pass it to `InsertZone` to expand all zones when any drag is in progress, not just the one being hovered.

---

### [US-04] Reorder fragment cells in notebook

**Criterion**: InsertZones appear between all cells during a drag
**Found**: Same issue as US-03 above — InsertZones only expand on hover, not when a drag is globally active. They are not collectively visible during a cell drag operation.
**Fix**: Same as US-03 fix — add a global drag-active state to expand all InsertZones.

---

### [US-08] Undo / Redo

**Criterion**: Keyboard shortcuts: `Ctrl+Z` / `Ctrl+Shift+Z` work when notebook canvas is focused
**Found**: No `keydown` event listener or `onKeyDown` handler for `Ctrl+Z` / `Ctrl+Shift+Z` exists anywhere in the SkillNotebook component tree (`NotebookCanvas.tsx`, `NotebookHeader.tsx`, `SkillNotebook.tsx`). The undo/redo buttons work via click only.
**Fix**: Add a `keydown` listener on the canvas container (or document while notebook is active) that calls `undo()` on `Ctrl+Z` and `redo()` on `Ctrl+Shift+Z`.

---

### [Non-functional] CSS token compliance

**Criterion**: All CSS values reference tokens from `tokens.css` — no hardcoded hex values
**Found**: Multiple hardcoded `rgba()` values appear in SkillNotebook and CatalogPanel CSS modules instead of referencing the `--accent-bg`, `--runner-bg`, or similar tokens from `tokens.css`:

- `PreviewSection.module.css:34` — `rgba(52, 211, 153, 0.13)` (should be a token, e.g. `var(--green)` alpha variant)
- `PreviewSection.module.css:46` — `rgba(45, 212, 191, 0.13)` (should use `--runner-bg` or similar)
- `InsertZone.module.css:16` — `rgba(56, 189, 248, 0.4)` (should use `--accent-bg` or `--accent-border`)
- `FragmentCell.module.css:65,70,75` — `rgba(52,211,153,0.15)`, `rgba(96,165,250,0.15)`, `rgba(251,191,36,0.15)` (no corresponding tokens in `tokens.css`)
- `FragmentCard.module.css:50,55,60,73` — same raw `rgba()` values

Note: `tokens.css` does define `--runner-bg: rgba(45, 212, 191, 0.08)` and `--accent-bg: rgba(56, 189, 248, 0.13)` which are close but not the same values used. There are no badge-background tokens defined.
**Fix**: Define new badge tokens (e.g. `--badge-core-bg`, `--badge-flow-bg`, `--badge-integration-bg`) in `tokens.css` and reference them in all badge CSS rules, or reuse existing tokens where semantically appropriate.
