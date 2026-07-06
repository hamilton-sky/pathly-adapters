# Board Differ — ASCII Mockups

> Informed by UI/UX Pro Max design intelligence.
>
> CLI queries run:
> - `pathly-design "impact-aware code diff viewer with a side impact panel, split and unified diff, dark mode Electron desktop app" --domain ux --stack react`
> - `pathly-design "diff viewer modal collapsible side panel inline badges dark UI" --domain style --stack react`
> - `pathly-design "dark SaaS dashboard product" --design-system --stack react --format markdown`
> - `pathly-design "modal overlay split pane inspector badge gutter dark theme" --domain color --stack react`
> - `pathly-design "code review inspector panel supervisor board dark" --domain ux --stack react`
>
> Key guidance extracted:
> - Container/Presentational split: `ImpactPanel` fetches, `ImpactPanelView` renders.
> - Error boundaries wrap the differ modal and the impact panel independently.
> - Heavy components (`CodeDiffView`, `ImpactPanel`) are lazy-loaded.
> - No inline styles anywhere — all tokens via CSS custom properties.
> - SVG icons only (Lucide) — no emoji, no raster.
> - `cursor: pointer` on every interactive element; hover transitions 100–150ms.
> - `prefers-reduced-motion` respected on all animations.
> - Focus rings visible (`--focus-ring: 2px solid var(--accent)`).
> - Dark ops/dashboard palette: deep bg (`#111827`), surface layers (`#1E2433`, `#283044`), accent sky-blue (`#38BDF8`), green (`#34D399`), orange (`#f97316`), red (`#f87171`), muted text (`#8899B0`).
> - Status colors (green/amber/red) for signal hierarchy — maps directly onto caller-count badges.

All Studio tokens below (`var(--...)`) reference `studio/src/renderer/src/styles/tokens.css`.

---

## 1. Artifact Card — "See changes" footer pill

Caption: The new "See changes" pill lands in the existing `.cardFoot` row alongside "Details", inheriting the `.artOpen` button style.

```
┌──────────────────────────────────────────────────────────────────┐
│ ● builder                                    [ARTIFACT]          │
│                                                                  │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ [FileText]  pathly_data/core/agents/builder.md               │ │
│ │             Agent role definition, updated with new          │ │
│ │             rigor-level handling for strict mode.            │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ [ℹ Details]  [GitDiff See changes]               BUILD  3m ago   │
└──────────────────────────────────────────────────────────────────┘
```

Tokens and interactions:
- `[Details]` and `[See changes]` both use `.artOpen`: `border: 1px solid var(--accent-border)`, `background: var(--accent-bg)`, `color: var(--accent)`, `font: 600 11px`, `padding: 4px 11px`, `border-radius: var(--radius-md)`.
- `[GitDiff]` icon: Lucide `GitDiff` at 11px, `flex-shrink: 0`.
- Pills sit in `.cardFoot` which is `display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end`. `[Details]` has `margin-right: auto` to pin left; `[See changes]` follows naturally.
- On hover: `border-color: var(--accent)`, `background: color-mix(in srgb, var(--accent) 18%, transparent)`.

---

## 1b. "See changes" — disabled / no baseline variant

Caption: When the artifact has no `artifactPath` or the file is untracked in git, the pill renders disabled with a tooltip.

```
┌──────────────────────────────────────────────────────────────────┐
│ ● you                                        [ARTIFACT]          │
│                                                                  │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ [FileText]  notes.tmp                                        │ │
│ │             Scratch notes — not tracked in git.              │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ [ℹ Details]  [GitDiff See changes ⊘]                    2m ago   │
│                         ↑                                        │
│               ┌─────────────────────────┐                        │
│               │ No git baseline         │  ← Tooltip on hover    │
│               │ (file is untracked)     │     var(--bg-mantle)   │
│               └─────────────────────────┘     var(--text-muted)  │
└──────────────────────────────────────────────────────────────────┘
```

