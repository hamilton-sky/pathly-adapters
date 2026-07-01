# User Stories — editor-comment-system

## Story → Conversation Map

| Story | Delivered in |
|---|---|
| S1 — Per-comment color on creation | Conv 1 |
| S2 — Colored highlight in preview | Conv 1 |
| S3 — Index badge on each card | Conv 1 |
| S4 — Anchor text preview on card | Conv 1 |
| S5 — Click card to scroll + pulse | Conv 1 |
| S9 — Stable index ordering contract | Conv 1 |
| S10 — Resolve still works with colors/indices | Conv 1 |
| S6 — Comment count badge on panel toggle | Conv 2 |
| S7 — Margin gutter badges | Conv 2 |
| S8 — Keyboard navigation between anchors | Conv 2 |

---

## S1 — Per-comment color on creation

**As a** developer reviewing markdown, **I want** to pick one of five preset colors when I create a comment, **so that** I can visually group or prioritize related comments.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 1a | CommentModal shows a 5-swatch color picker row | All 5 swatches (yellow, green, blue, purple, orange) visible in the modal | Any swatch missing or picker absent |
| 1b | Default color is yellow | Submitting modal with no swatch click persists `color: "yellow"` in sidecar JSON | Sidecar has no `color` field or a different default |
| 1c | Selected color is persisted | Sidecar JSON for a new comment contains the exact color the user clicked | Sidecar field is absent or shows wrong color |
| 1d | Old sidecars without `color` load without crashing | Opening a pre-existing `.comments.json` lacking the `color` field renders all comments with yellow highlights and no runtime error | Page crashes or comments fail to load |

---

## S2 — Colored highlight in preview

**As a** developer, **I want** each comment's anchor text highlighted in that comment's color, **so that** the panel card and highlighted text are visually linked.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 2a | Each unresolved comment has a per-color named highlight | `CSS.highlights` contains entries keyed as `pathly-comment-yellow/green/blue/purple/orange`; each entry covers only comments of that color | Entry absent or contains comments of wrong color |
| 2b | Legacy `pathly-submitted` highlight is not used for saved comments | Inspecting `CSS.highlights` in DevTools shows no `pathly-submitted` entry when at least one unresolved comment exists | `pathly-submitted` still present for saved comments |
| 2c | Resolved comments have no highlight | Resolving a comment causes its Range to be removed from the color bucket on next render | Resolved comment anchor remains highlighted |
| 2d | Eye toggle removes all per-comment highlights | Clicking the highlight toggle removes all `pathly-comment-*` entries from `CSS.highlights` | Highlights persist after toggle off |
| 2e | CSS Custom Highlight API unavailable = silent degradation | In a context where `'highlights' in CSS` is false, no error thrown and comments still display in panel | Error thrown or crash |

---

## S3 — Index badge on each card

**As a** developer, **I want** each comment numbered #1, #2, … in document order, **so that** I can reference comments unambiguously.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 3a | CommentItem shows an index badge | Each unresolved CommentItem renders a visible `#N` badge where N is 1-based position in the sorted unresolved list | Badge absent |
| 3b | Badge color matches comment color | Badge background uses `var(--comment-{color}-swatch)` matching the comment's stored `color` field | Badge uses wrong or default color |
| 3c | Resolved comments do not get an index | Resolved CommentItems have desaturated badge with no color; unresolved indices stay contiguous after resolve | Resolved comment retains a color badge or indices gap |

---

## S4 — Anchor text preview on card

**As a** developer, **I want** each card to show the first ~50 chars of the anchored text, **so that** I know what the comment refers to without scrolling to the preview.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 4a | Anchor text renders in monospace | `lineText` preview uses `var(--font-family-mono)` | Regular font used |
| 4b | Text truncates at 50 chars with ellipsis | A `lineText` longer than 50 chars shows first 50 chars followed by `…` | No truncation visible or ellipsis missing |
| 4c | Full text available on hover | The card's anchor element has `title={lineText}` set to the full `lineText` value | No title tooltip on hover |
| 4d | Whitespace collapsed for display | `lineText` with internal newlines or multiple spaces displays as single spaces in the preview chip | Newlines or doubled spaces visible in the chip |

---

## S5 — Click card to scroll + pulse

**As a** developer, **I want** clicking a comment card to scroll the preview to its anchor and pulse it, **so that** I can locate the referenced text instantly.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 5a | Clicking a CommentItem scrolls preview to anchor | Preview container scrolls so the highlighted anchor text is visible, vertically offset ~40px from top edge | No scroll occurs |
| 5b | Pulse highlight appears on arrival | For ~300ms after scroll, a stronger highlight overlay (`pathly-comment-pulse`) is visible on the anchor | No visual change on scroll |
| 5c | Pulse clears automatically | After 300ms the pulse highlight is gone and the normal color bucket remains | Pulse stays on screen or removes the normal highlight |
| 5d | Orphaned anchor produces no crash | Clicking a card whose `lineText` cannot be found in the preview (text deleted) produces no error and no scroll | Runtime error thrown |
| 5e | Multiple rapid clicks cancel prior pulse | Clicking two cards in quick succession: only the second pulse is active; no stuck highlights | Two pulse highlights overlap permanently |

