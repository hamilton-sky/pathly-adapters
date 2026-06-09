# DESIGN_SPEC — Editor & Notebook Enhancements

Feature: `editor-notebook-enhancements`
Author: architect
Date: 2026-06-09
Scope: 7 UI features across `Editor/` and `SkillNotebook/`

---

## 0. Codebase findings that constrain the design

Read before designing. These three facts override naive approaches:

1. **`skillNotebookStore` makes the entire `cells[]` array the undo/redo unit.**
   Every mutation calls `pushCells()`, which snapshots `cells` into `history[]`
   (cap 50). Putting transient view state (collapse, hover) into this store
   would pollute undo history — Ctrl+Z would "undo a collapse". This decides
   Features 5 and 6.

2. **The "no inline style" rule already has two enforcement levels in-tree.**
   - `MarkdownEditor.tsx:82` uses a static `style={{ height, overflow }}` — a real
     violation that should be fixed while we're in the file (Feature 3).
   - `BodyCell.tsx:223` uses `style={{ '--sel-x': ... } as React.CSSProperties}`
     for dynamic coordinates. CLAUDE.md says custom props must go through
     `ref.current.style.setProperty(...)`. The `SelectionTooltip` already does
     this correctly (`SelectionTooltip.tsx:14-18`). **`SelectionTooltip` is the
     canonical pattern; replicate it, do not copy BodyCell's selBar inline cast.**

3. **`CommentablePreview` already owns the selection + clear-on-mousedown +
   mark-injection machinery.** The new Find action (Feature 2) and the expanded
   tooltip (Feature 1) extend this existing component — they are not greenfield.
   Marks carry `data-comment-mark="true"` and `removeAllMarks()` keys off that
   attribute. Find-marks need a *different* attribute so the two systems don't
   clear each other.

### z-index map (measured, for stacking decisions)

```
9000  (proposed) Editor fullscreen panel
1000  SelectionTooltip                    [Editor/SelectionTooltip.module.css:6]
 200  cell ⋯ menu (Body + Fragment)       [FragmentCell.module.css:124]
   …  FragmentCell hover popover MUST sit between cell content and 200
```

---

## Feature 1 — Selection Tooltip expansion (Copy, Find, Explain, Ask Agent)

### Decision: extract a flat button row + a dedicated AgentPicker sibling

```
Editor/SelectionTooltip/
  SelectionTooltip.tsx        ~55 lines  — positioning shell + button row
  SelectionTooltip.module.css
  AgentPicker/
    AgentPicker.tsx           ~45 lines  — adapter sub-menu (claude/codex/agy)
    AgentPicker.module.css
  tooltipActions.ts           pure       — buildExplainPrompt, buildAskPrompt, adapter argv
```

**Why a sibling `AgentPicker/` folder and not elsewhere:** the picker is
meaningless outside this tooltip — it has no other call site, it shares the
tooltip's fixed-overlay coordinate space, and the folder rule in CLAUDE.md says
sub-sections extract "into its own file **in the same folder**". A separate
top-level component would imply reuse that does not exist. If a second consumer
appears later (e.g. CommentsPanel "send to agent"), promote it to `Editor/shared/`
then — not now (YAGNI).

**Why the tooltip stays under 150 lines:** the tooltip becomes a *layout shell*,
not a logic container. Three moves keep it small:

```
┌─ SelectionTooltip (shell) ──────────────────────────┐
│  positioning useEffect (setProperty --tip-x/-y)      │  ← unchanged, ~6 lines
│  ┌────────────────────────────────────────────────┐ │
│  │ [Comment][Copy][Find][Explain][Ask Agent ▾]     │ │  ← <ToolbarButton> ×5
│  └────────────────────────────────────────────────┘ │
│  {askOpen && <AgentPicker onPick={…} />}             │  ← sub-component
└──────────────────────────────────────────────────────┘
```

1. **All prompt/argv construction → `tooltipActions.ts`** (no React). Reuses the
   exact pattern from `commentUtils.ts` (`getSpawnCwd`, prompt-as-string-array).
2. **Each button is a `<ToolbarButton icon label onClick>`** rendered from a
   small config array — 5 buttons become ~5 lines of `.map`, not ~40 lines of JSX.