Tokens and interactions:
- Disabled pill: `color: var(--text-disabled)`, `border-color: var(--border-color)`, `background: transparent`, `cursor: not-allowed`, `opacity: 0.6`.
- The `⊘` is the Lucide `Ban` icon at 10px rendered inline after the label text.
- Tooltip uses the existing `<Tooltip>` component (same as "Artifact details" tooltip on Details).
- No click handler registered — `disabled` attribute on `<button>` prevents interaction.

---

## 2. Surface (a) — Diff modal, full width, Impact panel expanded

Caption: The primary differ modal: split diff on the left, ImpactPanel (240px) on the right, hunk badge in the line-number gutter.

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║  MODAL  min(1100px, calc(100vw - 40px)) × 88vh  ·  z-index: 9200                           ║
║  bg: var(--bg-surface0)  ·  border: 1px solid rgba(255,255,255,0.08)  ·  border-radius: 12px ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║  HEADER  padding: 13px 18px 13px 24px  ·  border-bottom: 1px solid rgba(255,255,255,0.07)  ║
║  [GitDiff]  pathly_orchestrator/adapters.py           +12  -4         [X]                   ║
║             var(--accent) mono 13px                 +green -red     close 24×24             ║
╠═══════════════════════════════════════════════════════════════╦══════════════════════════════╣
║  DIFF AREA  flex:1  min-width:0  overflow:hidden              ║  IMPACT PANEL  w:240px       ║
║                                                               ║  border-left: var(--border)  ║
║  ┌── FILE BAR ─────────────────────────────────────────────┐  ║                              ║
║  │ adapters.py  +12 -4              [Split] [Unified]      │  ║  [ChevronLeft]  Impact       ║
║  └─────────────────────────────────────────────────────────┘  ║  ─ Changed Symbols ─────────  ║
║                                                               ║  [fn]  _dash_safe_prompt     ║
║  SPLIT DIFF  bg: var(--bg-terminal)  font: mono 11.5px        ║  [fn]  resolve_command       ║
║  ┌──────────────────────┬────────────────────────────────┐    ║  [C]   RATE_LIMIT_RE         ║
║  │ 41  def _dash_safe_  │ 41  def _dash_safe_            │    ║                              ║
║  │ 42- │   if prompt.st │ 42+ │   if not prompt:         │    ║  ─ Affected Flows ──────────  ║
║  │ 43- │     return pro │ 43+ │     return ''            │    ║  runner prompt assembly       ║
║  │ 44  │   return prom… │ 44  │   return prom…           │    ║  ┌ get_provider        [>]   ║
║  │ 45  │                │ 45  │                ⚠ 3       │    ║  ├ code_query           [>]  ║
║  │     │                │     │                callers   │    ║  └ build_prompt         [>]  ║
║  │ 46  │   ...          │ 46  │   ...                    │    ║                              ║
║  └──────────────────────┴────────────────────────────────┘    ║  cli headless assembly       ║
║                                                               ║  └ _dash_safe_prompt   [>]   ║
║                                                               ║                              ║
╠═══════════════════════════════════════════════════════════════╩══════════════════════════════╣
║  FOOTER  padding: 12px 18px  ·  border-top: 1px solid rgba(255,255,255,0.07)               ║
║  [Dismiss]                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- Modal header `[GitDiff]`: Lucide `GitDiff` at 16px, `color: var(--runtime)`.
- Filename: `font: 600 13px var(--font-family-mono)`, `color: var(--text-primary)`.
- `+12` stat: `color: var(--green)`; `-4` stat: `color: var(--red)`.
- `[Split] [Unified]` segmented toggle: existing `CodeDiffView` `.seg` pattern, active tab `background: color-mix(in srgb, var(--accent) 16%, transparent)`, `color: var(--accent)`.
- Diff scroll area: `background: var(--bg-terminal)` (`#0d1117`), `font-size: 11.5px`, `line-height: 1.7`.
- Added lines (`42+`, `43+`): left gutter `background: rgba(52, 211, 153, 0.10)`, line `background: rgba(52, 211, 153, 0.06)`.
- Removed lines (`42-`, `43-`): left gutter `background: rgba(248, 113, 113, 0.10)`, line `background: rgba(248, 113, 113, 0.06)`.
- `⚠ 3 callers` badge: positioned in the right-pane line-number column of line 45. `data-callers="3"` drives CSS: 2+ callers → `color: var(--orange)` (`#f97316`), contrast 4.6:1 on `var(--bg-terminal)` (passes WCAG AA). Badge is a `<button>` 24×16px min touch target, `padding: 0 4px`, `border-radius: var(--radius-xs)`, `background: var(--orange-bg)`, `border: 1px solid var(--orange-border)`. Click scrolls ImpactPanel to the "runner prompt assembly" flow and expands it.
- ImpactPanel section headers: `font: 600 9px var(--font-family-mono)`, `letter-spacing: 0.06em`, `text-transform: uppercase`, `color: var(--text-muted)`.
- Symbol rows: `font: 11px var(--font-family-mono)`, `color: var(--text-secondary)`. `[fn]` icon = Lucide `Function` 10px, `color: var(--runtime)`; `[C]` = Lucide `Box` 10px for constants.
- Flow rows with `[>]` expander: Lucide `ChevronRight` 10px, toggles the caller list open/closed. `aria-expanded` set accordingly.
- `[Dismiss]` footer button: `color: var(--text-muted)`, `border: var(--border)`, `border-radius: var(--radius-md)`, `background: transparent`. No Apply/Discard in read-only surface (a).
- `[ChevronLeft]` collapse toggle: Lucide `ChevronLeft` 14px, `color: var(--text-muted)`. Click collapses panel to 36px rail (see mockup 3).

