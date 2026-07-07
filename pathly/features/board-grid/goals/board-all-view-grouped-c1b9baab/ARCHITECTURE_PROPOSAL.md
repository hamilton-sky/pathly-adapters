# Board-Grid — Architecture Proposal

**Feature:** `board-grid` · **Goal:** `board-all-view-grouped-c1b9baab`
**Scope:** presentation-only. A 4th "All" tab in the Command Center's `CommsPanel` that renders
every board item as compact, kind-banded tiles (Goals → Tasks → Messages → Artifacts).
**No data-model changes.** All content already arrives as `messages: Message[]`; the whole feature
is a new way to project that array.

Base path for all files below:
`studio/src/renderer/src/components/CommandCenter/CommsPanel/`

---

## 1. Layers touched

Everything lives in the renderer (`studio/src/renderer/`). Four existing files change; one new
component family is added. No store, IPC, main-process, or Python change.

```
CommsPanel/
  BoardViewToggle/
    BoardViewToggle.tsx        EDIT  — add 'grid' to BoardView union + 4th VIEWS entry
  CommsPanel/
    CommsPanel.tsx             EDIT  — rightAction null-branch + <GridView> render branch
  GridView/                    NEW   — the whole feature
    GridView.tsx                      bands + responsive grid + modal wiring (state owner)
    GridView.module.css
    gridBands.ts                      pure split Message[] → { goals, tasks, messages, artifacts }
    Tile/
      Tile.tsx                        one compact tile (badge + title + meta)
      Tile.module.css
  MessageDetailModal/          NEW   — MsgCard in a generic modal shell
    MessageDetailModal.tsx
    MessageDetailModal.module.css
```

`types.ts` does **not** change — `BoardView` is defined in `BoardViewToggle.tsx` (line 6), not in
`types.ts`. That is the single source of the union.

Reused as-is (no edits): `MessageTypeBadge`, `GoalDetailModal`, `ArtifactModal`, `MsgCard`,
`Timestamp`, `formatRelative`.

---

## 2. Component breakdown

### 2.1 `GridView` — band host + state owner
- **File:** `GridView/GridView.tsx` · **Budget:** ~120 lines
- **Responsibility:** call `gridBands(messages)`, render up to 4 `<section>` bands (each with a
  count header + a responsive tile grid), own all three "which modal is open" states, and render
  the three modals. It is the only stateful component in the family.
- **Props:**
  ```ts
  interface GridViewProps {
    messages: Message[]
    boardKey: string
    boardScope: BoardScope
  }
  ```
  `boardKey`/`boardScope` are required because `GoalDetailModal` needs them (note-saving path),
  matching how `GoalsView` receives them today.

### 2.2 `Tile` — one item
- **File:** `GridView/Tile/Tile.tsx` · **Budget:** ~70 lines
- **Responsibility:** render one compact tile: `MessageTypeBadge` + 2-line-clamped title + a meta
  row (author · relative time · atype/status). Pure/presentational — no modal state, no data
  fetching. Emits a single `onOpen` callback.
- **Props:**
  ```ts
  interface TileProps {
    message: Message
    onOpen: (m: Message) => void
  }
  ```
  The tile is a `<button type="button">` so it is keyboard-focusable and click-to-open for free.

### 2.3 `MessageDetailModal` — message tile target
- **File:** `MessageDetailModal/MessageDetailModal.tsx` · **Budget:** ~55 lines
- **Responsibility:** a portal + backdrop + focus-trap shell that renders a single read-only
  `MsgCard` for one message. See §7.
- **Props:**
  ```ts
  interface MessageDetailModalProps {
    message: Message
    siblings: Message[]
    onClose: () => void
  }
  ```

### 2.4 `gridBands.ts` — pure split
- **File:** `GridView/gridBands.ts` · **Budget:** ~40 lines. No React import. See §4.

---

## 3. Data flow

`messages` is already the fully-hydrated board array in `CommsPanel` (from `useCommsPanel`). The
grid is a pure downstream projection — same source `CommsMsgList`, `GoalsView`, and `ArtifactsView`
consume. Nothing new is fetched.

```
CommsPanel (owns messages: Message[])
   │  boardView === 'grid'
   ▼
GridView(messages, boardKey, boardScope)
   │
   ├─ gridBands(messages) ──► { goals[], tasks[], messages[], artifacts[] }
   │
   ├─ for each non-empty band:
   │     <section> [count header]
   │       <div grid>  band.map(m => <Tile message={m} onOpen={open} />)
   │
   └─ open(m) sets one of { openGoalId | openArtifact | openMessage }
         └─► renders GoalDetailModal | ArtifactModal | MessageDetailModal
```

