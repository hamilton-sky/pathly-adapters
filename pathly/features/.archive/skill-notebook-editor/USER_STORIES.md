# User Stories — skill-notebook-editor

> Feature: Jupyter-style Skill Notebook Editor embedded in Pathly Studio
> Rigor: standard (fast-forwarded to BUILDING — STORM/PLAN/DESIGN already complete)

---

## Epic: Compose AI agent skills visually by assembling body sections and fragments

---

### US-01 — Open skill in notebook mode
**As a** developer editing a skill file in Studio,
**I want** to open it in notebook mode (instead of raw markdown),
**so that** I can see my skill's body sections and fragments as interactive cells.

**Acceptance criteria:**
- Clicking a skill file in the sidebar sets `activePanel: 'skill-notebook'`
- The sidebar switches to CATALOG mode (shows fragment cards, not file tree)
- The notebook panel renders the skill's `##`-delimited sections as BodyCells
- Fragments listed in `composition.yaml` for that skill appear as FragmentCells below their insertion point
- A `FILES` tab in the sidebar lets the user switch back to the normal file tree
- TypeScript typechecks pass with zero errors

---

### US-02 — View fragment catalog
**As a** developer composing a skill,
**I want** to see all available fragments grouped by category (CORE / FLOW / INTEGRATION),
**so that** I can discover and drag capabilities into my skill.

**Acceptance criteria:**
- Catalog shows all `.md` files from `core/skills/fragments/` as cards
- Each card shows: name, one-line description, category badge
- INTEGRATION fragments show their `requires` gate badge (e.g. `⚠ can_spawn`, `⚠ mcp_github`)
- A search box filters cards by name and description (case-insensitive, live)
- Catalog is populated via `GET /skills/catalog` FSM endpoint

---

### US-03 — Drag fragment from catalog into notebook
**As a** developer,
**I want** to drag a fragment card from the catalog into the notebook canvas,
**so that** I can add a capability to my skill at a specific position.

**Acceptance criteria:**
- Fragment cards are draggable (`draggable="true"`, native HTML5 DnD)
- InsertZone slots appear between cells when a drag is active
- Dropping a card on an InsertZone inserts a new FragmentCell at that position
- The same fragment can be added more than once (no uniqueness constraint)
- Undo reverses the insert (1 undo step)
- Drop triggers a 150ms `scale(1.0→1.02→1.0)` pop animation on the new cell

---

### US-04 — Reorder fragment cells in notebook
**As a** developer,
**I want** to drag fragment cells up and down within the notebook,
**so that** I can control the order fragments appear in the assembled prompt.

**Acceptance criteria:**
- Fragment cells show a ⠿ drag handle on the left
- Dragging a FragmentCell reorders it relative to other cells (body cells are fixed anchors)
- BodyCells cannot be moved (lock icon, no drag handle)
- InsertZones appear between all cells during a drag
- Undo reverses the reorder

---

### US-05 — Delete fragment cell
**As a** developer,
**I want** to remove a fragment cell from the notebook,
**so that** I can exclude a capability from my skill.

**Acceptance criteria:**
- Each FragmentCell has an ✕ button (visible on hover)
- Clicking ✕ removes the cell
- Undo re-inserts it at the same position
- BodyCells have no ✕ button (read-only)

---

### US-06 — Live assembled prompt preview
**As a** developer,
**I want** to see a live preview of the fully assembled prompt as I edit,
**so that** I can verify how the skill will look to the runner at runtime.

**Acceptance criteria:**
- Preview panel shows structured sections with `[BODY]` / `[FRAG]` origin badges
- `<feature_path>` placeholders are rendered in teal (`var(--runtime)`) with the value from the feature path input
- Preview updates within 250ms of any cell change (debounced `POST /skills/preview`)
- Preview uses the same `compose_skill()` + `_inject_prompt_vars()` path as the real runner (no TS reimplementation)
- A token estimate (`~N tokens estimated`) is shown at the bottom of the preview
- A `Raw` toggle shows the assembled markdown string directly

---

### US-07 — Export skill composition
**As a** developer,
**I want** to export the current notebook state back to `composition.yaml` and the skill `.md` file,
**so that** the runner uses the updated composition.

**Acceptance criteria:**
- Export button writes the cell order to `composition.yaml` under the skill's key
- Fragment order in `composition.yaml` matches the order of FragmentCells in the notebook
- BodyCell content is NOT written back (body cells are read-only in V1)
- An inline success state replaces the Export button for 2s after a successful write
- Export uses `PUT /skills/export` FSM endpoint
- If `composition.yaml` does not yet have an entry for this skill, a new one is created

---

### US-08 — Undo / Redo
**As a** developer,
**I want** to undo and redo cell operations,
**so that** I can experiment without fear of losing my previous state.

**Acceptance criteria:**
- Undo/Redo buttons in the NotebookHeader are enabled/disabled based on history depth
- Supports up to 50 operations in the undo ring buffer
- Keyboard shortcuts: `Ctrl+Z` / `Ctrl+Shift+Z` work when notebook canvas is focused
- Operations tracked: insert fragment, delete fragment, reorder fragment

---

### Non-functional
- All components: single-responsibility, max ~150 lines per file (studio/CLAUDE.md rule)
- No inline styles — all CSS in `.module.css` files
- No external DnD library — native HTML5 DnD only
- All CSS values reference tokens from `tokens.css` — no hardcoded hex values
- `npm run typecheck` passes with zero errors after every conversation
