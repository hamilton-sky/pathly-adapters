Conv 2 RESULT: PASS

- `studio/src/renderer/src/components/Editor/CommentablePreview/useCommentKeyboardNav.ts` — new file: Alt+Up/Down keyboard nav hook
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.tsx` — wired `useCommentKeyboardNav`; extended `CommentablePreviewHandle` with `getOrphanedIds()`; guarded null cache in `getOrphanedIds`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.module.css` — added `@keyframes commentPulse` and `animation` on `::highlight(pathly-comment-pulse)`, reduced-motion override
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentGutter/CommentGutter.tsx` — added `ResizeObserver` alongside scroll listener
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx` — added `orphanedIds: Set<string>` and `onCollapse` props; added collapse (`ChevronRight`) button in header; threads `isOrphaned` to each `CommentItem`
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.module.css` — added `.headerBtns`, `.toggleBtn:focus-visible`
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentItem/CommentItem.tsx` — added `isOrphaned` prop; guard in click handler; "anchor lost" display in anchor preview row
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentItem/CommentItem.module.css` — added `.orphaned`, `.orphanedAnchor`
- `studio/src/renderer/src/components/Editor/index.tsx` — added `showPanel` state; `orphanedIds` state (polled 200ms after comments change); panel toggle button with count badge when panel hidden; `onCollapse`/`orphanedIds` wired to `CommentsPanel`
- `studio/src/renderer/src/components/Editor/index.module.css` — added `.toggleWrapper`, `.panelToggleBtn`, `.panelToggleBadge`

---

Conv 1 RESULT: PASS

## Files Changed

### New files
- `studio/src/renderer/src/components/Editor/CommentablePreview/useCommentRanges.ts`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentGutter/CommentGutter.tsx`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentGutter/CommentGutter.module.css`

### Modified files
- `studio/src/renderer/src/styles/tokens.css` — added 15 comment color CSS vars in `:root`, 5 swatch overrides in `[data-theme="light"]`
- `studio/src/renderer/src/components/Editor/useComments.ts` — added `COMMENT_COLORS`, `CommentColor`, `color` field to `Comment`, updated `add()` signature, defaulted missing color on sidecar load
- `studio/src/renderer/src/components/Editor/CommentablePreview/highlightUtils.ts` — added `COMMENT_HL_PREFIX`, `PULSE_HL`, `COMMENT_TINTS`, `COMMENT_TINTS_PULSE`, `resolveRange`, `applyCommentHighlights`, `pulseRange`; updated `clearHighlights` to delete all per-color and pulse highlights
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.tsx` — replaced `submittedAnchors: string[]` prop with `comments: Comment[]`, added `forwardRef` + `CommentablePreviewHandle`, wired `useCommentRanges`, renders `CommentGutter`, added `tabIndex={0}`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.module.css` — added per-color `::highlight()` rules and pulse highlight rule
- `studio/src/renderer/src/components/Editor/CommentModal/CommentModal.tsx` — added color picker row (5 swatches), `selectedColor` state (default yellow), updated `onAdd`/`onSendNow` to pass `CommentColor`
- `studio/src/renderer/src/components/Editor/CommentModal/CommentModal.module.css` — added `.swatchRow`, `.swatch`, `.swatchSelected`, `.srOnly`
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx` — added `onScrollTo: (id: string) => void` prop, threads to `CommentItem` with 1-based derived index
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentItem/CommentItem.tsx` — added `index`, `onScrollTo` props; index badge with color; color stripe via CSS var; anchor preview; card click-to-scroll; reopen button for resolved state
- `studio/src/renderer/src/components/Editor/CommentsPanel/CommentItem/CommentItem.module.css` — new classes: `.topRow`, `.indexBadge`, `.resolvedBadge`, `.topActions`, `.anchorPreview`, `.reopenBtn`; updated existing classes to use design tokens
- `studio/src/renderer/src/components/Editor/index.tsx` — added `previewRef`, removed `submittedAnchors` memo, threaded `color` through `handleModalAdd`/`handleModalSendNow`, passed `comments` directly to `CommentablePreview`, wired `onScrollTo` to `CommentsPanel`

## Typecheck output

```
studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
(no output — clean)
```
