# Implementation Plan — md-diagram-conversion

**Branch:** `claude/md-diagram-conversion-wze4x3`
**Rigor:** standard
**Layer:** Studio (Electron / React renderer only)

All file paths relative to `studio/src/renderer/src/` unless noted otherwise.
Architecture decisions are in `ARCHITECTURE_PROPOSAL.md`. Stories are in `USER_STORIES.md`.

---

## Phase 0 — Pre-flight Verification

**Goal:** Confirm the baseline is healthy before any new code lands. Surface any
TypeScript errors or test failures that exist today so Conv 1 starts from a clean state.

**Stories fulfilled:** (none new — this is a baseline gate)

**Files touched:** none (read-only scan)

**Done when:**
- `npm run typecheck` exits 0 in `studio/`
- `tsc --noEmit -p studio/tsconfig.node.json` exits 0
- Touchpoints confirmed: `uiStore.ts` `MdEditorActionRecord` shape, `EditorHeader.tsx` pill
  rendering pattern, `AnalysisPanel` CSS `.panel` block, `skillCompose.ts` `ComposeTransform.kind`
  union — all match the scout findings exactly

---

## Conversation 1 — State Scaffold + CLI/Preset Keys

**Goal:** Widen the Zustand store and constants to accept the `'diagram'` action without
touching any UI. After this phase, the existing Split and Analyze pills are unaffected.

**Stories fulfilled:** S-11 (store setter auto-open logic), S-12 (partial typecheck gate)

**Files changed:**

| File | Change |
|---|---|
| `store/uiStore.ts` | Add `diagram?` to `MdEditorActionRecord`; add `mdEditorDiagramsPaths: Record<string, string>`, `mdEditorDiagramPanelOpen: boolean`, setters `setMdEditorDiagramsPath` + `setMdEditorDiagramPanelOpen`, selectors `selectMdEditorDiagram` + `selectMdEditorDiagramsPath`; extend `setMdEditorPath` file-switch clear block |
| `components/MarkdownEditor/EditorHeader/editorCli.ts` | Add `CLI_KEY_DIAGRAM = 'pathly.notebook.cli.diagram'` and `PRESET_KEY_DIAGRAM = 'pathly.notebook.preset.diagram'` constants |
| `services/skillCompose.ts` | Add `'diagram'` to `ComposeTransform.kind` union |

**Implementation notes (ARCHITECTURE_PROPOSAL.md §3):**
- `setMdEditorDiagramsPath` copies `setMdEditorAnalysisPath` verbatim; rename all field references
- The auto-open guard (`key === s.mdEditorPath`) must be copied exactly — it is the mechanism for S-11
- `setMdEditorPath` clear block at lines ~198–201: add `mdEditorDiagramPanelOpen: false` to the spread
- Do NOT add any diagram keys to `partialize` (line 248) — session-only state, durability comes from sidecar on disk

**Done when:**
- `npm run typecheck` exits 0
- `setMdEditorAction` accepts `'diagram'` as a type-valid argument (confirmed by compiler, not runtime)
- Split and Analyze pill behavior is visually unchanged

---

## Conversation 2 — Sidecar I/O + Spawn Hook

**Goal:** Implement the pure I/O layer and the agent-spawn hook that drives the diagram
generation run. No UI yet — output visible only in a spawned terminal tab.

**Stories fulfilled:** S-02 (spawn hook), S-03 (sidecar I/O layer)

**Files created:**

| File | Purpose |
|---|---|
| `components/MarkdownEditor/EditorHeader/diagramPresets.ts` | `DIAGRAM_STYLES` array + 6 `PromptPreset[]` (flowchart, sequence, mindmap, architecture, boxes, uml); plantuml group labeled "Needs render engine" |
| `components/MarkdownEditor/DiagramGalleryPanel/diagramSidecar.ts` | Pure functions: `readSidecar`, `appendDiagram`, `removeDiagram`, `writeSidecar` + `Diagram` / `DiagramSidecar` types |
| `components/MarkdownEditor/EditorHeader/hooks/useEditorDiagramAction.ts` | Spawn hook cloned from `handleSplit` branch of `useEditorAgentActions.ts`; `outPath = file + '.diagrams.json'`; compose `kind: 'diagram'`; skill `'development/diagram'`; success: `setMdEditorDiagramsPath(outPath, forFile)` |

