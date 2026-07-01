# Implementation Plan — skill-notebook-editor

> Design artifacts: DESIGN.md, DESIGN_SPEC.md, preview.html (all in this folder)
> Tech stack: React + CSS Modules + Zustand (Electron/Vite)
> Pipeline entry: BUILDING state (STORM/PLAN/DESIGN already complete)

---

## Architecture decisions (locked)

| Decision | Choice | Reason |
|---|---|---|
| DnD library | Native HTML5 only | Linear list — no library needed; avoids bundle weight |
| Preview | `POST /skills/preview` FSM endpoint | Reuses `compose_skill()` + `_inject_prompt_vars()` — no drift risk |
| Body cells | Read-only in V1 | Editing body text is a separate concern; notebook = composition order only |
| Cell IDs | UUID v4 at parse time | Stable keys for React reconciliation and undo ring |
| State | Zustand `skillNotebookStore` | Follows existing studio store pattern |
| Export | `PUT /skills/export` → writes `composition.yaml` | Keeps Python as single source of truth for fragment resolution |
| Undo | Ring buffer, max 50 | Simple immutable snapshots of `cells[]` array |
| Fragment metadata | Parsed from YAML frontmatter in each fragment `.md` | Already required by fragment authoring convention |

---

## Data model

```typescript
// Body cell — derived from ## sections in skill .md file
type BodyCell = {
  id: string          // uuid
  type: 'body'
  heading: string     // e.g. "## Role"
  content: string     // text under the heading (preview only, not editable)
  locked: true
}

// Fragment cell — represents one fragment insertion
type FragmentCell = {
  id: string          // uuid
  type: 'fragment'
  fragmentName: string  // e.g. "completion-report"
  description: string
  category: 'core' | 'flow' | 'integration'
  requires?: string   // gate name, e.g. "can_spawn"
}

type Cell = BodyCell | FragmentCell

// skillNotebookStore shape
type SkillNotebookStore = {
  skillPath: string | null
  skillName: string            // e.g. "team/build"
  cells: Cell[]
  history: Cell[][]            // undo ring, max 50
  historyIndex: number
  featurePath: string          // value for <feature_path> substitution in preview
  previewSections: PreviewSection[]
  previewTokens: number
  previewLoading: boolean
}
```

---

## New FSM endpoints (Python — `src/pathly_orchestrator/`)

### `GET /skills/catalog`
Returns all fragments from `core/skills/fragments/` with metadata:
```json
[{
  "name": "completion-report",
  "description": "Write AGENT_DONE event...",
  "category": "core",
  "requires": null
}]
```

### `POST /skills/preview`
Body: `{ "skill": "team/build", "cells": [...], "feature_path": "pathly/plans/foo" }`
Returns: `{ "sections": [...], "tokens": 1840 }`
Routes through `compose_skill()` + `_inject_prompt_vars()` — NOT reimplemented in TS.

### `POST /skills/parse`
Body: `{ "skill_path": "src/pathly_data/core/skills/team/build.md" }`
Returns: `{ "body_cells": [...], "composition_key": "team/build" }`
Splits skill `.md` on `##` headings to produce BodyCell list.

### `PUT /skills/export`
Body: `{ "skill": "team/build", "fragment_order": ["scout-choreography", "feedback-protocol", ...] }`
Writes fragment order to `composition.yaml` under the skill key.

---

## Studio changes

### 1. `uiStore.ts`
- Add `'skill-notebook'` to `ActivePanel` union type
- Add `skillNotebookPath: string | null` + `setSkillNotebookPath(path: string)`

### 2. `App.tsx` (MainPanel switch)
- Add `case 'skill-notebook': return <SkillNotebookPanel />`

### 3. `Sidebar.tsx`
- When `activePanel === 'skill-notebook'`: show `[CATALOG | FILES]` tabs
  - CATALOG tab → renders `<CatalogPanel />`
  - FILES tab → renders existing `<LibraryPanel />` unchanged
- All other panels: existing WORKSPACE/LIBRARY tabs unchanged

### 4. `Sidebar.module.css`
- No structural change; catalog tab follows existing `.tab` / `.tabActive` pattern
- `.tabActive` uses `var(--accent)` border-bottom (already defined)

---

## Component tree

```
studio/src/renderer/src/components/SkillNotebook/
  SkillNotebook.tsx                  root: NotebookHeader + horizontal split
  SkillNotebook.module.css
  NotebookHeader/
    NotebookHeader.tsx               breadcrumb + stage badge + Undo/Redo + Validate + Export
    NotebookHeader.module.css        follows Monitor/HeaderBar.tsx pattern exactly
  NotebookCanvas/
    NotebookCanvas.tsx               cell list + insert zones + DnD coordinator
    NotebookCanvas.module.css
    BodyCell/
      BodyCell.tsx                   locked section (--accent left border, 🔒 icon)
      BodyCell.module.css
    FragmentCell/
      FragmentCell.tsx               draggable/deletable (--green left border, ⠿ handle)
      FragmentCell.module.css
    InsertZone/
      InsertZone.tsx                 invisible until drag active, animates height
      InsertZone.module.css
  PreviewPanel/
    PreviewPanel.tsx                 feature path input + sections + token count
    PreviewPanel.module.css
    PreviewSection/
      PreviewSection.tsx             one section row with [BODY]/[FRAG] badge
      PreviewSection.module.css

studio/src/renderer/src/components/sidebar/panels/
  CatalogPanel/
    CatalogPanel.tsx                 search + grouped fragment cards
    CatalogPanel.module.css
    FragmentCard/
      FragmentCard.tsx               single draggable catalog card
      FragmentCard.module.css

studio/src/renderer/src/store/
  skillNotebookStore.ts              Zustand store (cells, history, preview state)
```

---

## Conversation breakdown

| Conv | Scope | New files | Gate |
|---|---|---|---|
| 1 | Python: 3 FSM endpoints + body parser | `fsm_ops.py` additions, new routes file | `curl` smoke tests pass |
| 2 | TS: uiStore + App routing + Sidebar CATALOG mode + CatalogPanel | `uiStore.ts`, `App.tsx`, `Sidebar.tsx`, `CatalogPanel/` | `npm run typecheck` |
| 3 | TS: skillNotebookStore + NotebookCanvas + all cell components + DnD | `skillNotebookStore.ts`, `NotebookCanvas/` tree | `npm run typecheck` + visual |
| 4 | TS: PreviewPanel + NotebookHeader + SkillNotebook root + export | `SkillNotebook.tsx`, `NotebookHeader/`, `PreviewPanel/` | full end-to-end smoke test |

---

## CSS tokens in use (all from existing tokens.css)

```css
/* New semantic aliases to add to tokens.css */
--cell-body-border: var(--accent);        /* #38BDF8 sky-blue */
--cell-fragment-border: var(--green);     /* #34D399 green */
--cell-variable-highlight: var(--runtime); /* #2DD4BF teal */
```

No new color values. All spacing, typography, and transitions use existing tokens.

---

## Out of scope (V1)

- Editing body cell content (body cells are read-only)
- Creating new fragment files from the catalog
- Multi-skill comparison view
- Skill versioning / git diff view
- Mobile / responsive layout (Electron only)
