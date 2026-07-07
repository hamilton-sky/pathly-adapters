# board-grid — User Stories

## Context

The Studio Command Center's `CommsPanel` has three filtered tabs (Messages / Goals & Tasks / Artifacts).
A human supervisor monitoring headless agent runs has no single view that shows everything at once —
they must switch tabs to get a full picture of the board. This feature adds a 4th **"All"** tab that
renders the entire board as compact, kind-banded tiles, giving the supervisor a dense ticket-board
overview without changing the data model or any existing tab.

---

## Stories

### Story 1: 4th tab appears in BoardViewToggle

**As a** human supervisor, **I want** an "All" tab added to the board view toggle, **so that** I can switch to a tile-grid overview without losing access to the existing three tabs.

**Acceptance Criteria:**
- [ ] `BoardView` union includes `'grid'` (in `BoardViewToggle.tsx`)
- [ ] `VIEWS` array has a 4th entry: `{ id: 'grid', label: 'All', icon: <LayoutGrid size={12} /> }`
- [ ] `LayoutGrid` is imported from `lucide-react`
- [ ] The three existing tabs (messages, goals, artifacts) are unchanged
- [ ] `tsc --noEmit -p studio/tsconfig.web.json` passes

**Edge Cases:**
- Labels collapse to icon-only at ≤400px via the existing container-query — 4 icons must still fit
- Do NOT widen the `BoardViewToggle` control to accommodate the 4th button

**Delivered by:** Phase 5 → Conversation 2

---

### Story 2: Selecting "All" renders a banded tile grid

**As a** human supervisor, **I want** the board to render as kind-banded tiles when I select "All", **so that** I can scan everything on the board at a glance.

**Acceptance Criteria:**
- [ ] Selecting the All tab renders `<GridView messages={messages} boardKey={...} boardScope={...} />`
- [ ] `rightAction` in `BoardViewToggle` is `null` when `boardView === 'grid'` (no per-view action)
- [ ] The three existing tab views (CommsMsgList, GoalsView, ArtifactsView) are unchanged
- [ ] Content renders as bands in order: **Goals → Tasks → Messages → Artifacts**
- [ ] Empty bands are omitted; each rendered band shows a count header (`Label · N`)
- [ ] Band headers are sticky within the scroll container

**Edge Cases:**
- If the board is empty, GridView renders nothing (no bands, no placeholder bands)
- `rightAction` must yield `null` only for `'grid'`, not a fallback from the last `else`

**Delivered by:** Phases 4–6 → Conversation 2

---

### Story 3: Tile anatomy — compact + clickable

**As a** human supervisor, **I want** each tile to show type badge + title + meta and be clickable to open the correct detail modal, **so that** I can get full context on any item without switching tabs.

**Acceptance Criteria:**
- [ ] Each tile shows: `MessageTypeBadge` + 2-line-clamped title (`-webkit-line-clamp: 2`) + meta row
- [ ] Meta row contains: `from` (author) · relative time (`<Timestamp mode="relative">`) · `atype` for artifacts · `taskStatus` for tasks
- [ ] Clicking a **goal** tile opens `GoalDetailModal` at that goal's id
- [ ] Clicking a **task** tile opens `GoalDetailModal` at `task.goal_id` (no-op if `goal_id` is unknown)
- [ ] Clicking an **artifact** tile opens `ArtifactModal`
- [ ] Clicking a **message** tile opens `MessageDetailModal` (MsgCard in a portal shell)
- [ ] No action buttons on the tile itself (actions live in the modal)
- [ ] `MessageDetailModal` passes no action handlers to `MsgCard` (read-only)

**Edge Cases:**
- Task with missing/unknown `goal_id` → click is a no-op (do not open an empty modal)
- Tiles are `<button type="button">` — keyboard-focusable

**Delivered by:** Phases 1–4 → Conversations 1–2

---

### Story 4: Responsive grid with container query

**As a** human supervisor, **I want** the grid to reflow responsively based on available panel width, **so that** it works well whether the panel is narrow or wide.

**Acceptance Criteria:**
- [ ] Grid uses `container-type: inline-size; container-name: gridband` on the `.grid` wrapper (not the scroll root)
- [ ] ≥600px → 3-column grid (`minmax(0, 1fr)`)
- [ ] 400–599px → 2-column grid
- [ ] <400px → 1-column
- [ ] ≤~220px → placeholder banner ("Grid view is best in a wider board — widen to see the grid") detected via `ResizeObserver`; grid bands hidden
- [ ] At ≤200px, nothing escapes the panel (no overflow)

**Edge Cases:**
- `container-type` is on the `.grid` element (per-band), NOT on the scroll root — prevents sticky header clipping
- `minmax(0, 1fr)` (not `1fr`) prevents column blow-out from long unbroken titles

**Delivered by:** Phase 4 → Conversation 2

---

### Story 5: CSS — tokens only, no inline styles

**As a** developer, **I want** all styling to use CSS modules and `tokens.css` variables only, **so that** the feature respects the Studio design system.

**Acceptance Criteria:**
- [ ] No inline styles anywhere in the new component family
- [ ] Per-type tile tint via `data-type` attribute + `Tile.module.css` selectors + `tokens.css` vars
- [ ] `min-width: 0` on all flex children; `minmax(0, 1fr)` grid columns
- [ ] Tile meta row uses `text-overflow: ellipsis; white-space: nowrap; overflow: hidden` on each segment
- [ ] `overflow: hidden` on the scroll root (`.view`), never `overflow: visible`
- [ ] Each new component in its own folder with co-located `.module.css`; each file ≤~150 lines

**Edge Cases:**
- Long unbroken titles must not blow out tile width — handled by `minmax(0, 1fr)` + line-clamp

**Delivered by:** Phases 1–4 → Conversations 1–2

---

### Story 6: TypeScript stays clean

**As a** developer, **I want** `tsc --noEmit` to pass after the feature is merged, **so that** no new type errors are introduced.

**Acceptance Criteria:**
- [ ] No edits to `types.ts` `Message` or `MessageType` (presentation layer only)
- [ ] `BoardView` union widened in `BoardViewToggle.tsx` only (it is the single source of truth)
- [ ] All new interfaces defined in their co-located files
- [ ] `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes clean

**Delivered by:** Phase 5 → Conversation 2
