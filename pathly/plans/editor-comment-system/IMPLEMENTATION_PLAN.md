# Implementation Plan — editor-comment-system

## Architecture Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Extend `Comment` interface with `color: CommentColor`; derive `index` at render, never store it | `index` is a pure function of unresolved sort order — persisting it causes drift bugs. `color` is durable user intent and must survive reload. |
| D2 | Per-color highlight buckets (`pathly-comment-{color}`) not per-id | CSS Custom Highlight API requires static `::highlight()` rules. Per-id rules cannot be authored statically and dynamic `<style>` injection violates Studio coding rules. 5 color buckets = 5 static rules, correct visual result. |
| D3 | `rangeMapRef: Map<id, Range>` owned by CommentablePreview | DOM Ranges are session-only, not JSON-serializable, and only meaningful in the component that owns the DOM. State would cause unnecessary re-renders. Matches existing `pendingRangeRef` pattern. |
| D4 | `CommentablePreviewHandle` ref with `scrollToComment(id)` | Imperative handle avoids routing a "scroll target id" through state, which would re-render the full preview on every card click. One-way call: panel → editor → preview ref. |
| D5 | Pulse via `pathly-comment-pulse` named highlight + `setTimeout` | Custom Highlight API has no transition support. A named highlight set/deleted with a 300ms timer gives a flash affordance. Zero React state = zero re-render during pulse. |
| D6 | Gutter badges as absolute overlay layer inside `.root` (Option B) | Injecting DOM nodes into the rendered markdown would mutate the preview DOM, invalidate live Ranges on every keystroke, and break `findTextRange`'s text walker. Overlay layer has zero layout impact. |
| D7 | `Alt+Down/Up` keydown listener on the preview `.root` (tabIndex=0), not on document | Scoping to the preview's focusable root prevents capturing keystrokes from the MarkdownEditor textarea and the CommentModal, and does not collide with the existing document-level Ctrl+S handler. |
| D8 | Map 5 color names to existing tokens (`--yellow`, `--green`, etc.); add new `--comment-{color}-{swatch/tint/border}` tokens in `tokens.css` | Reuses theme-aware token infrastructure. Tint rgba strings are hardcoded constants in `highlightUtils.ts` because CSS Custom Highlight API does not resolve CSS variables at paint time. |
| D9 | `CommentItem` is the "CommentCard" — rename not required | Brief uses aspirational naming. `CommentItem` already exists and is load-bearing. Extend it in place; document the mapping in PR description so reviewers do not revert. |
| D10 | Extract `useCommentRanges` hook from CommentablePreview | CommentablePreview currently ~97 lines. Adding Range map, scroll-to, pulse, gutter wiring, and keyboard nav would exceed 150-line ceiling. Mandatory extraction to keep component as thin shell. |

---

## Conversation 1 — Core Comment System

**Stories delivered:** S1, S2, S3, S4, S5, S9, S10

### Files Modified

