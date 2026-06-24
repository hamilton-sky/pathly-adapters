# MD → Diagram — Feature Spec

**Branch:** `claude/md-diagram-conversion-wze4x3`
**Layer:** Studio (Electron/React renderer)
**Status:** Spec / planned (not yet implemented)

---

## 1. Summary

Add a third AI action to the Markdown editor header — a **Diagram** action — that
turns the open `.md` file into one or more diagrams explaining its content.
Generated diagrams persist in a **sidecar gallery** that stays with the file; the
user can keep, regenerate, view full-size, or delete each one.

It is a sibling of the existing **AI Split** and **AI Analyze** actions: same
configuration model, same spawn pipeline, same UI shape — only the prompt and the
output differ.

Supported styles (v1): **Mermaid** (rendered), **ASCII** (rendered), **PlantUML**
(source-only; live render deferred).

---

## 2. Goals / Non-goals

### Goals
- One-click generation of explanatory diagrams from an MD file.
- Multiple diagrams per file, accumulated (not overwritten).
- Diagrams persist alongside the file and survive reload.
- Per-card actions: view full-resolution, regenerate, delete.
- Reuse the existing shared AI-action infrastructure (engine picker, prompt
  config modal, spawn pipeline, pill UI) — Diagram is a new consumer, not a new
  system.

### Non-goals (deferred)
- The richer per-**model** configuration picker (tracked as the `ai-action-config`
  feature). Only the seam is left; when that lands on the shared config layer, the
  Diagram action inherits it automatically.
- PlantUML / D2 live rendering (needs a bundled render engine).
- Inserting a generated diagram back into the MD body (sidecar-only in v1).

---

## 3. Shared configuration model (reused, not rebuilt)

The Diagram action plugs into the same layer that AI Split, AI Analyze, and the
comment/edit action already share. "Same style and functionality, just different
output."

| Shared piece | File | Role |
|---|---|---|
| Engine picker | `editorCli.ts` → `EDITOR_CLIS` (from `ADAPTER_META`) | The engine/model dropdown — one list, all actions |
| Per-action persistence | `editorCli.ts` → `loadEditorCli`/`saveEditorCli` + `CLI_KEY_*` | Each action remembers its own engine choice |
| Prompt config UI | `PromptPeekModal` | The gear (⚙) modal — edit prompt, pick preset + engine |
| Presets | `actionPresets.ts` | Each action supplies its own preset list into the same modal |
| Spawn pipeline | `useEditorAgentActions.ts` → `buildCliArgv` → `buildHeadlessArgv` | Run → spawn engine → poll output file → set status |
| Pill UI | `SplitPill` | Segmented control: Run │ gear │ result |

**Diagram action contributes only:**
1. Its own preset set (`diagramPresets.ts`) — diagram styles instead of split/analyze presets.
2. Its own output handling — writes the sidecar gallery + renders cards, instead of a `.split.draft` diff or `.analysis` report.

**Engine vs. model nuance:** the shared picker currently selects the *engine*
(claude / codex), not a specific model id. The Diagram action reuses it as-is, so it
has the same selection granularity as Split/Analyze on day one. The richer per-model
picker is added once, to the shared layer, and all actions gain it together.

---

## 4. Sidecar format — `<file>.diagrams.json`

```jsonc
{
  "version": 1,
  "source": "ROADMAP.md",
  "diagrams": [
    {
      "id": "dg_<base36>",
      "title": "Pipeline flow",
      "style": "mermaid",          // mermaid | ascii | plantuml
      "content": "flowchart LR\n ...",
      "status": "kept",            // draft | kept
      "engine": "claude",
      "model": null,               // seam for the future per-model picker
      "createdAt": "2026-06-24T..."
    }
  ]
}
```

The generating agent **appends** an entry (read-modify-write), so multiple diagrams
accumulate for one file.

---

## 5. UI

### 5.1 Header pill
`DiagramPill` (clone of `SplitPill`) sits in the editor header after the AI Analyze
pill. Three segments:
- **Run** — generate a diagram in the selected style.
- **Style / gear (⚙)** — style picker + the shared `PromptPeekModal` (prompt + engine).
  Styles grouped **"Renders anywhere"** (Mermaid, ASCII) vs **"Needs render engine"**
  (PlantUML).
