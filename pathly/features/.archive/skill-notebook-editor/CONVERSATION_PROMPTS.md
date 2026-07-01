# Conversation Prompts — skill-notebook-editor

> 4 builder conversations. Each has a hard typecheck/test gate before moving on.
> Read DESIGN.md, DESIGN_SPEC.md, and IMPLEMENTATION_PLAN.md before starting any conversation.
> All CSS in .module.css — no inline styles. All colors via CSS custom properties from tokens.css.

---

## Conv 1 — Python: FSM endpoints + body parser

**Role:** builder
**Input artifacts:** IMPLEMENTATION_PLAN.md (New FSM endpoints section), DESIGN_SPEC.md

### Task

Add 3 new HTTP endpoints to the FSM orchestrator and a body parser utility.

**Files to read first:**
- `src/pathly_orchestrator/` — understand the existing route structure
- `src/pathly_data/core/design/scripts/search.py` — understand how the Python package is structured
- `src/pathly_data/core/skills/fragments/` — understand fragment file format
- `src/pathly_data/core/skills/composition.yaml` — understand fragment composition schema

**Implement:**

1. **Body parser** (`src/pathly_orchestrator/skill_parser.py` — new file):
   - `parse_skill_body(skill_path: str) -> list[dict]`
   - Splits `.md` file on `## ` headings
   - Returns list of `{ "id": uuid4, "heading": "## Role", "content": "..." }`
   - Strips YAML frontmatter (between `---` delimiters) before splitting

2. **Catalog reader** (`src/pathly_orchestrator/skill_catalog.py` — new file):
   - `read_fragment_catalog(core_skills_dir: str) -> list[dict]`
   - Reads all `.md` files in `core/skills/fragments/`
   - Parses YAML frontmatter (`name`, `description`, `category`, `requires`)
   - Falls back to filename-derived name if no frontmatter

3. **Three new routes** (add to existing FSM server routes):
   - `GET /skills/catalog` → calls `read_fragment_catalog()`, returns JSON array
   - `POST /skills/parse` → body: `{ "skill_path": "..." }`, calls `parse_skill_body()`, returns `{ "body_cells": [...], "composition_key": "..." }`
   - `POST /skills/preview` → body: `{ "skill": "team/build", "cells": [...], "feature_path": "pathly/plans/foo" }`:
     - Reconstruct fragment list from cells (FragmentCell type only, in order)
     - Call `compose_skill(skill_name, fragment_names)` from existing `fsm_ops.py`
     - Call `_inject_prompt_vars(text, feature=..., storage_path=...)` for variable substitution
     - Split result by `## ` headings → `sections: [{ "heading": "...", "content": "...", "origin": "body"|"fragment" }]`
     - Estimate tokens: `len(result.split()) * 1.3` (rough approximation)
     - Return `{ "sections": [...], "tokens": N }`
   - `PUT /skills/export` → body: `{ "skill": "team/build", "fragment_order": ["name1", "name2"] }`:
     - Read `composition.yaml`
     - Update (or insert) the skill key with `fragments: [fragment_order]`
     - Write back to `composition.yaml`
     - Return `{ "ok": true }`

**Gate:** Run these curl tests manually before marking conv done:
```bash
curl http://localhost:8765/skills/catalog
curl -X POST http://localhost:8765/skills/parse -H "Content-Type: application/json" -d '{"skill_path":"src/pathly_data/core/skills/team/build.md"}'
curl -X POST http://localhost:8765/skills/preview -H "Content-Type: application/json" -d '{"skill":"team/build","cells":[{"type":"fragment","fragmentName":"completion-report"}],"feature_path":"pathly/plans/test"}'
```
All three must return valid JSON without 500 errors.

---

## Conv 2 — TypeScript: Store + Routing + Sidebar CATALOG mode + CatalogPanel

**Role:** builder
**Input artifacts:** IMPLEMENTATION_PLAN.md, DESIGN.md, `studio/src/renderer/src/store/uiStore.ts`, `studio/src/renderer/src/components/sidebar/Sidebar.tsx`