| File | Change |
|---|---|
| `Editor/useComments.ts` | Add `CommentColor` type, `COMMENT_COLORS` constant, `color` field to `Comment` interface; update `add()` to accept `color` param (default `'yellow'`); default missing `color` to `'yellow'` on sidecar load |
| `Editor/index.tsx` | Add `previewRef = useRef<CommentablePreviewHandle>(null)`; pass `onScrollTo={(id) => previewRef.current?.scrollToComment(id)}` to `CommentsPanel`; thread `color` through `handleModalAdd` and `handleModalSendNow`; pass `comments` array directly to `CommentablePreview` instead of `submittedAnchors` |
| `Editor/CommentsPanel/CommentsPanel.tsx` | Accept `onScrollTo: (id: string) => void` prop; pass to each `CommentItem`; pass derived `index` (1-based position in unresolved) to each unresolved `CommentItem` |
| `Editor/CommentsPanel/CommentItem/CommentItem.tsx` | Add index badge (`#N` with color swatch background); add color border-left stripe; add anchor text preview (50-char truncation, monospace, `title` attr); add `onScrollTo` click handler; add resolved visual treatment (desaturated badge, hidden color picker row) |
| `Editor/CommentsPanel/CommentItem/CommentItem.module.css` | `.indexBadge`, `.colorBorder` (using `--comment-item-color` CSS var set via `useEffect`), `.anchorPreview`, `.resolvedBadge` |
| `Editor/CommentModal/CommentModal.tsx` | Add 5-swatch color picker row between anchor chip and textarea; track `selectedColor` state (default `'yellow'`); pass `color` up via `onAdd(body, color)` and `onSendNow(body, color)` |
| `Editor/CommentModal/CommentModal.module.css` | `.swatchRow`, `.swatch`, `.swatchSelected`, `.srOnly` |
| `Editor/CommentablePreview/CommentablePreview.tsx` | Replace `submittedAnchors: string[]` prop with `comments: Comment[]`; add `ref` forwarding for `CommentablePreviewHandle`; wire `useCommentRanges` hook; render `CommentGutter` |
| `Editor/CommentablePreview/highlightUtils.ts` | Add `COMMENT_HL_PREFIX`, `PULSE_HL`, `COMMENT_TINTS` constants; add `applyCommentHighlights(container, comments, rangeMap, pendingAnchor)` replacing per-id `applyHighlights`; add `pulseRange(range, container)` helper; add `resolveRange(container, id, anchor, cache)` helper; update `clearHighlights()` to delete all `pathly-comment-{color}` and `pathly-comment-pulse` entries |

### Files Created

| File | Purpose |
|---|---|
| `Editor/CommentablePreview/useCommentRanges.ts` | Owns `rangeMapRef`; drives `applyCommentHighlights` on content/comments change; exposes `scrollToComment(id)` (resolve range → scroll → pulse); ~120 lines |
| `Editor/CommentablePreview/CommentGutter/CommentGutter.tsx` | Absolute overlay; maps unresolved comments with resolvable Ranges to positioned badge `<button>` elements; click calls `onScrollTo(id)` |
| `Editor/CommentablePreview/CommentGutter/CommentGutter.module.css` | `.gutter` (absolute, pointer-events none except badges), `.badge` (uses `--badge-top`, `--badge-color` CSS vars set in effect) |

### Key Interfaces / Contracts

```ts
// useComments.ts
export const COMMENT_COLORS = ['yellow', 'green', 'blue', 'purple', 'orange'] as const
export type CommentColor = typeof COMMENT_COLORS[number]
export interface Comment {
  id: string
  lineNumber: number
  lineText: string          // anchorText — keep name, do not rename
  body: string              // comment text — keep name
  resolved: boolean
  createdAt: string
  color: CommentColor       // NEW — default 'yellow'
}

// CommentablePreview.tsx
export interface CommentablePreviewHandle {
  scrollToComment(id: string): void
}

// CommentModal.tsx (updated callbacks)
interface Props {
  onAdd: (body: string, color: CommentColor) => void
  onSendNow: (body: string, color: CommentColor) => void
  // ... existing props unchanged
}

// CommentsPanel.tsx (updated props)
interface Props {
  onScrollTo: (id: string) => void
  // ... existing props unchanged
}

// CommentItem.tsx (updated props)
interface Props {
  index: number             // derived 1-based position (unresolved only)
  onScrollTo: (id: string) => void
  // ... existing props unchanged
}

// useCommentRanges.ts (export shape)
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

---

## Conversation 2 — Polish and Extras

**Stories delivered:** S6, S7, S8

### Files Modified

| File | Change |
|---|---|
| `Editor/CommentsPanel/CommentsPanel.tsx` | Add count badge on the panel toggle button (reuse `styles.badge`); badge hidden when `unresolved.length === 0` |
| `Editor/CommentsPanel/CommentsPanel.module.css` | Style for toggle button badge if not already present from Conv 1; `.toggleBadge` positioning (absolute, top-right of toggle) |
| `Editor/CommentablePreview/CommentGutter/CommentGutter.tsx` | Wire scroll and resize reposition listener; ensure gutter badges reposition on container scroll (passive event listener added here or in `useCommentRanges`) |
| `Editor/CommentablePreview/CommentablePreview.module.css` | Add `--pulse-start` / `--pulse-end` CSS var references; add `.commenting-pulse` class + `commentPulse` keyframe; add `@media (prefers-reduced-motion)` override; add `::highlight(pathly-comment-pulse)` global rule; add per-color `::highlight(pathly-comment-{color})` global rules; add `.gutter` overflow model (confirm padding-left approach) |

### Files Created

| File | Purpose |
|---|---|
| `Editor/CommentablePreview/useCommentKeyboardNav.ts` | Registers Alt+Up/Down `keydown` listener on `.root` container; tracks `activeIndexRef`; calls `scrollToComment(id)` from `useCommentRanges`; skips orphaned anchors; ~40 lines |

### Key Constraints for Conv 2

- Count badge must reuse `styles.badge` — not a new CSS class or inline style.
- Gutter repositioning must share the existing highlight `useEffect` trigger, not add an independent per-frame loop.
- `useCommentKeyboardNav` must guard: `e.altKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')` only; must not fire when focus is in the MarkdownEditor textarea.
- Pulse CSS variables (`--pulse-start`, `--pulse-end`) set via `containerRef.current.style.setProperty(...)` in `useCommentRanges`, not via JSX prop.
- All 5 `::highlight(pathly-comment-{color})` and `::highlight(pathly-comment-pulse)` CSS rules are in `CommentablePreview.module.css` using `:global(::highlight(...))` syntax.
- WCAG AA: contrast check for all 10 color values (5 colors × 2 themes) required before merge.

