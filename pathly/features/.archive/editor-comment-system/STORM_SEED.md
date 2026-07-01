# STORM_SEED — editor-comment-system

Inline comment system for the Pathly Studio MD editor preview: per-comment colors,
index badges, scroll-to-with-pulse, margin gutter markers, and keyboard navigation.

> **Architect's note — reconcile with what already exists.**
> The feature brief describes a greenfield `{ id, text, anchorText, color, range, resolved, timestamp, index }`
> model and a new `CommentCard`. The repo already ships a working comment subsystem with a
> *different* shape and naming. The brief's field names are **aspirational**, not the ground truth.
> This seed designs by **extending the live system**, because the live model is load-bearing:
> - `useComments.ts` persists `Comment` to a sidecar `*.comments.json` on disk.
> - `commentUtils.buildSendPrompt()` reads `lineNumber` + `lineText` + `body` to build the
>   "Send to Agent" prompt. Renaming those fields breaks the agent round-trip silently.
> - `CommentsPanel` + `CommentItem` already render the list and the count badge.
>
> Net: we **add** `color`/`index`, we **keep** `lineText`/`lineNumber`/`body`/`createdAt`/`resolved`,
> and we **do not** persist `Range`. Naming below uses the live names with the brief's intent.

---

## Current architecture (as-built, verified)

```
Editor/index.tsx ── owns comment state via useComments(path)
  │   state: pendingAnchor, modalOpen, submittedAnchors (= unresolved lineText[])
  │
  ├─► CommentablePreview ── selection capture + CSS highlights
  │     • tooltipRangeRef   (Range, live at mouseup)
  │     • pendingRangeRef    (Range, promoted on "Comment")
  │     • applyHighlights() drives pathly-pending / pathly-submitted
  │
  ├─► CommentsPanel ── list + count badge + Send-to-Agent
  │     └─► CommentItem (×N)   ← this is today's "card"
  │
  └─► CommentModal ── compose body, Add / Send now

highlightUtils.ts (shared, no React):
  PENDING_HL='pathly-pending'  SUBMITTED_HL='pathly-submitted'
  findTextRange / findAnchorRange  (robust progressive fallback chain — REUSE)
  applyHighlights / clearHighlights
```

What is **missing** vs. the brief (this is the actual build scope):
per-comment color, index/`#N` badge, scroll-to-comment, 300ms pulse, margin gutter markers,
Alt+↑/↓ keyboard nav, and per-comment named highlights.

---

## Decision 1 — Comment data model & where Range lives

**Decision: extend the persisted model with `color` + `index`. Range is NEVER in state and
NEVER persisted. Live Ranges live in a ref `Map<id, Range>` owned by CommentablePreview.**

```ts
// useComments.ts — extend, do not rename
export const COMMENT_COLORS = ['yellow', 'green', 'blue', 'purple', 'orange'] as const
export type CommentColor = typeof COMMENT_COLORS[number]

export interface Comment {
  id: string
  lineNumber: number          // KEEP — buildSendPrompt + sort key
  lineText: string            // KEEP — this IS "anchorText"; sliced to 120 on add
  body: string                // KEEP — this IS "text"
  resolved: boolean           // KEEP
  createdAt: string           // KEEP — this IS "timestamp" (ISO string)
  color: CommentColor         // NEW — default 'yellow'
}
// `index` (#1 #2…) is DERIVED at render, NOT stored — see Decision 6.
// `range` is NOT a field — see below.
```

**Why Range is not in the model and not in state:**
- A DOM `Range` is not JSON-serializable → cannot live in the sidecar file.
- Putting a `Range` in `useState` forces a re-render whenever it changes and risks stale
  closures over detached nodes. The existing code already proves the pattern: `pendingRangeRef`
  is a `useRef`, never state.
- Ranges are *session-only* and *reconstructable* from `lineText` via `findAnchorRange`
  (already battle-tested). So the Range is a **cache**, not source of truth.

