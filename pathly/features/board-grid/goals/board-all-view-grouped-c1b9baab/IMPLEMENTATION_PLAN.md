# board-grid — Implementation Plan

## Overview

Add a 4th "All" tab to the Studio Command Center's `CommsPanel` that renders every board item
as compact, kind-banded tiles (Goals → Tasks → Messages → Artifacts). Presentation layer only —
no data model changes, no backend changes, no store changes. Everything lives in
`studio/src/renderer/src/components/CommandCenter/CommsPanel/`.

## Layer Architecture

```
Existing:  CommsPanel → boardView state → BoardViewToggle (3 tabs) → CommsMsgList/GoalsView/ArtifactsView
New:       CommsPanel → boardView === 'grid' → GridView(messages)
                                                  ├── gridBands() → {goals, tasks, messages, artifacts}
                                                  ├── Band × 4: section header + responsive tile grid
                                                  │     └── Tile × N → onOpen(m)
                                                  └── open() dispatch → GoalDetailModal | ArtifactModal | MessageDetailModal
```

## Prerequisites

- `studio/src/renderer/src/components/CommandCenter/CommsPanel/` directory exists (verified)
- `useFocusTrap`, `Timestamp`, `MessageTypeBadge`, `MsgCard`, `GoalDetailModal`, `ArtifactModal` all exist (verified)
- `BoardView` union is currently in `BoardViewToggle.tsx` line 6 (verified — not in `types.ts`)

---

## Phase 1: `gridBands.ts` — pure split function   ← Conversation: 1

