# Conversation Prompts — md-diagram-conversion

**Branch:** `claude/md-diagram-conversion-wze4x3`
**Layer:** Studio (Electron / React renderer only)
All paths relative to repo root. Renderer src root: `studio/src/renderer/src/`.

---

## Conv 0 — Pre-flight Verification

**Branch:** `claude/md-diagram-conversion-wze4x3`

You are doing a read-only pre-flight scan before any code changes. Do not edit any files.

**Step 1 — TypeScript baseline.**
In `studio/`, run:
```
npm run typecheck
tsc --noEmit -p studio/tsconfig.node.json
```
Record whether each exits 0 or lists errors. If either fails, report all errors verbatim and stop — do not proceed to Step 2.

**Step 2 — Touchpoint scan.**
Verify that the following live file shapes match what the plan expects:

1. `store/uiStore.ts` lines 44–47: `MdEditorActionRecord` has `split?` and `analyze?` fields — confirm no `diagram?` field exists yet.
2. `store/uiStore.ts` lines 160–175: `setMdEditorAnalysisPath` function — confirm the auto-open guard (`key === s.mdEditorPath`) is present.
3. `store/uiStore.ts` lines 198–201: `setMdEditorPath` clear block — confirm it spreads `mdEditorAnalysisPanelOpen: false` (that pattern is what Conv 1 will copy for `mdEditorDiagramPanelOpen`).
4. `store/uiStore.ts` line 248: `partialize` — confirm `mdEditorAnalysisPaths` and `mdEditorAnalysisPanelOpen` are NOT in the partialize list.
5. `components/MarkdownEditor/EditorHeader/editorCli.ts` lines 24–27 and 32–34: confirm `CLI_KEY_SPLIT`, `CLI_KEY_ANALYZE`, `PRESET_KEY_SPLIT`, `PRESET_KEY_ANALYZE` constant naming pattern.
6. `components/MarkdownEditor/EditorHeader/EditorHeader.tsx` line 60: confirm `pendingRun` type union contains `'split' | 'analyze'` but not `'diagram'` yet.
7. `components/MarkdownEditor/EditorHeader/EditorHeader.tsx` lines 277–361: confirm the Split pill block and Analyze pill block end at ~line 361.
8. `components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts` lines 85 and 105–176: confirm the reconciliation array `['split', 'analyze']` and the `handleSplit` function body (this is the clone target for Conv 2).
9. `services/skillCompose.ts` line 19: confirm `ComposeTransform.kind` is `'summary' | 'analysis' | 'split'` with no `'diagram'` yet.
10. `components/MarkdownEditor/MarkdownEditor.tsx` line 28: confirm `<AnalysisPanel />` is rendered with no props.

Report: for each touchpoint, state MATCH or MISMATCH and the actual line content. If any MISMATCH, report the real line numbers and content — the plan's line numbers are approximate.

**Do not touch:** any source files.

**Done when:** both typechecks exit 0 AND all 10 touchpoints are confirmed (with actual line numbers noted for the builder to use in Conv 1+).

---

## Conv 1 — State Scaffold + CLI/Preset Keys

**Branch:** `claude/md-diagram-conversion-wze4x3`

You are widening the Zustand store and constants to accept the `'diagram'` action. No UI components are created in this conversation. After your changes the existing Split and Analyze pills must be visually and functionally unaffected.

**Delivers:** S-11 (store setter auto-open logic), S-12 (partial typecheck gate)

**Files to edit — exactly these three, no others:**

### 1. `store/uiStore.ts`

Make these four targeted changes:

**A. Widen `MdEditorActionRecord` (at lines ~44–47).** Add `diagram?: MdEditorActionSlot` as a third optional field after `analyze?`.

**B. Add diagram state fields (after `mdEditorAnalysisPanelOpen: boolean` at line ~74).** Add:
```ts
mdEditorDiagramsPaths: Record<string, string>
mdEditorDiagramPanelOpen: boolean
```
Initialize both in the initial state: `mdEditorDiagramsPaths: {}`, `mdEditorDiagramPanelOpen: false`.