**Where the Range map lives — CommentablePreview ref, not Zustand:**
```ts
// inside CommentablePreview
const rangeMapRef = useRef<Map<string, Range>>(new Map())
```
- The preview owns the DOM container; only it can resolve text→Range against *its* render.
- Zustand would be wrong: a Range is meaningless outside the specific live DOM that produced
  it, and there is exactly one preview instance. No cross-component sharing need exists.
- The map is **lazily populated** during `applyHighlights` (we already iterate every anchor
  there) and **read** by scroll-to / gutter / keyboard nav. One source, one owner.

```
SOURCE OF TRUTH          SESSION CACHE (rebuildable)
┌──────────────────┐     ┌────────────────────────────┐
│ sidecar JSON     │     │ rangeMapRef (CommentablePrev)│
│ id,lineText,body │ ──► │ Map<id, Range>               │
│ color,resolved…  │     │ filled in applyHighlights    │
└──────────────────┘     └────────────────────────────┘
        keep                 never persisted, per-render
```

---

## Decision 2 — Color system (5 presets) & per-comment highlights

**Decision: colors are NOT new tokens. Map the 5 preset names directly onto the existing
theme-aware tokens in `tokens.css` (`--yellow --green --blue --purple --orange`, all 5 already
defined and re-declared per theme). Per-comment highlights use ONE named highlight *per color
bucket*, not per id.**

Why reuse existing tokens (verified present at tokens.css lines 36–81 and re-declared in every
theme block): they already adapt to light/dark/Nord/Dracula/etc. Hardcoding hex or inventing
`--comment-yellow` would (a) duplicate values and (b) break theming. The brief's `--comment-*`
suggestion is rejected for this reason.

**Per-comment highlight strategy — bucket by color, not by id:**

The CSS Custom Highlight API styles a *named* highlight via `::highlight(name)` in a **static**
stylesheet. You cannot write a `::highlight()` rule per dynamic id at runtime without inline
styles (forbidden) or injecting `<style>` (ugly, leaks). So:

```
5 static CSS rules (one per color), each a named highlight holding many Ranges:
  ::highlight(pathly-comment-yellow) { background: color-mix(--yellow 22%) }
  ::highlight(pathly-comment-green)  { background: color-mix(--green  22%) }
  ::highlight(pathly-comment-blue)   { … }   purple   orange
```

```ts
// highlightUtils.ts
export const COMMENT_HL_PREFIX = 'pathly-comment-'        // + color
export const PULSE_HL = 'pathly-comment-pulse'
```
At apply time we group unresolved comments by `color`, resolve each Range (live cache → text
fallback), and `CSS.highlights.set('pathly-comment-'+color, new Highlight(...ranges))`.
Five `set` calls max, regardless of comment count → cheap and static-CSS-only.

> The brief literally says `pathly-comment-{id}`. **Rejected**: a per-id highlight needs a
> per-id `::highlight()` CSS rule, which is impossible to author statically and violates the
> no-inline-style / CSS-modules-only rule. Per-color buckets give the same *visual* result
> (each comment shows its color) with 5 fixed rules. Individual targeting for pulse/gutter is
> handled by the Range map + pulse highlight, not by per-id background rules.

`pathly-pending` and `pathly-submitted` stay as-is for the in-flight draft flow; the new
per-color buckets replace `pathly-submitted` for *saved* comments (which now carry a color).

---

## Decision 3 — Range invalidation on content change

**Decision: `lineText` is the durable anchor; Range is a cache validated by
`startContainer.isConnected`. On any miss, re-run `findAnchorRange` and refill the map.**

The mechanism the brief asks for **already exists** — `isRangeConnected()` in highlightUtils
(line 107) wraps `range.startContainer.isConnected` in try/catch, and `applyHighlights`
(line 132) already does `liveOk ? pendingRange : findAnchorRange(...)`. We generalize it:

```ts
function resolveRange(container, id, anchor, cache): Range | null {
  const cached = cache.get(id)
  if (cached && isRangeConnected(cached)) return cached     // fast path
  const found = findAnchorRange(container, anchor)          // rebuild from text
  if (found) cache.set(id, found)
  else cache.delete(id)                                     // truly gone (text edited away)
  return found
}
```
- Triggered implicitly: `applyHighlights` already re-runs in a `useEffect` keyed on `content`
  (line 79). When `content` changes, React re-renders the preview, the effect fires, every
  cached Range is now detached → `resolveRange` rebuilds from `lineText`. No new wiring.
