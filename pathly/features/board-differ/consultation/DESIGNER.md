# Board Differ — Designer Consultation

_UI/UX review of `pathly/features/board-differ/APPROACH.md`, 2026-07-06 (grounded in the existing Studio components)._

## Verdict
The approach is sound and the component foundations are strong. The main UX risk is the **Impact panel competing with the diff for attention** and turning a focused review into an overwhelming two-pane analysis session. Fix that by making the Impact panel a **subordinate, pull-on-demand surface** rather than a peer pane.

## Key UX recommendations
1. **"See changes" belongs in the card footer, not a hover-only icon.** The `.cardFoot` row already holds "Details" / "summary" / timestamp — add "See changes" there as a third pill, styled like the existing `.artOpen` ("Details") button. Always render (hover-reveal fails at narrow widths). `GitDiff` icon at 11px. When no baseline can be computed (no `artifactPath`, or untracked) → disabled + tooltip "No git baseline available." Respect the footer's existing `flex-wrap`.
2. **The viewer is a modal, wider for surface (a).** Existing `DraftDiffViewer` is 800px × 80vh; surface (a) adds the Impact panel → use `min(1100px, calc(100vw - 40px))` × `88vh`. Place at z-index 9200 so it can overlay the ArtifactModal.
3. **Surface (a) inherits read-only `CodeDiffView`, not the full `DraftDiffViewer`.** Suppress the ViewToggle's Cards/List/Edit (triage affordances); expose only Code view + the Split/Unified sub-toggle. Strip `onApply`/`onDiscard`/`DraftDiffFooter`. Pass `readOnly={true}` as a discriminating prop.
4. **Default to split; switch to unified in narrow containers.** Split is best for a quick scan; below ~720px modal width a split becomes illegible → a CSS container query (`@container (max-width: 720px)`) hides the split toggle and forces unified.

## Layout proposal — Surface (a)
```
┌─────────────────────────────────────────────────────────────────────┐
│ HEADER  [GitDiff] pathly/src/foo.py  +12 -4              [X]        │
├───────────────────────────────────────────────────┬─────────────────┤
│ DIFF AREA (flex:1, min-width:0)                   │  IMPACT PANEL   │
│ [file bar: name · +12 -4 · Split | Unified]       │  240px          │
│  28  def foo():     28  def foo():                │  collapsible    │
│  29- old_val        29+ new_val   ⚠ 3 callers     │  border-left    │
├───────────────────────────────────────────────────┴─────────────────┤
│ FOOTER  [← Back] [Dismiss]        (no Apply in read-only surface a) │
└─────────────────────────────────────────────────────────────────────┘
```
`.body` is `flex row`; diff column `flex:1; min-width:0`; Impact column `width:240px; flex-shrink:0; border-left`. At ≤720px the panel shifts below the diff (`flex-direction: column` via container query). Panel is collapsible to a 36px rail (icon + aggregate call-count badge); collapsed state in `localStorage` (`pathly:impactPanelOpen`). Header = filename (mono) + `+N -N` stat pill + close X; the Split/Unified toggle lives in the `CodeDiffView` bar.

## Impact panel presentation
Two flat sections separated by a 1px border:
```
ImpactPanel (240px)
├─ [ChevronLeft collapse] "Impact"  [spinner/error]
├─ ── Changed Symbols ──
│   build_block  fn        MAX_RETRY  const   (mono 11px + icon)
└─ ── Affected Flows ──
    runner prompt assembly  [3 callers]
    └ get_provider · code_query · build_prompt
```
**The "⚠ N callers" hunk badge** lives in the diff **gutter** (line-number column of the split's right pane), right-aligned. `data-callers={n}` drives color: 1 = `var(--yellow)`, 2+ = `var(--orange)`. It's a **button** — clicking scrolls the Impact panel to the matching flow and expands its caller list (navigation shortcut, not a disclosure widget that inflates line height). Badge only on lines whose changed symbol is in `changed_symbols`; never on unchanged lines. Min touch target 24×16px.

Loading: panel body → spinner (`Loader2` 16px) + "Analyzing impact…"; header stays. **Don't defer the diff** while impact loads — diff renders immediately, impact populates async.

## States to handle
- **No code graph / backend off:** panel mounts → "absent" state (header + one row `[Info] Impact unavailable — code graph offline`). Diff renders fully; collapsed rail hidden so panel disappears at narrow widths.
- **New file (all-added):** all `+` hunks; `detect_changes` may return empty callers → panel body "No callers affected" (not error, not hidden). Standard all-green view.
- **Non-code artifact (`.md`/`.txt`/`.json`/`.yaml`):** Impact panel absent (no column, no rail); diff takes full width; default to **unified** for prose (harder to scan side-by-side) via `defaultLayout="unified"` on extension.
- **Binary / very large (`bytes > 500 000` or binary blob):** dedicated state `[FileX] name — diff not available (487 KB)`; panel absent; footer = Dismiss only. **Decide binary in the main process** (null-byte check in first 8 KB) and return `{type:'binary', size}` instead of content.
- **Identical files:** existing `DiffContent` behavior — `totalChanged === 0` → toast + `onClose()`; modal never renders.
- **Surface (b) reuse:** same modal `readOnly={false}` restores full ViewToggle + `DraftDiffFooter` (Apply/Discard); Impact panel shown too (callers matter during triage).
- **Surface (c):** title `a.py vs b.py`; a file-picker row above the diff; panel reflects the two-file diff (backend contract unchanged — still gets diff text).

## Accessibility & responsiveness
Reuse `useFocusTrap` (as in `ArtifactModal`); Escape closes; close btn `aria-label="Close diff viewer"`; collapse toggle `aria-expanded`/`aria-controls`; hunk badge `aria-label="3 callers affected — click to view"`; existing `role="tablist"`/`aria-selected` on Split/Unified is correct. Contrast: `--orange` (#f97316) on `--bg-surface0` (#1E2433) = 4.6:1 (AA); yellow badge (#FCD34D) = 9.1:1 (AAA) — no token changes. At ≤200px: panel hidden, diff → unified, filename ellipsis, footer `flex-wrap` so buttons stack.

## Open design questions
1. **"See changes" on superseded (struck-through, 0.55 opacity) cards** — keep active but tooltip "Viewing changes from a superseded artifact"?
2. **Panel at very wide widths** — resizable drag handle? Defer; start fixed 240px + collapse.
3. **`detect_changes` input contract** — path-only vs diff-argument decides whether the renderer must serialize/send hunks. Nail before building the IPC bridge.
4. **Multiple files changed in one run (surface b)** — one modal per file vs a multi-file PR view? Start one-file-at-a-time; add "N files changed" nav later.
5. **Hunk-to-caller precision** — if `detect_changes` returns line ranges for changed symbols, per-hunk badge placement is straightforward; if only symbol names, badge must be file-level (in the `CodeDiffView` bar), not per-hunk. Backend-contract question to resolve before implementing the badge interaction.