Ordering within a band is the array order as delivered (server order). No sort is introduced — the
Messages thread today does not re-sort, so we stay consistent. (If a chronological sort is later
wanted it belongs in `gridBands`, not the view.)

---

## 4. `gridBands.ts`

A single pure function. One pass over `messages`, bucketed by kind. Band order is **fixed** and
matches the SPEC: **Goals → Tasks → Messages → Artifacts**.

```ts
import type { Message } from '../../types'

export interface GridBands {
  goals: Message[]
  tasks: Message[]
  messages: Message[]   // everything that is not goal/task/artifact
  artifacts: Message[]
}

// Ordered list the view iterates — keeps band order + labels in one place.
export const BAND_ORDER: Array<{ key: keyof GridBands; label: string }> = [
  { key: 'goals', label: 'Goals' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'messages', label: 'Messages' },
  { key: 'artifacts', label: 'Artifacts' },
]

export function gridBands(messages: Message[]): GridBands {
  const goals: Message[] = []
  const tasks: Message[] = []
  const msgs: Message[] = []
  const artifacts: Message[] = []
  for (const m of messages) {
    if (m.type === 'goal') goals.push(m)
    else if (m.type === 'task') tasks.push(m)
    else if (m.type === 'artifact') artifacts.push(m)
    else msgs.push(m)              // nudge/decision/question/answer/status/
  }                                 // discovery/warning/escalation/phase/note
  return { goals, tasks, messages: msgs, artifacts }
}
```

**Decisions:**
- **Messages band is the catch-all** (`else`), so every board item lands in exactly one band and
  nothing is silently dropped. This is deliberately more inclusive than the Messages *thread*
  (`CommsMsgList` hides `phase` + supervisor/system `status` in a Monitor lane). The "All" tab's
  contract is *show everything*, so phase/monitor rows appear as tiles here.
- **Tasks band is flat** — no per-goal grouping (SPEC). Grouping is `GoalDetailModal`'s job.
- **Pinned messages are not special-cased** — a pinned decision is just a `decision` tile in the
  Messages band. The grid is a flat inventory, not the thread.
- Pure and side-effect-free → trivially unit-testable and reusable. `CommsMsgList`/`GoalsView` are
  **not** refactored to consume it in P1 (they filter inline and their logic differs — the Monitor
  split, ungrouped-task handling); forcing a shared helper there now would be a lossy merge. The
  SPEC's "factor out a shared helper" intent is satisfied by `gridBands` being the one home for the
  All-tab split; converging the other two views is out of scope.

---

## 5. Responsive strategy

Container-query driven, mirroring the existing `container-type: inline-size` pattern. The grid
column count follows the **band's own width**, so tiles reflow correctly even when the Command
Center is split into narrow side-by-side panels (container query, not viewport `@media`).

**Container placement:** the `container-type` goes on the tile-grid wrapper inside each band
(`.grid`), not on `GridView`'s scroll root. Putting it on the grid element means each grid is its
own query container and the `@container` rules resolve against the real available width. Give it a
name to avoid accidental nesting matches:

```css
/* GridView.module.css */
.grid {
  container-type: inline-size;
  container-name: gridband;
  display: grid;
  grid-template-columns: 1fr;          /* <400px default: 1 col */
  gap: var(--space-2);
}

@container gridband (min-width: 400px) {
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@container gridband (min-width: 600px) {
  .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
```

- `minmax(0, 1fr)` (not `1fr`) is required so columns can shrink below tile content width — the grid
  analogue of the `min-width: 0` flex rule. Without it, long unbroken titles blow out the columns.
- Breakpoints exactly per SPEC: **≥600 = 3-col, 400–599 = 2-col, <400 = 1-col.**

**Placeholder banner at ≤~220px:** below ~220px even a single column is too cramped to be legible.
Rather than a third CSS breakpoint (a `@container` can hide the grid but can't easily swap in
replacement content), detect width in JS and swap the whole band body for a one-line banner.

Use a `ResizeObserver` on `GridView`'s root (one observer for the whole view, not per band):

```
width ≤ 220px  → render <PlaceholderBanner> ("Panel too narrow — widen to see the grid")
width  > 220px → render the bands
```