- If the anchored text was *deleted* from the markdown, `findAnchorRange` returns null → the
  comment simply has no highlight/gutter that frame, but the card still shows in the panel
  (anchor lost, comment retained). This is the correct, non-destructive behavior.

---

## Decision 4 — Scroll-to mechanism

**Decision: `onScrollToComment(id)` prop on CommentablePreview. Resolve Range (cache→text
fallback), use `getBoundingClientRect()` relative to the scroll container, then
`container.scrollTo({ top, behavior:'smooth' })`. Pulse on arrival. Detached → rebuild first.**

```
CommentItem click ──► panel onScrollTo(id) ──► Editor lifts to ref ──► preview.scrollToComment(id)
                                                       │
                          ┌────────────────────────────┘
                          ▼
   resolveRange(id)  ──hit──►  rect = range.getBoundingClientRect()
        │                       cRect = container.getBoundingClientRect()
        │ miss (text gone)      top  = container.scrollTop + (rect.top - cRect.top) - 40px
        ▼                       container.scrollTo({ top, behavior:'smooth' })
   no-op (flash panel card)     → then pulse(range)  [Decision 5]
```

- Use `getBoundingClientRect()` (single rect) for the scroll target, not `getClientRects()`
  (per-line list — only needed for hit-testing, as the existing resume-click does at line 61).
- 40px top offset keeps the anchor off the very edge under the sticky toolbar/ConfigForm.
- The existing resume-click handler already wraps Range geometry in try/catch for detachment
  (line 71); scroll-to reuses `resolveRange` so the detached case is handled *before* geometry.

**Wiring the imperative call up to Editor:** CommentablePreview exposes the action without
adding render state. Two clean options; pick the ref handle:
```ts
// preview takes a ref the parent fills:
export interface CommentablePreviewHandle { scrollToComment(id: string): void }
// Editor:  const previewRef = useRef<CommentablePreviewHandle>(null)
//          <CommentsPanel onScrollTo={(id) => previewRef.current?.scrollToComment(id)} />
```
This avoids round-tripping a "scrollTarget" through state (which would re-render the whole
preview on every click). Same philosophy as the Range-in-ref decision.

---

## Decision 5 — Pulse animation

**Decision: a dedicated `pathly-comment-pulse` named highlight, set on arrival and `delete`d
after 300ms via `setTimeout`. Zero React state, zero re-render.**

```ts
// highlightUtils.ts
export function pulseRange(range: Range): void {
  setHL(PULSE_HL, [range])
  setTimeout(() => deleteHL(PULSE_HL), 300)
}
```
```css
/* CommentablePreview.module.css */
:global(::highlight(pathly-comment-pulse)) {
  background-color: color-mix(in srgb, var(--accent) 55%, transparent);
}
```
- The Custom Highlight API has no transition/animation support (only bg/color/text-decoration/
  text-shadow are honored), so "pulse" = a brief strong overlay that disappears. That reads as a
  flash, which is the intended affordance. A true fade would require a DOM element overlay — not
  worth it here.
- Crucially this mutates **only** `CSS.highlights`, never component state, so there is **no
  re-render flash** and it cannot fight the `content`-keyed `applyHighlights` effect. The brief's
  "avoids re-render flash" requirement is met exactly.
- Pulse paints *on top of* the comment's color bucket (it's a separate named highlight); when
  deleted, the underlying color remains. No need to restore anything.

---

## Decision 6 — Margin gutter badges (① ② ③)

**Decision: Option B — a single absolutely-positioned overlay layer inside the preview's
`position: relative` root, one badge `<button>` per resolvable Range, positioned from
`getBoundingClientRect()`. NOT DOM injection into the rendered markdown.**