### Task

Wire the skill-notebook panel into the Studio's routing and sidebar system.

**Files to read first:**
- `studio/src/renderer/src/store/uiStore.ts` — activePanel type, sidebarCollapsed
- `studio/src/renderer/src/App.tsx` — MainPanel switch and body layout
- `studio/src/renderer/src/components/sidebar/Sidebar.tsx` — tab switching, LibraryPanel render
- `studio/src/renderer/src/components/sidebar/Sidebar.module.css` — tab styles
- `studio/src/renderer/src/styles/tokens.css` — CSS custom properties
- `studio/src/renderer/src/styles/buttons.css` — .pathly-btn-b class

**Implement:**

1. **`uiStore.ts`** — extend ActivePanel union:
   ```typescript
   type ActivePanel = 'plan' | 'editor' | 'flow' | 'monitor' | 'settings' | 'skill-notebook'
   ```
   Add state: `skillNotebookPath: string | null`, setter: `setSkillNotebookPath(path: string | null)`

2. **`skillNotebookStore.ts`** (new file, `store/skillNotebookStore.ts`):
   ```typescript
   // Zustand store — full shape in IMPLEMENTATION_PLAN.md
   // cells[], history (ring buffer 50), historyIndex,
   // featurePath, previewSections, previewTokens, previewLoading
   // Actions: pushCells, undo, redo, setFeaturePath, setPreview
   ```

3. **`App.tsx`** — add to MainPanel switch:
   ```typescript
   case 'skill-notebook': return <SkillNotebookPanel />
   ```
   Import `SkillNotebookPanel` from `./components/SkillNotebook/SkillNotebook`
   Create `SkillNotebook.tsx` as a PLACEHOLDER (renders `<div>Notebook TODO</div>`) so the route works

4. **`Sidebar.tsx`** — add CATALOG mode:
   - Read `activePanel` from store
   - When `activePanel === 'skill-notebook'`:
     - Show `[CATALOG | FILES]` tab bar (replaces WORKSPACE/LIBRARY tabs)
     - CATALOG tab → `<CatalogPanel />`
     - FILES tab → `<LibraryPanel ... />` (existing, pass same props)
   - All other panels: unchanged (WORKSPACE/LIBRARY tabs as today)

5. **`CatalogPanel/CatalogPanel.tsx`** + `CatalogPanel.module.css`:
   - On mount: `fetch('http://localhost:8765/skills/catalog')` → populate fragment list
   - Search input (live filter by name + description)
   - Three groups: CORE / FLOW / INTEGRATION
   - Renders `<FragmentCard />` for each fragment

6. **`CatalogPanel/FragmentCard/FragmentCard.tsx`** + `.module.css`:
   - Props: `{ name, description, category, requires? }`
   - `draggable="true"`, `onDragStart` sets `dataTransfer.setData('fragment-name', name)`
   - Category badge: CORE=green, FLOW=blue, INTEGRATION=yellow (from tokens.css)
   - `requires` badge: amber warning chip if present
   - Left border: `var(--cell-fragment-border)` (2px solid)
   - Hover: background shifts to `var(--bg-surface1)`, `var(--transition-base)`

**Gate:** `npm run typecheck` — zero errors. Open Studio, click a skill file → sidebar shows CATALOG tab with fragment cards loaded from FSM.

---

## Conv 3 — TypeScript: skillNotebookStore + NotebookCanvas + cells + DnD

**Role:** builder
**Input artifacts:** IMPLEMENTATION_PLAN.md, DESIGN.md, DESIGN_SPEC.md (DnD section), Conv 2 output

### Task

Implement the notebook canvas: parse skill into cells, render body/fragment cells, handle drag-and-drop reordering and insertion.

