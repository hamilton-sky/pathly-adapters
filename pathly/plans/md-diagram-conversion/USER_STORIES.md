# User Stories — md-diagram-conversion

_Decomposed from PO_NOTES.md. Each story is tagged with the conversation that delivers it._

---

## S-01: Diagram action button appears in the editor header

**As a** Studio user working with Markdown files,
**I want** a Diagram button in the editor header alongside Split and Analyze,
**So that** I can trigger AI diagram generation without leaving the editor.

**Acceptance criteria:**
- [ ] A third `<ActionPill>` with `ariaName="Diagram"` is rendered in `EditorHeader.tsx` after the Analyze pill.
- [ ] The pill is visible when any `.md` file is open.
- [ ] The pill shows an idle state (Lucide icon, no spinner) when no diagram run is active.
- [ ] Clicking the pill opens the `PromptPeekModal` or triggers the `SendPreviewModal` confirm step (same flow as Split/Analyze).
- [ ] `npm run typecheck` is clean after the pill is added.
- [ ] The Split and Analyze pills are unaffected (visual regression: both still render and respond to their own run state).

**Delivered by:** Conv 3

---

## S-02: Run generates AI diagram source

**As a** Studio user,
**I want** clicking Run to spawn an AI agent that writes diagram source to a sidecar file,
**So that** diagram content is generated and persisted without manual copy-paste.

**Acceptance criteria:**
- [ ] Clicking Run (after the preview modal) spawns a terminal tab visible in Studio.
- [ ] The pill transitions to `running` state during generation (spinner + "Generating…").
- [ ] The agent writes output to `<file>.diagrams.json` adjacent to the `.md` file.
- [ ] On success, the pill transitions to `success` state with a result chip showing the diagram count.
- [ ] On failure (agent exits non-zero or writes invalid JSON), the pill shows `error` state and a toast appears.
- [ ] A second click while already running is a no-op (run-guard prevents double-spawn for the same file).

**Delivered by:** Conv 2 (spawn hook), Conv 3 (header wiring)

---

## S-03: Sidecar persists across file close and reload

**As a** Studio user,
**I want** previously generated diagrams to reappear when I re-open the same Markdown file,
**So that** I don't need to regenerate diagrams I already created.

**Acceptance criteria:**
- [ ] When the editor loads a `.md` file, `useDiagramSidecar` checks for `<file>.diagrams.json` and reads it if present.
- [ ] All diagram cards from the sidecar are displayed in the gallery without running the AI action again.
- [ ] If the sidecar file is missing or contains invalid JSON, the gallery shows an empty state (no crash).
- [ ] Deleting all diagram cards and reloading shows an empty gallery (sidecar has been updated or removed).

**Delivered by:** Conv 2 (sidecar I/O), Conv 4 (gallery reads sidecar on mount)

---

## S-04: Gallery panel shows all diagram cards for the current file

**As a** Studio user,
**I want** a side panel listing all generated diagrams for the current file,
**So that** I can browse, compare, and manage multiple diagram iterations.

**Acceptance criteria:**
- [ ] `DiagramGalleryPanel` opens as an absolute right panel (same shape as `AnalysisPanel`, width 380px) when triggered.
- [ ] Each diagram card shows: style badge (mermaid / ascii / plantuml), status, ISO date, and engine name.
- [ ] A compact inline preview is rendered per card (`DiagramRender` in `mode="card"`).
- [ ] The panel is dismissed by clicking its close button or switching files.
- [ ] When switching files, the panel clears and loads diagrams for the new file.
- [ ] The panel is scrollable when more cards than panel height allows.

**Delivered by:** Conv 4

---

## S-05: Mermaid diagrams render as SVG

**As a** Studio user,
**I want** Mermaid-style diagrams to render as SVG in the gallery card and lightbox,
**So that** I can read flowcharts, sequence diagrams, and architecture diagrams as visual graphics.

**Acceptance criteria:**
- [ ] `MermaidView.tsx` lazy-imports `mermaid` (dynamic `import('mermaid')`) — no static import.
- [ ] The SVG is generated via `mermaid.render(uniqueId, content)` and inserted via `dangerouslySetInnerHTML` (only the sanitized SVG, never raw agent text).
- [ ] `securityLevel: 'strict'` is passed to `mermaid.initialize()`.
- [ ] Theme variables are read from `getComputedStyle(document.documentElement)` — no hard-coded hex values in `MermaidView.tsx`.
- [ ] A `loading` state is shown while the async import resolves (no blank flash in tests).
- [ ] If `mermaid.render` throws, the card shows the raw source in a `<pre>` with an error note — no crash.
- [ ] `mermaid` is present in `studio/package.json` as a dependency.

**Delivered by:** Conv 5

---

## S-06: ASCII diagrams render in a `<pre>` block

**As a** Studio user,
**I want** ASCII-art diagrams to render in a monospace `<pre>` block,
**So that** box-drawing characters display correctly without interpretation as HTML.

**Acceptance criteria:**
- [ ] `DiagramRender.tsx` routes `style === 'ascii'` diagrams to a `<pre>` element (text node, no `dangerouslySetInnerHTML`).
- [ ] The `<pre>` block uses a monospace font from `tokens.css` (no hard-coded font families).
- [ ] In `mode="full"` (lightbox), the `<pre>` is rendered at a larger font size with horizontal scroll if content exceeds width.

**Delivered by:** Conv 5

---

## S-07: PlantUML diagrams show source with a notice