**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/gridBands.ts` — CREATE

**Done when:** The file exports `GridBands`, `BAND_ORDER`, and `gridBands()`; every board `Message` lands in exactly one band; a basic import from a sibling file compiles cleanly.

**Delivers stories:** S3, S5

**Depends on:** nothing (pure TypeScript, no React)

**Enables:** Phase 2 (Tile imports `Message` type), Phase 4 (GridView consumes this)

**Details:**
- Import `type { Message } from '../../types'`
- Export `GridBands` interface: `{ goals: Message[]; tasks: Message[]; messages: Message[]; artifacts: Message[] }`
- Export `BAND_ORDER`: `Array<{ key: keyof GridBands; label: string }>` — fixed order Goals/Tasks/Messages/Artifacts
- Export `gridBands(messages: Message[]): GridBands` — single-pass O(n) bucketing; `else` is the catch-all for the messages band (includes phase/monitor rows — intentional for the "All" tab)
- No sorting — preserve server order

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 2: `Tile` component   ← Conversation: 1

**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/Tile/Tile.tsx` — CREATE
**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/Tile/Tile.module.css` — CREATE

**Done when:** `Tile` renders badge + 2-line-clamped title + meta row; `data-type` attribute is set; left-accent tints exist for all 13 message types; `onOpen` fires on click.

**Delivers stories:** S3, S5

**Depends on:** Phase 1 (Message type)

**Enables:** Phase 4 (GridView renders Tile)

**Details:**

`Tile.tsx` (~70 lines):
- Props: `{ message: Message; onOpen: (m: Message) => void }`
- Root element: `<button type="button" className={s.tile} data-type={message.type} onClick={() => onOpen(message)}>`
- Row 1: `<MessageTypeBadge type={message.type} />` — import from `../../MessageTypeBadge/MessageTypeBadge`
- Row 2: `<div className={s.title}>` — 2-line clamp via CSS (no inline style)
- Row 3 meta: author (`message.from`) · `<Timestamp mode="relative" ts={message.ts} />` · for artifacts: `message.atype ?? ''` · for tasks: `message.taskStatus ?? ''`
  - Import `Timestamp` from `../../../../Timestamp/Timestamp`
- Pure/presentational — no state, no modal logic

`Tile.module.css`:
- `.tile`: `display: flex; flex-direction: column; gap: 4px; padding: 8px; border-left: 3px solid var(--border); background: var(--bg-surface1); border-radius: 4px; cursor: pointer; min-width: 0; overflow: hidden`
- `.title`: `-webkit-line-clamp: 2; display: -webkit-box; -webkit-box-orient: vertical; overflow: hidden`
- `.meta`: `display: flex; gap: 6px; font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0`
- Per-type left-border tints via `data-type` selectors (all 13 types as in ARCHITECTURE_PROPOSAL.md §8)

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 3: `MessageDetailModal` — MsgCard in a portal shell   ← Conversation: 1

**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/MessageDetailModal/MessageDetailModal.tsx` — CREATE
**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/MessageDetailModal/MessageDetailModal.module.css` — CREATE

**Done when:** `MessageDetailModal` renders a dimmed backdrop with a `MsgCard` inside a focus-trapped box; Escape and click-outside close it; no action handlers passed to `MsgCard`.

**Delivers stories:** S3

**Depends on:** nothing (standalone modal pattern)

**Enables:** Phase 4 (GridView uses this modal)

**Details:**

`MessageDetailModal.tsx` (~55 lines):
- Props: `{ message: Message; siblings: Message[]; onClose: () => void }`
- `useFocusTrap(boxRef)` — import from `../../../../hooks/useFocusTrap`
- `useEffect` for Escape key → `onClose` (same pattern as `ArtifactModal`)
- `createPortal(...)` to `document.body`
- Backdrop: `<div className={s.backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}`
- Box: `<div ref={boxRef} role="dialog" aria-modal="true" aria-label="Message details" className={s.box}>`
- Close button: `<button type="button" className={s.close} onClick={onClose} aria-label="Close"><X size={15} /></button>`
- `<MsgCard message={message} flash={false} siblings={siblings} />` — import from `../cards/MsgCard/MsgCard`
- **No** `onDelete`/`onSupersede`/`onAnswer`/`onResolve` handlers → read-only

`MessageDetailModal.module.css`:
- `.backdrop`: fixed overlay, dimmed (same pattern as `ArtifactModal.module.css`)
- `.box`: centered scrollable box, `max-width: 640px`, `max-height: 80vh`
- `.close`: absolute top-right close button

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 4: `GridView` component   ← Conversation: 2

**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/GridView.tsx` — CREATE
**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/GridView.module.css` — CREATE

**Done when:** `GridView` renders non-empty bands in order with sticky headers; the responsive grid reflowing at 3/2/1 columns works via container query; the placeholder banner appears at ≤220px; all three modals open and close correctly; no inline styles.

**Delivers stories:** S2, S3, S4, S5

**Depends on:** Phase 1 (gridBands), Phase 2 (Tile), Phase 3 (MessageDetailModal)

**Enables:** Phase 6 (CommsPanel imports GridView)

**Details:**

`GridView.tsx` (~120 lines):
- Props: `{ messages: Message[]; boardKey: string; boardScope: BoardScope }`
  - Import `type { BoardScope, Message } from '../../types'`
- `useRef<HTMLDivElement>(null)` for the root + `ResizeObserver` effect to track width
- `const [narrow, setNarrow] = useState(false)` — true when width ≤ 220
- `const bands = useMemo(() => gridBands(messages), [messages])`
- Three modal states: `openGoalId`, `openArtifact`, `openMessage` (all nullable)
- `open(m: Message)` dispatcher: goal → `setOpenGoalId(m.id)`; task → `setOpenGoalId(m.goal_id ?? null)` (guard: only mount GoalDetailModal when non-null); artifact → `setOpenArtifact(m)`; else → `setOpenMessage(m)`
- Render: if `narrow`, render `<div className={s.placeholder}>Grid view is best in a wider board — widen to see the grid</div>`
- Otherwise: `BAND_ORDER.map(({ key, label }) => ...)` — skip empty bands; for each non-empty band render `<section>` with sticky header + `.grid` div of `<Tile>` elements
- Import GoalDetailModal, ArtifactModal, MessageDetailModal; render conditionally at bottom
- Pass `messages` + `boardKey` + `boardScope` to `GoalDetailModal` (same as `GoalsView`)
- Guard `GoalDetailModal`: mount only when `openGoalId` is non-null

`GridView.module.css`:
- `.view`: `overflow-y: auto; overflow-x: hidden; flex: 1; min-height: 0`
- `.bands`: `display: flex; flex-direction: column; gap: var(--space-4); padding: var(--space-2)`
- `.band header`: `position: sticky; top: 0; background: var(--bg-surface1); padding: 6px 0 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em`
- `.count`: `color: var(--text-muted); font-weight: 400`
- `.grid`: `container-type: inline-size; container-name: gridband; display: grid; grid-template-columns: 1fr; gap: var(--space-2)`
- `@container gridband (min-width: 400px)`: 2-col `repeat(2, minmax(0, 1fr))`
- `@container gridband (min-width: 600px)`: 3-col `repeat(3, minmax(0, 1fr))`
- `.placeholder`: `padding: var(--space-4); text-align: center; color: var(--text-muted); font-size: 13px`

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 5: `BoardViewToggle.tsx` — widen union + 4th tab   ← Conversation: 2

**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/BoardViewToggle/BoardViewToggle.tsx` — EDIT