**Implementation notes (ARCHITECTURE_PROPOSAL.md §4–§5):**
- `diagramSidecar.ts`: all four functions operate on `window.pathly.fs`; `readSidecar` returns `{ version: 1, source: 'agent', diagrams: [] }` on any miss or parse failure — no throw
- `useEditorDiagramAction.ts`: clone `handleSplit` lines 105–176 of `useEditorAgentActions.ts`; differences are: `outPath`, `kind`, `skill`, the success-validation (parse JSON, check `{diagrams:[]}` shape), and the setter called on success
- `resolveActionPrompt` call must pass `'development/diagram'` as skill id and `'diagram'` as kind
- Reconciliation array `['split', 'analyze']` at line 85 of `useEditorAgentActions.ts`: add `'diagram'`
- `diagramPresets.ts`: every preset prompt must include `{{FILE}}` and `{{SIDECAR}}` placeholders; plantuml preset must be in a group distinct from mermaid/ascii

**Done when:**
- `npm run typecheck` exits 0
- Invoking `handleDiagram(prompt)` from the browser console spawns a terminal tab
- The tab exits and `.diagrams.json` appears adjacent to the test `.md` file
- Invoking a second `handleDiagram` while one is running is a no-op (run-guard active)

---

## Conversation 3 — Header Pill

**Goal:** Wire the third `<ActionPill>` in `EditorHeader.tsx` so the full generate flow is
accessible from the UI, including the `PromptPeekModal`, `SendPreviewModal` confirm, and the
result chip that toggles the gallery panel.

**Stories fulfilled:** S-01, S-02 (full UI wiring), S-11 (result chip toggles panel)

**Files changed:**

| File | Change |
|---|---|
| `components/MarkdownEditor/EditorHeader/EditorHeader.tsx` | Add `diagramOncePrompt`, `diagramCli`, `diagramPreset`, `diagramPeekOpen` state vars; add `openDiagramPreview` handler; add `'diagram'` to `pendingRun.kind` union; add `'diagram'` case to `submitPendingRun`; render 3rd `<ActionPill>` after Analyze pill (lines ~362+); wire `PromptPeekModal` + `SendPreviewModal` diagram branch |

**Implementation notes (ARCHITECTURE_PROPOSAL.md §5 — Header wiring):**
- New state vars insert near lines 53–58 (beside existing `splitOncePrompt` etc.)
- `openDiagramPreview` copies the pattern at lines 83–92 exactly
- `submitPendingRun` at lines 93–98: add `case 'diagram': handleDiagram(pendingRun.prompt)`
- 3rd `<ActionPill>`: `ariaName="Diagram"`, `mainIcon=<Network/>` (Lucide), `tone="green"`
- Result chip: `resultLabel` = `` `🖼 ${diagramCount}` ``, `resultReady={diagramCount > 0}`, `onOpenResult={() => setMdEditorDiagramPanelOpen(!mdEditorDiagramPanelOpen)}`
- `diagramCount` derived from `selectMdEditorDiagramsPath` + `useDiagramSidecar` (may be 0 on first render before gallery mounts)
- `useEditorDiagramAction` called as a standalone hook call in the same component, alongside `useEditorAgentActions`

**Done when:**
- `npm run typecheck` exits 0
- Clicking the Diagram pill opens `PromptPeekModal` with diagram style presets
- Confirming through `SendPreviewModal` spawns a terminal tab and shows spinner on the pill
- On run completion the pill shows success state and a chip with count > 0
- Split and Analyze pills are visually and functionally unaffected

---

## Conversation 4 — Gallery Panel + Card

**Goal:** Build the `DiagramGalleryPanel`, the `useDiagramSidecar` hook, and `DiagramCard`
so that generated diagrams accumulate in a scrollable side panel with working Delete and
Regenerate controls. Mount the panel in `MarkdownEditor.tsx`.

**Stories fulfilled:** S-03 (gallery reads sidecar on mount), S-04, S-09, S-10, S-11 (panel auto-open)

**Files created:**

| File | Purpose |
|---|---|
| `components/MarkdownEditor/DiagramGalleryPanel/useDiagramSidecar.ts` | Hook: load sidecar on `mdEditorPath` change; expose `diagrams`, `reload`, `removeDiagram` |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.tsx` | Panel shell: absolute right panel, header (title + close), `[+ New ▾]` style menu, scrollable card list |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.module.css` | `.panel` block copied verbatim from `AnalysisPanel.module.css` |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.tsx` | Card: style badge, status, date, engine; View / Regenerate / Delete buttons (all `type="button"`) |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.module.css` | Card layout + badge variants |

**Files changed:**

| File | Change |
|---|---|
| `components/MarkdownEditor/MarkdownEditor.tsx` | Import + render `<DiagramGalleryPanel />` as sibling after `<AnalysisPanel />` at line 28 |

