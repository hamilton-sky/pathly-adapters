# board-grid — Conversation Guide

Split into 2 conversations. Each produces runnable, type-checked code.
After each conversation, **commit your changes** before starting the next.

All files live under:
`studio/src/renderer/src/components/CommandCenter/CommsPanel/`

---

## Conversation 1: Leaf components — gridBands, Tile, MessageDetailModal (Phases 1–3)

**Stories delivered:** S3, S5

**Prompt to paste:**
```
Read pathly/features/board-grid/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement board-grid Conversation 1 (Phases 1–3) from pathly/features/board-grid/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation creates:**
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/gridBands.ts` — CREATE pure split function
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/Tile/Tile.tsx` — CREATE tile component
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/Tile/Tile.module.css` — CREATE tile styles
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/MessageDetailModal/MessageDetailModal.tsx` — CREATE modal shell
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/MessageDetailModal/MessageDetailModal.module.css` — CREATE modal styles

Scope (implement exactly these phases in order):

**Phase 1 — gridBands.ts:** Export `GridBands` interface, `BAND_ORDER` array (Goals/Tasks/Messages/Artifacts), and `gridBands(messages: Message[]): GridBands` pure function. Import `type { Message } from '../../types'` (relative from GridView/). Single-pass O(n) bucketing; `else` is the catch-all for the messages band. Preserve server order (no sorting).

**Phase 2 — Tile.tsx + Tile.module.css:** Props: `{ message: Message; onOpen: (m: Message) => void }`. Root: `<button type="button" className={s.tile} data-type={message.type} onClick={() => onOpen(message)}>`. Rows: (1) `<MessageTypeBadge type={message.type} />`, (2) 2-line-clamped title div, (3) meta row with `from` + `<Timestamp mode="relative" ts={message.ts} />` + atype (artifacts) or taskStatus (tasks). No state, no modal logic. Tile.module.css: left-accent border tints via `data-type` selectors for all 13 message types using `tokens.css` vars (see ARCHITECTURE_PROPOSAL.md §8 for the exact token map). `min-width: 0` on the flex column. 2-line title clamp in CSS only.

**Phase 3 — MessageDetailModal.tsx + .module.css:** Props: `{ message: Message; siblings: Message[]; onClose: () => void }`. Use `useFocusTrap(boxRef)` from `../../../../hooks/useFocusTrap`. Escape key effect → onClose. `createPortal(...)` to `document.body`. Backdrop with click-outside close. `<MsgCard message={message} flash={false} siblings={siblings} />` from `../cards/MsgCard/MsgCard` — pass NO action handlers (read-only). Modal CSS: fixed backdrop (dimmed), centered box (max-width 640px, max-height 80vh), absolute close button.

Architectural rules to observe:
- No inline styles anywhere — CSS modules + tokens.css vars only
- `data-*` attribute variant pattern for per-type tints (not className toggling)
- Every component in its own folder; each file ≤~150 lines
- Studio responsiveness: min-width:0 on all flex children

Do NOT touch BoardViewToggle.tsx, CommsPanel.tsx, or GridView.tsx yet.

Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
After done, update pathly/features/board-grid/PROGRESS.md phases 1–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 5 new files; tsc passes clean; no changes to existing files.
**Files created:** `GridView/gridBands.ts`, `GridView/Tile/Tile.tsx`, `GridView/Tile/Tile.module.css`, `MessageDetailModal/MessageDetailModal.tsx`, `MessageDetailModal/MessageDetailModal.module.css`

---

## Conversation 2: GridView assembly + wiring — GridView, BoardViewToggle, CommsPanel (Phases 4–6)

**Stories delivered:** S1, S2, S4, S5, S6

**Prompt to paste:**
```
Read pathly/features/board-grid/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement board-grid Conversation 2 (Phases 4–6) from pathly/features/board-grid/IMPLEMENTATION_PLAN.md.
Conversation 1 (leaf components) is complete — gridBands.ts, Tile, and MessageDetailModal exist.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation creates or edits:**
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/GridView.tsx` — CREATE
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/GridView.module.css` — CREATE
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/BoardViewToggle/BoardViewToggle.tsx` — EDIT
- `studio/src/renderer/src/components/CommandCenter/CommsPanel/CommsPanel/CommsPanel.tsx` — EDIT

Scope (implement exactly these phases in order):

**Phase 4 — GridView.tsx + GridView.module.css:** Props: `{ messages: Message[]; boardKey: string; boardScope: BoardScope }`. Track panel width via `ResizeObserver` on a root ref; `narrow = width ≤ 220`. `bands = useMemo(() => gridBands(messages), [messages])`. Three modal states: `openGoalId: string|null`, `openArtifact: Message|null`, `openMessage: Message|null`. `open(m)` dispatcher: goal → `setOpenGoalId(m.id)`; task → `setOpenGoalId(m.goal_id ?? null)`; artifact → `setOpenArtifact(m)`; else → `setOpenMessage(m)`. Render: if `narrow`, show placeholder banner. Otherwise: `BAND_ORDER.map(...)` — skip empty bands; each non-empty band is a `<section>` with a sticky header (`Band · N`) + a `.grid` div of `<Tile>` components. Modals at bottom: mount `GoalDetailModal` ONLY when `openGoalId` is non-null; `ArtifactModal` when `openArtifact`; `MessageDetailModal` when `openMessage`. Pass `messages`, `boardKey`, `boardScope` to `GoalDetailModal`. GridView.module.css: container-query on `.grid` (not scroll root); `container-name: gridband`; `grid-template-columns: 1fr` default, `repeat(2, minmax(0, 1fr))` at ≥400px, `repeat(3, minmax(0, 1fr))` at ≥600px. Sticky band headers outside the query container (on the `<section>`). `.view` has `overflow-y: auto; overflow-x: hidden`.

**Phase 5 — BoardViewToggle.tsx:** Add `LayoutGrid` to the `lucide-react` import. Widen the union: `export type BoardView = 'messages' | 'goals' | 'artifacts' | 'grid'`. Append to `VIEWS`: `{ id: 'grid', label: 'All', icon: <LayoutGrid size={12} /> }`. No other changes.

**Phase 6 — CommsPanel.tsx:** Add `import { GridView } from '../GridView/GridView'`. Restructure `rightAction` ternary so `'grid'` yields `null` (see IMPLEMENTATION_PLAN.md Phase 6 for the exact shape). Add the GridView conditional render after the ArtifactsView block: `{boardView === 'grid' && <GridView messages={messages} boardKey={feature} boardScope={scope} />}`. Match GoalsView's pattern for the boardKey and boardScope values.

Architectural rules to observe:
- No inline styles anywhere — CSS modules + tokens.css vars only
- `container-type: inline-size` goes on `.grid` (per-band tile wrapper), NOT on the scroll root
- `minmax(0, 1fr)` (not `1fr`) for all grid columns
- `min-width: 0` on all flex children
- Ungrouped tasks (goal_id null/missing) → no-op click (do not open an empty GoalDetailModal)
- MessageDetailModal passes NO action handlers to MsgCard (read-only)
- Every new component in its own folder with co-located .module.css; ≤~150 lines each

Do NOT touch any file outside the list above. Do NOT edit types.ts.

Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
After done, update pathly/features/board-grid/PROGRESS.md phases 4–6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 2 new files + 2 edited files; tsc passes clean; the "All" tab appears in the Studio board view.
**Files created:** `GridView/GridView.tsx`, `GridView/GridView.module.css`
**Files edited:** `BoardViewToggle/BoardViewToggle.tsx`, `CommsPanel/CommsPanel.tsx`
