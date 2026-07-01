# Progress — md-diagram-conversion

**Branch:** `claude/md-diagram-conversion-wze4x3`
**Updated:** 2026-06-29

| Conv | Topic | Status | Done When |
|---|---|---|---|
| 0 | Pre-flight verification | TODO | `npm run typecheck` exits 0; `tsc --noEmit -p studio/tsconfig.node.json` exits 0; touchpoint scan confirms scout findings match live file shapes |
| 1 | State scaffold + CLI/preset keys | TODO | `uiStore.ts` accepts `'diagram'` action; `setMdEditorDiagramsPath` auto-opens panel for current file; `CLI_KEY_DIAGRAM` + `PRESET_KEY_DIAGRAM` exported; `'diagram'` in `ComposeTransform.kind`; typecheck clean; Split + Analyze pills unaffected |
| 2 | Sidecar I/O + spawn hook | TODO | `diagramSidecar.ts` reads/writes `.diagrams.json`; `diagramPresets.ts` exports 6 presets; `useEditorDiagramAction.ts` spawns a terminal tab, writes sidecar, sets run slot; run-guard blocks double-spawn; typecheck clean |
| 3 | Header pill | TODO | Third `<ActionPill ariaName="Diagram">` renders after Analyze; clicking Run spawns agent + shows spinner; result chip shows diagram count; chip toggles `mdEditorDiagramPanelOpen`; typecheck clean |
| 4 | Gallery panel + card | TODO | `DiagramGalleryPanel` auto-opens on run complete; cards render from sidecar; Delete removes card + updates disk; Regenerate spawns new run; last-delete closes panel; file reload restores cards; typecheck clean |
| 5 | Render dispatch + Mermaid + Lightbox | TODO | Mermaid renders as SVG (`securityLevel:'strict'`); ASCII renders in `<pre>`; PlantUML shows source + exact notice; lightbox opens with zoom/pan; Esc + backdrop close; no hex literals in `MermaidView.tsx`; typecheck clean |
| 6 | Polish + final verification | TODO | Both typechecks (`npm run typecheck` + `tsc -p tsconfig.node.json`) exit 0; theme flip re-renders mermaid SVGs; all `type="button"` present; all files ≤ 150 lines; manual smoke test passes |