```
┌─ CommentablePreview .root (position: relative) ─────────────┐
│ ┌─ .gutter (absolute, left:0, width:22px) ─┐                │
│ │  ①   ← top = rectTop - containerTop      │  markdown …    │
│ │      + scrollTop                          │  the quick …   │
│ │  ②                                        │  brown fox …   │
│ └───────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────┘
```

**Why Option B (overlay) beats Option A (inject DOM into preview):**

| | A: inject `<span>` into markdown | B: overlay layer (CHOSEN) |
|---|---|---|
| Markdown integrity | mutates rendered DOM → fights re-render, breaks `findTextRange` text walk | preview DOM untouched → text walker stays clean |
| Highlight API | DOM mutation invalidates live Ranges every keystroke | Ranges survive; overlay just reads geometry |
| Reflow risk | inserted nodes shift text, change wrapping | absolute layer, zero layout impact |
| Cleanup | must find+remove injected nodes | React unmount/remount of overlay children |
| Coding rules | inline positioning ⇒ inline styles | positions via `setProperty` in effect (allowed) |

Option A directly contradicts the project's whole reason for using the Custom Highlight API
("zero DOM mutation", highlightUtils.ts header). So A is rejected on principle, not just taste.

**Index derivation (`#N` / ①):** index is the **1-based position of the comment in the
unresolved list sorted by `lineNumber`** (the list is already sorted on `add`, line 50 of
useComments). Compute at render via `unresolved.map((c, i) => i + 1)`; pass `index` to both the
gutter badge and `CommentItem`'s `#N` badge so panel and gutter always agree. Not persisted.