- **Result chip (🖼 N)** — opens the gallery panel; shows diagram count.

### 5.2 Gallery panel
`DiagramGalleryPanel` reuses the side-panel slot (same area as `AnalysisPanel`; one
panel open at a time). Lists `DiagramCard`s — each shows style badge, status, date,
engine, and **View / Regenerate / Delete**. New diagrams accumulate via `[+ New ▾]`.

### 5.3 Full-resolution view
Clicking a card (or **View**) opens `DiagramLightbox` — a large centered modal
(clone of the existing modal shell) rendering the diagram full-size:
- Mermaid: SVG scaled to fit, with zoom (scroll/pinch) + pan (drag).
- ASCII: large monospace view.
- Esc / backdrop-click closes.
The card itself stays a compact preview; the lightbox is where complex diagrams are read.

---

## 6. Rendering

| Style | v1 behavior | Dependency |
|---|---|---|
| Mermaid | `MermaidView` lazy-imports `mermaid`, `mermaid.render()` → SVG, themed from `tokens.css` vars | add `mermaid` (renderer dep) |
| ASCII | monospace `<pre>` | none |
| PlantUML | source in `<pre>` + "render engine not bundled yet" notice | none (v1) |

---

## 7. Files

### Add
```
EditorHeader/DiagramPill/DiagramPill.tsx + .module.css      # clone of SplitPill
EditorHeader/diagramPresets.ts                               # DIAGRAM_STYLES + prompts
EditorHeader/hooks/useEditorDiagramAction.ts                # clone of split flow
MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.tsx + .module.css
MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.tsx + .module.css
MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender.tsx
MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx
MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx + .module.css
```

### Edit
- `EditorHeader/EditorHeader.tsx` — render `<DiagramPill>` after AI Analyze pill.
- `EditorHeader/editorCli.ts` — add `CLI_KEY_DIAGRAM`, `PRESET_KEY_DIAGRAM`.
- `store/uiStore.ts` — add `'diagram'` action slot; `mdEditorDiagramsPath`,
  `mdEditorDiagramPanelOpen` + setters + selectors (mirror analysis).
- `MarkdownEditor.tsx` — render `<DiagramGalleryPanel>` in the panel slot.
- `studio/package.json` — add `mermaid`.

No new IPC expected — sidecar read/write uses existing `window.pathly.fs.read/write/delete`
(as `AnalysisPanel` does).

---

## 8. Prompt design (`diagramPresets.ts`)

Each style has a prompt template with `{{FILE}}` + `{{SIDECAR}}` placeholders
instructing the agent to: read the MD file, produce a diagram in the chosen syntax,
and append a JSON entry to the sidecar. Presets:
- Mermaid: `flowchart`, `sequence`, `mindmap`, `architecture`
- ASCII: `boxes`
- PlantUML: `uml`

---

## 9. Compliance (Studio UI rules)

- Every renderer file ≤ 150 lines (gallery is split into Panel / Card / Render /
  MermaidView / Lightbox for this reason).
- No inline styles; all CSS in `.module.css` using `tokens.css` vars; `data-style` /
  `data-status` attributes for card variants.
- All `<button>` have explicit `type="button"`; responsive (`min-width: 0`,
  verified ≤ 200px).
- Per-action localStorage persistence mirrors the split/analyze keys.

---

## 10. Verification

- `npm run typecheck` (renderer) + `tsc --noEmit -p studio/tsconfig.node.json` if any
  main-process change — both clean.
- Manual: open an MD file → generate Mermaid (renders SVG) → generate ASCII (renders
  in `<pre>`) → generate a 3rd → all appear as cards → click a card → opens
  full-resolution lightbox with zoom/pan → delete one → reload file → remaining
  diagrams persist from the sidecar.

---

## 11. Commit policy

- Develop on `claude/md-diagram-conversion-wze4x3`.
- No PR unless explicitly requested. Never push to master.
