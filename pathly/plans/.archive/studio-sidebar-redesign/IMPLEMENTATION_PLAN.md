# Implementation Plan — studio-sidebar-redesign

## Overview

Three conversations. Each leaves the codebase in a runnable, type-check-passing state. No conversation depends on the next being completed first — each is independently mergeable.

---

## Conversation 1 — Context-aware sidebar switch

**Stories delivered:** S1, S2

**Goal:** Remove all manual tab toggle logic. Replace `TabBar` with `SidebarHeader`. Drive sidebar content from `activePanel` in Zustand `uiStore`. Move plan progress rows from `WorkspacePanel` into `Monitor`.

### Phases

**Phase 1.1 — Audit and remove `libraryOpen` / `switchTab`**
- Full-repo search for `libraryOpen` and `switchTab` identifiers.
- Confirm they are local state only in `Sidebar.tsx` and props passed to `TabBar.tsx` and `FilterRow` (per scout findings). No Zustand store entry to clean.
- Remove `libraryOpen` state and `switchTab` handler from `Sidebar.tsx`.
- Remove `TabBar.tsx` import and render from `Sidebar.tsx`.
- Update `FilterRow` props to remove `libraryOpen`.

**Phase 1.2 — Create `SidebarHeader.tsx`**
- New file: `studio/src/renderer/src/components/sidebar/shell/SidebarHeader.tsx`.
- Props: `context: 'workspace' | 'library'`.
- Renders a plain `<h2>` or `<header>` with "Workspace" or "Library" label.
- No toggle buttons, no tab elements.
- Export type for use in `Sidebar.tsx`.

**Phase 1.3 — Wire `Sidebar.tsx` to `activePanel`**
- Subscribe to `uiStore.activePanel` in `Sidebar.tsx`.
- Derive `sidebarContext`: `activePanel === 'flow'` → `'library'`; `activePanel === 'monitor'` → `'workspace'`; all other values → `'workspace'` with `console.warn`.
- Conditionally render `<WorkspacePanel>` or `<LibraryPanel>` based on `sidebarContext`.
- Add 150ms opacity + 4px y-translate CSS transition class in `Sidebar.module.css`. Use a single class toggle, not chained timers.
- Render `<SidebarHeader context={sidebarContext} />` above the conditional panel.

**Phase 1.4 — Remove `PlanSection` from `WorkspacePanel`**
- Remove `PlanSection` import and render from `WorkspacePanel.tsx`.
- Confirm remaining items: Debugs, Explorations, Lessons, Pipeline-walkthrough.
- Retain `PlanSection.tsx` component file — it will be reused in Monitor.

**Phase 1.5 — Add plan progress rows to Monitor**
- Create `studio/src/renderer/src/components/Monitor/PlanProgress.tsx`.
- Imports `PlanSection` (or `usePlanFiles()` hook) for data.
- Renders plan rows with `max-height` + `overflow-y: auto` to protect short viewports.
- Renders empty-state ("No active plans") when list is empty.
- Import and render `<PlanProgress />` at the top of `Monitor/index.tsx` body, above `EventLog`, `FsmView`, `HealthCheck`.

**Phase 1.6 — Typecheck gate**
- Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from repo root.
- All errors must be resolved before conversation is complete.

### Preconditions
- Scout findings confirm `libraryOpen` / `switchTab` are local-only (no Zustand entry). Confirmed.
- `usePlanFiles()` hook or equivalent is accessible from Monitor directory.

### Postconditions
- No `switchTab` or `libraryOpen` references remain in sidebar components.
- `TabBar.tsx` is no longer imported anywhere (file may be deleted or marked deprecated).
- Sidebar switches content automatically on `activePanel` change.
- Monitor renders plan progress rows above event log.
- `tsc --noEmit` passes.

---

## Conversation 2 — Library card grid + pill filters + My Library chips

**Stories delivered:** S3, S4, S6

**Goal:** Completely replace the file-system tree in `LibraryPanel.tsx` with a 2-column card grid driven by pill filters, add a My Library chip row below it, and establish all sidebar CSS tokens.

**Note:** This conversation should be preceded by UI/UX Pro Max design guidance from the designer agent before builder starts coding. The designer provides layout specs, spacing, and visual detail for the card and chip components before any code is written.

### Phases

**Phase 2.1 — Define CSS tokens in `Sidebar.module.css`**
- Add CSS custom properties: `--accent-global`, `--accent-mine`, `--type-flow`, `--type-skill`, `--type-agent`, `--type-template`.
- Set sidebar `background: #0d0d14` and `width: 280px`.
- Scoped to sidebar module — not leaked to global styles.
- Add card-grid layout classes: 2-column grid, 6px radius, `#12121f` card background, 1px border.
- Add pill tab classes: active/inactive states, accent colors.
- Add chip row class: horizontal scroll, no vertical overflow.