**C. Add setters (copy `setMdEditorAnalysisPath` at lines ~160–175 verbatim; rename).** The new setter is:
```ts
setMdEditorDiagramsPath: (p: string | null, forFile?: string) => void
setMdEditorDiagramPanelOpen: (v: boolean) => void
```
`setMdEditorDiagramsPath` must include the auto-open guard: `if (key === s.mdEditorPath) { mdEditorDiagramPanelOpen: true }` — this is the mechanism for S-11. Copy the existing analysis setter logic exactly, substituting `mdEditorDiagramsPaths` for `mdEditorAnalysisPaths` and `mdEditorDiagramPanelOpen` for `mdEditorAnalysisPanelOpen`.

**D. Extend the `setMdEditorPath` clear block (at lines ~198–201).** In the spread that clears analysis state on file switch, add `mdEditorDiagramPanelOpen: false`.

**E. Add selectors (after the existing analysis selectors).** Add:
```ts
export const selectMdEditorDiagram = (s: UiStore) =>
  s.mdEditorActions[s.mdEditorPath ?? '']?.diagram

export const selectMdEditorDiagramsPath = (s: UiStore) =>
  s.mdEditorDiagramsPaths[s.mdEditorPath ?? ''] ?? null
```

**Do NOT** add any diagram keys to `partialize` (line ~248). Session-only state — durability comes from the sidecar file on disk.

### 2. `components/MarkdownEditor/EditorHeader/editorCli.ts`

After the existing `PRESET_KEY_ANALYZE` constant (at lines ~32–34), add:
```ts
export const CLI_KEY_DIAGRAM = 'pathly.notebook.cli.diagram'
export const PRESET_KEY_DIAGRAM = 'pathly.notebook.preset.diagram'
```

### 3. `services/skillCompose.ts`

At the `ComposeTransform.kind` union (line ~19), add `| 'diagram'`:
```ts
kind: 'summary' | 'analysis' | 'split' | 'diagram'
```

**Gate:** run `npm run typecheck` in `studio/`. It must exit 0 with zero new errors. Confirm that calling `setMdEditorAction(filePath, 'diagram', null)` is type-valid (the action type union must now include `'diagram'`).

**Do not touch:** `EditorHeader.tsx`, `useEditorAgentActions.ts`, any component files, `MarkdownEditor.tsx`.

**Done when:** `npm run typecheck` exits 0; the three files are the only modified files; Split and Analyze pills still render in Studio without error.

---

## Conv 2 — Sidecar I/O + Spawn Hook

**Branch:** `claude/md-diagram-conversion-wze4x3`

You are creating three new files: the sidecar I/O module, the diagram presets, and the spawn hook. No UI is mounted yet. Confirm Conv 1 changes are on the branch before starting.

**Delivers:** S-02 (spawn hook), S-03 (sidecar I/O layer)

**Files to create — exactly these three:**

### 1. `components/MarkdownEditor/DiagramGalleryPanel/diagramSidecar.ts` (≤ 120 lines)

Pure functions over `window.pathly.fs` — no React, no imports from store.

Define these types:
```ts
export interface Diagram {
  id: string            // crypto.randomUUID() — set by the agent
  style: 'mermaid' | 'ascii' | 'plantuml'
  source: string        // the raw diagram text
  prompt: string        // the prompt used to generate it
  engine: string        // CLI engine name
  status: 'ok' | 'error'
  createdAt: string     // ISO timestamp
}

export interface DiagramSidecar {
  version: number       // always 1
  source: string        // always 'agent'
  diagrams: Diagram[]
}
```