**Files to read first:**
- `studio/src/renderer/src/store/skillNotebookStore.ts` (from Conv 2)
- `studio/src/renderer/src/store/uiStore.ts` (skillNotebookPath)
- `studio/src/renderer/src/styles/tokens.css` — tokens to reference
- `studio/src/renderer/src/components/SkillNotebook/SkillNotebook.tsx` (current placeholder)

**Implement:**

1. **`skillNotebookStore.ts`** — fill out (may already exist from Conv 2 as stub):
   - `loadSkill(skillPath: string)`: calls `POST /skills/parse`, calls `GET /skills/catalog`, populates `cells[]` from body cells + fragment cells from composition.yaml order
   - `insertFragment(fragmentName, afterCellId)`: inserts FragmentCell, pushes to history
   - `removeCell(cellId)`: removes FragmentCell (noop on BodyCell), pushes to history
   - `moveCell(cellId, afterCellId)`: reorders FragmentCell, pushes to history
   - `undo()` / `redo()`: ring buffer navigation
   - `pushCells(cells)`: snapshot → history ring (max 50, oldest dropped)

2. **`NotebookCanvas/NotebookCanvas.tsx`** + `.module.css`:
   - On mount: calls `loadSkill(skillNotebookPath)` from store
   - Renders alternating `<BodyCell>` and `<FragmentCell>` in order
   - Inserts `<InsertZone>` between every pair of cells (and before first, after last)
   - DnD coordinator state: `draggingCellId: string | null`, `draggingSource: 'catalog' | 'cell' | null`
   - `onDragOver` on canvas: sets insert zone highlight
   - `onDrop` on InsertZone: calls `insertFragment` or `moveCell` depending on source

3. **`BodyCell/BodyCell.tsx`** + `.module.css`:
   - Left border: `3px solid var(--cell-body-border)` (sky-blue)
   - Background: `var(--bg-surface0)`
   - Heading in `var(--accent)`, body preview in `var(--text-secondary)` at 11px
   - Lock icon (lucide `Lock`, 12px, `var(--text-muted)`) in top-right
   - Collapsed by default if content > 3 lines; "▾ Show full content" toggle
   - NOT draggable — no drag handle

4. **`FragmentCell/FragmentCell.tsx`** + `.module.css`:
   - Left border: `3px solid var(--cell-fragment-border)` (green)
   - Background: `var(--bg-surface0)`
   - ⠿ drag handle (lucide `GripVertical`, 14px) on left — `draggable="true"`, `onDragStart` sets `dataTransfer.setData('cell-id', id)`
   - Category badge (small chip, same colors as FragmentCard)
   - ✕ delete button (lucide `X`, 12px) — visible on hover, calls `removeCell(id)`
   - Hover: background to `var(--bg-surface1)`

5. **`InsertZone/InsertZone.tsx`** + `.module.css`:
   - Height: 6px normally; 32px when `dragActive` prop is true
   - `"+ Drop here"` label appears at 32px height
   - Background: `var(--accent-border)` (rgba 40% sky-blue) when active
   - CSS class toggle only (no JS style prop) for height transition — supports `prefers-reduced-motion`
   - `onDragOver`: calls `preventDefault()`, sets highlight
   - `onDrop`: calls parent handler with this zone's `afterCellId`

6. **Update `SkillNotebook.tsx`** (replace placeholder):
   - Horizontal flex layout: `<NotebookCanvas flex:1>` + `<ResizeHandle 4px>` + `<PreviewPanel 320px>`
   - ResizeHandle: 4px wide, `var(--bg-surface1)` background, draggable to resize preview

**Gate:** `npm run typecheck` — zero errors. Visual: open a skill → cells render correctly → can drag fragment from catalog and drop into notebook → can reorder cells → undo reverses last operation.

---

## Conv 4 — TypeScript: PreviewPanel + NotebookHeader + Export

**Role:** builder
**Input artifacts:** IMPLEMENTATION_PLAN.md, DESIGN.md, Conv 3 output, `studio/src/renderer/src/components/Monitor/` (header pattern reference)

### Task

Complete the preview panel, notebook header toolbar, and export flow.

