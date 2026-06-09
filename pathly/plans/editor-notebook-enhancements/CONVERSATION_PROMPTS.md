# Conversation Prompts — Editor & Notebook Enhancements

> Builder runs these prompts in sequence. Each conversation is a self-contained build unit.
> Architecture decisions and design specs are in IMPLEMENTATION_PLAN.md.
> Run typecheck after each conversation: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Conv 1 — Selection Tooltip: Copy, Explain, Ask Agent, Find

**Files to modify:**
- `studio/src/renderer/src/components/Editor/SelectionTooltip/SelectionTooltip.tsx`
- `studio/src/renderer/src/components/Editor/SelectionTooltip/SelectionTooltip.module.css`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.tsx`
- `studio/src/renderer/src/components/Editor/CommentablePreview/CommentablePreview.module.css`
- `studio/src/renderer/src/components/Editor/commentUtils.ts`
- `studio/src/renderer/src/components/Editor/index.tsx`

**Files to create:**
- `studio/src/renderer/src/components/Editor/SelectionTooltip/AgentPicker/AgentPicker.tsx`
- `studio/src/renderer/src/components/Editor/SelectionTooltip/AgentPicker/AgentPicker.module.css`

### Prompt:

You are implementing new actions on the selection tooltip in the Pathly Studio markdown editor.

**Context:** The Editor's `CommentablePreview` component shows a `SelectionTooltip` when the user selects text in preview mode. Currently the tooltip has one button: "Comment". You are adding 4 more actions.

**Rule set (non-negotiable):**
- No inline `style={{...}}` props. All styling in `.module.css`. Exception: CSS custom properties via `ref.current.style.setProperty(...)` in a `useEffect`.
- Every component file ≤ 150 lines. Extract sub-components if needed.
- Every `<button>` must have `type="button"`.
- Lucide icons already installed. Import from `lucide-react`.

**New SelectionTooltip behavior:**

The tooltip has two modes controlled by local `mode` state (`'actions' | 'adapters'`):

**`actions` mode** — the default row:
```
[ Copy ]  |  [ Comment ]  [ Find ]  [ Explain ]  |  [ Ask agent ▾ ]
 icon-only     icon+label  icon-only  icon-only       icon+label