---

## 3. Impact panel — collapsed to 36px rail

Caption: The ImpactPanel collapses to a narrow vertical rail; the diff expands to fill the freed width. State persisted to `localStorage` key `pathly:impactPanelOpen`.

```
╔══════════════════════════════════════════════════════════════════════╗
║  HEADER  [GitDiff]  adapters.py   +12 -4                      [X]  ║
╠═══════════════════════════════════════════════════════════════╦══════╣
║  DIFF AREA  (now wider, flex:1)                               ║  36px║
║                                                               ║      ║
║  FILE BAR  adapters.py  +12 -4        [Split] [Unified]       ║  [>] ║
║                                                               ║      ║
║  ┌──────────────────────────┬───────────────────────────────┐ ║  (2) ║
║  │ 41  def _dash_safe_      │ 41  def _dash_safe_           │ ║      ║
║  │ 42- │   if prompt.st     │ 42+ │   if not prompt:        │ ║      ║
║  │ 43- │     return pro     │ 43+ │     return ''           │ ║  [I] ║
║  │ 44  │   return prom…     │ 44  │   return prom…  ⚠ 3    │ ║      ║
║  │ 45  │                    │ 45  │                         │ ║      ║
║  └──────────────────────────┴───────────────────────────────┘ ║      ║
║                                                               ║      ║
╠═══════════════════════════════════════════════════════════════╩══════╣
║  FOOTER  [Dismiss]                                                   ║
╚══════════════════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- Rail: `width: 36px`, `flex-shrink: 0`, `border-left: var(--border)`, `display: flex`, `flex-direction: column`, `align-items: center`, `padding-top: 10px`, `gap: 8px`.
- `[>]` expand toggle: Lucide `ChevronRight` 14px at top of rail, `color: var(--text-muted)`. `aria-expanded="false"`, `aria-label="Expand impact panel"`. Click restores 240px width.
- `(2)` aggregate badge: the total count of affected flows shown as a compact mono label `2` in `color: var(--orange)`, `font: 700 10px var(--font-family-mono)`. Gives at-a-glance signal without expanding.
- `[I]` icon: Lucide `Workflow` 14px, `color: var(--text-muted)`, serves as a visual anchor for the collapsed rail meaning.
- The `⚠ 3 callers` hunk badge remains active and clickable in the collapsed state; clicking it auto-expands the panel and scrolls to the matching flow.
- `prefers-reduced-motion`: collapse/expand width transition is `width 120ms var(--ease-out)` normally, `0ms` when reduced motion is preferred.

---

## 4. Narrow width (≤720px) — Impact panel stacked below, unified diff

Caption: Container query triggers at modal width ≤720px: Impact panel moves below the diff, diff switches to unified layout, Split toggle hidden.

```
╔══════════════════════════════════════════════════════════╗
║  HEADER                                                  ║
║  [GitDiff]  adapters.py   +12 -4                   [X]  ║
╠══════════════════════════════════════════════════════════╣
║  DIFF AREA  (full width)                                 ║
║                                                          ║
║  FILE BAR  adapters.py  +12 -4           [Unified]       ║
║            (Split toggle hidden via container query)     ║
║                                                          ║
║  ┌────────────────────────────────────────────────────┐  ║
║  │ 42-  if prompt.startswith('---'):                  │  ║
║  │ 42+  if not prompt:                                │  ║
║  │ 43-      return prompt.lstrip('-').strip()         │  ║
║  │ 43+      return ''                   ⚠ 3 callers  │  ║
║  │ 44   return prompt.strip()                         │  ║
║  └────────────────────────────────────────────────────┘  ║
╠══════════════════════════════════════════════════════════╣
║  IMPACT PANEL  (stacked below, full width, collapsible)  ║
║  ─────────────────────────────────  [ChevronUp] Impact   ║
║  Changed: _dash_safe_prompt  resolve_command             ║
║  Flows:   runner prompt assembly (3)  ·  cli headless    ║
╠══════════════════════════════════════════════════════════╣
║  FOOTER  [Dismiss]                                       ║
╚══════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- Container query on the modal element: `@container (max-width: 720px)` applied to `.body` wrapper which has `container-type: inline-size`.
- `.body` flips from `flex-direction: row` to `flex-direction: column`.
- ImpactPanel shifts from `width: 240px; flex-shrink: 0` to `width: 100%; height: auto; border-left: none; border-top: var(--border)`.
- `CodeDiffView` hides the `[Split]` button and forces `layout = 'unified'` when the container is ≤720px — implemented as a CSS `display: none` on the Split button plus a JS check of `containerRef.offsetWidth` in a `ResizeObserver`.
- Unified diff: removed lines prefixed `-` with `background: rgba(248, 113, 113, 0.06)`, added lines prefixed `+` with `background: rgba(52, 211, 153, 0.06)`.
- `⚠ 3 callers` badge remains in the right margin of the unified view at the changed line.
- ImpactPanel in stacked mode: collapsed via `[ChevronUp]` / expanded via `[ChevronDown]`, toggling `max-height: 0` → `max-height: 200px` with `overflow: hidden`. This is a height-collapse (not a width-collapse) for the stacked orientation.
- At ≤200px width: ellipsis on filename, footer buttons `flex-wrap: wrap`, diff degrades to scroll rather than reflowing.

