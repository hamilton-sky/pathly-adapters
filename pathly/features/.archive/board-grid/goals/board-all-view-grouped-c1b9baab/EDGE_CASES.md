# board-grid — Edge Cases

## Phase 1 — gridBands.ts

- **Unknown future message type:** The `else` catch-all in `gridBands` ensures no item is silently dropped — unknown types go in the messages band. This is intentional: the "All" tab shows everything.
- **Empty board:** `gridBands([])` returns four empty arrays. `GridView` omits all bands → no empty band headers rendered → a blank (but valid) view.
- **All items of one kind:** E.g. all artifacts → only the Artifacts band renders. Goals/Tasks/Messages bands are omitted.

## Phase 2 — Tile

- **Long unbroken title (URL or hash):** `-webkit-line-clamp: 2` truncates at the second line; `minmax(0, 1fr)` in the grid prevents column blow-out. Both CSS rules must be present.
- **Missing `from` field:** Render empty string — no crash. The meta row skips the author slot gracefully.
- **Missing `ts` field:** `<Timestamp>` should handle null/undefined — verify the component contract; if it does not, guard with `ts && <Timestamp .../>`.
- **Message with no `taskStatus` and no `atype`:** Meta row renders author + time only — this is correct and expected.
- **RTL text in title:** `-webkit-line-clamp` behavior differs in RTL; not in scope for P1.

## Phase 3 — MessageDetailModal

- **MsgCard with action handlers absent:** `MsgCard` renders cleanly with no `onDelete`/`onSupersede`/`onAnswer`/`onResolve` — the action buttons do not render. Confirm via visual inspection.
- **Very long message body:** The modal box has `max-height: 80vh; overflow-y: auto` so long markdown content scrolls inside the modal — the backdrop does not scroll.
- **Modal opened on a phase/monitor message:** These are valid message types and render correctly via `MsgCard`. No special handling needed.
- **Focus trap edge case:** If `MsgCard` contains no focusable elements, `useFocusTrap` should still not crash — verify the hook's behavior on focus-empty content.

## Phase 4 — GridView

- **Ungrouped task (task with no `goal_id` or unknown `goal_id`):** `open(m)` sets `openGoalId = null` for such a task. The `GoalDetailModal` mount guard (`openGoalId !== null`) prevents opening an empty modal — the click is a no-op.
- **ResizeObserver not supported:** Unlikely in Electron (Chromium), but if unavailable, the `narrow` state defaults to `false` (grid renders). Add a safety guard: `if (typeof ResizeObserver === 'undefined') return`.
- **Panel width measurement timing:** The `ResizeObserver` fires asynchronously after mount. On first render, `narrow` is `false` (grid renders at full width); it corrects on the first resize event. This is acceptable — no FOUC risk.
- **Very large board (hundreds of items):** `gridBands` is O(n) and returns plain arrays. Rendering hundreds of tiles in the DOM is acceptable for P1 (no virtualization). If perf becomes an issue, that is P2.
- **Sticky header inside a query container:** The `container-type: inline-size` is on `.grid` (the tile grid wrapper), NOT on the `<section>` (which contains the sticky header). This prevents containment from clipping the sticky header — the architecture proposal explicitly calls this out.
- **3 modal states mutually exclusive by convention, not enforced:** Only one modal opens at a time because the `open()` function only calls one setter. If `onOpen` is ever called twice rapidly, the last call wins. This is acceptable.

## Phase 5 — BoardViewToggle

- **4 icon buttons at ≤200px:** The existing container-query label-hide and `min-width: 0` pattern keeps the seg control compact. Verify at ≤200px that 4 icons still fit without clipping. If they don't, reduce icon `size` from 12 to 11 — do NOT widen the control.
- **Exhaustive switch on `BoardView`:** TypeScript does not enforce exhaustiveness on type unions in JSX ternaries. Ensure the `rightAction` ternary in `CommsPanel` explicitly handles all 4 values — a final `null` fallback is correct.

## Phase 6 — CommsPanel

- **`feature` variable name collision:** In `CommsPanel`, the `feature` string (from `useCommsPanel`) is used as `boardKey`. Verify the variable name matches — if it's renamed in the file, adjust accordingly.
- **boardView state doesn't reset on scope change:** If the user switches `CommsPanel` scope while on the 'grid' tab, `boardView` stays 'grid'. This is acceptable — same behavior as the other tabs.
- **GridView unmount on tab switch:** When `boardView !== 'grid'`, the `{boardView === 'grid' && ...}` guard unmounts GridView, resetting all modal states. This is correct — no stale modal can persist after leaving the tab.
