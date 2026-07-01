# Conversation Prompts — studio-sidebar-redesign

---

## Conv 1 — Context-aware sidebar switch

**Stories:** S1, S2
**Precondition:** Codebase is on a feature branch (not master). No prior conversation required.

**Builder prompt:**

```
Implement Conv 1 of the studio-sidebar-redesign feature.

Stories delivered: S1 (context-aware sidebar), S2 (plan rows into Monitor).
Plan files: C:\Users\Yafit\pathly-adapters\pathly\plans\studio-sidebar-redesign\

Files to modify or create:
- studio/src/renderer/src/components/sidebar/Sidebar.tsx
- studio/src/renderer/src/components/sidebar/shell/TabBar.tsx (delete or deprecate)
- studio/src/renderer/src/components/sidebar/shell/SidebarHeader.tsx (CREATE NEW)
- studio/src/renderer/src/components/sidebar/panels/WorkspacePanel.tsx
- studio/src/renderer/src/components/sidebar/panels/LibraryPanel.tsx (no content changes — sidebar routing only)
- studio/src/renderer/src/components/sidebar/Sidebar.module.css
- studio/src/renderer/src/components/Monitor/index.tsx
- studio/src/renderer/src/components/Monitor/PlanProgress.tsx (CREATE NEW)

Work in this order:

1. Search the full repo for `switchTab` and `libraryOpen`. Confirm they exist only in Sidebar.tsx, TabBar.tsx, and FilterRow. Remove all occurrences.

2. Create SidebarHeader.tsx:
   - Props: `context: 'workspace' | 'library'`
   - Renders a plain header element with label text ("Workspace" or "Library")
   - No toggle buttons

3. Update Sidebar.tsx:
   - Subscribe to `useUIStore().activePanel`
   - Derive sidebarContext: 'flow' → 'library'; 'monitor' → 'workspace'; all other values → 'workspace' + console.warn
   - Render <SidebarHeader context={sidebarContext} /> above conditional panel
   - Conditionally render <WorkspacePanel> or <LibraryPanel> based on sidebarContext
   - Add 150ms opacity + 4px translateY CSS transition in Sidebar.module.css (single class toggle, not chained setTimeout)

4. Remove PlanSection from WorkspacePanel.tsx. Keep the PlanSection.tsx file — it will be reused.

5. Create PlanProgress.tsx in Monitor/:
   - Use usePlanFiles() or PlanSection component for data
   - Wrap in max-height + overflow-y: auto container for short-viewport safety
   - Render empty-state ("No active plans") when list is empty

6. Import and render <PlanProgress /> at the top of Monitor/index.tsx, above EventLog/FsmView/HealthCheck.

7. Run: node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
   Fix all type errors before finishing.

Acceptance criteria are in: pathly/plans/studio-sidebar-redesign/USER_STORIES.md (S1: AC1.1–AC1.8, S2: AC2.1–AC2.6)
Progress checklist: pathly/plans/studio-sidebar-redesign/PROGRESS.md
```

---

## Conv 2 — Library card grid + pill filters + My Library chips

**Stories:** S3, S4, S6
**Precondition:** Conv 1 complete and type-check passing. Designer agent has provided card/chip layout specs before builder starts.

**Designer prompt (run before builder):**

```
Design system task: studio-sidebar-redesign Conv 2 — Library Panel visual design.

You are the UI/UX designer. Produce precise layout and spacing specs for:

1. LibraryCard component (2-column grid, 6px radius, #12121f bg, 1px border, type-color left accent)
   - Card inner padding, label sizing, description sizing
   - Left-border accent width
   - Hover state definition

2. Pill filter tabs (ALL | FLOWS | SKILLS | AGENTS | TEMPLATES)
   - Height, horizontal padding, border-radius, font size
   - Active state: which background/border treatment
   - Inactive state
   - Gap between pills

3. My Library chip (horizontal scroll row)
   - Chip height, padding, border-radius, font size
   - Accent treatment (#6c72ff)
   - Scroll container height

4. Empty-state treatments for: zero cards, zero chips

Fixed constraints (non-negotiable):
- Sidebar width: 280px, background: #0d0d14
- Type colors: Flows=#00ff87, Skills=#ff9f43, Agents=#6c72ff, Templates=#ff6b9d
- Accent-global: #00ff87, Accent-mine: #6c72ff
- Card labels: JetBrains Mono. Descriptions: base sans-serif.
- Existing CSS tokens available: --bg-surface0, --text-primary, --text-secondary, --text-muted, --transition-base

Produce a spec table or annotated component list, not code. The builder uses this as the source of truth for Conv 2.
```

**Builder prompt:**

