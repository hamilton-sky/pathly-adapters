# Conversation Prompts — editor-comment-system

---

## Conversation 1 — Core Comment System

**Stories:** S1, S2, S3, S4, S5, S9, S10
**Goal:** Leave the codebase in a fully runnable state with per-comment colors, index badges, anchor previews, per-color CSS highlights, and click-to-scroll with pulse. All existing comment functionality must continue to work.

---

You are implementing the core comment system for Pathly Studio's markdown editor preview.

### What already exists (do not re-implement)

- `Editor/useComments.ts` — `Comment` interface, `useComments` hook, 400ms debounced sidecar persist
- `Editor/CommentablePreview/CommentablePreview.tsx` — preview with selection capture, `pendingRangeRef`, `tooltipRangeRef`, `applyHighlights` effect
- `Editor/CommentablePreview/highlightUtils.ts` — CSS Custom Highlight API plumbing, `findAnchorRange`, `applyHighlights`, `clearHighlights`, `PENDING_HL`, `SUBMITTED_HL`
- `Editor/CommentsPanel/CommentsPanel.tsx` — panel with unresolved/resolved list, count badge in header, Send-to-Agent
- `Editor/CommentsPanel/CommentItem/CommentItem.tsx` — existing card with edit/resolve/delete
- `Editor/CommentModal/CommentModal.tsx` — floating modal for composing comments
- `Editor/index.tsx` — orchestrates all of the above

### Key files to read before starting

- `studio/src/renderer/src/components/Editor/useComments.ts`
- `studio/src/renderer/src/components/Editor/index.tsx`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.tsx`
- `studio/src/renderer/src/components/Editor/CommentablePreview/highlightUtils.ts`
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx`
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentItem/CommentItem.tsx`
- `studio/src/renderer/src/components/Editor/CommentModal/CommentModal.tsx`
- `studio/src/renderer/src/assets/tokens.css` (for existing token names)

### Coding rules (hard — never violate)

- No `style={{}}` JSX props. All styling in `.module.css`. CSS custom properties via `ref.current.style.setProperty()` in a `useEffect` only.
- Every `<button>` requires `type="button"`.
- ARIA attributes on all interactive elements (`aria-label`, `aria-pressed`).
- ~150 lines per file hard limit — extract hooks/components if over.

### Phase 1 — Data model and token foundation

**1. Add CSS tokens to `studio/src/renderer/src/assets/tokens.css`**

In the `:root` block add 15 new properties (5 colors × 3 roles: swatch, tint, border):
```css
--comment-yellow-swatch: #FCD34D;  --comment-yellow-tint: rgba(252, 211, 77, 0.24);  --comment-yellow-border: rgba(252, 211, 77, 0.55);
--comment-green-swatch:  #34D399;  --comment-green-tint:  rgba(52, 211, 153, 0.22);  --comment-green-border:  rgba(52, 211, 153, 0.50);
--comment-blue-swatch:   #60A5FA;  --comment-blue-tint:   rgba(96, 165, 250, 0.22);  --comment-blue-border:   rgba(96, 165, 250, 0.50);
--comment-purple-swatch: #A78BFA;  --comment-purple-tint: rgba(167, 139, 250, 0.22); --comment-purple-border: rgba(167, 139, 250, 0.50);
--comment-orange-swatch: #F97316;  --comment-orange-tint: rgba(249, 115, 22, 0.22);  --comment-orange-border: rgba(249, 115, 22, 0.50);
```
In `[data-theme="light"]` add swatch overrides only (tint/border values are unchanged):
```css
--comment-yellow-swatch: #D97706;  --comment-green-swatch: #047857;
--comment-blue-swatch:   #1D4ED8;  --comment-purple-swatch: #7C3AED;
--comment-orange-swatch: #C2410C;
```

**2. Extend `useComments.ts`**

- Export `COMMENT_COLORS = ['yellow', 'green', 'blue', 'purple', 'orange'] as const` and `CommentColor` type
- Add `color: CommentColor` field to `Comment` interface
- Update `add()` signature: `add(lineNumber, lineText, body, color: CommentColor = 'yellow')`
- On sidecar load, default missing `color` to `'yellow'`: `color: (c.color ?? 'yellow') as CommentColor`

### Phase 2 — CommentModal color picker

**3. Update `CommentModal.tsx`**

- Add `selectedColor` state (`useState<CommentColor>('yellow')`)
- Add a color picker row between the anchor chip and textarea:
  - 5 `<button type="button">` elements, each 24×24px touch target, 12px visual circle centered inside
  - `aria-label="Set comment color to {color}"`, `aria-pressed={selectedColor === color}` on each
  - A visually-hidden `<span className={styles.srOnly}>Comment color</span>` label
- Update `onAdd(body, selectedColor)` and `onSendNow(body, selectedColor)` callback signatures
- Reset `selectedColor` to `'yellow'` when modal closes/cancels
- Update `CommentModal.module.css`: `.swatchRow`, `.swatch`, `.swatchSelected`, `.srOnly`

**4. Update `index.tsx`**

- `handleModalAdd(commentBody, color)` — add `color` param, pass to `addComment`
- `handleModalSendNow(commentBody, color)` — same
- Add `previewRef = useRef<CommentablePreviewHandle>(null)` (type imported from CommentablePreview)
- Pass `ref={previewRef}` to `<CommentablePreview>`
- Pass `onScrollTo={(id) => previewRef.current?.scrollToComment(id)}` to `<CommentsPanel>`
- Change `submittedAnchors` memo to pass full `comments` array to `CommentablePreview` instead

### Phase 3 — highlightUtils update

**5. Update `highlightUtils.ts`**

Keep all existing exports unchanged (`PENDING_HL`, `SUBMITTED_HL`, `findTextRange`, `findAnchorRange`, `isRangeConnected`, `applyHighlights`, `clearHighlights`).

Add new exports:
```ts
export const COMMENT_HL_PREFIX = 'pathly-comment-'   // + color name
export const PULSE_HL = 'pathly-comment-pulse'