Implement these four functions:
- `readSidecar(file: string): Promise<DiagramSidecar>` — reads `file + '.diagrams.json'` via `window.pathly.fs.read`; on any error (file missing, parse failure) returns `{ version: 1, source: 'agent', diagrams: [] }` — never throws.
- `writeSidecar(file: string, sidecar: DiagramSidecar): Promise<void>` — `JSON.stringify(sidecar, null, 2)` → `window.pathly.fs.write`.
- `appendDiagram(file: string, entry: Diagram): Promise<void>` — `readSidecar` → push entry → `writeSidecar`.
- `removeDiagram(file: string, id: string): Promise<void>` — `readSidecar` → filter out `entry.id === id` → `writeSidecar`.

### 2. `components/MarkdownEditor/EditorHeader/diagramPresets.ts` (≤ 150 lines)

Define `DIAGRAM_STYLES` and 6 `PromptPreset[]` entries. Each preset prompt must reference `{{FILE}}` and `{{SIDECAR}}` placeholders. Group in two sections:

**Renders anywhere (style picker group "Renders anywhere"):**
- Flowchart (style: `'mermaid'`, hint: "Flowchart diagram")
- Sequence (style: `'mermaid'`, hint: "Sequence diagram")
- Mindmap (style: `'mermaid'`, hint: "Mind map")
- Architecture boxes (style: `'ascii'`, hint: "ASCII box diagram")

**Needs render engine (style picker group "Needs render engine"):**
- Architecture (style: `'plantuml'`, hint: "Component diagram")
- UML class (style: `'plantuml'`, hint: "UML class diagram")

Import `PromptPreset` type from wherever `analyzePresets.ts` imports it (check the existing file for the correct import path).

Export: `DIAGRAM_PRESETS: PromptPreset[]` and `DIAGRAM_STYLE_GROUPS` (array of `{ label: string; presets: PromptPreset[] }` for the style picker menu).

### 3. `components/MarkdownEditor/EditorHeader/hooks/useEditorDiagramAction.ts` (≤ 150 lines)

Clone the `handleSplit` branch of `useEditorAgentActions.ts` (lines 105–176). Change only these five things from the split branch:

1. `outPath = forFile + '.diagrams.json'` (not `.split.draft`)
2. Compose call: `kind: 'diagram'`, skill id: `'development/diagram'`
3. Success validation: parse `content` as JSON; treat it as success only if it is a `{diagrams: [...]}` shaped object; otherwise treat as run failure (error toast, `'error'` status)
4. On success: call `setMdEditorDiagramsPath(outPath, forFile)` — do NOT call `setMdEditorViewMode` or `setSplitDraftPath`
5. `resolveActionPrompt` call: pass `'development/diagram'` as skill id and `'diagram'` as kind

Additionally, extend the stale-run reconciliation array at line ~85 of `useEditorAgentActions.ts` to include `'diagram'`: change `['split', 'analyze']` to `['split', 'analyze', 'diagram']`.

The hook returns `{ handleDiagram, stopDiagram }`. It is invoked as a standalone hook call in `EditorHeader.tsx` (Conv 3).

**Gate:** run `npm run typecheck` in `studio/`. Must exit 0.

Manually verify: call `handleDiagram('Generate a flowchart for this file')` from the browser devtools console while a `.md` file is open in the editor. A terminal tab should appear in Studio, and after it exits, `<filename>.diagrams.json` should exist on disk adjacent to the `.md` file.

**Do not touch:** `EditorHeader.tsx`, `MarkdownEditor.tsx`, any gallery panel files, `uiStore.ts`.

**Done when:** `npm run typecheck` exits 0; sidecar file appears on disk after a manual test run; a second `handleDiagram` call while one is running is a no-op (run-guard active per the `status === 'running'` guard inherited from the split clone).

---

## Conv 3 — Header Pill

**Branch:** `claude/md-diagram-conversion-wze4x3`

You are adding the third `<ActionPill>` to `EditorHeader.tsx` and wiring it to the spawn hook from Conv 2. After this conversation the full generate-flow is usable from the UI.

**Delivers:** S-01, S-02 (full UI wiring), S-11 (result chip toggles panel)