```
Implement Conv 2 of the studio-sidebar-redesign feature.

Stories delivered: S3 (card grid + pill filters), S4 (My Library chips), S6 (CSS tokens).
Plan files: C:\Users\Yafit\pathly-adapters\pathly\plans\studio-sidebar-redesign\
Use designer specs (from the designer prompt above) for all sizing and spacing values.

Files to modify or create:
- studio/src/renderer/src/components/sidebar/Sidebar.module.css (add tokens)
- studio/src/renderer/src/components/sidebar/panels/LibraryPanel.tsx (complete rewrite of content)
- studio/src/renderer/src/components/sidebar/items/LibraryCard.tsx (CREATE NEW)
- studio/src/renderer/src/components/sidebar/items/MyLibraryChips.tsx (CREATE NEW)

Work in this order:

1. Add CSS custom properties to Sidebar.module.css:
   --accent-global: #00ff87
   --accent-mine: #6c72ff
   --type-flow: #00ff87
   --type-skill: #ff9f43
   --type-agent: #6c72ff
   --type-template: #ff6b9d
   Set sidebar background: #0d0d14, width: 280px.
   Add grid, pill, and chip layout classes per designer specs.
   Scope to sidebar module only.

2. Create LibraryCard.tsx:
   Props: type ('flow'|'skill'|'agent'|'template'), name (string), description? (string)
   Left-border accent from type token.
   Label: font-family JetBrains Mono. Description: base sans.
   Title: overflow: hidden, text-overflow: ellipsis, white-space: nowrap.
   No drag logic in this file (added in Conv 3).

3. Create MyLibraryChips.tsx:
   Props: items: Array<{ id: string; name: string; type: string }>
   Horizontal scroll chip row using --accent-mine.
   Empty-state when items is empty.

4. Rewrite LibraryPanel.tsx content:
   Remove all file-tree logic.
   Add pill filter row (local useState, default: 'all').
   Render LibraryCard components in 2-column CSS grid, filtered by active pill.
   Empty-state message when filter yields zero cards.
   Render MyLibraryChips below the card grid.

5. Run: node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
   Fix all type errors before finishing.

Acceptance criteria: pathly/plans/studio-sidebar-redesign/USER_STORIES.md (S3: AC3.1–AC3.9, S4: AC4.1–AC4.6, S6: AC6.1–AC6.5)
Progress checklist: pathly/plans/studio-sidebar-redesign/PROGRESS.md
```

---

## Conv 3 — Drag-to-canvas for all library item types

**Stories:** S5
**Precondition:** Conv 2 complete and type-check passing. `LibraryCard.tsx` and `MyLibraryChips.tsx` exist with no drag logic.

**Builder prompt:**

```
Implement Conv 3 of the studio-sidebar-redesign feature.

Stories delivered: S5 (drag library items onto canvas).
Plan files: C:\Users\Yafit\pathly-adapters\pathly\plans\studio-sidebar-redesign\

Files to modify:
- studio/src/renderer/src/components/sidebar/items/LibraryCard.tsx
- studio/src/renderer/src/components/sidebar/items/MyLibraryChips.tsx
- studio/src/renderer/src/components/sidebar/Sidebar.module.css (cursor + affordance styles)

Files NOT to modify:
- Any canvas component or canvas drop handler
- studio/src/renderer/src/types/index.ts (read only — use PathlyCanvasDragItem as-is)

Work in this order:

1. Read studio/src/renderer/src/types/index.ts. Confirm:
   - PATHLY_DRAG_MIME constant value
   - PathlyCanvasDragItem shape: { dragType: 'canvas', name: string, section: PathlySection, path: string[] }
   Document the mapping from (type, id, name) → (section, path) for each library item type.

2. Add drag to LibraryCard.tsx:
   - draggable={true} on root element
   - onDragStart: dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify({ dragType: 'canvas', name, section, path }))
   - CSS: cursor: grab on hover, cursor: grabbing while dragging (use :active or a dragging className)
   - Visible drag-handle affordance rendered by default (not hover-only) — use a grip icon or CSS dot grid

3. Extend LibraryCard for Flow type to support expandable nested items:
   - Flows can expand to show child items
   - Each child item has draggable={true} with its own onDragStart payload
   - Child onDragStart calls event.stopPropagation() — parent card drag must NOT fire
   - Children also carry drag-handle affordances

4. Add drag to MyLibraryChips.tsx:
   - draggable={true} on each chip
   - onDragStart: same PATHLY_DRAG_MIME + PathlyCanvasDragItem payload
   - cursor: grab on hover, drag-handle affordance visible by default

5. Verify (by code inspection):
   - Every onDragStart produces a valid PathlyCanvasDragItem payload
   - Canvas drop handler file is unmodified
   - No other drop handler files are broken

6. Run: node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
   Fix all type errors before finishing.

Acceptance criteria: pathly/plans/studio-sidebar-redesign/USER_STORIES.md (S5: AC5.1–AC5.8)
Progress checklist: pathly/plans/studio-sidebar-redesign/PROGRESS.md
```