export const COMMENT_TINTS: Record<CommentColor, string> = {
  yellow: 'rgba(252, 211, 77, 0.24)',
  green:  'rgba(52, 211, 153, 0.22)',
  blue:   'rgba(96, 165, 250, 0.22)',
  purple: 'rgba(167, 139, 250, 0.22)',
  orange: 'rgba(249, 115, 22, 0.22)',
}

export const COMMENT_TINTS_PULSE: Record<CommentColor, string> = {
  yellow: 'rgba(252, 211, 77, 0.65)',
  green:  'rgba(52, 211, 153, 0.60)',
  blue:   'rgba(96, 165, 250, 0.60)',
  purple: 'rgba(167, 139, 250, 0.60)',
  orange: 'rgba(249, 115, 22, 0.60)',
}

// Resolve a Range for a comment: try cache first, fall back to text search, update cache
export function resolveRange(
  container: HTMLElement,
  id: string,
  anchor: string,
  cache: Map<string, Range>
): Range | null

// Apply per-color comment highlights (groups unresolved comments by color)
export function applyCommentHighlights(
  container: HTMLElement,
  comments: Comment[],
  cache: Map<string, Range>,
  pendingAnchor: string | null
): void

// Flash the pulse highlight; cancels any in-flight pulse first
export function pulseRange(range: Range, container: HTMLElement, color: CommentColor): void
```

Update `clearHighlights()` to also delete `pathly-comment-yellow/green/blue/purple/orange` and `pathly-comment-pulse`.

Implementation of `applyCommentHighlights`: group unresolved comments by `color`, skip any whose `lineText === pendingAnchor`, call `resolveRange` for each, build per-color Range arrays, call `setHL('pathly-comment-'+color, ranges)` for each color that has ranges, call `deleteHL('pathly-comment-'+color)` for colors with no ranges.

Implementation of `pulseRange`: delete `PULSE_HL` first (cancel any prior), set `--pulse-start` and `--pulse-end` on container via `setProperty`, set `PULSE_HL` with the range, `setTimeout(() => deleteHL(PULSE_HL), 300)`.

### Phase 4 — useCommentRanges hook (new file)

**6. Create `Editor/CommentablePreview/useCommentRanges.ts`**

This hook is the brains of the highlight + scroll subsystem. It must stay under 120 lines.

```ts
export function useCommentRanges(
  containerRef: RefObject<HTMLDivElement>,
  comments: Comment[],
  pendingAnchor: string | null,
  pendingRangeRef: RefObject<Range | null>,
  modalOpen: boolean,
  showHighlights: boolean
): {
  rangeMapRef: RefObject<Map<string, Range>>
  scrollToComment: (id: string) => void
}
```

Internals:
- `rangeMapRef = useRef(new Map<string, Range>())`
- `activeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)` (for pulse cancellation)
- `applyHighlights useEffect` keyed on `[pendingAnchor, modalOpen, content (via comments), showHighlights]`:
  - If `!showHighlights`: `clearHighlights(); return`
  - Apply pending highlight (existing logic from `CommentablePreview` — keep `PENDING_HL`)
  - Call `applyCommentHighlights(container, comments, rangeMapRef.current, pendingAnchor)`
- `scrollToComment(id)`:
  1. Find comment in `comments` array by id; no-op if not found
  2. `resolveRange(container, id, comment.lineText, rangeMapRef.current)` → if null, no-op
  3. `rect = range.getBoundingClientRect(); cRect = container.getBoundingClientRect()`
  4. `container.scrollTo({ top: container.scrollTop + (rect.top - cRect.top) - 40, behavior: 'smooth' })`
  5. If `activeTimeoutRef.current` exists, `clearTimeout` it and `deleteHL(PULSE_HL)` first
  6. `pulseRange(range, container, comment.color)`; store the new `setTimeout` handle in `activeTimeoutRef`

### Phase 5 — CommentGutter component (new files)

**7. Create `Editor/CommentablePreview/CommentGutter/CommentGutter.tsx`**

Props:
```ts
interface Props {
  containerRef: RefObject<HTMLDivElement>
  comments: Comment[]          // already filtered to unresolved by parent
  rangeMapRef: RefObject<Map<string, Range>>
  showHighlights: boolean
  onScrollTo: (id: string) => void
}
```

- If `!showHighlights`, render nothing
- Render a `<div className={styles.gutter} aria-hidden="true">` containing one `<button>` per comment whose Range is resolvable
- Each badge button:
  - `type="button"`, `aria-label="Jump to comment #N"` where N is derived index (1-based position in the passed array)
  - `data-comment-id={comment.id}` for the `useEffect` to target
  - `onClick={() => onScrollTo(comment.id)}`
  - Badge content: the index number as text
- `useEffect` keyed on `[comments, showHighlights]`:
  - For each badge ref, call `resolveRange` to get the range
  - `rect = range.getBoundingClientRect(); cRect = containerRef.current.getBoundingClientRect()`
  - `top = containerRef.current.scrollTop + rect.top - cRect.top`
  - Set `--badge-top` and `--badge-color` via `el.style.setProperty()` on each badge element

**8. Create `Editor/CommentablePreview/CommentGutter/CommentGutter.module.css`**

```css
.gutter {
  position: absolute;
  left: 2px;
  top: 0;
  width: 20px;
  pointer-events: none;
}
.badge {
  position: absolute;
  top: var(--badge-top, 0px);
  width: 16px;
  height: 16px;
  border-radius: var(--radius-full);
  background: var(--badge-color, var(--comment-yellow-swatch));
  color: #111827;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  pointer-events: all;
  min-width: 24px;
  min-height: 24px;
  transform: translateX(-50%) translateY(-50%);
}
```

### Phase 6 — CommentablePreview and CommentItem wiring

**9. Update `CommentablePreview.tsx`**

- Replace `submittedAnchors: string[]` prop with `comments: Comment[]`
- Import and forward ref for `CommentablePreviewHandle`:
  ```ts
  export const CommentablePreview = forwardRef<CommentablePreviewHandle, Props>(function CommentablePreview(props, ref) { ... })
  ```
- Call `useCommentRanges(containerRef, comments, pendingAnchor, pendingRangeRef, modalOpen, showHighlights)` inside the component
- Use the returned `scrollToComment` to implement `useImperativeHandle(ref, () => ({ scrollToComment }))`
- Render `<CommentGutter containerRef={containerRef} comments={unresolvedComments} rangeMapRef={rangeMapRef} showHighlights={showHighlights} onScrollTo={scrollToComment} />` inside `.root`
- Remove the existing `applyHighlights` useEffect (replaced by `useCommentRanges`)
- Add `tabIndex={0}` to `.root` div (required for keyboard nav scoping in Conv 2)

**10. Update `CommentItem.tsx`**

- Add `index: number` and `onScrollTo: (id: string) => void` to Props
- Add index badge in the top row: `<span className={styles.indexBadge}>#N</span>` — N is `index` prop
- Add left border stripe via `--comment-item-color` CSS var set in a `useEffect` with `itemRef.current?.style.setProperty('--comment-item-color', ...)`
- Add anchor preview row below top row: monospace truncated `lineText`, `title={comment.lineText}`
- Add `onClick={() => onScrollTo(comment.id)}` on the card root (entire card is clickable)
- Resolved state: apply `styles.resolvedBadge` to badge, do not show color picker row
- Update `CommentsPanel.tsx` to:
  - Accept `onScrollTo: (id: string) => void` and thread to each `CommentItem`
  - Pass derived `index` (unresolved only, 1-based) to each unresolved `CommentItem`