3. **The adapter list lives in `AgentPicker`**, so adding a 4th adapter never
   touches the tooltip.

### Contract change — `SelectionTooltip` props

The tooltip currently takes one callback (`onComment`). It must not grow one prop
per action (Copy/Find are local, Explain/Ask spawn terminals owned by the parent).
Split by ownership:

```ts
interface Props {
  x: number
  y: number
  selectedText: string                 // NEW — needed for Copy + prompt building
  onComment: () => void
  onFind: () => void                    // NEW — Find lives in CommentablePreview (Feature 2)
  onSpawnAgent: (adapter: AdapterId, action: 'explain' | 'ask') => void  // NEW
}
// Copy is fully local: navigator.clipboard.writeText(selectedText) — no prop.
```

`onSpawnAgent` is one callback, not four, because the parent
(`CommentablePreview` → `Editor`) owns terminal spawning and already has
`addTab/openTab/spawn` wired (`Editor/index.tsx:181-200`). Tooltip stays dumb
about adapters beyond passing the chosen id up.

**Risk — Copy needs clipboard access.** In Electron renderer with
contextIsolation, `navigator.clipboard.writeText` works in a user-gesture
handler (the click qualifies). No IPC needed. If it ever fails (focus quirks),
fall back to `window.pathly.clipboard?.write` — but do not build that until the
direct path is shown to fail.

**Risk — tooltip dismiss vs. AgentPicker.** The document `mousedown` listener in
CommentablePreview clears the tooltip. The picker submenu must `stopPropagation`
on its own `onMouseDown` (the tooltip root already does this at line 24) so
opening the picker does not dismiss its parent.

---

## Feature 2 — CommentablePreview "Find" (highlight all occurrences)

### Decision: new exported utility `highlightAllOccurrences`, separate mark namespace

`injectMarkForText` returns after the **first** match (`return mark` inside the
TreeWalker loop). Do not modify it — comment-marks depend on first-match-only
semantics for anchoring. Add a parallel function.

```ts
// in CommentablePreview.tsx (or extract both into commentablePreviewMarks.ts
// if the file crosses 150 lines after this — it is at 144 now, so extract).

export function highlightAllOccurrences(
  container: HTMLElement,
  searchTerm: string,
  className: string,
): number    // returns count, for a "3 matches" affordance later
```

It reuses the same whitespace-normalised matching logic as `injectMarkForText`
but (a) loops all text nodes, (b) does not `return` early, (c) tags marks with a
**different** dataset attribute:

```
data-comment-mark="true"   → comment anchors      (removeAllMarks clears these)
data-find-mark="true"      → find highlights       (clearFindMarks clears these)
```

This separation is the whole point: a Find must not wipe comment highlights, and
re-running the comment-mark effect (`CommentablePreview.tsx:110`) must not wipe
an active Find. Add a sibling `clearFindMarks(container)` that queries
`[data-find-mark]` only.

**Edge case — overlapping ranges.** When you split a text node to inject a mark,
the TreeWalker's live node list shifts. `injectMarkForText` sidesteps this by
returning immediately. For all-occurrences, collect match positions in a first
pass (read-only, no DOM mutation), then mutate in a second pass **back-to-front**
(highest offset first) so earlier offsets stay valid. This is the standard
"find-and-highlight" two-pass pattern and avoids the live-collection trap.

### Decision: clear find-marks by extending the existing mousedown listener

Do **not** add a second document listener. The `onDocMouseDown` handler at
`CommentablePreview.tsx:97-101` already fires on any outside click and clears the
tooltip. Extend it to also call `clearFindMarks(containerRef.current)`. One
listener, one clear path, no ordering bugs.

State needed: a single `findTerm: string | null` in CommentablePreview. The
mark-injection runs in its own `useEffect([findTerm, content])`. Setting
`findTerm` from the tooltip's `onFind` triggers highlight; mousedown sets it back
to `null` and clears.

```
ASCII flow:
  user selects text ──► tooltip shows ──► clicks [Find]
        │                                      │
        │                          setFindTerm(selectedText)
        ▼                                      ▼
  onDocMouseDown ◄── effect: highlightAllOccurrences(container, term, .findMark)
        │                          (marks tagged data-find-mark)
  clearFindMarks + setFindTerm(null)
```