**Implementation notes (ARCHITECTURE_PROPOSAL.md §2, §4):**
- `DiagramGalleryPanel` guards internally: if `!mdEditorDiagramPanelOpen || !diagramsPath` return null
- Panel dismisses on close button click (`setMdEditorDiagramPanelOpen(false)`) and on file switch (store setter clears flag automatically)
- Delete: calls `removeDiagram(file, id)` from `diagramSidecar.ts`; if `diagrams.length === 0` after, close panel
- Regenerate: calls `handleDiagram` with the card's stored `style` preset prompt; disabled if a run is already active for this file
- `[+ New ▾]` style menu opens the same flow as the header pill but with a specific style pre-selected
- All `<button>` elements must carry `type="button"`
- No inline styles; all layout in `.module.css` using `tokens.css` vars

**Done when:**
- `npm run typecheck` exits 0
- Generating a diagram auto-opens the panel showing the new card
- Deleting a card removes it from the panel and updates the sidecar on disk
- Closing and re-opening the file restores all remaining cards (sidecar persists)
- Deleting the last card closes the panel

---

## Conversation 5 — Render Dispatch + Mermaid + Lightbox

**Goal:** Implement all three render paths (mermaid → SVG, ascii → `<pre>`, plantuml → source
+ notice) and the lightbox with CSS-transform zoom/pan.

**Stories fulfilled:** S-05, S-06, S-07, S-08

**Files created:**

| File | Purpose |
|---|---|
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender.tsx` | Dispatch: `style === 'mermaid'` → `<MermaidView>`; `style === 'ascii'` → `<pre>`; `style === 'plantuml'` → source `<pre>` + notice |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx` | Lazy `import('mermaid')`; module-level promise cache; `securityLevel:'strict'`; token theming via `getComputedStyle`; theme subscription via `useUiStore`; loading + error fallback states |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx` | Full-res modal; `<DiagramRender mode="full"/>`; wheel→scale (0.5×–4×); pointer drag→translate; Esc key + backdrop click close |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.module.css` | Lightbox overlay + content frame styles |

**Implementation notes (ARCHITECTURE_PROPOSAL.md §6, decisions D3–D5):**
- `mermaid` must be added to `studio/package.json` as a dependency (not devDependency)
- `MermaidView.tsx`: module-level promise cache so `import('mermaid')` + `initialize` run once per session; unique id per render call (`dg_<id>_<n>`); no hex literals — read all colors from `getComputedStyle(document.documentElement)` CSS vars
- `dangerouslySetInnerHTML` used only for the sanitized SVG mermaid returns — never for raw agent text
- On `mermaid.render` throw: show raw source in `<pre>` with error note — no crash
- Unmount-safety: capture `active` flag in the async `useEffect` body; bail if unmounted before import resolves
- ASCII `<pre>`: use text node (no `dangerouslySetInnerHTML`); monospace font from `tokens.css`
- PlantUML notice text exact string: `"PlantUML render engine not bundled. Paste source into plantuml.com to render."`
- Lightbox zoom/pan: wheel event → `scale` CSS custom property (clamp 0.5–4); pointer events for drag → `translateX`/`translateY` CSS custom properties; no `svg-pan-zoom` dependency
- All files ≤ 150 lines

**Done when:**
- `npm run typecheck` exits 0
- A mermaid diagram renders as SVG in a card and in the lightbox
- An ASCII diagram renders in `<pre>` with correct monospace font
- A PlantUML card shows source + the exact notice string
- Lightbox opens on "View"; wheel zooms 0.5×–4×; drag pans; Esc and backdrop click close
- `grep -n '#[0-9a-fA-F]' MermaidView.tsx` returns no matches

---

## Conversation 6 — Polish + Final Verification

**Goal:** Compliance pass across all files. Theme re-render on light/dark flip. All `type="button"`
attributes confirmed. Both TypeScript checks clean. Manual smoke test per ARCHITECTURE_PROPOSAL.md §10.

**Stories fulfilled:** S-12, S-13

**Files touched:** all files created or edited across Phases 1–5 (audit only — targeted fixes)

**Done when:**
- `npm run typecheck` exits 0 (zero errors, zero warnings treated as errors)
- `tsc --noEmit -p studio/tsconfig.node.json` exits 0
- `grep -n '#[0-9a-fA-F]' MermaidView.tsx` returns no matches
- Flipping Studio theme causes mermaid SVGs to re-render with updated token colors
- Manual smoke test: open MD → generate Mermaid (SVG) → generate ASCII → generate a 3rd → 3 cards → lightbox with zoom/pan → delete one → reload file → remaining cards persist
- Every `<button>` in `DiagramCard.tsx` and `DiagramLightbox.tsx` carries `type="button"`
- Every renderer file is ≤ 150 lines
