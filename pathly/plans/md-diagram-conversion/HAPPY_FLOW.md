# Happy Flow — md-diagram-conversion

**Branch:** `claude/md-diagram-conversion-wze4x3`
**Layer:** Studio (Electron / React renderer)

This document traces the primary end-to-end success path: a user opens a Markdown file,
generates a Mermaid flowchart, reads it in the lightbox, then confirms persistence by closing
and re-opening the file. It is the single coherent thread that exercises every major component
delivered by Conv 0–6.

---

## Primary scenario

> "I have a complex Markdown architecture document. I want to generate a flowchart diagram,
> view it at full size, and know it will still be there when I come back to the file tomorrow."

---

## End-to-end narrative

### Before the feature: baseline

The user opens `architecture.md` in the Markdown editor. The header shows two action pills:
Split and Analyze. There is no Diagram pill yet. Conv 0 confirms the codebase is clean and
the exact touchpoint line numbers are noted for builders.

---

### Conv 0 — Pre-flight (read-only)

No user-visible change. The builder runs both TypeScript checks, scans 10 touchpoints, and
records actual line numbers. The branch is clean and ready for code changes.

**Observable signal:** both `npm run typecheck` and `tsc --noEmit -p studio/tsconfig.node.json`
exit 0; all 10 MATCH results reported.

---

### Conv 1 — Store scaffold lands; nothing visible yet

The Zustand store is widened. `diagram?` is added to `MdEditorActionRecord`. Two new fields —
`mdEditorDiagramsPaths` and `mdEditorDiagramPanelOpen` — are added to state, initialized to
`{}` and `false`. Setters and selectors are added. The `setMdEditorPath` clear-block is
extended to also close the diagram panel on file switch.

The user sees no change in Studio — Split and Analyze pills are unaffected.

**Observable signal:** `npm run typecheck` exits 0; `setMdEditorAction(path, 'diagram', null)`
compiles without error.

---

### Conv 2 — Sidecar I/O and spawn hook exist; still no UI

`diagramSidecar.ts` is created: four pure functions (`readSidecar`, `writeSidecar`,
`appendDiagram`, `removeDiagram`) that read/write `<file>.diagrams.json` via
`window.pathly.fs`. Returns an empty `{ diagrams: [] }` on any failure — never throws.

`diagramPresets.ts` is created with 6 presets in two groups ("Renders anywhere":
flowchart, sequence, mindmap, architecture boxes; "Needs render engine": architecture/plantuml,
UML class/plantuml). Each preset references `{{FILE}}` and `{{SIDECAR}}` placeholders.

`useEditorDiagramAction.ts` is created as a clone of the split branch in
`useEditorAgentActions.ts`. The hook spawns a terminal tab, polls for
`<file>.diagrams.json` after PTY exit, validates the JSON structure, and calls
`setMdEditorDiagramsPath(sidecarPath, forFile)` on success. The stale-run reconciliation
array in the parent hook is widened from `['split', 'analyze']` to `['split', 'analyze', 'diagram']`.

**Observable signal:** a developer can call `handleDiagram(prompt)` from browser devtools
while `architecture.md` is open; a terminal tab appears, and `architecture.md.diagrams.json`
appears on disk after exit.

---

### Conv 3 — The Diagram pill appears in the editor header

The user now sees three pills: Split, Analyze, Diagram (Network icon, green tone).

**User action:** clicks the Diagram pill.

`PromptPeekModal` opens showing 6 diagram style presets. The user selects "Flowchart" and
confirms. `SendPreviewModal` appears with the title "Generate Diagram" and the Network icon.
The user confirms.

**What happens next:**
- The pill transitions to `running` state (spinner + "Generating...").
- A terminal tab opens in Studio showing the agent running.
- The agent reads `architecture.md`, generates Mermaid flowchart source, and writes
  `architecture.md.diagrams.json` with one entry.
- The PTY exits. The hook polls `architecture.md.diagrams.json` (up to 5 × 600 ms).
- The poll resolves. `setMdEditorDiagramsPath(sidecarPath, forFile)` is called.
- Because `forFile === s.mdEditorPath`, the setter sets `mdEditorDiagramPanelOpen = true`.
- The pill transitions to `success` state. The result chip shows "🖼 1".

