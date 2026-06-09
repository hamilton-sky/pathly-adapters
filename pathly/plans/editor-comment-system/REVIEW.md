# Review Report — editor-comment-system (Conv 2)

Reviewed files: all files listed in VERIFY.md (Conv 1 + Conv 2 changes).
TypeScript: not run (no shell access); structural analysis performed instead.

---

## Violations

### BLOCKER

- `studio/src/renderer/src/components/Editor/index.tsx:245-250` — **No `type` attribute on `<button>`** — Three tab buttons inside the `tabs.map(...)` block have no `type="button"`. Rule: every `<button>` must have an explicit `type`. Same applies to the "Edit source" button at line 260 and the Save button at line 266-271. That is 5 missing `type` attributes in this file alone.

- `studio/src/renderer/src/components/Editor/useComments.ts:75` — **Reopen is broken: `resolve` always sets `resolved: true`** — The `resolve` callback hard-codes `resolved: true`. The reopen button in `CommentItem` calls `onResolve`, which maps to this function. Clicking Reopen on an already-resolved comment silently no-ops instead of toggling `resolved` to `false`. This is a runtime behavioral bug.

- `studio/src/renderer/src/components/Editor/index.tsx` — **File exceeds 150-line hard limit** — File is 373 lines. Rule: hard limit ~150 lines per component file; extract logical sub-sections. The frontmatter parsing functions (`parseFrontmatter`, `parseSimpleYaml`, `serializeFrontmatter`, ~70 lines) and the `Editor` component itself (~290 lines) all coexist. This was not introduced by the current conv but the changed file must conform to the rule.

---

### WARNING (non-blocking)

- `studio/src/renderer/src/components/Editor/CommentablePreview/highlightUtils.ts:208` — **Pulse `setTimeout` not cancellable on unmount** — `pulseRange` schedules `setTimeout(() => deleteHL(PULSE_HL), 300)` and discards the timer id. If the component unmounts within 300ms, the callback still fires. Because `deleteHL` touches global `CSS.highlights`, no crash occurs, but the dangling timer is a hygiene issue. `useCommentRanges` has an `activeTimeoutRef` for a *different* purpose but never cancels the pulse timer from `pulseRange`. No cleanup is wired in the `useEffect` unmount path.

- `studio/src/renderer/src/components/Editor/CommentablePreview/useCommentKeyboardNav.ts` — **Alt+Up/Down navigation not announced to screen readers** — The keyboard shortcut cycles through comments but no `aria-live` region announces which comment became active. WCAG 2.1 SC 4.1.3 requires status changes resulting from user actions to be announced.

- `studio/src/renderer/src/components/Editor/useComments.ts` — **Stale sidecar timer not cancelled on filePath change** — When `filePath` changes, the `persist` callback is re-created (correct), but an in-flight `saveTimerRef.current` from the previous `filePath` may fire after the file changes and write stale data to the *new* sidecar. The `useEffect` that loads comments has no cleanup that calls `clearTimeout(saveTimerRef.current)`.

- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentGutter/CommentGutter.tsx:33` — **`el.style.setProperty('display', 'none')` — inline style mutation** — The rule permits `el.style.setProperty(...)` in a `useEffect` for values impossible to express in static CSS. Hiding a badge by imperatively setting `display: none` is semantically an application-state toggle, not a dynamic CSS value. Consider a CSS class toggle (`el.classList.add(styles.hidden)`) instead. Not a hard violation (the exception covers `setProperty`-in-effect) but worth noting.

- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentItem/CommentItem.tsx:16` — **Component function signature line very long** — Line 16 is a single-line destructure of 7 props. Not a rules violation but contributes to readability debt.

---

## Pass

- **No `style={{ ... }}` JSX inline style props** found in any changed file. All dynamic values use `el.style.setProperty(...)` in effects (permitted exception) or CSS custom properties.
- **CSS Highlight API — `clearHighlights()`** correctly deletes all 5 per-color highlights (`pathly-comment-yellow` through `pathly-comment-orange`) plus `pathly-pending`, `pathly-submitted`, and `pathly-comment-pulse`. Loop over `ALL_COMMENT_COLORS` is complete.
- **`pendingAnchor` highlight removal** — `applyCommentHighlights` skips any comment whose `lineText === pendingAnchor`, and `applyHighlights` skips submitted anchors matching `pendingAnchor`. `pathly-pending` is removed from highlights when `pendingAnchor` clears (`useEffect` at `CommentablePreview.tsx:113-115` nulls `pendingRangeRef`; `useCommentRanges` re-runs the effect and calls `clearHighlights()` when `showHighlights` is false or re-applies without the pending range).
- **Range cloneRange() before selection cleared** — `handleMouseUp` at line 77 calls `range.cloneRange()` and stores it before clearing the selection. Correct.
- **`isRangeConnected` fallback** — `resolveRange` checks `isRangeConnected(cached)` before returning from cache, and falls back to `findAnchorRange`. The `isConnected` check is wrapped in try/catch for detached nodes.
- **Memory leak on comment delete** — `remove` in `useComments` filters out the deleted comment; the range map in `useCommentRanges` is a plain `Map<string, Range>` — stale entries remain but are harmless (they will be naturally evicted when `rangeMapRef.current` is re-used or the component unmounts via `clearHighlights`). Not a leak in the GC sense.
- **Gutter badge positioning across re-renders** — `repositionBadges` runs inside a `useEffect` that re-fires on `[comments, showHighlights, containerRef, rangeMapRef]` changes, and a `ResizeObserver` + scroll listener keep it current. Badge element refs are managed via a stable `Map<string, HTMLButtonElement>` in `badgeRefs`.
- **All `<button>` elements in changed files** (outside `index.tsx`) have explicit `type="button"` or `type="submit"`.
- **Color swatches have `aria-label`** — Each swatch button in `CommentModal.tsx` has `aria-label={`Set comment color to ${color}`}` and `aria-pressed`.
- **Resolve button has `aria-label`** — `aria-label="Resolve comment"` present at line 67 of `CommentItem.tsx`.
- **No hardcoded credentials or injection risks** found.
- **Dependency direction** — all imports flow from lower layers (hooks, utils, types) up to components. No component imports from a layer above it.