**File to edit — exactly one:**

### `components/MarkdownEditor/EditorHeader/EditorHeader.tsx`

**A. Import additions (top of file).**
- Import `useEditorDiagramAction` from `'./hooks/useEditorDiagramAction'`
- Import `CLI_KEY_DIAGRAM, PRESET_KEY_DIAGRAM` from `'./editorCli'`
- Import `DIAGRAM_PRESETS` (or `DIAGRAM_STYLE_GROUPS`) from `'./diagramPresets'`
- Import `selectMdEditorDiagramsPath, selectMdEditorDiagramPanelOpen` from `'../../../../store/uiStore'` (verify path against existing analysis imports)
- Import `Network` from `'lucide-react'`

**B. State vars (near lines 53–58, after existing `splitOncePrompt`/`analyzeOncePrompt`).** Add:
```ts
const [diagramOncePrompt, setDiagramOncePrompt] = useState<string | null>(null)
const [diagramCli, setDiagramCli]     = useState(() => loadEditorCli(CLI_KEY_DIAGRAM))
const [diagramPreset, setDiagramPreset] = useState(() => loadPreset(PRESET_KEY_DIAGRAM))
const [diagramPeekOpen, setDiagramPeekOpen] = useState(false)
```

**C. Store reads (alongside existing analysis selectors).**
```ts
const diagramsPath = useUiStore(selectMdEditorDiagramsPath)
const diagramPanelOpen = useUiStore(s => s.mdEditorDiagramPanelOpen)
const setDiagramPanelOpen = useUiStore(s => s.setMdEditorDiagramPanelOpen)
```

**D. Hook call (alongside the `useEditorAgentActions` call).**
```ts
const { handleDiagram, stopDiagram } = useEditorDiagramAction({
  diagramOncePrompt,
  onDiagramOnceUsed: () => setDiagramOncePrompt(null),
  diagramCli,
})
```

**E. Handler (after `openAnalyzePreview` at lines ~83–92).**
```ts
const openDiagramPreview = (prompt: string) => {
  setPendingRun({ kind: 'diagram', prompt, engine: diagramCli, action: PRESET_KEY_DIAGRAM })
}
```

**F. Widen `pendingRun.kind` union (line ~60).** Change `'split' | 'analyze'` to `'split' | 'analyze' | 'diagram'`.

**G. Add diagram case to `submitPendingRun` (at lines ~93–98).**
```ts
case 'diagram':
  handleDiagram(pendingRun.prompt)
  break
```

**H. Diagram count (derived).**
```ts
// diagramCount: read from sidecar path; default 0 when no path or not yet loaded
const diagramCount = /* use useDiagramSidecar or derive from store — pick the same pattern
  that analyzePanel uses for its count, to stay consistent */
```
If the analysis panel derives its count from the store, do the same. If it reads from a hook, do the same. Match the pattern exactly.

**I. Third `<ActionPill>` (after the Analyze pill, which ends at ~line 361).** Insert:
```tsx
<ActionPill
  ariaName="Diagram"
  mainIcon={<Network size={14} />}
  tone="green"
  runSlot={useUiStore(selectMdEditorDiagram)}
  onRun={() => openDiagramPreview(diagramPreset?.prompt ?? '')}
  onStop={stopDiagram}
  onOpenSettings={() => setDiagramPeekOpen(true)}
  resultLabel={`🖼 ${diagramCount}`}
  resultReady={diagramCount > 0}
  onOpenResult={() => setDiagramPanelOpen(!diagramPanelOpen)}
/>
```
(Verify the exact prop names against the existing Split/Analyze `<ActionPill>` instances — use the same prop names verbatim.)

**J. `PromptPeekModal` for diagram (after the existing Analyze `PromptPeekModal`).**
Copy the Analyze `PromptPeekModal` block verbatim; substitute `diagramPeekOpen`, `setDiagramPeekOpen`, `DIAGRAM_PRESETS`, `diagramPreset`, `setDiagramPreset`, `PRESET_KEY_DIAGRAM`, `diagramCli`, `CLI_KEY_DIAGRAM`.

