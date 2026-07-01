# Feature Index — md-diagram-conversion

**Branch:** `claude/md-diagram-conversion-wze4x3`
**Rigor:** standard
**FSM state:** PLANNING
**Layer:** Studio (Electron / React renderer only)

---

## What this feature builds

A third AI action — Diagram — in the Markdown editor header, alongside the existing Split and Analyze actions. Users click Run, an AI agent generates diagram source (Mermaid / ASCII / PlantUML), the output is persisted as a per-file sidecar (`.diagrams.json`), and a gallery panel shows all diagrams for the current file with View (lightbox with zoom/pan), Regenerate, and Delete controls.

## Who it is for

Studio users who work with Markdown files and want AI-generated visual explanations — developers and technical writers already using the Pathly Studio Markdown editor.

---

## Layer map

All new files are under `studio/src/renderer/src/` unless noted. Paths are relative to that root.

### Files to create

| File | Purpose |
|---|---|
| `components/MarkdownEditor/EditorHeader/diagramPresets.ts` | `DIAGRAM_STYLES` + 6 `PromptPreset[]` (flowchart, sequence, mindmap, architecture, boxes, uml) |
| `components/MarkdownEditor/EditorHeader/hooks/useEditorDiagramAction.ts` | Spawn hook — clone of split branch; output = `.diagrams.json`; compose kind `'diagram'` |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.tsx` | Panel shell + card list + `[+ New ▾]` style menu |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.module.css` | Absolute right-panel shape (copy of AnalysisPanel `.panel` block) |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.tsx` | Card: style badge, status, date, engine + View/Regenerate/Delete |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.module.css` | Card styles |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender.tsx` | Dispatch: mermaid → `MermaidView`; ascii → `<pre>`; plantuml → source + notice |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx` | Lazy mermaid import + token theming + strict mode + singleton cache |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx` | Full-res modal with zoom/pan |
| `components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.module.css` | Lightbox styles |
| `components/MarkdownEditor/DiagramGalleryPanel/diagramSidecar.ts` | Pure I/O: `readSidecar`, `appendDiagram`, `removeDiagram`, `writeSidecar` |
| `components/MarkdownEditor/DiagramGalleryPanel/useDiagramSidecar.ts` | Data hook: load sidecar on file change |

### Files to edit

| File | Change |
|---|---|
| `store/uiStore.ts` | Widen `MdEditorActionRecord` to add `diagram?`; add `mdEditorDiagramsPaths`, `mdEditorDiagramPanelOpen`, setters, selectors |
| `components/MarkdownEditor/EditorHeader/editorCli.ts` | Add `CLI_KEY_DIAGRAM`, `PRESET_KEY_DIAGRAM` |
| `components/MarkdownEditor/EditorHeader/EditorHeader.tsx` | Third `<ActionPill>`, `PromptPeekModal`, `SendPreviewModal` branch, `pendingRun.kind: 'diagram'` |
| `services/skillCompose.ts` | Add `'diagram'` to `ComposeTransform.kind` |
| `components/MarkdownEditor/MarkdownEditor.tsx` | Mount `<DiagramGalleryPanel />` in the panel slot |
| `studio/package.json` | Add `mermaid` dependency |

---

## Key decisions (D1–D6)

**D1 — No DiagramPill component.** SPEC said "clone SplitPill" but there is no SplitPill. Pills are a single shared props-driven `ActionPill`. Add a third `<ActionPill>` instance. Zero new pill component.

**D2 — Copy the `.panel` CSS block, do not extract a shared SidePanel.** `AnalysisPanel` and `DiagramGalleryPanel` share an absolute-positioned right-panel shape. Two consumers of a 13-line CSS block is below the extraction threshold.

**D3 — DiagramRender takes `mode: 'card' | 'full'`.** The same component renders compact card previews and full lightbox views. Zoom/pan transform lives in `DiagramLightbox`, not `DiagramRender`.

**D4 — Agent owns sidecar append; renderer only reads + deletes.** No optimistic card. Panel auto-opens after the `pollForFile` poll resolves post-run. Matches how Analyze treats `.analysis`.

**D5 — Zoom/pan = CSS transform, not a library.** `wheel → scale` + `drag → translate` via a CSS custom property. No `svg-pan-zoom` dependency.

**D6 — PlantUML is source-only.** Styled group "Needs render engine" in the picker. Card shows source in `<pre>` + a "render engine not bundled yet" notice.

---

## Constraints

- Every renderer file ≤ 150 lines.
- No inline styles (`style={{}}`); all in `.module.css` using `tokens.css` vars.
- `npm run typecheck` (renderer) and `tsc --noEmit -p studio/tsconfig.node.json` both clean before done.
- No new IPC channels — sidecar I/O reuses `window.pathly.fs.read / write / delete`.
- `mermaid` added to `studio/package.json`; lazy-imported (`import('mermaid')`) to avoid initial-bundle inflation.
- `securityLevel: 'strict'` for all mermaid renders (untrusted agent output).
- All `<button>` elements must carry `type="button"`.
- Branch: `claude/md-diagram-conversion-wze4x3`. No push to master.

---

## Conversations at a glance

| Conv | Topic | Gate |
|---|---|---|
| 0 | Pre-flight (baseline verification) | existing tests pass; touchpoint scan clean |
| 1 | State scaffold + CLI/preset keys | typecheck clean; existing pills unaffected |
| 2 | Sidecar I/O + spawn hook | spawns tab, writes sidecar, sets run slot |
| 3 | Header pill | Run generates diagram; result chip shows count |
| 4 | Gallery panel + card | cards render from sidecar; delete/regenerate work |
| 5 | Render dispatch + Mermaid + Lightbox | all three render types; lightbox with zoom/pan |
| 6 | Polish + final verification | both typechecks clean; manual smoke test passes |

---

## Story map

| Story | Delivered by Conv |
|---|---|
| S-01: Diagram action button in header | Conv 3 |
| S-02: AI generates diagram source | Conv 2, Conv 3 |
| S-03: Sidecar persistence survives reload | Conv 2 (I/O), Conv 4 (gallery reads it) |
| S-04: Gallery panel with cards | Conv 4 |
| S-05: Mermaid renders as SVG | Conv 5 |
| S-06: ASCII renders in `<pre>` | Conv 5 |
| S-07: PlantUML shows source + notice | Conv 5 |
| S-08: Lightbox with zoom/pan | Conv 5 |
| S-09: Delete a diagram card | Conv 4 |
| S-10: Regenerate a diagram card | Conv 4 |
| S-11: Panel auto-opens on run complete | Conv 3 (flag), Conv 4 (panel) |
| S-12: TypeScript clean; no regressions | Conv 6 |
| S-13: Theme re-render on light/dark flip | Conv 6 |