```
Icons: `Copy`, `MessageSquarePlus`, `Search`, `Lightbulb`, `Terminal` + `ChevronDown`

**`adapters` mode** — when "Ask agent" is clicked:
```
[ ← ]  [ Claude ]  [ Codex ]  [ Antigravity ]
```
Back button returns to `actions` mode. Adapter buttons call `onAskAgent(adapter)` and close.

Extract the adapter row into `SelectionTooltip/AgentPicker/AgentPicker.tsx`.

**New SelectionTooltip Props:**
```tsx
interface Props {
  x: number; y: number
  onComment: () => void
  onCopy: () => void
  onFind: () => void
  onExplain: () => void
  onAskAgent: (adapter: string) => void
}
```

**CSS additions to SelectionTooltip.module.css:**
- Add `.btnIcon` (28×28, icon-only, hover: bg-surface0)
- Add `.btnAskAgent` (accent color, hover: accent-bg)
- Add `.divider` (1px, 16px tall, rgba(255,255,255,0.10))
- Add tooltip enter animation (opacity + translateY -4px → final, 120ms ease-out)
- Rename existing `.btn` to stay but add the new classes

**AgentPicker.tsx + AgentPicker.module.css:**
Three adapters: `['claude', 'codex', 'agy']` with labels `['Claude', 'Codex', 'Antigravity']`.
Back button (ChevronLeft icon, 26px, icon-only) calls `onBack`.
Adapter chips: border `var(--accent-border)`, hover: bg `var(--accent-bg)`, color `var(--accent)`.
```tsx
interface Props { onPick: (adapter: string) => void; onBack: () => void }
```

**CommentablePreview changes:**

Add to Props:
```tsx
onSelectionExplain: (text: string) => void
onSelectionAskAgent: (text: string, adapter: string) => void
```

Add local handlers: `handleCopy`, `handleFind`, `handleExplain`, `handleAskAgent`.

Add exported utility functions at module top level:
```tsx
export function removeAllFindMarks(container: HTMLElement): void
function highlightAllOccurrences(container: HTMLElement, searchTerm: string, className: string): void
```
`highlightAllOccurrences`: collect ALL matching text nodes first (read-only pass), then mutate back-to-front by reversing the array before wrapping. Each match creates a `<mark>` with `data-find-mark="true"` and the given className. Handles multiple occurrences per text node using a fragment builder.
`removeAllFindMarks`: `querySelectorAll('[data-find-mark]')` → replace with text node.
Clear find marks in the existing `onDocMouseDown` handler (alongside tooltip clear).

Add to CommentablePreview.module.css:
```css
.findMark {
  background: color-mix(in srgb, var(--yellow) 35%, transparent);
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
  border-bottom: 1px solid color-mix(in srgb, var(--yellow) 70%, transparent);
}
```

**Editor index.tsx changes:**

Add to `commentUtils.ts`:
```ts
export function buildAskAgentArgv(adapter: string, prompt: string): string[] {
  if (adapter === 'codex') return ['codex', 'exec', prompt, '--full-auto']
  if (adapter === 'agy') return ['agy', prompt]
  return ['claude', '-p', prompt, '--print', '--dangerously-skip-permissions']
}
```

In `Editor/index.tsx`, add two new `useCallback` handlers after `handleResume`:
```tsx
const handleSelectionExplain = useCallback((text: string) => {
  if (!effectivePath) return
  const prompt = `Explain the following in the context of this file (${effectivePath.split('/').pop()}):\n\n${text}`
  const tabId = `explain-${Date.now().toString(36)}`
  addTab(tabId, `Explain · ${text.slice(0, 30)}`)
  openTab(tabId)
  void window.pathly.terminal.spawn(tabId, getSpawnCwd(effectivePath), undefined,
    ['claude', '-p', prompt, '--print', '--dangerously-skip-permissions'])
}, [effectivePath, addTab, openTab])