---

## 5a. State — No code graph (Impact panel absent)

Caption: When `codebase-memory-mcp` is offline or the `op:"impact"` call returns an error, the Impact panel column is removed entirely.

```
╔══════════════════════════════════════════════════════════════════════╗
║  HEADER  [GitDiff]  adapters.py   +12 -4                      [X]  ║
╠══════════════════════════════════════════════════════════════════════╣
║  DIFF AREA  (full modal width, no right column)                     ║
║                                                                     ║
║  FILE BAR  adapters.py  +12 -4                    [Split] [Unified] ║
║                                                                     ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │ 42-  if prompt.startswith('---'):   │ 42+  if not prompt:   │    ║
║  │ 43-      return prompt.lstrip(…)   │ 43+      return ''    │    ║
║  │ 44   return prompt.strip()         │ 44   return prompt…   │    ║
║  └─────────────────────────────────────────────────────────────┘    ║
║                                                                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  FOOTER  [Dismiss]                                                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

No hunk badges appear (nothing to badge against). No rail. Diff takes full width.

Tokens and interactions:
- The `ImpactPanel` component is not mounted; no column or rail placeholder renders. The `.body` flex row contains only the diff column.
- The diff does not mention the absent panel — no inline "impact unavailable" notice in the diff gutter. This avoids noise for the common non-code case.
- If the backend returns an error mid-session (panel was loading then failed), the panel body shows: `[Info icon 14px color:var(--text-muted)]  Impact unavailable — code graph offline` at 11px `var(--text-muted)`, then the body collapses the panel to `width: 0` after 300ms, yielding width to the diff.

---

## 5b. State — New file (all-added diff)

Caption: The artifact is a newly created file — no original content, every line is an addition.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║  HEADER  [GitDiff]  blueprints/comms/new_route.py   +48 -0             [X]     ║
╠═════════════════════════════════════════════════════════╦══════════════════════╣
║  DIFF AREA                                             ║  IMPACT PANEL        ║
║                                                        ║                      ║
║  FILE BAR  new_route.py  +48 -0         [Split][Unif] ║  [ChevronLeft] Impact ║
║                                                        ║  ─ Changed Symbols ─  ║
║  ┌─────────────────────────────────────────────────┐  ║  [fn]  get_new_route  ║
║  │  (empty)            │  1+  from flask import bp  │  ║  [fn]  _validate_id   ║
║  │                     │  2+  from . import db      │  ║                       ║
║  │                     │  3+  @bp.route('/new')     │  ║  ─ Affected Flows ──  ║
║  │                     │  4+  def get_new_route():  │  ║  No callers affected  ║
║  │  (empty)            │  5+      ...               │  ║  (new symbol)         ║
║  └─────────────────────────────────────────────────┘  ║                       ║
║                                                        ║                       ║
╠═════════════════════════════════════════════════════════╩══════════════════════╣
║  FOOTER  [Dismiss]                                                             ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- Left pane (original) is empty — renders the left column with a `var(--bg-terminal)` background and no line numbers. A subtle `(new file)` label in `var(--text-muted)` 10px centers in the empty left pane.
- All right-pane lines have the added-line styling: `background: rgba(52, 211, 153, 0.06)`, gutter `background: rgba(52, 211, 153, 0.10)`.
- ImpactPanel: `detect_changes` returns the new symbols but no callers (new code has no existing callers yet). "No callers affected (new symbol)" is rendered in `var(--text-muted)` 11px in the Affected Flows section — not an error state, just an informational row.
- No `⚠ N callers` hunk badges appear (0 callers = no badge rendered).

---

## 5c. State — Non-code artifact (text diff, no Impact panel)

Caption: A markdown plan artifact — shows text diff in unified layout with no Impact panel column.

```
╔══════════════════════════════════════════════════════════════════════════╗
║  HEADER  [GitDiff]  IMPLEMENTATION_PLAN.md   +8 -3                [X]  ║
╠══════════════════════════════════════════════════════════════════════════╣
║  DIFF AREA  (full width, no Impact column)                              ║
║                                                                         ║
║  FILE BAR  IMPLEMENTATION_PLAN.md  +8 -3             [Unified]          ║
║            (Split toggle absent for prose — defaultLayout="unified")    ║
║                                                                         ║
║  ┌───────────────────────────────────────────────────────────────────┐  ║
║  │   ## Phase 2 — Storage                                            │  ║
║  │ -  Nest goals under their feature directory.                      │  ║
║  │ +  Nest goals under their feature directory (board-scoped).       │  ║
║  │    See pathly/features/storage-restructure/SPEC.md                │  ║
║  │                                                                   │  ║
║  │ -  Artifact hydration uses pathly/plans/ prefix.                  │  ║
║  │ +  Artifact hydration uses pathly/features/ prefix.               │  ║
║  └───────────────────────────────────────────────────────────────────┘  ║
║                                                                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║  FOOTER  [Dismiss]                                                      ║
╚══════════════════════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- Extension check at the IPC layer before opening: `.md`, `.txt`, `.json`, `.yaml` → `isCodeFile = false`.
- `isCodeFile = false` → `ImpactPanel` not mounted, `defaultLayout = 'unified'`, `[Split]` button not rendered.
- Diff background: `var(--bg-terminal)` unchanged (consistent dark base regardless of file type).
- Removed lines: `color: var(--red)`, `background: rgba(248, 113, 113, 0.06)`.
- Added lines: `color: var(--green)`, `background: rgba(52, 211, 153, 0.06)`.