This keeps the ≤200px verification rule satisfied: at ≤200px the panel shows a single contained
banner with `overflow: hidden`, nothing escapes. The banner is a small inline block inside
`GridView.tsx` (a few lines) — not worth its own folder; if it grows, extract to
`GridView/PlaceholderBanner/`.

**Band header** carries the label + count: `Goals · 3`. Sticky within the scroll container
(`position: sticky; top: 0`) so the kind label stays visible while scrolling a long band.

---

## 6. Modal wiring

**State lifts to `GridView`** — it is the lowest common ancestor of all tiles and already re-renders
on `messages` change. Three mutually-exclusive open-states (a tile opens exactly one modal):

```ts
const [openGoalId, setOpenGoalId]   = useState<string | null>(null)
const [openArtifact, setOpenArtifact] = useState<Message | null>(null)
const [openMessage, setOpenMessage]   = useState<Message | null>(null)
```

A single `open(m: Message)` dispatcher, passed to every `Tile` as `onOpen`, routes by kind:

```ts
function open(m: Message): void {
  if (m.type === 'goal')          setOpenGoalId(m.id)
  else if (m.type === 'task')     setOpenGoalId(m.goal_id ?? null)  // task → its goal's modal
  else if (m.type === 'artifact') setOpenArtifact(m)
  else                            setOpenMessage(m)
}
```

Rendered conditionally at the bottom of `GridView` (each modal already self-portals to
`document.body`, so placement in the tree is irrelevant):

| Tile kind | Modal | Key props |
|---|---|---|
| goal | `GoalDetailModal` | `messages`, `initialGoalId={openGoalId}`, `boardKey`, `boardScope`, `onClose` |
| task | `GoalDetailModal` | same, `initialGoalId = task.goal_id` |
| artifact | `ArtifactModal` | `message={openArtifact}`, `onClose` |
| message | `MessageDetailModal` | `message={openMessage}`, `siblings={messages}`, `onClose` |

**Task → goal decision:** `GoalDetailModal` has no `focusTaskId` prop (confirmed, lines 18–24).
Clicking a task tile opens its goal's modal on the DAG tab; scroll-to-task is **P2 polish**, not P1.
**Edge case:** a task whose `goal_id` is missing/unknown (`ungrouped`) → `openGoalId` becomes
`null`. Guard the render: only mount `GoalDetailModal` when `openGoalId` is a non-null id that
resolves to a real goal message; otherwise no-op the click (a task with no goal has no goal modal to
show). This mirrors `GoalsView`'s ungrouped handling and avoids opening an empty modal.

---

## 7. `MessageDetailModal` — why MsgCard-in-a-shell

Goals and artifacts have purpose-built modals; plain messages do not. Building a bespoke
message-detail modal for P1 would duplicate everything `MsgCard` already renders (badge, avatar,
author, body via `CardBody`/`MarkdownRenderer`, footer, timestamp, answer/resolve affordances).

**Decision:** wrap the existing `MsgCard` in a minimal portal shell. `MsgCard` is the canonical,
already-styled message renderer — reusing it guarantees the modal view matches the thread view and
inherits future card improvements for free. The shell contributes only: portal → `document.body`,
dimmed backdrop with click-outside close, `useFocusTrap` on the box, and Escape-to-close — exactly
the pattern `ArtifactModal` and `GoalDetailModal` already use.

```tsx
// MessageDetailModal.tsx (~55 lines)
export function MessageDetailModal({ message, siblings, onClose }: MessageDetailModalProps) {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)
  useEffect(() => { /* Escape → onClose, same as siblings */ }, [onClose])
  return createPortal(
    <div className={s.backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={boxRef} role="dialog" aria-modal="true" aria-label="Message details" className={s.box}>
        <button type="button" className={s.close} onClick={onClose} aria-label="Close"><X size={15} /></button>
        <MsgCard message={message} flash={false} siblings={siblings} />
      </div>
    </div>,
    document.body,
  )
}
```

**Read-only on purpose:** `MsgCard` is passed **no** `onDelete`/`onSupersede`/`onAnswer`/`onResolve`
handlers, so it renders as a clean detail view with no destructive actions inside the grid's modal.
`siblings` is passed only because `MsgCard`'s type allows it; with no `onSupersede` the
`SupersedeMenu` never renders. Interactive question/answer flows stay in the Messages *thread* — the
All tab is an overview surface.

---

## 8. CSS approach — `data-type` tint, zero inline styles