---

## CSS Token Additions (Both Conversations)

Tokens added to `studio/src/renderer/src/assets/tokens.css` `:root` block (dark defaults) and overridden in `[data-theme="light"]`:

```css
/* :root (dark) */
--comment-yellow-swatch:  #FCD34D;
--comment-yellow-tint:    rgba(252, 211, 77, 0.24);
--comment-yellow-border:  rgba(252, 211, 77, 0.55);
--comment-green-swatch:   #34D399;
--comment-green-tint:     rgba(52, 211, 153, 0.22);
--comment-green-border:   rgba(52, 211, 153, 0.50);
--comment-blue-swatch:    #60A5FA;
--comment-blue-tint:      rgba(96, 165, 250, 0.22);
--comment-blue-border:    rgba(96, 165, 250, 0.50);
--comment-purple-swatch:  #A78BFA;
--comment-purple-tint:    rgba(167, 139, 250, 0.22);
--comment-purple-border:  rgba(167, 139, 250, 0.50);
--comment-orange-swatch:  #F97316;
--comment-orange-tint:    rgba(249, 115, 22, 0.22);
--comment-orange-border:  rgba(249, 115, 22, 0.50);

/* [data-theme="light"] overrides for swatches only */
--comment-yellow-swatch:  #D97706;
--comment-green-swatch:   #047857;
--comment-blue-swatch:    #1D4ED8;
--comment-purple-swatch:  #7C3AED;
--comment-orange-swatch:  #C2410C;
```

`COMMENT_TINTS` constant in `highlightUtils.ts` (hardcoded rgba — Custom Highlight API cannot resolve CSS vars at paint time):

```ts
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
```

---

## Edge Case Handling Reference

| Edge case | Required behavior |
|---|---|
| Anchor text deleted from file | `resolveRange` returns null; no highlight, no gutter badge, no scroll; CommentItem shows "orphaned" visual state; comment stays in panel |
| Two comments on overlapping text | Each gets its own color bucket Range; last-registered color wins overlap region; both gutter badges render with minimal overlap stacking |
| Pulse while another pulse active | Cancel (delete) existing pulse highlight before starting new one; `setTimeout` cleared with `clearTimeout` |
| Alt+Down while MarkdownEditor focused | `keydown` listener not active (scoped to preview `.root` with `tabIndex=0`); no scroll fires |
| Panel collapsed / preview mounted | `scrollToComment` targets preview DOM; safe no-op if preview unmounted |
| Rapid resolve + add churn | Highlights re-derive from `comments` array on every render; 400ms debounced persist; no stale snapshot |
| Old sidecar without `color` field | `useComments` load defaults `color` to `'yellow'` for any comment missing the field |