**K. `SendPreviewModal` diagram branch.**
The existing `SendPreviewModal` renders when `pendingRun !== null`. It already has `if (pendingRun.kind === 'split')` and `if (pendingRun.kind === 'analyze')` branches for the title/icon. Add `else if (pendingRun.kind === 'diagram')` with `title="Generate Diagram"` and the `<Network/>` icon.

**Gate:** run `npm run typecheck` in `studio/`. Must exit 0.

Manually verify: open a `.md` file → click the Diagram pill → `PromptPeekModal` opens with 6 diagram style presets → select one and confirm → `SendPreviewModal` appears with "Generate Diagram" title → confirm → terminal tab appears + spinner on pill → on completion, pill shows success + chip with count.

**Do not touch:** `MarkdownEditor.tsx`, any gallery panel files, `uiStore.ts`, `diagramSidecar.ts`.

**Done when:** `npm run typecheck` exits 0; end-to-end generate flow works from the pill; result chip shows count > 0; Split and Analyze pills are unaffected.

---

## Conv 4 — Gallery Panel + Card

**Branch:** `claude/md-diagram-conversion-wze4x3`

You are building the `DiagramGalleryPanel`, the `useDiagramSidecar` hook, and `DiagramCard`. After this conversation users can browse, delete, and regenerate diagram cards from the side panel.

**Delivers:** S-03 (gallery reads sidecar on mount), S-04, S-09, S-10, S-11 (panel auto-open)

**Files to create:**

### 1. `components/MarkdownEditor/DiagramGalleryPanel/useDiagramSidecar.ts` (≤ 90 lines)

Hook that loads the sidecar whenever `mdEditorPath` or `diagramsPath` changes.

```ts
export function useDiagramSidecar() {
  const diagramsPath = useUiStore(selectMdEditorDiagramsPath)
  const [diagrams, setDiagrams] = useState<Diagram[]>([])

  const reload = useCallback(async () => {
    if (!diagramsPath) { setDiagrams([]); return }
    const sidecar = await readSidecar(/* strip '.diagrams.json' suffix to get the base file */)
    setDiagrams(sidecar.diagrams)
  }, [diagramsPath])

  useEffect(() => { reload() }, [reload])

  const removeDiagramById = async (file: string, id: string) => {
    await removeDiagram(file, id)
    await reload()
  }

  return { diagrams, reload, removeDiagram: removeDiagramById }
}
```

### 2. `components/MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.tsx` (≤ 120 lines)

Panel shell. Read from store: `mdEditorDiagramPanelOpen`, `mdEditorPath`, `setMdEditorDiagramPanelOpen`, `setMdEditorDiagramsPath`.

Guard at the top: `if (!mdEditorDiagramPanelOpen) return null`

Structure:
```
.panel (absolute right 0, top 0, bottom 0, width 380px — from CSS)
  header: "Diagrams" title + close button (type="button")
  [+ New ▾] button (type="button") → style picker dropdown (DIAGRAM_STYLE_GROUPS)
  scrollable body: diagrams.map(d => <DiagramCard key={d.id} diagram={d} … />)
  empty state: when diagrams.length === 0 and no run active
```

On delete (received from `DiagramCard`):
```ts
await removeDiagram(mdEditorPath, id)
if (diagrams.length - 1 === 0) {
  setMdEditorDiagramPanelOpen(false)
  setMdEditorDiagramsPath(null, mdEditorPath)
}
```

### 3. `components/MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.module.css`

Copy the `.panel` block verbatim from `AnalysisPanel.module.css` (the block with `position: absolute; top: 0; right: 0; bottom: 0; width: 380px; display: flex; flex-direction: column; background: var(--bg-base); border-left: var(--border); z-index: 20; box-shadow: -4px 0 20px rgba(0,0,0,0.25)`). Add additional classes for the header bar, close button, body scroll area, empty state, and `[+ New]` button — all using `tokens.css` vars, no inline styles.

