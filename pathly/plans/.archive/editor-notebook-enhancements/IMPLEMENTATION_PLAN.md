# Implementation Plan — Editor & Notebook Enhancements

## Architecture decisions (from architect consultation)

| Decision | Choice | Why |
|---|---|---|
| AgentPicker location | `SelectionTooltip/AgentPicker/AgentPicker.tsx` | Only call site is SelectionTooltip; YAGNI to share |
| Tooltip logic | Extract `tooltipActions.ts` for prompt/argv building | Keeps SelectionTooltip < 150 lines |
| Tooltip morph | State `mode: 'actions' \| 'adapters'` in SelectionTooltip | Atomic swap, no sub-row |
| Find utility | `highlightAllOccurrences` exported from CommentablePreview.tsx | Separate from `injectMarkForText` (comments depend on it) |
| Find pass order | Back-to-front on collected text nodes | Avoids TreeWalker live-list shift bug |
| Find clear | Reuse existing `mousedown` listener, add `removeAllFindMarks` | One listener, not two |
| CM autocomplete | `markdownLanguage.data.of({ autocomplete: fn })` | Additive, doesn't kill markdown completions |
| CM shortcuts | `Prec.high(keymap.of([...]))` | Overrides basicSetup defaults safely |
| Fullscreen state | `uiStore` (`editorFullscreen: boolean`) | Survives file-switch effect; other panels may react |
| Fullscreen portal | `position:fixed;inset:0` — stacking context check needed | Portal to `document.body` if ancestor traps stacking |
| Cell collapse state | Local `useState` in BodyCell | Must NOT enter undo history (skillNotebookStore) |
| Fragment hover | State-driven, `position: fixed`, `pointer-events: none` | z-index escape + hover-intent delay |
| Fragment hover z | `z-index: 150` + `!menuOpen` guard | Below cell menus (200), no conflict |
| Canvas focus track | `focusedCellId` local state via `onFocusCapture` | view-mode cells have no focusable element |
| Alt+Enter in edit mode | Does nothing (no `useImperativeHandle`) | Avoids imperative wiring; edit-mode textarea handles Enter |

## Design decisions (from designer consultation)

| Feature | Design choice |
|---|---|
| Tooltip layout | icon-only for Copy/Find/Explain; icon+label for Comment and Ask agent |
| Adapter picker | Morph: button row replaced by `← Claude · Codex · Antigravity` |
| Status bar position | Between toolbar and CodeMirror (not VS Code bottom bar) |
| Status bar height | 22px, 10px mono font, `var(--text-muted)` |
| Fullscreen animation | scale 0.985→1 + opacity, 180ms, `prefers-reduced-motion` respected |
| Fullscreen exit | Floating badge top-right, opacity 0.35 at rest |
| Cell collapse toggle | ChevronDown/Up, leftmost in strip, opacity 0.72 on collapsed |
| Fragment hover | 300ms delay, below chip, `fixed`, pointer-events:none |
| Keyboard HUD | Transient, sticky bottom of canvas, fades after 2400ms |

---

## File changes by conversation

### Conv 1 — Selection Tooltip (A1 Copy, A3 Explain, A4 Ask Agent, A2 Find)

**Files created:**
- `components/Editor/SelectionTooltip/AgentPicker/AgentPicker.tsx`
- `components/Editor/SelectionTooltip/AgentPicker/AgentPicker.module.css`
- `components/Editor/commentUtils.ts` — add `buildAskAgentArgv(adapter, prompt): string[]`

**Files modified:**
- `components/Editor/SelectionTooltip/SelectionTooltip.tsx` — new interface, morph state, 5 buttons
- `components/Editor/SelectionTooltip/SelectionTooltip.module.css` — new classes: `.btnIcon`, `.btnAskAgent`, `.divider`, `.adapterChip`, `.backBtn`, tooltip enter animation
- `components/Editor/CommentablePreview/CommentablePreview.tsx` — add `highlightAllOccurrences`, `removeAllFindMarks`, new handlers, new props `onSelectionExplain` + `onSelectionAskAgent`
- `components/Editor/CommentablePreview/CommentablePreview.module.css` — add `.findMark`
- `components/Editor/index.tsx` — add `handleSelectionExplain`, `handleSelectionAskAgent`, wire to CommentablePreview