The tile reuses `MessageTypeBadge` for the badge itself, so the badge's own tint (owned by
`MessageTypeBadge.module.css`) is free. For the **tile surface** tint (left accent bar / faint
background per kind) the tile carries a `data-type` attribute and `Tile.module.css` owns the
selectors, mirroring the token families already used by `MessageTypeBadge.module.css`:

```tsx
// Tile.tsx
<button type="button" className={s.tile} data-type={message.type} onClick={() => onOpen(message)}>
```
```css
/* Tile.module.css — mirror the MessageTypeBadge token families */
.tile { border-left: 3px solid var(--border); background: var(--bg-surface1); }
.tile[data-type='goal']       { border-left-color: var(--blue); }
.tile[data-type='task']       { border-left-color: var(--purple); }
.tile[data-type='artifact']   { border-left-color: var(--runtime); }
.tile[data-type='decision'],
.tile[data-type='nudge']      { border-left-color: var(--accent); }
.tile[data-type='question']   { border-left-color: var(--yellow); }
.tile[data-type='answer']     { border-left-color: var(--green); }
.tile[data-type='warning']    { border-left-color: var(--orange); }
.tile[data-type='escalation'] { border-left-color: var(--red); }
.tile[data-type='discovery']  { border-left-color: var(--blue); }
.tile[data-type='status'],
.tile[data-type='phase'],
.tile[data-type='note']       { border-left-color: var(--text-muted); }
```

- **Every color comes from `tokens.css` vars** — no literals, no `useTheme()` in JSX.
- **No `style={{}}`** anywhere in the family. The only per-element dynamic value is `data-type`,
  which is a data attribute, not a style prop — fully within the rules.
- **Title 2-line clamp** via `-webkit-line-clamp: 2` + `display: -webkit-box` in CSS.
- **`min-width: 0`** on the tile's inner flex column and on the meta row's flex children so long
  authors/paths ellipsize instead of overflowing. `overflow: hidden` on the scroll root
  (`GridView.module.css .view`) — never `overflow: visible`.
- Meta row uses `text-overflow: ellipsis; white-space: nowrap; overflow: hidden` on each segment.

---

## 9. TypeScript surface

All changes are additive; `tsc --noEmit -p studio/tsconfig.web.json` must stay green.

1. **`BoardView` union** (`BoardViewToggle.tsx` line 6):
   ```ts
   export type BoardView = 'messages' | 'goals' | 'artifacts' | 'grid'
   ```
   Because `CommsPanel`'s `boardView` state is typed `BoardView`, this one edit widens it
   everywhere. The `rightAction` ternary in `CommsPanel` must gain a branch that yields `null` for
   `'grid'` (no right action on the All tab) — TS will not force this, but the SPEC requires it, and
   the existing final `else` currently returns `<MessagesFilter>`, so the ternary must be
   restructured so only `messages` gets the filter:
   ```tsx
   rightAction={
     boardView === 'goals'     ? <NewGoalButton .../> :
     boardView === 'artifacts' ? <SummaryConfig .../> :
     boardView === 'messages'  ? <MessagesFilter .../> :
     null                       /* grid */
   }
   ```

2. **`VIEWS` entry** (`BoardViewToggle.tsx` line 8–12): append
   `{ id: 'grid', label: 'All', icon: <LayoutGrid size={12} /> }` and add `LayoutGrid` to the
   `lucide-react` import on line 2.

3. **New exported types** in `gridBands.ts`: `GridBands`, `BAND_ORDER` (§4).

4. **New component prop interfaces**: `GridViewProps`, `TileProps`, `MessageDetailModalProps` (§2).

No change to `Message` or `MessageType` — the grid reads existing fields only
(`type`, `from`, `text`, `ts`, `goal_id`, `atype`, `taskStatus`, `artifact`).

---