**Observable signal:** the pill shows a chip reading "🖼 1"; a terminal tab opened and
closed; `architecture.md.diagrams.json` exists on disk.

---

### Conv 4 — The gallery panel appears; cards are browsable

`DiagramGalleryPanel` mounts in `MarkdownEditor.tsx` alongside `AnalysisPanel`. When
`mdEditorDiagramPanelOpen` becomes `true` (set by the setter in Conv 3), the panel slides in
from the right (absolute, width 380px, same shape as `AnalysisPanel`).

`useDiagramSidecar` reads the sidecar and populates `diagrams[]`. One `DiagramCard` renders,
showing: style badge "mermaid", status "ok", today's date, engine name.

The card preview area renders a placeholder `<div>` for now (Conv 5 fills in the real render).

**User can:**
- Click the close button to dismiss the panel.
- Click "Delete" on the card — `removeDiagram` removes the entry from the sidecar on disk;
  because `diagrams.length === 0` after deletion, the panel closes and `mdEditorDiagramPanelOpen`
  is set to `false`.
- Click "Regenerate" on the card — re-spawns a new diagram run; on completion, a second card
  appears in the gallery (the agent appends a new entry, the old card remains).

**User reopens the file:** `useDiagramSidecar` reads the sidecar on mount and cards reappear
without re-running the agent.

**Observable signal:** panel auto-opens on run complete; card list shows; delete updates disk
and closes panel if last card; file reload restores cards.

---

### Conv 5 — Diagrams render; lightbox opens with zoom/pan

`DiagramRender` dispatches by `diagram.style`:
- `mermaid` → `MermaidView`: lazy-imports mermaid, renders SVG via `mermaid.render()`,
  inserts the sanitized SVG via `dangerouslySetInnerHTML`. Theme tokens read from
  `getComputedStyle`. No hex literals.
- `ascii` → `<pre>` with monospace font from `tokens.css`. Text node only.
- `plantuml` → `<pre>` source + notice "PlantUML render engine not bundled. Paste source
  into plantuml.com to render."

**User action:** clicks "View" on the flowchart card.

`DiagramLightbox` opens as a full-screen overlay. `DiagramRender` renders in `mode="full"` —
no size clamp, horizontal scroll for ASCII. For Mermaid, the SVG fills the lightbox frame.

User scrolls the mouse wheel — the SVG scales from 1× up to 4× (or down to 0.5×). User
click-drags to pan. User presses Esc — lightbox closes.

**Observable signal:** SVG visible in card and lightbox; wheel zooms 0.5×–4×; drag pans;
Esc and backdrop click both close; no hex literals in `MermaidView.tsx`; `mermaid` is in
`studio/package.json`.

---

### Conv 6 — Polish and final verification

Compliance sweep: `type="button"` audit, hex literal check, line budget check, PlantUML
notice exact string, theme re-render verification. Both TypeScript checks clean. Full manual
smoke test (9 steps) passes.

**Theme flip test:** user flips Studio to light mode — all Mermaid SVGs re-render with updated
`themeVariables` read from the new `getComputedStyle` values. No hex drift.

**Observable signal:** `npm run typecheck` exits 0; `tsc --noEmit -p studio/tsconfig.node.json`
exits 0; all compliance grep checks return clean; all 9 manual smoke steps pass.

---

## Milestone table