### Done check for Conv 1

Run `npm run typecheck` — zero errors.

Verify manually:
- Open a markdown file in preview tab
- Select text → modal appears with 5 color swatches, yellow pre-selected
- Submit → highlight appears in selected color, card shows `#1` badge in that color
- Card shows first 50 chars of anchor text in monospace
- Click card → preview scrolls to anchor with 300ms pulse
- Resolve comment → highlight gone, badge desaturated, card moves to Resolved section
- Add two more comments → they number #1 #2 in line order; resolving one renumbers the other

---

## Conversation 2 — Polish and Extras

**Stories:** S6, S7, S8
**Goal:** Add comment count badge on panel toggle, gutter badge scroll reposition, keyboard navigation with Alt+Up/Down, and color accessibility polish. All previous functionality must remain working.

### What was built in Conv 1 (assume working)

- `Comment` interface with `color` field; `COMMENT_COLORS` and `CommentColor` exported from `useComments.ts`
- `CommentablePreviewHandle` ref with `scrollToComment(id)`
- `useCommentRanges` hook (range map, scroll, pulse)
- `CommentGutter` component (overlay badges)
- `CommentItem` with index badge, color stripe, anchor preview, click-to-scroll
- Per-color `applyCommentHighlights` in `highlightUtils.ts`

