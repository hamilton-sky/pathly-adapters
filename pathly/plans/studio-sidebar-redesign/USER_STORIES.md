# User Stories — studio-sidebar-redesign

---

## S1 — Context-aware sidebar driven by activePanel

**Delivered by:** Conv 1

**As a** Studio user switching between Monitor and Canvas panels,
**I want** the sidebar to automatically show the relevant content for whichever main panel I am using,
**So that** I do not waste clicks toggling tabs that show me the wrong thing.

### Acceptance Criteria

- AC1.1: When `activePanel === 'monitor'` (from Zustand `uiStore`), the sidebar renders only Workspace content (file tree of Debugs, Explorations, Lessons, Pipeline-walkthrough). No library cards or pill filters are visible.
- AC1.2: When `activePanel === 'flow'` (Canvas), the sidebar renders only Library content (card grid + My Library chips). No workspace file tree is visible.
- AC1.3: No tab bar or WORKSPACE/LIBRARY toggle is visible in either context. `TabBar.tsx` is replaced by `SidebarHeader.tsx`.
- AC1.4: `SidebarHeader.tsx` renders a plain text section title ("Workspace" or "Library") reflecting the current context. No toggle buttons.
- AC1.5: Switching `activePanel` triggers a 150ms opacity + 4px y-translate CSS transition between sidebar contexts. Rapid switching does not stack or glitch — a single transition class is used.
- AC1.6: When `activePanel` is neither `'monitor'` nor `'flow'`, the sidebar falls back to rendering Workspace content.
- AC1.7: Zero references to `switchTab` or `libraryOpen` remain in `Sidebar.tsx` or any imported sidebar component after the change.
- AC1.8: `npm run typecheck` passes with no new errors after the change.

### Edge Cases

- Rapid panel switching: transition must not animate multiple times or leave a visual artifact. Implement via a single CSS class toggle, not chained `setTimeout` animations.
- `activePanel` values outside `'monitor'` and `'flow'`: the fallback is Workspace; a `console.warn` is emitted in development mode.

---

## S2 — Move plan folder list into Monitor panel body

**Delivered by:** Conv 1

**As a** Studio user inspecting a plan in the Monitor panel,
**I want** plan progress rows to appear above the event log in the Monitor panel itself,
**So that** the sidebar workspace stays focused on raw artifacts and the Monitor shows the run state in one place.

### Acceptance Criteria

- AC2.1: `PlanSection` is removed from `WorkspacePanel.tsx` entirely. The component file may be retained for reuse in Monitor but must not be imported into WorkspacePanel.
- AC2.2: The Monitor panel (`Monitor/index.tsx`) renders plan progress rows at the top of its body, above the existing event log, FSM view, and health check.
- AC2.3: Plan progress rows reuse the `usePlanFiles()` hook (or its equivalent data source) already used by `PlanSection`.
- AC2.4: The sidebar workspace section lists only: Debugs, Explorations, Lessons, Pipeline-walkthrough — no plan folders.
- AC2.5: On short viewports, plan progress rows do not push the event log fully off-screen. A `max-height` with `overflow-y: auto` is applied to the plan progress section.
- AC2.6: `npm run typecheck` passes with no new errors after the change.

### Edge Cases

- No active plans: plan progress section renders an empty-state placeholder ("No active plans") rather than collapsing to zero height.
- Monitor rendered without Zustand FSM data: plan rows must handle loading and error states gracefully.

---

## S3 — Library card grid with pill filter tabs

**Delivered by:** Conv 2

**As a** Canvas user assembling a flow,
**I want** the library presented as a 2-column card grid with pill filter tabs,
**So that** I can browse Flows, Skills, Agents, and Templates visually rather than navigating a file tree.

### Acceptance Criteria

- AC3.1: `LibraryPanel.tsx` replaces the file-system tree with a 2-column card grid. No file-tree component remains in the Library panel.
- AC3.2: Pill filter tabs are displayed at the top of the Library section: ALL | FLOWS | SKILLS | AGENTS | TEMPLATES (in that order).
- AC3.3: Pill filter tabs are single-select. Selecting a pill filters the card grid to show only that type. "ALL" shows all types.
- AC3.4: Each card uses the type-color left-border accent: Flows=`#00ff87`, Skills=`#ff9f43`, Agents=`#6c72ff`, Templates=`#ff6b9d`.
- AC3.5: Card labels use JetBrains Mono (monospace); card descriptions use the base sans-serif font.
- AC3.6: Long card titles truncate with CSS ellipsis — they do not wrap to a second line.
- AC3.7: When no items match the selected pill filter, a centered empty-state message is shown (e.g., "No FLOWS found").
- AC3.8: Global library section header uses `--accent-global: #00ff87` accent.
- AC3.9: `npm run typecheck` passes with no new errors after the change.