---

## 5d. State — Binary or large file

Caption: Binary file or file >500 KB — diff is not available; modal shows a dedicated state component.

```
╔═══════════════════════════════════════════════════════════════════════╗
║  HEADER  [GitDiff]  model_weights.bin   —                      [X]   ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║                                                                       ║
║                        [FileX icon 24px]                              ║
║                        color: var(--text-muted)                       ║
║                                                                       ║
║                  model_weights.bin                                    ║
║                  font: 600 13px mono  color: var(--text-secondary)    ║
║                                                                       ║
║                  Diff not available (binary file, 487 KB)             ║
║                  font: 12px base  color: var(--text-muted)            ║
║                                                                       ║
║                                                                       ║
╠═══════════════════════════════════════════════════════════════════════╣
║  FOOTER  [Dismiss]                                                    ║
╚═══════════════════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- This state component (`DiffUnavailableView`) is a single presentational component in its own folder per Studio rules.
- Icon: Lucide `FileX` at 24px, `color: var(--text-muted)`.
- File size is human-formatted (487 KB, not 498,688 bytes) — computed in the main-process IPC handler and returned alongside `{ type: 'binary', size, sizeLabel }`.
- The modal is intentionally smaller in practice (auto-fit content height), but the header and footer chrome remain for visual consistency.
- No Impact panel, no diff scroll area, no file bar. The `.body` uses `align-items: center; justify-content: center` for the centered empty state.
- `[Dismiss]` is the only footer action.

---

## 6a. Surface (b) — Accept/reject triage (draft vs original)

Caption: Agent staged a `.draft` file — full DraftDiffViewer with ViewToggle restored, triage footer active.

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║  HEADER                                                                                     ║
║  [GitDiff]  Reviewing draft — builder.md              [Cards][List][Code][Edit]    [X]      ║
╠═════════════════════════════════════════════════════════════════╦════════════════════════════╣
║  DIFF AREA (Cards view shown)                                   ║  IMPACT PANEL (240px)      ║
║                                                                 ║                            ║
║  ┌── HUNK CARD — "Rigor levels"  [changed]  ────────────────┐  ║  [<]  Impact               ║
║  │  ORIGINAL                      DRAFT                     │  ║  ─ Changed Symbols ───────  ║
║  │  nano (1 conv, no review)  →  nano (1 conv, no review    │  ║  [fn]  rigor_for_stage     ║
║  │                                fast path)                │  ║                            ║
║  │                      [Reject] [Accept]                   │  ║  ─ Affected Flows ───────  ║
║  └───────────────────────────────────────────────────────────┘  ║  stage dispatch (2)        ║
║                                                                 ║  ├ build_block      [>]    ║
║  ┌── HUNK CARD — "Strict mode"  [added]  ───────────────────┐  ║  └ stage_for_rigor [>]    ║
║  │  (not in original)                                        │  ║                            ║
║  │  DRAFT: strict (standard + audit) — DESIGN_REVIEW.md     │  ║                            ║
║  │  required.                                                │  ║                            ║
║  │                               [Reject] [Accept ✓]        │  ║                            ║
║  └───────────────────────────────────────────────────────────┘  ║                            ║
║                                                                 ║                            ║
╠═════════════════════════════════════════════════════════════════╩════════════════════════════╣
║  FOOTER  [Discard draft]   1 unreviewed  ·  2/3 accepted              [Close]  [Apply →]    ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- Surface (b) passes `readOnly={false}` — the full `ViewToggle` is present (Cards, List, Code, Edit icons).
- Hunk cards: accepted hunk has `[Accept ✓]` in `color: var(--green)`, `border-color: color-mix(in srgb, var(--green) 35%, transparent)`. Unreviewed hunk has `[Accept]` and `[Reject]` as standard bordered buttons.
- `DraftDiffFooter` shows: unreviewed count in `color: var(--yellow)`, accepted/total in `color: var(--text-secondary)`.
- `[Apply →]`: `background: var(--accent)`, `color: #fff`, `font-weight: 600`. Disabled state when `unreviewedCount > 0` (supervisor must review all before applying).
- Impact panel is active here too — knowing which callers the accepted change touches informs the accept/reject decision.
- No source pair change from surface (a) — same `originalPath`/`draftPath` shape, just `readOnly` prop differs.