**Risk — Find inside an existing comment-mark.** A `<mark data-comment-mark>`
contains a text node; the TreeWalker will descend into it and can inject a nested
`<mark data-find-mark>`. Nested `<mark>` is valid HTML and renders fine; on clear
the inner one is unwrapped and the comment-mark survives. Acceptable. Do not try
to skip comment-mark subtrees — that would make Find miss real matches.

---

## Feature 3 — MarkdownEditor CodeMirror extensions

### Decision A: keep `basicSetup`, layer overrides with `Prec.high`

Markdown shortcuts (Ctrl+B/I/`) wrap selection. basicSetup binds Ctrl+B? No — but
to be safe against any default and to win deterministically, register them as:

```ts
import { Prec } from '@codemirror/state'
import { keymap } from '@codemirror/view'

Prec.high(keymap.of([
  { key: 'Mod-b', run: wrapWith('**') },
  { key: 'Mod-i', run: wrapWith('*')  },
  { key: 'Mod-`', run: wrapWith('`')  },
]))
```

`Mod-` is the cross-platform Ctrl/Cmd token — required since the app runs on
Windows and macOS. `Prec.high` guarantees our keymap is consulted before
basicSetup's, regardless of extension array order. Each `run` returns `true` to
stop propagation, `false` to fall through. Put `wrapWith` in a new
`markdownCommands.ts` (pure CM commands, no React).

### Decision B (the real question): autocomplete — use `override`, do NOT exclude basicSetup's

**Answer: you can keep basicSetup's `autocompletion()` and add your source via a
second `autocompletion({ override: [...] })`, but `override` is the wrong knob.**

Here is the precise CodeMirror semantics that resolves the question:

- `autocompletion()` is a config **facet**. When the extension appears twice,
  CodeMirror **merges** the configs — it does not run two independent autocomplete
  systems. There is one completion system; multiple `autocompletion()` calls
  combine their options.
- `override: [fn]` **replaces the entire source list** with exactly `fn`. If you
  pass `override` you turn OFF every language-derived source (markdown word
  completion, snippet completion, etc.) and get *only* your template-variable
  source. That is usually not what you want.
- The additive path is `EditorState.languageData` completion sources, surfaced by
  registering your source through the language, OR simpler: provide it as an
  extra source. The clean, documented additive API is:

```ts
import { autocompletion } from '@codemirror/autocomplete'

// ADDITIVE — template vars on top of markdown's own completions:
autocompletion({
  override: undefined,           // leave language sources intact
  // register the extra source via the language facet instead:
})
markdownLanguage.data.of({ autocomplete: templateVarSource })
```

**Recommendation:** register `templateVarSource` on the markdown language's
`data` facet (`markdown().language.data.of({ autocomplete: source })`), and leave
basicSetup's `autocompletion()` untouched. This gives template vars *in addition
to* markdown completions, scoped to the markdown language. Use `override` only if
product wants template vars to be the **sole** completion source — confirm intent
before choosing that.

```
                          ┌─ basicSetup autocompletion() (the engine) ─┐
markdown lang.data ──┐    │  collects sources from all language.data   │
  + templateVar src  ├──► │  facets + any override                     │ ──► popup
basicSetup defaults ─┘    └─────────────────────────────────────────────┘
```

`templateVarSource: CompletionSource` returns `{ from, options }` where `from` is
the match start (e.g. position after `{{`). Trigger on `{{` via a `matchBefore`
regex. Put it in `templateCompletion.ts`.

### Decision C: fix the static inline style while here

Replace `MarkdownEditor.tsx:82` `<div style={{ height:'100%', overflow:'auto' }}>`
with a `.module.css` class. The component currently has no CSS module — add
`MarkdownEditor.module.css`. The editor theme stays inline in the CM `theme()`
call (that is CodeMirror's API, not a DOM style prop — exempt).

### MarkdownEditor decomposition

The file is 83 lines and the extension list is about to grow. Extract the
extension assembly so the component stays a thin lifecycle wrapper:

```
Editor/
  MarkdownEditor.tsx              keep <150 — refs, mount/destroy, value sync
  MarkdownEditor.module.css       NEW — host div sizing
  editorExtensions.ts             NEW — buildExtensions(theme, onChange): Extension[]
  markdownCommands.ts             NEW — wrapWith, CM keybindings
  templateCompletion.ts           NEW — templateVarSource
```

`buildExtensions` composes `[basicSetup, markdown(), shortcutsKeymap, themeExt,
updateListener]` plus the language-data completion registration. One place to
reason about precedence.

---

## Feature 4 — Editor status bar + fullscreen

### Decision: counts in a pure util + presentational `EditorStatusBar`

```
Editor/
  EditorStatusBar/
    EditorStatusBar.tsx     ~40 lines — words · ~tokens · dirty dot · fullscreen btn
    EditorStatusBar.module.css
  editorStats.ts            countWords(body), estimateTokens(body)
```

`estimateTokens = Math.ceil(body.length / 4)` and
`countWords = body.split(/\s+/).filter(Boolean).length` as specified. Wrap both
in `useMemo(() => …, [body])` in `Editor` — `body` changes on every keystroke and
`split` on a large doc is not free. The status bar receives numbers, not `body`.

### Decision: fullscreen state goes in `uiStore`, persisted-off

**Answer to the open question: lift to `uiStore`, do not keep local.** Three
reasons grounded in the code:

1. `uiStore` already owns every cross-cutting layout flag (`sidebarCollapsed`,
   `chatOpen`, `notebookPreviewOpen`) — fullscreen is the same class of state.
2. Other components must *react* to editor-fullscreen: the sidebar/topbar should
   not capture clicks behind a `z-index:9000` panel, and Escape-to-exit should
   work even if focus left the editor. A local boolean can't coordinate that.
3. Local state is wiped on `effectivePath` change (the big reset effect at
   `Editor/index.tsx:120-137`); fullscreen should survive switching files.

Add:
```ts
editorFullscreen: boolean
setEditorFullscreen: (v: boolean) => void
// Do NOT add to partialize() — fullscreen should reset on app restart.
```

### Decision: fullscreen via `position:fixed; inset:0; z-index:9000` — works, with two caveats

It works in Electron (Chromium) **provided the panel is not trapped in an
ancestor stacking context with a lower z-index**. Two real risks:

```
RISK 1 — ancestor stacking context
  If any wrapper between <body> and .panel has transform / filter / opacity<1 /
  will-change, then z-index:9000 is scoped to THAT context, and a sibling with
  z-index:200 outside it can still paint on top.
  → MITIGATION: render the fullscreen panel through a React portal to document.body
    (createPortal) when editorFullscreen is true. This escapes all ancestor
    contexts. This is the robust fix; prefer it over hunting for offending
    ancestors.

RISK 2 — Electron custom title bar / traffic lights
  inset:0 covers the OS drag region. On a frameless window the user can no longer
  drag or reach window controls while fullscreen.
  → MITIGATION: inset the top by the title-bar height (use the existing
    --titlebar-height token if present; otherwise top: var(--titlebar-h)), OR
    add an in-panel "exit fullscreen" button + Escape handler. Ship the Escape
    handler regardless.
```

This is **CSS fullscreen, not the Fullscreen API** (`requestFullscreen`). Good —
the native API hides the menu/title bar entirely and behaves erratically in
Electron. Stick with CSS + portal.

```
ASCII — fullscreen render path:
  editorFullscreen === false → <div class=panel> … </div>           (in place)
  editorFullscreen === true  → createPortal(<div class="panel fs">,  document.body)
                               .fs { position:fixed; inset:0; z-index:9000 }
                               + useEffect: keydown Escape → setEditorFullscreen(false)
```

---

## Feature 5 — BodyCell collapse

### Decision: LOCAL state. Do NOT touch skillNotebookStore.

**Answer to the open question: stay local.** This is forced by finding #1.
`skillNotebookStore` snapshots `cells[]` on every mutation for undo/redo. If
`collapsed` lived on the cell, you would either:
- pollute undo history (Ctrl+Z toggles a collapse — wrong), or
- have to thread collapse around `pushCells` with special-casing — fragile.

Collapse is *view state*, not *document state*. It belongs next to the existing
`expanded`/`menuOpen`/`cellMode` locals already in BodyCell
(`BodyCell.tsx:37-43`).

```ts
const [collapsed, setCollapsed] = useState(false)
// when collapsed: render only the strip + a one-line summary; hide heading input,
// body, split, selBar.
```

**Trade-off acknowledged:** collapse does not survive navigation away and back
(BodyCell unmounts when the notebook view changes). That is the *correct* default
for transient view state and matches how `expanded` already behaves (also local,
also non-persistent). If product later wants persistence, the right home is a
**separate, non-undo store keyed by cell id** (e.g. a `collapsedCells: Set<id>`
slice in `uiStore`), explicitly outside the history mechanism — not the cell
model. Do not build that now.

### Summary line content

```
┌─ [body] ⋯  ▸  "Heading text" · 42 lines ───────────────┐   (collapsed)
└─────────────────────────────────────────────────────────┘
```
Show `displayTitle` + a line count (`content.split('\n').length`). The expand
chevron reuses the existing `.toggle` button styling.

**Interaction with `cellMode`:** collapsing while in `edit`/`split` should first
commit-or-discard. Simplest correct rule: **collapse is only available in `view`
mode** (disable/hide the collapse control when `isEditing`), mirroring how
`selBar` is gated to view mode (`BodyCell.tsx:71`). This avoids "collapsed an
unsaved edit" ambiguity.

---

## Feature 6 — FragmentCell hover preview

### Decision: state-driven (`useState`), NOT pure CSS `:has()`

**Answer to the open question: use `useState(hoverActive)` + a positioned
popover, not CSS-only.** Even though `:has()` is available in Chromium, CSS-only
loses on three counts here:

1. **z-index escape.** The popover must paint above sibling cells but the cell
   menu is `z-index:200` (`FragmentCell.module.css:124`). A CSS-only popover that
   is a child of `.cell` is bounded by the cell's stacking/overflow. State-driven
   lets you portal it (or at least control z-index deterministically) — see risk.
2. **Dismiss-on-scroll / dismiss-on-menu-open.** When the ⋯ menu opens, the hover
   popover should yield. Coordinating "menu open hides popover" is trivial with
   state (`menuOpen && return null`), impossible-to-awkward with pure `:hover`.
3. **Hover intent / delay.** A raw `:hover` popover flickers on pass-through. A
   small open-delay (120ms) via `setTimeout` needs JS anyway.

```ts
const [hover, setHover] = useState(false)
// onMouseEnter name → setTimeout(()=>setHover(true), 120)
// onMouseLeave      → clear timer, setHover(false)
// render popover only when hover && !menuOpen && description
```

### Decision: popover z-index sits at 150 (below the 200 menu)

**Answer to the z-index question:** give the popover `z-index: 150` — above
normal cell content, deliberately **below** the ⋯ menu (200). Combined with the
`!menuOpen` render guard, the menu always wins and they never visually fight. If
the popover must escape the cell's bounds (long descriptions clipped by
`overflow`), portal it to `document.body` and position via the canonical
`setProperty('--pop-x'/'--pop-y')` pattern (the SelectionTooltip pattern), **not**
a `style={{}}` cast.

```
z-order:
   200  ⋯ menu              (wins; popover suppressed while open)
   150  hover popover       (NEW)
     0  cell content
```

### Decomposition

The popover is its own concern; extract it so FragmentCell stays focused:
```
SkillNotebook/FragmentCell/
  FragmentCell.tsx                 (adds hover state + 2 handlers, ~12 lines)
  DescriptionPopover/
    DescriptionPopover.tsx         ~35 lines — positioned card, takes {text,x,y}
    DescriptionPopover.module.css
```

---

## Feature 7 — NotebookCanvas keyboard shortcuts

### Decision: track `focusedCellId` in NotebookCanvas local state, seeded by focus events — do NOT poll `document.activeElement`

**Answer to question 1:** keep a `focusedCellId: string | null` in
NotebookCanvas, updated by `onFocus`/`onClick` bubbling from cells. Reject
`document.activeElement` as the source of truth because:

- Cells in `view` mode have no focusable element — `activeElement` would be
  `<body>`, so Alt+↑/↓ would have no target. Explicit tracking covers view-mode
  cells.
- The global `keydown` listener (added the same way as the existing undo/redo
  listener at `NotebookCanvas.tsx:28-35`) needs a *stable, synchronous* answer for
  "which cell" — reading `activeElement` inside the handler is brittle when focus
  is mid-transition (e.g. just clicked the ⋯ menu).
- React's synthetic `onFocusCapture` on each cell wrapper gives a clean signal
  without each cell knowing about the canvas.

Wiring: `BodyCell`/`FragmentCell` already render a root `<div>` (BodyCell even has
`tabIndex={-1}` at line 91). Add `onFocusCapture={() => onFocusCell(cell.id)}` and
`onMouseDown={() => onFocusCell(cell.id)}` on the cell wrappers in
NotebookCanvas's `.map`, passing a new `onFocusCell` prop down — or simpler, wrap
each cell in NotebookCanvas:

```tsx
<div onFocusCapture={() => setFocusedCellId(cell.id)}
     onMouseDownCapture={() => setFocusedCellId(cell.id)}>
  {cell.type === 'body' ? <BodyCell …/> : <FragmentCell …/>}
</div>
```

This keeps cells ignorant of focus tracking (no prop drilling into the cell
components) and centralises it in the canvas. Add a matching `.focused` class for
a visual ring.

### Decision: Alt+Enter / Alt+↑↓ — scope by edit mode

**Answer to question 2 (focus while a textarea is focused):**

```
SHORTCUT       view-mode cell focused        edit-mode cell (textarea focused)
─────────────  ──────────────────────────    ───────────────────────────────────
Alt+↑ / Alt+↓  move cell up/down              move cell up/down  (Alt frees it from
                                              textarea caret nav — safe to keep)
Alt+Enter      primary action (e.g. insert    COMMIT the edit, then act — OR just
               cell below / toggle edit)      commit. Alt+Enter must NOT insert a
                                              newline in the textarea.
```

Rules that make this unambiguous:

1. **Gate the global handler on `e.altKey`.** Plain Enter, plain arrows, Ctrl+Z
   etc. are left entirely to the focused textarea / existing listeners. We only
   ever intercept the Alt-modified combos, so we never fight normal typing.
2. **`Alt+↑/↓` are safe even with a textarea focused** — Alt is not a text-caret
   modifier, so intercepting it does not break editing. They reorder the
   `focusedCellId` cell via the existing `moveCell` store action.
3. **`Alt+Enter` in edit mode must `preventDefault()`** so no newline is inserted,
   then dispatch the cell's primary action. Because edit state (`cellMode`,
   `draft`) lives *inside* BodyCell, the canvas can't commit it directly. Resolve
   with a small **imperative handle**: cells expose `commit()` via a ref the
   canvas keeps per focused cell, OR — cleaner — the canvas only *requests* the
   action by bumping a counter/event the focused cell subscribes to. Recommended:
   a lightweight per-cell `useImperativeHandle({ primaryAction(): void })`
   collected in a `Map<id, handle>` in the canvas. This is the one place an
   imperative escape hatch is justified, because the action target is determined
   at the canvas level but the state lives in the child.

```
keydown(Alt+…) on document
   │
   ├─ no focusedCellId → ignore
   ├─ Alt+ArrowUp  → moveCell(focusedCellId, prev)          [store]
   ├─ Alt+ArrowDown→ moveCell(focusedCellId, next)          [store]
   └─ Alt+Enter    → preventDefault();
                     cellHandles.get(focusedCellId)?.primaryAction()
```

**Risk — listener stacking.** There will now be (a) the existing undo/redo
listener and (b) this new one, both on `document`. Combine them into **one**
`keydown` effect in NotebookCanvas to avoid double-`preventDefault` and ordering
surprises. Depend on `[undo, redo, focusedCellId, cells]`.

**Risk — focus after move.** After Alt+↓ the cell remounts at a new index (key is
stable `cell.id`, so it actually does NOT remount — good). But DOM focus can be
lost if the cell wrapper re-renders. After `moveCell`, re-assert focus on the
moved cell's wrapper via a ref + `requestAnimationFrame` so repeated Alt+↓ works.

---

## Cross-cutting: contract & file change summary

### New files
```
Editor/SelectionTooltip/AgentPicker/AgentPicker.tsx + .module.css
Editor/SelectionTooltip/tooltipActions.ts
Editor/MarkdownEditor.module.css
Editor/editorExtensions.ts
Editor/markdownCommands.ts
Editor/templateCompletion.ts
Editor/editorStats.ts
Editor/EditorStatusBar/EditorStatusBar.tsx + .module.css
Editor/commentablePreviewMarks.ts            (if CommentablePreview > 150 lines)
SkillNotebook/FragmentCell/DescriptionPopover/DescriptionPopover.tsx + .module.css
```

### Store changes
```
uiStore.ts:
  + editorFullscreen: boolean
  + setEditorFullscreen: (v) => void
  (NOT added to partialize — non-persistent)

skillNotebookStore.ts:  NO CHANGES.
  (collapse + hover are deliberately kept out of the undo-tracked store)
```

### Modified component contracts
```
SelectionTooltip Props:  + selectedText, + onFind, + onSpawnAgent  (Copy is local)
CommentablePreview:      + findTerm state, + highlightAllOccurrences/clearFindMarks,
                         extend onDocMouseDown to clear find-marks,
                         pass selectedText/onFind/onSpawnAgent into tooltip
Editor/index.tsx:        + read editorFullscreen from uiStore,
                         + portal wrapper when fullscreen,
                         + Escape handler, + status bar, + onSpawnAgent impl
                           (reuse existing addTab/openTab/spawn block)
MarkdownEditor.tsx:      use buildExtensions(); replace static inline style w/ CSS module
NotebookCanvas.tsx:      + focusedCellId state, + unified keydown effect,
                         + per-cell focus wrappers + cellHandles Map
BodyCell.tsx:            + collapsed local state + summary render + useImperativeHandle
FragmentCell.tsx:        + hover state + DescriptionPopover render
```

### No IPC / no FSM / no Python changes
All seven features are renderer-only. Terminal spawning (Explain/Ask Agent) reuses
the existing `window.pathly.terminal.spawn(tabId, cwd, undefined, argv)` channel —
no new IPC. The adapter argv table is already in the prompt and matches
`Editor/index.tsx:197`.

---

## Risk register (ranked by likelihood × cost)

| # | Risk | Feature | Mitigation | Severity |
|---|------|---------|------------|----------|
| 1 | Fullscreen trapped in ancestor stacking context | 4 | Portal to `document.body` | High |
| 2 | `override` silently disables markdown completions | 3 | Use `language.data.of`, not `override` | High |
| 3 | Find-marks & comment-marks clearing each other | 2 | Separate `data-find-mark` attr + dedicated clear | High |
| 4 | Collapse in store pollutes undo/redo | 5 | Keep collapse local; never via `pushCells` | High |
| 5 | Alt+Enter inserts newline in textarea | 7 | `preventDefault` in edit mode | Medium |
| 6 | Two document keydown listeners conflict | 7 | Single combined effect | Medium |
| 7 | Hover popover clipped by cell overflow | 6 | Portal + z-index:150 under menu | Medium |
| 8 | TreeWalker live-list shift on multi-mark | 2 | Two-pass, mutate back-to-front | Medium |
| 9 | Tooltip dismissed when opening AgentPicker | 1 | `stopPropagation` on picker mousedown | Low |
| 10 | Frameless-window drag region covered | 4 | Inset top by titlebar height + Escape | Low |

---

## Open product question (needs a human answer before BUILD)

Feature 3 autocomplete has two valid product shapes and the choice changes the
implementation:

- **(A) Additive** — template vars appear *alongside* markdown word/snippet
  completions. → `markdownLanguage.data.of({ autocomplete: source })`, leave
  basicSetup alone.
- **(B) Exclusive** — when typing `{{`, show *only* template variables, nothing
  else. → `autocompletion({ override: [templateVarSource] })`, which disables all
  other sources globally (not just inside `{{`).

I recommend (A): it is non-destructive, scoped to the markdown language, and
matches how editors normally surface custom completions. (B) is only right if the
product explicitly wants a dedicated variable-only popup.