---

## S6 — Comment count badge on panel toggle

**As a** developer, **I want** the unresolved comment count visible on the panel toggle button, **so that** I know there are open comments even when context is limited.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 6a | Badge shows unresolved count | Toggle button displays a numeric badge equal to `comments.filter(c => !c.resolved).length` | Badge absent, wrong count, or shows resolved too |
| 6b | Badge hidden when count is 0 | When no unresolved comments exist, no badge element renders (not just `display:none` on a visible `0`) | `0` badge still visible or badge element present |
| 6c | Existing badge styling reused | Badge uses `styles.badge` from CommentsPanel.module.css, not a new parallel style | New inline style or separate CSS file introduced |

---

## S7 — Margin gutter badges

**As a** developer, **I want** small numbered markers at the left edge of each highlighted span, **so that** I can scan the document margin and map regions to comments.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 7a | Gutter badge aligns to anchor top edge | Badge `top` CSS var equals `range.getBoundingClientRect().top - containerRect.top + scrollTop` | Badge positioned at wrong vertical position |
| 7b | Badge shows same index as card | Gutter badge number matches the `#N` shown on the corresponding CommentItem | Numbers disagree |
| 7c | Badge color matches comment color | Badge background uses `var(--comment-{color}-swatch)` for the comment's color | Wrong or default color |
| 7d | Resolved comments have no gutter badge | Resolving a comment removes its gutter badge on next render | Resolved comment gutter badge remains |
| 7e | Eye toggle removes all gutter badges | When `showHighlights` is false, CommentGutter renders no badge elements | Badges remain when highlights are toggled off |
| 7f | Reposition on scroll | Scrolling the preview container triggers badge reposition (scroll event listener on container) | Badges drift from anchor text on scroll |
| 7g | No inline `style={{}}` props | CommentGutter.tsx has zero JSX `style={{}}` props; positions come from `el.style.setProperty` in a `useEffect` | Any `style={{}}` prop found in CommentGutter.tsx |

---

## S8 — Keyboard navigation between anchors

**As a** developer, **I want** Alt+Down / Alt+Up to jump between comment anchors while focused in the preview, **so that** I can review comments without the mouse.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 8a | Alt+Down moves to next anchor in document order | With preview focused, Alt+Down scrolls to the next unresolved comment anchor by `lineNumber` sort | No scroll or wrong anchor visited |
| 8b | Alt+Up moves to previous anchor | Alt+Up scrolls to the prior anchor | No scroll or direction reversed |
| 8c | Navigation wraps at ends | Alt+Down from last anchor jumps to first; Alt+Up from first jumps to last | Navigation stops at ends |
| 8d | Same pulse plays on keyboard nav | Scroll-to from keyboard triggers the identical 300ms pulse as card click | No pulse on keyboard nav |
| 8e | Listener scoped to preview container | Alt+Down while focus is in the MarkdownEditor textarea produces no scroll | Arrow key in editor textarea scrolls preview |
| 8f | No collision with Ctrl+S handler | Alt+Down does not trigger save; Ctrl+S in preview does trigger save | Either cross-fires |
| 8g | Unreachable anchors skipped | If an anchor cannot be located, nav moves to the next one rather than stopping | Navigation stops on orphaned anchor |

---

## S9 — Stable index ordering contract

**As a** developer, **I want** comment numbers to stay predictable as I add, resolve, and delete, **so that** indices remain meaningful during a review session.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 9a | Index derived at render, not stored | The sidecar JSON for a comment never contains an `index` field | Sidecar JSON has an `index` field |
| 9b | Order is by `lineNumber` ascending | Adding a comment at line 10 after comments at lines 5 and 20 gives it index #2 | Index assigned by creation time or arbitrary order |
| 9c | Card, gutter, and highlight always agree | All three representations show the same number for a given comment within one render | Any representation shows a stale or different number |

---

## S10 — Resolve still works with colors/indices

**As a** developer, **I want** resolving a comment to remove its highlight, gutter marker, and index badge color, **so that** the review surface reflects only open items.

| # | Acceptance Criterion | PASS condition | FAIL condition |
|---|---|---|---|
| 10a | Resolving removes from color bucket highlight | After resolve, the comment's Range is absent from `CSS.highlights.get('pathly-comment-{color}')` | Range still present in highlight |
| 10b | Remaining unresolved comments renumber | After resolving comment #2 of 3, the former #3 becomes #2 | Gap persists in numbering (#1 then #3) |
| 10c | Resolved card moves to Resolved section | Resolved CommentItem appears under the "Resolved" divider (existing behavior retained) | Resolved card stays in unresolved list |
| 10d | Resolved card shows desaturated badge | Resolved card's index badge uses `var(--bg-surface1)` background and `var(--text-muted)` text | Badge remains colored |