---

## 6b. Surface (c) — Two-artifact compare (picker row)

Caption: The user picks any two board artifacts to diff against each other — a file-picker row appears below the header.

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║  HEADER                                                                                     ║
║  [GitDiff]  Comparing artifacts                                   [Cards][List][Code]  [X]  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║  PICKER ROW  padding: 10px 18px  border-bottom: var(--border)                              ║
║                                                                                             ║
║  Base  ▾ [builder.md  (3h ago, builder)]         vs  ▾ [builder.md  (1h ago, builder)]     ║
║         └── dropdown of board artifact messages         └── dropdown of board artifact msgs ║
╠═════════════════════════════════════════════════════════════════╦════════════════════════════╣
║  DIFF AREA                                                      ║  IMPACT PANEL              ║
║                                                                 ║  (reflects diff between    ║
║  FILE BAR  builder.md  +5 -2                [Split] [Unified]  ║   the two chosen artifacts)║
║                                                                 ║  ─ Changed Symbols ──────  ║
║  ┌──────────────────────────────────────────────────────────┐  ║  [fn]  rigor_for_stage     ║
║  │ (split diff of the two selected artifact versions)        │  ║                            ║
║  └──────────────────────────────────────────────────────────┘  ║  ─ Affected Flows ───────  ║
║                                                                 ║  stage dispatch (2)        ║
╠═════════════════════════════════════════════════════════════════╩════════════════════════════╣
║  FOOTER  [Dismiss]                                                                          ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝
```

Tokens and interactions:
- Picker row: two `<select>`-style dropdown buttons, each showing the artifact name, timestamp, and author. Styled as `border: var(--border)`, `border-radius: var(--radius-md)`, `background: var(--bg-mantle)`, `color: var(--text-secondary)`, `font: 12px var(--font-family-base)`, `padding: 5px 10px`. `[▾]` is a `ChevronDown` icon.
- Swapping either picker re-runs `useDraftDiff` with the new path pair and re-fetches impact for the new diff.
- Impact panel reflects the diff between the two chosen files, not against git HEAD. The backend `op:"impact"` receives the serialized diff text — this is the surface where the diff-argument vs path-argument open question (from APPROACH.md) is most consequential.
- Surface (c) is read-only: no `[Apply]` button. `[Dismiss]` only.
- The "Edit" view-mode tab is absent (nothing to apply edits to when comparing two arbitrary artifacts).
- Title "Comparing artifacts" in place of "Reviewing draft — filename.md" to signal different provenance.

---

## Token reference for implementors

| Element | Token |
|---|---|
| Modal background | `var(--bg-surface0)` |
| Modal border | `1px solid rgba(255,255,255,0.08)` |
| Diff scroll background | `var(--bg-terminal)` (`#0d1117`) |
| Impact panel background | `var(--bg-surface0)` (same as modal — no visual separation needed beyond border) |
| Added line row | `background: rgba(52, 211, 153, 0.06)` |
| Added line gutter | `background: rgba(52, 211, 153, 0.10)` |
| Removed line row | `background: rgba(248, 113, 113, 0.06)` |
| Removed line gutter | `background: rgba(248, 113, 113, 0.10)` |
| Caller badge (1 caller) | `color: var(--yellow)`, `background: rgba(252,211,77,0.12)` |
| Caller badge (2+ callers) | `color: var(--orange)`, `background: var(--orange-bg)` |
| Impact section header text | `var(--text-muted)`, 9px mono, uppercase, 0.06em spacing |
| Symbol row icon (fn) | `var(--runtime)` (`#2DD4BF`) |
| Stat `+N` | `var(--green)` |
| Stat `-N` | `var(--red)` |
| Accent buttons (Accept, Apply) | `var(--accent)` / `var(--accent-bg)` / `var(--accent-border)` |
| Destructive buttons (Discard) | `var(--red)` / `var(--red-bg)` / `var(--red-border)` |
| Footer dismiss | `var(--text-muted)`, `border: var(--border)` |
| Focus ring | `2px solid var(--accent)` (all interactive elements) |
| Modal z-index | `9200` (above `ArtifactModal` at 9100) |