const handleSelectionAskAgent = useCallback((text: string, adapter: string) => {
  if (!effectivePath) return
  const prompt = `Context from ${effectivePath.split('/').pop() ?? 'file'}:\n\n${text}`
  const tabId = `ask-${adapter}-${Date.now().toString(36)}`
  addTab(tabId, `${adapter} · ${text.slice(0, 25)}`)
  openTab(tabId)
  void window.pathly.terminal.spawn(tabId, getSpawnCwd(effectivePath), undefined,
    buildAskAgentArgv(adapter, prompt))
}, [effectivePath, addTab, openTab])
```

Import `buildAskAgentArgv` from `./commentUtils`.
Pass both to `CommentablePreview`:
```tsx
onSelectionExplain={handleSelectionExplain}
onSelectionAskAgent={handleSelectionAskAgent}
```

**Typecheck after:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Conv 2 — MarkdownEditor: Shortcuts, Autocomplete, Status Bar, Fullscreen

**Files to modify:**
- `studio/src/renderer/src/components/Editor/MarkdownEditor.tsx`
- `studio/src/renderer/src/components/Editor/index.tsx`
- `studio/src/renderer/src/components/Editor/index.module.css`
- `studio/src/renderer/src/store/uiStore.ts`

### Prompt:

You are adding MarkdownEditor capabilities and fullscreen mode to the Pathly Studio editor.

**Same rule set as Conv 1.**

**B1 — Markdown keyboard shortcuts in MarkdownEditor.tsx:**

Add these imports (all available in already-installed packages):
```tsx
import { Prec } from '@codemirror/state'
import { keymap } from '@codemirror/view'
```

Add top-level helper (outside component):
```tsx
function wrapWith(open: string, close: string) {
  return (view: EditorView): boolean => {
    const { from, to } = view.state.selection.main
    if (from === to) return false
    const sel = view.state.sliceDoc(from, to)
    view.dispatch({
      changes: { from, to, insert: `${open}${sel}${close}` },
      selection: { anchor: from + open.length, head: to + open.length + sel.length },
    })
    return true
  }
}
```

In the extensions array (after `markdown()`), add:
```tsx
Prec.high(keymap.of([
  { key: 'Ctrl-b', run: wrapWith('**', '**') },
  { key: 'Ctrl-i', run: wrapWith('_', '_') },
  { key: 'Ctrl-`', run: wrapWith('`', '`') },
])),
```

**B2 — Template variable autocomplete:**

Import from `@codemirror/lang-markdown`:
```tsx
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
```

Add top-level completion function (outside component):
```tsx
function templateVarSource(context: CompletionContext) {
  const word = context.matchBefore(/<[A-Z_]*/)
  if (!word || (word.from === word.to && !context.explicit)) return null
  const doc = context.state.doc.toString()
  const vars = [...new Set([...doc.matchAll(/<([A-Z][A-Z0-9_]*)>/g)].map(m => m[1]))]
  if (!vars.length) return null
  return {
    from: word.from,
    options: vars.map(v => ({ label: `<${v}>`, type: 'variable' as const })),
  }
}
```

Import `CompletionContext` from `@codemirror/autocomplete`.

In the extensions array, add AFTER `markdown(markdownLanguage.data.of({ autocomplete: templateVarSource }))` — i.e., change `markdown()` to `markdown({ extensions: [] })` and register via:
```tsx
markdownLanguage.data.of({ autocomplete: templateVarSource }),
```
as a separate extension entry after `markdown()`.

**Fix MarkdownEditor inline style violation:** Replace `style={{ height: '100%', overflow: 'auto' }}` on the return div with a CSS module class. Add a tiny `MarkdownEditor.module.css` with:
```css
.root { height: 100%; overflow: auto; }
```

**B3 — Status bar in Editor/index.tsx:**

Add this JSX between `<ConfigForm .../>` and `<div className={styles.editorArea}>`:
```tsx
{(tab === 'edit' || tab === 'split') && (
  <div className={styles.statusBar}>
    <span className={styles.statusItem}>{body.split(/\s+/).filter(Boolean).length} words</span>
    <span className={styles.statusDot} />
    <span className={styles.statusItem}>≈ {Math.ceil(body.length / 4)} tokens</span>
  </div>
)}
```

Add to index.module.css:
```css
.statusBar {
  display: flex; align-items: center; gap: 10px;
  height: 22px; padding: 0 14px;
  background: var(--bg-mantle);
  border-bottom: 1px solid var(--bg-surface0);
  flex-shrink: 0; user-select: none;
}
.statusItem {
  font-family: var(--font-family-mono); font-size: 10px;
  color: var(--text-muted); white-space: nowrap; line-height: 1;
}
.statusDot {
  width: 3px; height: 3px; border-radius: 50%;
  background: var(--text-muted); opacity: 0.4; flex-shrink: 0;
}
```

**B4 — Fullscreen in uiStore.ts:**

Add to state interface and implementation:
```ts
editorFullscreen: boolean
toggleEditorFullscreen: () => void
```
Default: `editorFullscreen: false`.
Toggle: `set(s => ({ editorFullscreen: !s.editorFullscreen }))`.

In Editor/index.tsx, read from store:
```tsx
const editorFullscreen = useUiStore(s => s.editorFullscreen)
const toggleEditorFullscreen = useUiStore(s => s.toggleEditorFullscreen)
```

Add Escape key handler to the existing keydown effect:
```tsx
if (e.key === 'Escape' && editorFullscreen) toggleEditorFullscreen()
```

Add to the `.panel` div className:
```tsx
className={`${styles.panel} ${editorFullscreen ? styles.panelFullscreen : ''}`}
```

Add fullscreen toggle button to `.actions` div (before Save button):
```tsx
<button type="button" className={styles.tab}
  onClick={toggleEditorFullscreen}
  aria-label={editorFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
  {...(editorFullscreen ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
>
  {editorFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
</button>
```

Add fullscreen exit badge (render when `editorFullscreen`, outside `.panel` flow):
```tsx
{editorFullscreen && (
  <button type="button" className={styles.fullscreenExitBtn}
    onClick={toggleEditorFullscreen} aria-label="Exit fullscreen (Esc)">
    <Minimize2 size={11} /> Esc to exit
  </button>
)}
```

Add to index.module.css:
```css
.panelFullscreen {
  position: fixed; inset: 0; z-index: 900;
  background: var(--bg-base);
  animation: fullscreenIn 180ms cubic-bezier(0.16,1,0.3,1) both;
}
@keyframes fullscreenIn {
  from { opacity: 0.7; transform: scale(0.985); }
  to   { opacity: 1;   transform: scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  .panelFullscreen { animation: none; }
}
.fullscreenExitBtn {
  position: fixed; top: 8px; right: 8px; z-index: 910;
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  background: color-mix(in srgb, var(--bg-surface1) 80%, transparent);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,0.1); border-radius: 5px;
  font-size: 10px; font-weight: 600; color: var(--text-muted); cursor: pointer;
  opacity: 0.35;
  transition: opacity 150ms ease-out, color 100ms ease-out, background 100ms ease-out;
}
.fullscreenExitBtn:hover { opacity: 1; color: var(--text-primary); background: var(--bg-surface1); }
```

Import `Maximize2`, `Minimize2` from `lucide-react`.

**Typecheck after:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Conv 3 — Notebook: Cell Collapse, Fragment Hover Preview, Keyboard Shortcuts + HUD

**Files to modify:**
- `studio/src/renderer/src/components/SkillNotebook/BodyCell/BodyCell.tsx`
- `studio/src/renderer/src/components/SkillNotebook/BodyCell/BodyCell.module.css`
- `studio/src/renderer/src/components/SkillNotebook/FragmentCell/FragmentCell.tsx`
- `studio/src/renderer/src/components/SkillNotebook/FragmentCell/FragmentCell.module.css`
- `studio/src/renderer/src/components/SkillNotebook/NotebookCanvas/NotebookCanvas.tsx`
- `studio/src/renderer/src/components/SkillNotebook/NotebookCanvas/NotebookCanvas.module.css`

**Files to create:**
- `studio/src/renderer/src/components/SkillNotebook/ShortcutHud/ShortcutHud.tsx`
- `studio/src/renderer/src/components/SkillNotebook/ShortcutHud/ShortcutHud.module.css`

### Prompt:

You are adding three Notebook UX improvements to Pathly Studio. Same rules as previous conversations.

**C1 — BodyCell collapse:**

Add `collapsed` local state (default `false`) in BodyCell.tsx.
Add `ChevronDown` / `ChevronUp` button as the **first** child of `.strip`, before the type badge.

Only show the collapse button when NOT `isEditing`:
```tsx
{!isEditing && (
  <button type="button" className={styles.actionBtn}
    title={collapsed ? 'Expand cell' : 'Collapse cell'}
    aria-label={collapsed ? 'Expand cell' : 'Collapse cell'}
    {...(collapsed ? { 'aria-expanded': 'false' } : { 'aria-expanded': 'true' })}
    onClick={() => setCollapsed(c => !c)}
  >
    {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
  </button>
)}
```

When `collapsed`, replace the heading + body with a summary line:
```tsx
{collapsed ? (
  <div className={styles.collapsedSummary}>{displayTitle}</div>
) : (
  /* existing heading JSX */
)}
{!collapsed && (
  /* existing body JSX (cellMode === 'split' block AND the regular cellBody block) */
)}
```

Add class to the cell root when collapsed:
```tsx
className={`${styles.cell} ${isSystem ? styles.cellSystem : styles.cellBodyType}${collapsed ? ` ${styles.cellCollapsed}` : ''}${menuOpen ? ` ${styles.cellMenuOpen}` : ''}`}
```

Add to BodyCell.module.css:
```css
.cellCollapsed { opacity: 0.72; transition: opacity 160ms ease-out; }
.cellCollapsed:hover, .cellCollapsed:focus-within { opacity: 1; }
.collapsedSummary {
  font-family: var(--font-family-mono); font-size: 12px;
  color: var(--text-muted); padding: 2px 0 6px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
```

**C2 — FragmentCell hover preview:**

Add `hoverActive` state and `hoverTimerRef`:
```tsx
const [hoverActive, setHoverActive] = useState(false)
const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
const popoverRef = useRef<HTMLDivElement>(null)
const chipRef = useRef<HTMLSpanElement>(null)
```

Handlers:
```tsx
function handleChipMouseEnter(): void {
  hoverTimerRef.current = setTimeout(() => setHoverActive(true), 300)
}
function handleChipMouseLeave(): void {
  if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current)
  setHoverActive(false)
}
```

Clear timer on unmount: `useEffect(() => () => { if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current) }, [])`.

Position popover in a `useEffect` when `hoverActive`:
```tsx
useEffect(() => {
  if (!hoverActive || !popoverRef.current || !chipRef.current) return
  const chip = chipRef.current.getBoundingClientRect()
  popoverRef.current.style.setProperty('--pop-x', `${chip.left}px`)
  popoverRef.current.style.setProperty('--pop-y', `${chip.bottom + 6}px`)
}, [hoverActive])
```

On the `.name` span, add `ref={chipRef}`, `onMouseEnter`, `onMouseLeave`.

Render popover at the bottom of the component (outside `.cell` wrapper flow, using `position:fixed`):
```tsx
{hoverActive && !menuOpen && (
  <div ref={popoverRef} className={styles.fragmentPopover}
    style={{ left: 'var(--pop-x)', top: 'var(--pop-y)' } as React.CSSProperties}>
    {category && <div className={styles.fragmentPopoverCategory}>{category.toUpperCase()}</div>}
    <div className={styles.fragmentPopoverDesc}>{description || 'No description available.'}</div>
  </div>
)}
```

IMPORTANT: The popover uses inline `style` for `left`/`top` because these are dynamic coordinates set via `setProperty` — this is the allowed pattern. Use `as React.CSSProperties` cast to satisfy TypeScript with the CSS custom property approach, OR use direct coordinate values if using the direct style approach.

Actually, for simplicity: position it with actual numeric values from `getBoundingClientRect` directly in the `useEffect`:
```tsx
useEffect(() => {
  if (!hoverActive || !popoverRef.current || !chipRef.current) return
  const r = chipRef.current.getBoundingClientRect()
  popoverRef.current.style.left = `${r.left}px`
  popoverRef.current.style.top = `${r.bottom + 6}px`
}, [hoverActive])
```

The popover is `position: fixed` via CSS, so `left`/`top` set by JS coordinate values is correct.

Add to FragmentCell.module.css:
```css
.fragmentPopover {
  position: fixed; z-index: 150; pointer-events: none;
  background: var(--bg-surface1);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.30);
  padding: 8px 12px; max-width: 240px;
  animation: popoverIn 120ms cubic-bezier(0.16,1,0.3,1) both;
}
@keyframes popoverIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.fragmentPopoverCategory {
  font-size: 9px; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--green); margin-bottom: 4px;
}
.fragmentPopoverDesc {
  font-size: 11px; color: var(--text-secondary); line-height: 1.45;
}
```

Ensure `.cell` in FragmentCell.module.css has `position: relative` (needed so JS can reference the chip rect correctly).

**C3 — NotebookCanvas keyboard shortcuts:**

Add state: `const [focusedCellId, setFocusedCellId] = useState<string | null>(null)`

Merge with existing keydown handler:
```tsx
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (e.ctrlKey && !e.shiftKey && e.key === 'z') { e.preventDefault(); undo() }
    if (e.ctrlKey && e.shiftKey  && e.key === 'z') { e.preventDefault(); redo() }
    if (!e.altKey || !focusedCellId) return
    const idx = cells.findIndex(c => c.id === focusedCellId)
    if (idx === -1) return
    if (e.key === 'Enter') {
      e.preventDefault()
      const id = insertBodyCell('New section', '', focusedCellId)
      setNewCellId(id); setFocusedCellId(id)
    }
    if (e.key === 'ArrowUp' && idx > 0) {
      e.preventDefault()
      moveCell(focusedCellId, idx <= 1 ? null : cells[idx - 2].id)
    }
    if (e.key === 'ArrowDown' && idx < cells.length - 1) {
      e.preventDefault()
      moveCell(focusedCellId, cells[idx + 1].id)
    }
  }
  document.addEventListener('keydown', handler)
  return () => document.removeEventListener('keydown', handler)
}, [undo, redo, focusedCellId, cells, insertBodyCell, moveCell])
```

Wrap each cell in the map with a focus-tracking div:
```tsx
{cells.map((cell, idx) => (
  <React.Fragment key={cell.id}>
    <div
      onFocusCapture={() => setFocusedCellId(cell.id)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setFocusedCellId(null)
      }}
    >
      {cell.type === 'body' ? <BodyCell ... /> : <FragmentCell ... />}
    </div>
    <InsertZone ... />
  </React.Fragment>
))}
```

**ShortcutHud component (new):**

```tsx
// ShortcutHud.tsx
import React, { useEffect, useState } from 'react'
import styles from './ShortcutHud.module.css'