### 4. `components/MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.tsx` (≤ 120 lines)

Props: `diagram: Diagram`, `onDelete: () => void`, `onRegenerate: () => void`, `onView: () => void`.

Card structure:
```
.card
  .header: style badge (data-style={diagram.style}) · status · ISO date · engine
  .preview: <DiagramRender diagram={diagram} mode="card" />   [stub — renders nothing yet, Conv 5 fills this in]
  .actions:
    <button type="button" onClick={onView}>View</button>
    <button type="button" onClick={onRegenerate}>Regenerate</button>
    <button type="button" onClick={onDelete}>Delete</button>
```

Style badge shows `mermaid`, `ascii`, or `plantuml` text using a `data-style` CSS attribute selector. Date formatted as `new Date(diagram.createdAt).toLocaleDateString()`.

### 5. `components/MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.module.css`

Card layout + badge variants using `tokens.css` vars. No inline styles.

**File to edit:**

### `components/MarkdownEditor/MarkdownEditor.tsx`

After `<AnalysisPanel />` at line ~28, add:
```tsx
<DiagramGalleryPanel />
```
Import `DiagramGalleryPanel` from `'./DiagramGalleryPanel/DiagramGalleryPanel'`.

**Gate:** run `npm run typecheck` in `studio/`. Must exit 0.

Manually verify: generate a diagram via the header pill → panel opens automatically → card appears with style badge and metadata → click Delete → card removed → sidecar on disk reflects deletion → close and re-open file → (if sidecar has cards) cards reload from disk.

**Do not touch:** `EditorHeader.tsx`, `uiStore.ts`, `diagramSidecar.ts`, `diagramPresets.ts`, `useEditorDiagramAction.ts`. Do not implement `DiagramRender` yet — `DiagramCard` renders a placeholder `<div>` for the preview area.

**Done when:** `npm run typecheck` exits 0; panel auto-opens on run complete; delete works and updates disk; file reload restores cards; deleting last card closes panel.

---

## Conv 5 — Render Dispatch + Mermaid + Lightbox

**Branch:** `claude/md-diagram-conversion-wze4x3`

You are implementing all three render paths and the lightbox. After this conversation all diagram types render correctly and the lightbox opens with zoom/pan.

**Delivers:** S-05, S-06, S-07, S-08

**Before starting:** verify `mermaid` is not yet in `studio/package.json`. Add it as a production dependency: `"mermaid": "^10.0.0"` (or latest stable). Run `npm install` in `studio/`.

**Files to create:**

### 1. `components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender.tsx` (≤ 80 lines)

Props: `diagram: Diagram`, `mode: 'card' | 'full'`.

Dispatch:
```tsx
if (diagram.style === 'mermaid') return <MermaidView content={diagram.source} mode={mode} />
if (diagram.style === 'ascii')   return <pre className={styles.ascii}>{diagram.source}</pre>
// plantuml:
return (
  <div className={styles.plantumlWrap}>
    <pre className={styles.ascii}>{diagram.source}</pre>
    <p className={styles.notice}>PlantUML render engine not bundled. Paste source into plantuml.com to render.</p>
  </div>
)
```

`<pre>` uses a text node (no `dangerouslySetInnerHTML`). ASCII and PlantUML `<pre>` use `var(--font-mono)` from `tokens.css` — no hard-coded font families.

In `mode="full"`, apply a CSS class that removes the card size clamp and enables horizontal scroll for the `<pre>`.

### 2. `components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx` (≤ 120 lines)

Props: `content: string`, `mode: 'card' | 'full'`.

Module-level promise cache (declared outside the component):
```ts
let mermaidPromise: Promise<typeof import('mermaid').default> | null = null

function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then(m => {
      m.default.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base' })
      return m.default
    })
  }
  return mermaidPromise
}
```