### Key files to read before starting

- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx`
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.module.css`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.tsx`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.module.css`
- `studio/src/renderer/src/components/Editor/CommentablePreview/useCommentRanges.ts`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentGutter/CommentGutter.tsx`

### Phase 1 — Comment count badge on panel toggle

**1. Identify the panel toggle button in `Editor/index.tsx`**

The panel toggle is the button that shows/hides `CommentsPanel`. If no such toggle exists at the layout level, check `CommentsPanel.tsx` for a collapse mechanism. The badge must appear on whichever button controls panel visibility.

Add a count badge showing `unresolved.length` beside the toggle icon:
- Reuse `styles.badge` from `CommentsPanel.module.css` (not a new class)
- Render only when `unresolved.length > 0`
- Badge: 16px circle, `var(--accent)` background, white text, `var(--font-size-xs)`

**2. Update `CommentsPanel.module.css`**

Ensure `.badge` is positioned absolutely on the toggle if it is not already:
```css
.toggleWrapper { position: relative; display: inline-flex; }
.badge {
  position: absolute;
  top: -4px; right: -4px;
  min-width: 16px; height: 16px;
  border-radius: var(--radius-full);
  background: var(--accent);
  color: #fff;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
  display: flex; align-items: center; justify-content: center;
  padding: 0 3px;
  pointer-events: none;
}
```

### Phase 2 — Gutter badge scroll reposition

**3. Wire scroll listener in `CommentGutter.tsx`**

Add a passive `scroll` event listener on `containerRef.current` inside the gutter's `useEffect`. When the container scrolls, rerun position computation for all badge refs:

```ts
useEffect(() => {
  const container = containerRef.current
  if (!container) return
  // ... existing position compute logic ...
  container.addEventListener('scroll', repositionBadges, { passive: true })
  return () => container.removeEventListener('scroll', repositionBadges)
}, [comments, showHighlights])
```

Ensure `repositionBadges` is a named inner function extracting the `setProperty` calls so it can be called from both the initial effect run and the scroll handler without duplicating logic.

**4. Add resize observer in `CommentGutter.tsx`**

```ts
const resizeObserver = new ResizeObserver(repositionBadges)
resizeObserver.observe(container)
return () => { resizeObserver.disconnect(); container.removeEventListener('scroll', repositionBadges) }
```

### Phase 3 — Keyboard navigation (Alt+Up/Down)

**5. Create `Editor/CommentablePreview/useCommentKeyboardNav.ts`**

```ts
export function useCommentKeyboardNav(
  containerRef: RefObject<HTMLDivElement>,
  unresolvedComments: Comment[],       // sorted by lineNumber
  scrollToComment: (id: string) => void
): void
```

Internals:
- `activeIndexRef = useRef(-1)` — current position in the nav order
- `useEffect` keyed on `[unresolvedComments]`:
  - Reset `activeIndexRef.current` to -1 when comment list changes (so nav restarts from the top)
- `useEffect` for keydown listener keyed on `[]` (mount/unmount only):
  - Attach `keydown` to `containerRef.current` (not document)
  - Handler: if `e.altKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')`:
    - `e.preventDefault()`
    - Get current `unresolvedComments` via a ref to avoid stale closure
    - Navigate: find next/prev index that has a resolvable anchor (skip orphaned) with wraparound
    - Update `activeIndexRef.current`
    - Call `scrollToComment(targetComment.id)`
  - Detach on cleanup