**Contracts:**
```tsx
// SelectionTooltip new Props
interface Props {
  x: number; y: number
  onComment: () => void
  onCopy: () => void
  onFind: () => void
  onExplain: () => void
  onAskAgent: (adapter: string) => void
}

// CommentablePreview new Props additions
onSelectionExplain: (text: string) => void
onSelectionAskAgent: (text: string, adapter: string) => void

// AgentPicker Props
interface Props { onPick: (adapter: string) => void }

// tooltipActions.ts additions
export function buildAskAgentArgv(adapter: string, prompt: string): string[]
```

---

### Conv 2 — MarkdownEditor (B1 Shortcuts, B2 Autocomplete, B3 Status bar, B4 Fullscreen)

**Files modified:**
- `components/Editor/MarkdownEditor.tsx` — add `wrapWith()`, `templateVarCompletion()`, register via `markdownLanguage.data.of(...)` and `Prec.high(keymap.of(...))`
- `components/Editor/index.tsx` — add `fullscreen` state read from `uiStore`, add stats bar JSX, add fullscreen button, add Escape handler, add fullscreen exit button JSX
- `components/Editor/index.module.css` — add `.statusBar`, `.statusItem`, `.statusDot`, `.panelFullscreen`, `.fullscreenExitBtn` + animations
- `store/uiStore.ts` — add `editorFullscreen: boolean` + `toggleEditorFullscreen: () => void`

**Note:** `basicSetup` already includes `search` (Ctrl+F) and `foldGutter` — verify they work, do not add duplicates.

**MarkdownEditor inline style fix:** replace `style={{ height: '100%', overflow: 'auto' }}` on the return div with a CSS class.

---

### Conv 3 — Notebook (C1 Cell Collapse, C2 Fragment Hover, C3 Keyboard Shortcuts + HUD)

**Files modified:**
- `components/SkillNotebook/BodyCell/BodyCell.tsx` — add `collapsed` local state, add ChevronUp/Down toggle as leftmost strip item, conditional render of heading + body
- `components/SkillNotebook/BodyCell/BodyCell.module.css` — add `.cellCollapsed`, `.cellBodyCollapsed`, `.collapsedSummary`, `.cellBodyExpanding` animation
- `components/SkillNotebook/FragmentCell/FragmentCell.tsx` — add `hoverActive` state with 300ms delay, `popoverRef` for fixed positioning, `!menuOpen` guard
- `components/SkillNotebook/FragmentCell/FragmentCell.module.css` — add `.fragmentPopover`, `.fragmentPopoverCategory`, `.fragmentPopoverDesc`
- `components/SkillNotebook/NotebookCanvas/NotebookCanvas.tsx` — add `focusedCellId` state, extend keydown handler with Alt+Enter/↑/↓, add `onFocusCapture` wrappers around cells, add `ShortcutHud` component trigger
- `components/SkillNotebook/NotebookCanvas/NotebookCanvas.module.css` — add `.shortcutHud`, `.shortcutHint`, `.kbd` classes

**Files created:**
- `components/SkillNotebook/ShortcutHud/ShortcutHud.tsx` — transient HUD component with 2400ms auto-hide
- `components/SkillNotebook/ShortcutHud/ShortcutHud.module.css`

---

## PROGRESS tracking

| Conv | Feature | Status |
|---|---|---|
| Conv 1 | A1 Copy + A3 Explain + A4 Ask Agent + A2 Find | TODO |
| Conv 2 | B1 Shortcuts + B2 Autocomplete + B3 Status bar + B4 Fullscreen | TODO |
| Conv 3 | C1 Cell Collapse + C2 Fragment Hover + C3 Keyboard + HUD | TODO |

---

## Risk log

| Risk | Mitigation |
|---|---|
| CM autocomplete `override` kills markdown completions | Use `markdownLanguage.data.of(...)` additive pattern (architect decision) |
| Fullscreen trapped by ancestor stacking context | Use `uiStore.editorFullscreen`, test in Electron; portal if needed |
| `highlightAllOccurrences` mutates DOM mid-TreeWalker | Collect nodes first, then mutate back-to-front |
| Find marks cleared by comment mark injection | Separate `data-find-mark` vs `data-comment-mark` attributes |
| Fragment popover clips in overflow:hidden | `position: fixed`, coordinates from `getBoundingClientRect()` |
| Alt+Enter in edit mode conflicts with textarea | Gate on `focusedCellId` cell mode !== 'edit' check |
| `agy` adapter not in adapters.yaml headless config | Use `['agy', prompt]` directly (terminal.ts allows `agy` in ALLOWED_SHELLS) |