Inside the component, `useEffect` (dependencies: `[content, theme]`):
1. Capture `let active = true` before the async call.
2. `const mermaid = await getMermaid()` (one-time load).
3. Re-read theme tokens: `const cs = getComputedStyle(document.documentElement)` and call `mermaid.initialize({ ..., themeVariables: { background: cs.getPropertyValue('--bg-base'), primaryColor: cs.getPropertyValue('--bg-surface0'), primaryTextColor: cs.getPropertyValue('--text-primary'), lineColor: cs.getPropertyValue('--text-muted') } })`.
4. `const { svg } = await mermaid.render('dg_' + uniqueId + '_' + renderCounter, content)`.
5. If `!active` bail; else set `svgState`.
6. Cleanup: `return () => { active = false }`.

Error path: if `mermaid.render` throws, set `errorState = true` and render:
```tsx
<pre className={styles.errorPre}>{content}</pre>
<p className={styles.errorNote}>Diagram parse error — showing raw source.</p>
```

SVG render: `<div ref={ref} dangerouslySetInnerHTML={{ __html: svg }} />` — only the sanitized SVG mermaid returns, never raw agent text.

Subscribe to `useUiStore(s => s.theme)` and include it in the `useEffect` dependency array — this is what triggers re-render on light/dark flip (S-13).

No hex literals anywhere in this file. Verify with `grep -n '#[0-9a-fA-F]' MermaidView.tsx` — must return no matches.

### 3. `components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx` (≤ 150 lines)

Props: `diagram: Diagram | null`, `onClose: () => void`.

Guard: `if (!diagram) return null`.

Structure:
```
.backdrop (full-screen overlay, onClick={onClose})
  .lightboxFrame (centered content, stopPropagation on click)
    .lightboxHeader: diagram.style badge + date + close button (type="button")
    .renderWrap (the zoom/pan target)
      <DiagramRender diagram={diagram} mode="full" />
```

Zoom/pan implementation:
```ts
const [scale, setScale] = useState(1)
const [translate, setTranslate] = useState({ x: 0, y: 0 })

// Wheel → scale (clamp 0.5–4)
onWheel={(e) => {
  e.preventDefault()
  setScale(s => Math.min(4, Math.max(0.5, s - e.deltaY * 0.001)))
}}

// Pointer drag → translate
onPointerDown / onPointerMove / onPointerUp pattern
```

Apply as inline transform on `.renderWrap` (this is the one sanctioned exception to the no-inline-styles rule — dynamic transform values cannot live in a static CSS file):
```tsx
style={{ transform: `scale(${scale}) translate(${translate.x}px, ${translate.y}px)` }}
```

Esc key: `useEffect` that adds `keydown` listener on mount, removes on unmount; calls `onClose` when `e.key === 'Escape'`.

**Wire up the lightbox in `DiagramCard.tsx`:** add `lightboxDiagram: Diagram | null` + `setLightboxDiagram` state in `DiagramGalleryPanel.tsx` (the panel owns lightbox state, not each card). Pass `onView={() => setLightboxDiagram(diagram)}` to `DiagramCard`. Render `<DiagramLightbox diagram={lightboxDiagram} onClose={() => setLightboxDiagram(null)} />` at the bottom of `DiagramGalleryPanel.tsx`.

### 4. `components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.module.css`

Backdrop: `position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 100; display: flex; align-items: center; justify-content: center`. No hard-coded hex colors for UI elements — use `tokens.css` vars. `rgba(0,0,0,0.6)` for the backdrop scrim is an allowed exception (not a brand color).

**Gate:** run `npm run typecheck` in `studio/`. Must exit 0.

Manually verify:
- Generate a mermaid diagram → card shows SVG (not loading spinner indefinitely, not blank).
- Generate an ASCII diagram → card shows monospace `<pre>`.
- Generate a plantuml diagram → card shows source `<pre>` + notice string exactly: `"PlantUML render engine not bundled. Paste source into plantuml.com to render."`.
- Click View on any card → lightbox opens; wheel zooms (0.5×–4×); drag pans; Esc closes; backdrop click closes.
- `grep -n '#[0-9a-fA-F]' studio/src/renderer/src/components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx` returns no matches.