## 10. Key risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **4 tab buttons overflow at ≤200px** — `BoardViewToggle` already fits 3; a 4th "All" tightens the segmented control. | Buttons clip / labels collide. | The toggle already hides labels via `.segLabel` at narrow widths (icon-only) with a `Tooltip`. Keep the "All" label short and rely on the existing icon-only collapse. Verify the seg row at ≤200px; if it still overflows, the existing `min-width: 0` + label-hide handles it — no new layout needed. Do **not** widen the toggle. |
| **Container query placement** — putting `container-type` on the scroll root makes all bands query the same width and defeats per-band reflow; also `container-type` establishes containment that can clip sticky headers. | Wrong column counts; sticky header bugs. | Put `container-type: inline-size` on each `.grid` (the tile wrapper), **not** on the band `<section>` or the scroll root. Sticky band headers live on the `<section>`, outside the query container, so containment doesn't clip them. |
| **`GoalDetailModal` needs `messages`** — it filters goals/tasks from the full array, not a single goal object. | Passing only the goal message → empty DAG. | `GridView` already holds the full `messages` array; pass it straight through (same as `GoalsView` does). `boardKey`/`boardScope` also threaded through for the note-save path. |
| **Task tile with unknown `goal_id`** (ungrouped). | Opening an empty goal modal. | Guard: only open `GoalDetailModal` when `goal_id` resolves to a real goal message; otherwise the click is a no-op (§6). |
| **Messages band pulls in monitor/phase noise** the thread hides. | Grid looks noisier than the thread. | Intentional — "All" means all. Documented in §4. If it proves noisy, a future filter chip can hide monitor rows; not P1. |
| **`MsgCard` inside modal renders destructive actions.** | Delete/supersede from a read-only overview. | Pass no action handlers (§7) — the buttons don't render. |
| **File-size creep** past ~150 lines. | Violates the size rule. | `GridView` stays lean by delegating: `gridBands` (split), `Tile` (item), band rendering is a `BAND_ORDER.map`. If it approaches 150, extract the band renderer into `GridView/Band/Band.tsx`. |

---

## 11. Acceptance checklist

Maps 1:1 to the SPEC acceptance criteria. Each is verifiable by a builder.

- [ ] `BoardView` union includes `'grid'`; `VIEWS` has a 4th entry `{ id:'grid', label:'All', icon:<LayoutGrid size={12}/> }`.
- [ ] Selecting the **All** tab renders `<GridView messages boardKey boardScope />`; the other three tabs are unchanged.
- [ ] `rightAction` is `null` when `boardView === 'grid'` (no per-view action on the All tab); `messages` still gets `MessagesFilter`, `goals` gets `NewGoalButton`, `artifacts` gets `SummaryConfig`.
- [ ] Content renders as bands in order **Goals → Tasks → Messages → Artifacts**; empty bands are omitted; each rendered band shows a count header (`Label · N`).
- [ ] Each tile shows: `MessageTypeBadge` + 2-line-clamped title + meta (author · relative time via `<Timestamp mode="relative">`/`formatRelative` · atype for artifacts / status for tasks).
- [ ] Clicking a **goal** tile opens `GoalDetailModal` at that goal; **task** tile opens `GoalDetailModal` at `task.goal_id` (no-op if unknown); **artifact** tile opens `ArtifactModal`; **message** tile opens `MessageDetailModal` (MsgCard in a shell).
- [ ] Tasks band is flat (no per-goal grouping).
- [ ] Grid is responsive via **container query**: ≥600px = 3-col, 400–599px = 2-col, <400px = 1-col; ≤~220px shows the placeholder banner.
- [ ] No inline styles anywhere; per-type tint via `data-type` + `Tile.module.css` selectors using `tokens.css` vars only.
- [ ] `min-width: 0` on all flex children; `minmax(0,1fr)` grid columns; verified visually at ≤200px (banner, nothing escapes) and ~700px (3-col).
- [ ] Every new component in its own folder with a co-located `.module.css`; each file ≤ ~150 lines.
- [ ] No data-model change (no edits to `types.ts` `Message`/`MessageType`).
- [ ] `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes clean.

---

## Appendix — import paths (depth-checked)

From `GridView/GridView.tsx`:
- `import type { BoardScope, Message } from '../../types'`
- `import { gridBands, BAND_ORDER } from './gridBands'`
- `import { Tile } from './Tile/Tile'`
- `import { GoalDetailModal } from '../GoalDetailModal/GoalDetailModal'`
- `import { ArtifactModal } from '../ArtifactModal/ArtifactModal'`
- `import { MessageDetailModal } from '../MessageDetailModal/MessageDetailModal'`

From `GridView/Tile/Tile.tsx`:
- `import type { Message } from '../../../types'`
- `import { MessageTypeBadge } from '../../MessageTypeBadge/MessageTypeBadge'`
- `import { Timestamp } from '../../../../Timestamp/Timestamp'`

From `MessageDetailModal/MessageDetailModal.tsx`:
- `import type { Message } from '../../types'`
- `import { MsgCard } from '../cards/MsgCard/MsgCard'`
- `import { useFocusTrap } from '../../../../hooks/useFocusTrap'`