interface Props { visible: boolean }

export default function ShortcutHud({ visible }: Props): JSX.Element | null {
  const [phase, setPhase] = useState<'in' | 'out' | 'hidden'>('hidden')
  useEffect(() => {
    if (!visible) return
    setPhase('in')
    const hideTimer = setTimeout(() => setPhase('out'), 2400)
    const unmountTimer = setTimeout(() => setPhase('hidden'), 2800)
    return () => { clearTimeout(hideTimer); clearTimeout(unmountTimer) }
  }, [visible])
  if (phase === 'hidden') return null
  return (
    <div className={`${styles.hud} ${phase === 'out' ? styles.hudOut : ''}`} aria-hidden="true">
      <span className={styles.hint}><kbd className={styles.kbd}>Alt+Enter</kbd> Add cell below</span>
      <span className={styles.sep}>·</span>
      <span className={styles.hint}><kbd className={styles.kbd}>Alt+↑↓</kbd> Move cell</span>
    </div>
  )
}
```

In NotebookCanvas, track `hudKey` to re-trigger HUD on each new cell focus:
```tsx
const [hudKey, setHudKey] = useState(0)
// in the onFocusCapture: setFocusedCellId(cell.id); setHudKey(k => k + 1)
```

Render: `<ShortcutHud key={hudKey} visible={focusedCellId !== null} />`

The `key={hudKey}` forces the component to remount (and re-run the effect) each time a cell is focused.

ShortcutHud.module.css:
```css
.hud {
  position: sticky; bottom: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding: 6px 0 10px;
  background: linear-gradient(to bottom, transparent 0%, var(--bg-base) 45%);
  pointer-events: none;
  animation: hudIn 200ms ease-out both;
}
.hudOut { animation: hudOut 400ms ease-in both; }
@keyframes hudIn  { from { opacity: 0; } to { opacity: 1; } }
@keyframes hudOut { from { opacity: 1; } to { opacity: 0; } }
.hint { display: inline-flex; align-items: center; gap: 6px; font-size: 10px; color: var(--text-muted); }
.sep { font-size: 10px; color: var(--text-muted); opacity: 0.4; }
.kbd {
  display: inline-flex; align-items: center; padding: 1px 5px;
  background: var(--bg-surface0); border: 1px solid var(--bg-surface1);
  border-radius: 3px; font-family: var(--font-family-mono); font-size: 9px;
  font-weight: 600; color: var(--text-secondary); white-space: nowrap; line-height: 1.5;
}
```

**Typecheck after:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