**6. Wire `useCommentKeyboardNav` into `CommentablePreview.tsx`**

Import and call with `containerRef`, `unresolvedComments` (derived from `comments` prop), and `scrollToComment` from `useCommentRanges`.

Verify `.root` has `tabIndex={0}` (set in Conv 1 — confirm it is present).

### Phase 4 — CSS highlight rules

**7. Update `CommentablePreview.module.css`**

Add global rules for the 5 color highlight buckets and pulse:

```css
:global(::highlight(pathly-comment-yellow)) { background-color: var(--comment-yellow-tint); color: inherit; }
:global(::highlight(pathly-comment-green))  { background-color: var(--comment-green-tint);  color: inherit; }
:global(::highlight(pathly-comment-blue))   { background-color: var(--comment-blue-tint);   color: inherit; }
:global(::highlight(pathly-comment-purple)) { background-color: var(--comment-purple-tint); color: inherit; }
:global(::highlight(pathly-comment-orange)) { background-color: var(--comment-orange-tint); color: inherit; }
:global(::highlight(pathly-comment-pulse))  { background-color: var(--pulse-start, rgba(252, 211, 77, 0.65)); }

@keyframes commentPulse {
  0%, 40% { background-color: var(--pulse-start, rgba(252, 211, 77, 0.65)); }
  100%     { background-color: var(--pulse-end,   rgba(252, 211, 77, 0.24)); }
}

@media (prefers-reduced-motion: reduce) {
  @keyframes commentPulse {
    0%, 100% { background-color: var(--pulse-start, rgba(252, 211, 77, 0.65)); }
  }
}
```

Note: The `--pulse-start` and `--pulse-end` CSS vars are set on `containerRef.current` via `style.setProperty()` inside `pulseRange()` in `highlightUtils.ts`. The keyframe references them to allow per-color pulse intensity.

### Phase 5 — Edge case hardening

**8. Orphaned card visual state in `CommentItem.tsx`**

- If `comment.lineText` cannot be found (the `resolveRange` result for this id is absent from `rangeMapRef`), add a visual signal to the card. The panel does not have direct access to `rangeMapRef`, so use an `isOrphaned` prop passed from `CommentsPanel`.
- `CommentsPanel` receives the range map via a new `orphanedIds: Set<string>` prop computed in `Editor/index.tsx` — or alternatively, expose a `getOrphanedIds(): Set<string>` method on `CommentablePreviewHandle`.
- When `isOrphaned` is true, the anchor preview row shows a small "anchor lost" label in `var(--text-muted)` and the card click does nothing (guard `if (!isOrphaned) onScrollTo(id)` in the handler).

### Done check for Conv 2

Run `npm run typecheck` — zero errors.

Verify manually:
- With 2+ unresolved comments: panel toggle button shows a count badge
- Badge disappears after resolving all comments
- After scrolling the preview, gutter badges reposition to track their anchor text
- With preview focused (click into it), press Alt+Down → jumps to first anchor with pulse
- Press Alt+Down again → jumps to second; Alt+Up → back to first; wraps at ends
- While typing in the markdown editor, Alt+Down does not jump to comments
- Resolve a comment: it disappears from keyboard nav order; remaining anchors are visited correctly
- Delete all anchor text for a comment: card shows "anchor lost" state; keyboard nav skips it
