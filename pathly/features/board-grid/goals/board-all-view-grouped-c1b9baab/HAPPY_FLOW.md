# board-grid — Happy Flow

## Phase 1 — gridBands.ts

1. Developer imports `gridBands` in a sibling file.
2. They pass the full `messages: Message[]` array from `CommsPanel`.
3. One pass over the array buckets every item: goals in `goals[]`, tasks in `tasks[]`, artifacts in `artifacts[]`, everything else in `messages[]`.
4. The caller iterates `BAND_ORDER` to render bands in the fixed order (Goals → Tasks → Messages → Artifacts).
5. No item is silently dropped; no item appears in two bands.

## Phase 2 — Tile

1. `GridView` renders `<Tile message={m} onOpen={open} />` for each item in a band.
2. The tile shows the `MessageTypeBadge` color-coded by `message.type`.
3. The title is 2-line-clamped — long titles truncate cleanly without blowing out the grid column.
4. The meta row shows author, a relative timestamp, and (for artifacts) the atype or (for tasks) the taskStatus.
5. The left-accent border color matches the badge color via `data-type` CSS selectors — no inline styles.
6. The user clicks the tile → `onOpen(message)` fires → `GridView`'s dispatcher routes to the correct modal.

## Phase 3 — MessageDetailModal

1. The user clicks a message tile.
2. `GridView`'s `open()` sets `openMessage = m`.
3. `MessageDetailModal` portals to `document.body`, dimming the background.
4. Focus is trapped inside the box (keyboard navigation works without escaping the modal).
5. `MsgCard` renders the full message — badge, author, body (markdown), timestamp — with no action buttons (no delete, no supersede).
6. The user reads the detail, then presses Escape or clicks the × button → `onClose` fires → `openMessage` is cleared → modal unmounts.

## Phase 4 — GridView

1. `CommsPanel` passes `messages`, `boardKey`, `boardScope` to `<GridView>`.
2. `useMemo` computes `bands` synchronously — no fetch, no async.
3. The component checks panel width via `ResizeObserver`. Width > 220 → bands render.
4. The user sees up to 4 labeled sections (only non-empty bands appear), each with a sticky count header and a responsive tile grid.
5. At the panel's current width (say, ~700px), the grid shows 3 columns of tiles.
6. The user drags the panel narrower → at 400px the grid snaps to 2 columns → at <400px to 1 column.
7. The user drags narrower still to ≤220px → the placeholder banner appears instead of the grid.

## Phase 5 — BoardViewToggle

1. The toggle renders 4 segmented buttons: Messages, Goals & Tasks, Artifacts, All.
2. At ≤400px the labels hide; only icons show — all 4 icons fit comfortably.
3. The user clicks **All** → `onChange('grid')` fires → `boardView` in `CommsPanel` becomes `'grid'`.

## Phase 6 — CommsPanel wiring

1. `boardView === 'grid'`:
   - `rightAction` resolves to `null` (no per-view action button on the All tab).
   - The `CommsMsgList`, `GoalsView`, `ArtifactsView` blocks are all skipped.
   - `<GridView messages={messages} boardKey={feature} boardScope={scope} />` renders.
2. The user switches back to the Messages tab → `boardView` becomes `'messages'` → `CommsMsgList` renders, `GridView` unmounts.
3. No state leaks between tab switches.