**Do not touch:** `EditorHeader.tsx`, `uiStore.ts`, `diagramSidecar.ts`, `diagramPresets.ts`, `useEditorDiagramAction.ts`.

**Done when:** `npm run typecheck` exits 0; all three render types work; lightbox opens with zoom/pan; Esc and backdrop close it; no hex literals in `MermaidView.tsx`.

---

## Conv 6 — Polish + Final Verification

**Branch:** `claude/md-diagram-conversion-wze4x3`

You are doing a compliance sweep across all new and edited files, fixing any gaps found, and running the final acceptance gate. This conversation does not add new features — it brings the entire feature to a shippable state.

**Delivers:** S-12 (TypeScript clean), S-13 (theme re-render)

**Step 1 — TypeScript clean.**
Run:
```
npm run typecheck
tsc --noEmit -p studio/tsconfig.node.json
```
Fix every error reported. Do not suppress errors with `// @ts-ignore` or `as unknown as X` casts without justification.

**Step 2 — Theme re-render verification (S-13).**
In `MermaidView.tsx`, confirm `useUiStore(s => s.theme)` is subscribed and included in the `useEffect` dependency array. If `mermaid.initialize()` proves unsafe to call multiple times (crashes or produces garbled SVG on second call), use the `key` prop fallback instead: pass `key={theme}` to `<MermaidView>` from `DiagramCard.tsx` to force remount on theme change. Document which approach was used in a comment in `MermaidView.tsx`.

**Step 3 — `type="button"` audit.**
Run:
```
grep -rn '<button' studio/src/renderer/src/components/MarkdownEditor/DiagramGalleryPanel/
```
Every `<button` must have `type="button"`. Fix any missing attributes.

**Step 4 — No hex literals in `MermaidView.tsx`.**
Run:
```
grep -n '#[0-9a-fA-F]' studio/src/renderer/src/components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx
```
Must return no matches. Replace any hex values with `getComputedStyle(document.documentElement).getPropertyValue('--<token-name>')`.

**Step 5 — Line budget audit.**
Check every file in `DiagramGalleryPanel/` and `EditorHeader/hooks/useEditorDiagramAction.ts`:
```
wc -l <file>
```
Any file over 150 lines must be split before this conversation closes. The allowed splits are pre-defined in `ARCHITECTURE_PROPOSAL.md §1`.

**Step 6 — PlantUML notice exact string.**
Run:
```
grep -n "PlantUML render engine" studio/src/renderer/src/components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender.tsx
```
The string must be exactly: `PlantUML render engine not bundled. Paste source into plantuml.com to render.`

**Step 7 — Manual smoke test.**
Perform this sequence in Studio:
1. Open a Markdown file.
2. Click Diagram pill → select Flowchart preset → confirm → wait for run to complete → pill shows chip with count 1.
3. Gallery panel auto-opens → one card with style badge "mermaid" and SVG preview.
4. Click Diagram pill again → select Architecture boxes (ascii) preset → confirm → count becomes 2.
5. Click View on the mermaid card → lightbox opens → wheel-zoom → drag-pan → Esc closes.
6. Click Delete on the ASCII card → card removed → sidecar on disk has 1 entry.
7. Close and re-open the `.md` file → 1 card remains (sidecar persists across reload).
8. Flip Studio theme (light ↔ dark) → mermaid SVG re-renders with updated colors.
9. Split and Analyze pills still render and respond to their own run state normally.

**Do not push to master.** The branch is `claude/md-diagram-conversion-wze4x3`. Do not create a PR unless explicitly requested.

**Done when:** both typechecks exit 0; all manual smoke test steps pass; all compliance checks (Step 3–6) produce clean output.