**Phase 2.2 — Build `LibraryCard.tsx`**
- New component: `studio/src/renderer/src/components/sidebar/items/LibraryCard.tsx`.
- Props: `type: 'flow' | 'skill' | 'agent' | 'template'`, `name: string`, `description?: string`.
- Left-border accent driven by `type` → type-color token.
- Label: JetBrains Mono. Description: base sans-serif.
- Title truncates with CSS ellipsis — no wrapping.
- No drag logic in this phase (added in Conv 3).

**Phase 2.3 — Build pill filter tab row**
- New component or inline section in `LibraryPanel.tsx`: pill tabs for ALL | FLOWS | SKILLS | AGENTS | TEMPLATES.
- Single-select state (local React `useState`). Default selected: ALL.
- Filtering logic: cards rendered = all items where `type` matches selected pill (or all if ALL).
- Active pill: accent background (`--accent-global`). Inactive: muted border.

**Phase 2.4 — Replace file tree with card grid in `LibraryPanel.tsx`**
- Remove all file-tree render logic and imports from `LibraryPanel.tsx`.
- Render the pill filter row at top.
- Render `<LibraryCard>` components in a 2-column CSS grid below.
- Wire filter state to card list.
- Empty-state message when filter yields zero results.

**Phase 2.5 — Build `MyLibraryChips.tsx` and integrate**
- New component: `studio/src/renderer/src/components/sidebar/items/MyLibraryChips.tsx`.
- Props: `items: Array<{ id: string; name: string; type: string }>`.
- Renders a horizontal scroll chip row.
- Chip background: `--accent-mine` tint. Text: chip label.
- Empty-state: single placeholder chip or text "Your saved items appear here".
- Render `<MyLibraryChips>` below the card grid in `LibraryPanel.tsx`.

**Phase 2.6 — Typecheck gate**
- Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from repo root.
- All errors must be resolved before conversation is complete.

### Preconditions
- Conv 1 complete (sidebar drives from `activePanel`; `LibraryPanel` is rendered when `activePanel === 'flow'`).
- Designer agent has provided card/chip layout and spacing specs.

### Postconditions
- File tree is gone from `LibraryPanel`.
- Card grid with pill filters renders for Canvas context.
- My Library chip row renders below card grid.
- All CSS tokens defined and scoped.
- `tsc --noEmit` passes.

---

## Conversation 3 — Drag-to-canvas for all library item types

**Stories delivered:** S5

**Goal:** Attach drag behavior to every draggable element in the library — cards, nested items inside Flow cards, and My Library chips — using the existing `PathlyCanvasDragItem` payload contract.

### Phases

**Phase 3.1 — Audit existing drag contract**
- Read `studio/src/renderer/src/types/index.ts` to confirm `PathlyCanvasDragItem` shape and `PATHLY_DRAG_MIME` constant.
- Confirm canvas drop handler validates `dragType === 'canvas'` and that only `{ dragType, name, section, path }` fields are needed.
- Document the mapping from library card data (type, id, name) to `{ section, path }` for each item type.

**Phase 3.2 — Add drag to `LibraryCard.tsx`**
- Add `draggable={true}` to card root element.
- `onDragStart`: call `event.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))` where payload is `PathlyCanvasDragItem`.
- Set `cursor: grab` on hover via CSS module; `cursor: grabbing` during drag (`:active` or `dragging` class).
- Add visible drag-handle affordance (grip icon or `⋮⋮` dots) rendered by default, not only on hover.

**Phase 3.3 — Flow card expansion and nested item drag**
- Extend `LibraryCard.tsx` (or create `FlowCard.tsx`) to support an expandable nested item list for Flow-type cards.
- Nested items render below the card header when expanded.
- Each nested item has `draggable={true}` with its own `onDragStart` payload.
- Nested `onDragStart` calls `event.stopPropagation()` to prevent parent card drag.
- Nested items also carry visible drag-handle affordances.

**Phase 3.4 — Add drag to `MyLibraryChips.tsx`**
- Add `draggable={true}` to each chip element.
- `onDragStart`: set `PATHLY_DRAG_MIME` data with chip's `PathlyCanvasDragItem` payload.
- Chips show `cursor: grab` on hover and drag-handle affordance by default.

**Phase 3.5 — Smoke-test drag contract**
- Verify (by code inspection, not runtime) that every `onDragStart` handler produces a payload satisfying `PathlyCanvasDragItem` shape.
- Verify canvas drop handler file is unmodified.
- Verify no other drop handlers exist in the codebase that would be broken by the new drag sources.

**Phase 3.6 — Typecheck gate**
- Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from repo root.
- All errors must be resolved before conversation is complete.

### Preconditions
- Conv 2 complete (`LibraryCard.tsx` and `MyLibraryChips.tsx` exist, no drag logic yet).
- `PathlyCanvasDragItem` and `PATHLY_DRAG_MIME` confirmed in `types/index.ts` (scout findings confirm this).

### Postconditions
- All cards, nested flow items, and chips are draggable with correct `PathlyCanvasDragItem` payload.
- Canvas drop handler works without modification.
- Drag-handle affordances visible by default on all draggable elements.
- `tsc --noEmit` passes.
- No modifications to any canvas component.