### Edge Cases

- Empty library: card grid shows empty-state placeholder rather than blank space.
- Very long card title (>40 chars): text truncated with ellipsis at card boundary.
- Filter pill switching: card grid re-renders immediately with correct subset; no loading spinner needed (data is local).

---

## S4 — My Library compact chip row

**Delivered by:** Conv 2

**As a** Canvas user with personally saved items,
**I want** my personal library shown as a compact horizontal scroll chip row below the global library,
**So that** my items are visually distinct and accessible without dominating the sidebar.

### Acceptance Criteria

- AC4.1: A "My Library" section appears below the global library section in the Library panel.
- AC4.2: My Library items render as a compact, single-row horizontal scroll chip row (not a grid).
- AC4.3: The chip row uses purple/violet accent `#6c72ff` (`--accent-mine`) to differentiate from the green `#00ff87` global library.
- AC4.4: When My Library has zero items, the section renders an empty-state placeholder chip or message ("Your saved items appear here") rather than collapsing entirely.
- AC4.5: The chip row is scrollable horizontally; it does not overflow the sidebar boundary vertically.
- AC4.6: `npm run typecheck` passes with no new errors after the change.

### Edge Cases

- Zero chips: placeholder renders, not an invisible empty section.
- Many chips: row scrolls horizontally; sidebar width does not expand.

---

## S5 — Drag library items onto Canvas

**Delivered by:** Conv 3

**As a** Canvas user building a flow,
**I want** to drag any library card or chip — including items nested inside a flow card — directly onto the canvas,
**So that** I can build flows by dragging without leaving the sidebar.

### Acceptance Criteria

- AC5.1: All library cards (Flows, Skills, Agents, Templates) have `draggable={true}` and set `dataTransfer` with MIME key `application/pathly-drag-item`.
- AC5.2: Items nested inside a Flow card (expanded child items) are individually draggable. Dragging a nested item does NOT trigger a drag on the parent Flow card (event propagation stopped at nested item).
- AC5.3: All chips in "My Library" have `draggable={true}` and set the same MIME key.
- AC5.4: The drag payload for every draggable item is `{ dragType: 'canvas', name: string, section: PathlySection, path: string[] }` — matching the existing `PathlyCanvasDragItem` contract in `types/index.ts`. The existing canvas drop handler receives it without modification.
- AC5.5: Cards and chips show `cursor: grab` on hover; `cursor: grabbing` while actively dragging.
- AC5.6: A visible drag-handle affordance (e.g., a grip icon or dots pattern) is present on each draggable element by default — not only on hover.
- AC5.7: The existing canvas drop handler (`dragType === 'canvas'` validation) continues to work unchanged. No modifications to canvas drop logic are required.
- AC5.8: `npm run typecheck` passes with no new errors after the change.

### Edge Cases

- Drag starts on nested item inside a Flow card: `event.stopPropagation()` prevents parent card drag from firing.
- Drop outside canvas: browser default behavior (drag cancelled); no error thrown.
- Drag of a chip from My Library: payload maps chip data to the `PathlyCanvasDragItem` shape correctly (type, id, name → section, path).

---

## S6 — Sidebar visual system tokens

**Delivered by:** Conv 2

**As a** Studio user,
**I want** the redesigned sidebar to feel cohesive with the broader Studio dark theme,
**So that** it reads as a polished part of the app rather than a bolted-on panel.

### Acceptance Criteria

- AC6.1: Sidebar background is `#0d0d14`; sidebar width is `280px`. Both are applied via CSS custom properties or directly in `Sidebar.module.css`.
- AC6.2: The following CSS custom properties are defined in `Sidebar.module.css` or a shared token file: `--accent-global: #00ff87`, `--accent-mine: #6c72ff`, `--type-flow: #00ff87`, `--type-skill: #ff9f43`, `--type-agent: #6c72ff`, `--type-template: #ff6b9d`.
- AC6.3: JetBrains Mono is applied to all card label text. Base sans-serif is applied to card description text.
- AC6.4: All new tokens and font rules are scoped to the sidebar module — they do not leak into the global stylesheet.
- AC6.5: `npm run typecheck` passes with no new errors after the change.