| Milestone | Delivered by | Artifact on disk / in-app | "It's working" signal |
|---|---|---|---|
| Baseline is clean | Conv 0 | none | both typechecks exit 0; 10 MATCH results |
| Store accepts 'diagram' | Conv 1 | uiStore.ts (widened) | `setMdEditorAction(path,'diagram',null)` compiles |
| Sidecar written on run | Conv 2 | `<file>.diagrams.json` created | file appears on disk after devtools call |
| Preset picker has 6 options | Conv 2 | diagramPresets.ts | 6 entries visible in `DIAGRAM_PRESETS` |
| Pill visible in header | Conv 3 | EditorHeader.tsx (3rd pill) | third pill renders between Analyze and edge |
| Run spawns a terminal tab | Conv 3 | terminal tab in Studio | tab opens, spinner on pill |
| Result chip shows count | Conv 3 | pill chip "🖼 1" | chip visible after run completes |
| Panel auto-opens | Conv 3 (flag) + Conv 4 (panel) | DiagramGalleryPanel mounted | panel slides in without user click |
| Cards show from sidecar | Conv 4 | DiagramCard list | one card with badge, date, engine |
| Delete updates disk | Conv 4 | sidecar has one fewer entry | file open shows one fewer card |
| Reload restores cards | Conv 4 | sidecar read on mount | cards appear without re-running agent |
| Mermaid SVG in card | Conv 5 | MermaidView renders SVG | SVG visible (not blank, not spinner) |
| ASCII pre in card | Conv 5 | DiagramRender routes ascii | monospace text, box chars correct |
| PlantUML source + notice | Conv 5 | DiagramRender routes plantuml | exact notice string visible |
| Lightbox opens | Conv 5 | DiagramLightbox renders | overlay appears on "View" click |
| Zoom/pan works | Conv 5 | CSS transform on renderWrap | wheel changes scale; drag moves SVG |
| TypeScript fully clean | Conv 6 | zero typecheck errors | both checks exit 0 |
| Theme re-render | Conv 6 | MermaidView re-renders | SVG color changes on theme flip |

---

## State / artifacts at each major gate

```
After Conv 0
  In-flight branch: claude/md-diagram-conversion-wze4x3
  Files changed: none
  State artifacts: none
  Notes: actual line numbers for touchpoints recorded

After Conv 1
  Files changed: uiStore.ts, editorCli.ts, services/skillCompose.ts
  State artifacts: mdEditorDiagramsPaths={}, mdEditorDiagramPanelOpen=false
  Notes: no UI change visible to user

After Conv 2
  Files added: diagramSidecar.ts, diagramPresets.ts, useEditorDiagramAction.ts
  State artifacts: none yet (hook not wired into UI)
  Disk artifact: <file>.diagrams.json (only via devtools test)

After Conv 3
  Files changed: EditorHeader.tsx
  In-app: 3rd pill visible; full generate flow usable from UI
  Disk artifact: <file>.diagrams.json written on each run
  Store state: mdEditorDiagramsPath set on success; mdEditorDiagramPanelOpen=true (panel not mounted yet — no visible effect)

After Conv 4
  Files added: DiagramGalleryPanel/, useDiagramSidecar.ts, DiagramCard/
  Files changed: MarkdownEditor.tsx (panel mounted)
  In-app: panel opens automatically; cards visible; delete and regenerate work
  Disk artifact: sidecar updated on delete

After Conv 5
  Files added: DiagramRender/, MermaidView.tsx, DiagramLightbox/
  Files changed: studio/package.json (mermaid added), DiagramCard (stub replaced)
  In-app: all 3 render types; lightbox with zoom/pan

After Conv 6
  Files changed: any compliance fixes found during audit
  Final state: all typechecks clean; all smoke steps pass; branch ready for PR
```

---

## Stories cross-reference

| Story | Happy flow step |
|---|---|
| S-01 Diagram button in header | Conv 3: pill appears |
| S-02 AI generates diagram source | Conv 2 (hook) + Conv 3 (UI wiring) |
| S-03 Sidecar persists across reload | Conv 2 (I/O) + Conv 4 (gallery reads on mount) |
| S-04 Gallery panel with cards | Conv 4: panel + card list |
| S-05 Mermaid renders as SVG | Conv 5: MermaidView |
| S-06 ASCII renders in pre | Conv 5: DiagramRender ascii branch |
| S-07 PlantUML shows source + notice | Conv 5: DiagramRender plantuml branch |
| S-08 Lightbox with zoom/pan | Conv 5: DiagramLightbox |
| S-09 Delete a diagram card | Conv 4: delete button + sidecar update |
| S-10 Regenerate a diagram card | Conv 4: regenerate → re-spawn run |
| S-11 Panel auto-opens on run complete | Conv 1 (store setter) + Conv 3 (chip) + Conv 4 (panel) |
| S-12 TypeScript clean | Conv 6 (final); partial gates Conv 1–5 |
| S-13 Theme re-render | Conv 6 |