**Done when:** `BoardView` includes `'grid'`; the `VIEWS` array has a 4th entry with `LayoutGrid`; `LayoutGrid` is imported from `lucide-react`; existing tests/snapshots unaffected.

**Delivers stories:** S1, S6

**Depends on:** nothing (standalone union widening)

**Enables:** Phase 6 (CommsPanel uses `boardView === 'grid'`)

**Details:**
- Line 2: add `LayoutGrid` to the `lucide-react` named imports
- Line 6: widen union → `export type BoardView = 'messages' | 'goals' | 'artifacts' | 'grid'`
- Append to `VIEWS` array: `{ id: 'grid', label: 'All', icon: <LayoutGrid size={12} /> }`
- No other changes — the toggle's render loop is generic over `VIEWS`, so no additional edits needed

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 6: `CommsPanel.tsx` — rightAction + GridView branch   ← Conversation: 2

**File:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/CommsPanel/CommsPanel.tsx` — EDIT

**Done when:** `boardView === 'grid'` renders `<GridView>`; `rightAction` is `null` for `'grid'`; the three existing views are unchanged; tsc is green.

**Delivers stories:** S2, S6

**Depends on:** Phase 4 (GridView exists), Phase 5 (BoardView includes 'grid')

**Enables:** Feature is complete

**Details:**
- Add import: `import { GridView } from '../GridView/GridView'`
- Restructure `rightAction` prop ternary so `messages` → `MessagesFilter`, `goals` → `NewGoalButton` + `EvaluateBoardButton`, `artifacts` → `SummaryConfig`, `grid` (catch-all `null`):
  ```tsx
  rightAction={
    boardView === 'goals'     ? <><NewGoalButton .../><EvaluateBoardButton .../></> :
    boardView === 'artifacts' ? <SummaryConfig .../> :
    boardView === 'messages'  ? <MessagesFilter .../> :
    null  /* grid */
  }
  ```
- After the existing `{boardView === 'artifacts' && <ArtifactsView .../>}` block, add:
  ```tsx
  {boardView === 'grid' && (
    <GridView
      messages={messages}
      boardKey={feature}
      boardScope={scope}
    />
  )}
  ```
- Verify `boardKey` maps to `feature` (the string from `useCommsPanel`) and `boardScope` to `scope` prop — match GoalsView's pattern

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Key Decisions

- **gridBands is pure and side-effect-free** — `CommsMsgList`/`GoalsView` are NOT refactored to use it (their filter logic differs; the SPEC's "shared helper" intent is satisfied by `gridBands` existing as the canonical All-tab split).
- **Tasks band is flat** — no per-goal grouping. Task→goal linking happens in `GoalDetailModal`, not the grid.
- **Messages band is the catch-all** (`else`) — phase/monitor rows intentionally appear as tiles here ("All" means all).
- **`container-type` on `.grid` not on scroll root** — prevents sticky header clipping (architecture risk mitigated).
- **`minmax(0, 1fr)` not `1fr`** — prevents column blow-out from long unbroken text.
- **MessageDetailModal is read-only** — no action handlers passed to `MsgCard`.
- **Ungrouped tasks (no `goal_id`) are no-ops** — do not open an empty `GoalDetailModal`.