- Positioning values (`top`, color) are dynamic → set via `el.style.setProperty('--top', …)`
  in a `useEffect`, consumed by the CSS module. This is the explicitly-allowed exception in
  studio/CLAUDE.md ("CSS custom properties set imperatively via ref … bypasses the JSX style
  prop"). No `style={{}}` prop anywhere.
- Badge click = the same `scrollToComment(id)` path as Decision 4 (gutter and panel share it).
- The overlay recomputes positions in the same effect that runs `applyHighlights` (keyed on
  `content`, comments, scroll). Add a `scroll` listener on the container to reposition on scroll.

---

## Decision 7 — Keyboard navigation (Alt+↑ / Alt+↓)

**Decision: the keydown listener lives in CommentablePreview, scoped to the container (not
document). The ordered comment list is owned by Editor (it already derives `submittedAnchors`)
and passed down as the same `comments` array; nav order = unresolved sorted by `lineNumber`.**

```
Editor (owns comments, sorted)
   │  passes comments + scrollToComment handle
   ▼
CommentablePreview
   • keydown on .root (tabIndex=0) :  Alt+ArrowDown → next id, Alt+ArrowUp → prev id
   • tracks activeIndexRef (useRef, not state — no re-render)
   • next/prev → scrollToComment(id)  → reuses Decision 4 + pulse Decision 5
```

**Why the listener lives in the preview, scoped to container:**
- Editor already owns a *document*-level keydown for Ctrl+S (line 139). A second document
  listener for arrows would capture keystrokes while the user types in the CommentModal textarea
  or the Markdown editor → hijacked arrow keys. Scoping to the preview's focusable `.root`
  confines nav to "focus is in the preview", which is exactly the brief's "Alt+↑/↓ in preview".
- The preview already owns the Range map + scroll mechanism, so nav is a 3-line consumer of
  existing internals — no prop drilling of geometry.
- `activeIndexRef` is a ref (not state): advancing the cursor must not re-render and must not
  re-run `applyHighlights`. Consistent with every other Range/cursor decision here.
- Order is unambiguous: `comments.filter(!resolved)` is already kept sorted by `lineNumber` on
  insert, so "next/prev" = document reading order. Wrap around at ends (down from last → first).

---

## Decision 8 — File structure (new + modified)

**Hard limit ~150 lines/file. CommentablePreview is the at-risk file — it gains the Range map,
scroll-to, pulse glue, gutter overlay, and keyboard nav. Extract aggressively into a hook +
sibling components so the component stays a thin shell.**

```
Editor/CommentablePreview/
  CommentablePreview.tsx        MOD  thin shell: render + wires hook; exposes
                                     CommentablePreviewHandle ref (scrollToComment)
  CommentablePreview.module.css MOD  add ::highlight(pathly-comment-{color}) ×5,
                                     ::highlight(pathly-comment-pulse), .gutter layer
  highlightUtils.ts             MOD  COMMENT_HL_PREFIX, PULSE_HL, COMMENT_COLORS-aware
                                     applyCommentHighlights(byColor), pulseRange(),
                                     resolveRange() helper; keep findAnchorRange untouched
  useCommentRanges.ts           NEW  owns rangeMapRef + resolveRange + applyHighlights driver
                                     + scrollToComment(id) + pulse; the brains, ~120 lines
  useCommentKeyboardNav.ts      NEW  Alt+↑/↓ container listener, activeIndexRef, calls
                                     scrollToComment; ~40 lines
  CommentGutter/
    CommentGutter.tsx           NEW  overlay layer; maps id→position→badge button
    CommentGutter.module.css    NEW  .gutter (absolute) + .badge (uses --top, --color vars)

Editor/CommentsPanel/
  CommentsPanel.tsx             MOD  thread onScrollTo(id) down to items; count badge already exists
  CommentItem/CommentItem.tsx   MOD  add #N index badge + color dot/stripe; click → onScrollTo(id);
                                     this IS the brief's "CommentCard" (rename NOT required)
  CommentItem/CommentItem.module.css  MOD  .indexBadge, .colorDot per-color via --color var

Editor/CommentModal/
  CommentModal.tsx              MOD  add 5-swatch color picker (default yellow); pass color up
  CommentModal.module.css       MOD  .swatch / .swatchRow

Editor/
  useComments.ts                MOD  Comment gains `color`; add(color) param, default 'yellow';
                                     COMMENT_COLORS + CommentColor exports
  commentUtils.ts               (no change — buildSendPrompt still uses lineNumber/lineText/body)
  index.tsx                     MOD  hold previewRef (CommentablePreviewHandle); pass scrollTo
                                     from panel→preview; thread color through handleModalAdd
```

```
DATA / CONTROL FLOW (after)
                              add(color)         persist
 CommentModal ──color──► Editor ──► useComments ──► sidecar.json
   (5 swatches)             │  comments (sorted, +color, +derived index)
                            ├──────────────► CommentsPanel ──► CommentItem  (#N, color, click→scrollTo)
                            │                                         │ onScrollTo(id)
                            │  previewRef.scrollToComment(id) ◄───────┘
                            ▼
                     CommentablePreview (shell)
                        ├ useCommentRanges  rangeMapRef · applyCommentHighlights · scrollToComment · pulse
                        ├ useCommentKeyboardNav  Alt+↑/↓ → scrollToComment
                        └ CommentGutter  ① ② ③ overlay (positions from resolveRange)
```

---

## Risks / watch-items for BUILD

1. **150-line ceiling on CommentablePreview.** It currently sits at ~97 lines and *must not*
   absorb the new logic inline. The `useCommentRanges` extraction is mandatory, not optional —
   flag in review if logic creeps back into the component.
2. **Effect thrash.** `applyHighlights` is keyed on `content` and re-runs on every keystroke in
   split/edit. The gutter overlay must share that single effect, not add its own per-frame loop.
   Add a `scroll` listener (passive) for reposition; debounce not needed for scroll repaint.
3. **Color highlight z-order vs. pending.** While a draft is pending, `pathly-pending` and a
   color bucket could both target overlapping ranges. Keep the pending flow on its own highlight
   and exclude the in-flight anchor from color buckets (mirror the existing
   `if (anchor === pendingAnchor) continue` skip at highlightUtils line 124).
4. **Sidecar back-compat.** Old `*.comments.json` files have no `color`. `useComments` load must
   default missing `color` to `'yellow'` so existing comment files don't crash on read.
5. **Brief-vs-reality naming.** Anyone reading the brief expects `CommentCard`/`anchorText`/
   `text`/`index` fields. The build keeps `CommentItem`/`lineText`/`body` and derives `index`.
   Document this mapping in the PR description so reviewers don't "fix" it back to the brief.