**As a** Studio user,
**I want** PlantUML-style diagrams to show their source code with a clear "render engine not bundled" notice,
**So that** I can copy the source to an external PlantUML renderer while understanding why it is not rendered inline.

**Acceptance criteria:**
- [ ] `DiagramRender.tsx` routes `style === 'plantuml'` diagrams to a `<pre>` source block + a notice text below it.
- [ ] The notice says exactly: "PlantUML render engine not bundled. Paste source into plantuml.com to render."
- [ ] The style picker in `diagramPresets.ts` groups plantuml under a "Needs render engine" label.
- [ ] No external HTTP request is made for plantuml rendering.

**Delivered by:** Conv 5

---

## S-08: Lightbox opens with full-resolution view and zoom/pan

**As a** Studio user,
**I want** to click a diagram card to open a full-resolution lightbox with zoom and pan,
**So that** I can read complex diagrams that are too small in the card preview.

**Acceptance criteria:**
- [ ] Clicking "View" on any card opens `DiagramLightbox.tsx` overlaid on the panel.
- [ ] The lightbox renders the same diagram via `<DiagramRender mode="full" />` at full panel width.
- [ ] Mouse wheel zoom: scaling from 0.5× to 4× via `transform: scale()` on the SVG wrapper.
- [ ] Click-drag pan: translate the SVG wrapper via pointer events.
- [ ] The lightbox closes on Esc key or backdrop click.
- [ ] No `svg-pan-zoom` or other external library is used — zoom/pan is CSS transform only.
- [ ] `DiagramLightbox.tsx` is ≤ 150 lines.

**Delivered by:** Conv 5

---

## S-09: Delete a diagram card

**As a** Studio user,
**I want** to delete individual diagram cards from the gallery,
**So that** I can remove stale or failed diagrams without affecting the rest.

**Acceptance criteria:**
- [ ] Each card has a Delete button (`type="button"`).
- [ ] Clicking Delete calls `removeDiagram(file, id)` in `diagramSidecar.ts`, which reads the sidecar, filters out the matching `id`, and writes the updated sidecar.
- [ ] The card disappears from the gallery immediately after deletion (optimistic UI or reload).
- [ ] If the last card is deleted, the gallery panel closes and `mdEditorDiagramPanelOpen` is set to `false`.
- [ ] After deletion, reloading the file confirms the card is gone (sidecar was updated on disk).

**Delivered by:** Conv 4

---

## S-10: Regenerate a diagram card

**As a** Studio user,
**I want** to regenerate a specific diagram from its card,
**So that** I can get a fresh version of a diagram (with an updated prompt or file content) without opening the header pill.

**Acceptance criteria:**
- [ ] Each card has a Regenerate button (`type="button"`).
- [ ] Clicking Regenerate spawns a new diagram run using the card's stored `style` (and the current prompt preset for that style).
- [ ] The spawned run appends a new entry to the sidecar (agent-side append) — the old card is NOT overwritten.
- [ ] The gallery refreshes to show the new card once the run completes and the poll resolves.
- [ ] The run-guard still applies: if a run is already in progress for this file, Regenerate is disabled or no-ops.

**Delivered by:** Conv 4

---

## S-11: Gallery panel auto-opens when a diagram run completes

**As a** Studio user,
**I want** the gallery panel to open automatically when a diagram run finishes,
**So that** I see my newly generated diagram immediately without having to click again.

**Acceptance criteria:**
- [ ] `setMdEditorDiagramsPath` in `uiStore.ts` sets `mdEditorDiagramPanelOpen = true` when the path being set matches `s.mdEditorPath` (the currently visible file).
- [ ] If the run finishes while the user is on a different file, the panel does NOT open for the current file.
- [ ] Clicking the result chip on the Diagram pill also toggles `mdEditorDiagramPanelOpen`.

**Delivered by:** Conv 1 (store setter logic), Conv 3 (result chip wiring)

---

## S-12: TypeScript type-checks clean; existing actions do not regress

**As a** developer,
**I want** both TypeScript checks to pass with zero new errors,
**So that** the feature does not introduce type debt or break existing editor functionality.

**Acceptance criteria:**
- [ ] `npm run typecheck` exits 0 in the `studio/` directory.
- [ ] `tsc --noEmit -p studio/tsconfig.node.json` exits 0.
- [ ] The Split and Analyze pills continue to render and respond to their respective run states (no prop-type collision from the widened union).
- [ ] `setMdEditorAction` accepts `'split' | 'analyze' | 'diagram'` — confirmed by a TypeScript call-site compile check, not a runtime test.

**Delivered by:** Conv 6 (final pass); partial gates at Conv 1, 2, 3, 4, 5

---

## S-13: Mermaid diagrams re-render when the Studio theme changes

**As a** Studio user who switches between light and dark mode,
**I want** Mermaid SVGs to re-render with the updated color tokens,
**So that** diagrams are always readable in the current theme.

**Acceptance criteria:**
- [ ] `MermaidView.tsx` subscribes to `useUiStore`'s theme value as a `useEffect` dependency.
- [ ] When the theme changes, `mermaid.initialize()` is called with updated `themeVariables` (re-read from `getComputedStyle`) and the SVG is re-rendered.
- [ ] If repeated `initialize()` calls prove unsafe during implementation, `MermaidView` is force-remounted via a `key` prop on theme change (fallback — must be documented in the PR).
- [ ] No hex literals appear in `MermaidView.tsx` (verified by `grep -n '#[0-9a-fA-F]' MermaidView.tsx` returning no matches).

**Delivered by:** Conv 6