**Files to read first:**
- `studio/src/renderer/src/components/Monitor/HeaderBar.tsx` — panel header pattern to follow exactly
- `studio/src/renderer/src/components/Monitor/Monitor.module.css` — headerRoot, headerTopRow CSS classes
- `studio/src/renderer/src/styles/buttons.css` — .pathly-btn-b class
- `studio/src/renderer/src/store/skillNotebookStore.ts` (from Conv 3)

**Implement:**

1. **`PreviewPanel/PreviewPanel.tsx`** + `.module.css`:
   - Feature path text input at top (updates `store.featurePath`, triggers debounced preview)
   - On `cells` or `featurePath` change: debounce 250ms → `POST /skills/preview`
   - Renders list of `<PreviewSection>` components
   - Token estimate at bottom: `~N tokens estimated` in `var(--text-muted)` monospace
   - Loading state: subtle pulse animation on sections while fetching
   - Raw toggle: shows `<pre>` with joined markdown string

2. **`PreviewPanel/PreviewSection/PreviewSection.tsx`** + `.module.css`:
   - Props: `{ heading, content, origin: 'body' | 'fragment' }`
   - Heading row: heading text (uppercase, `var(--text-muted)`, 10px semibold) + badge chip right-aligned
   - BODY badge: `var(--accent-bg)` background, `var(--accent)` text
   - FRAG badge: green-bg tint, `var(--green)` text (use `rgba(52,211,153,0.13)`)
   - Content: `var(--text-secondary)` 11px; inline `<feature_path>` spans highlighted with `var(--runtime)` color and subtle `rgba(45,212,191,0.13)` background

3. **`NotebookHeader/NotebookHeader.tsx`** + `.module.css`:
   - Follow `Monitor/HeaderBar.tsx` pattern EXACTLY for CSS class names
   - `.headerRoot`: `background: var(--bg-surface0); border-bottom: 1px solid var(--bg-surface1); padding: 8px 12px 6px; flex-shrink: 0`
   - LEFT: breadcrumb `Skills › <parent> ›` in muted + skill name in primary + stage badge
   - Stage badge: `var(--accent-bg)` bg, `var(--accent)` text, uppercase 10px
   - RIGHT: Undo button (`class="pathly-btn-b"`, lucide `Undo2`, disabled if no history)
   - Redo button (`class="pathly-btn-b"`, lucide `Redo2`, disabled if at latest)
   - Divider `1px solid var(--bg-surface1)`
   - Validate button (`class="pathly-btn-b"`) — for now just checks FSM health via `GET /health`
   - Export Skill button: `background: var(--accent); color: var(--bg-mantle); border: none` — calls export handler

4. **Export handler** (in `NotebookHeader.tsx` or extracted to `useExport` hook):
   - Collect FragmentCell names in order from `store.cells`
   - `PUT /skills/export` with `{ skill: skillName, fragment_order: [...] }`
   - On success: button transitions to ✓ check + "Exported" text for 2s, then resets
   - On error: button shows red error state for 3s

5. **Wire `SkillNotebook.tsx`**:
   - Compose: `<NotebookHeader>` + horizontal body
   - Pass `onUndo`, `onRedo` callbacks from store to header
   - On `skillNotebookPath` change: call `store.loadSkill(path)`

6. **Tokens.css** — add semantic aliases at end of `:root` block:
   ```css
   --cell-body-border: var(--accent);
   --cell-fragment-border: var(--green);
   --cell-variable-highlight: var(--runtime);
   ```

**Gate:** Full end-to-end smoke test:
1. Click `team/build.md` in sidebar → notebook opens
2. Sidebar shows CATALOG tab with fragment cards
3. Drag `mcp-github-pr` from catalog into notebook → appears as FragmentCell
4. Preview updates within 250ms showing new FRAG section
5. Click Export → `composition.yaml` updated
6. Undo → fragment removed, composition.yaml NOT yet updated (undo is in-memory only)
7. `npm run typecheck` — zero errors
