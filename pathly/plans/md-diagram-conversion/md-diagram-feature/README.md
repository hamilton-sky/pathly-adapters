# Diagram feature — components

TypeScript React components for the Markdown-editor **Diagram** action: a one-click
agent run writes a `<file>.diagrams.json` sidecar, a right-docked gallery renders
Mermaid / ASCII / PlantUML cards, and a zoomable lightbox shows full-resolution views.

Every component is **themed entirely from the project's `src/styles/tokens.css`** — no
hard-coded colours. All surfaces, borders, radii, type sizes and signal hues are
`var(--…)` tokens, so the feature inherits all 12 shipped themes (Dark, Light, Nord,
Mocha, Dracula, …) and re-themes automatically, including the live Mermaid SVGs.

## Layout

Drop this folder's contents into `src/components/MarkdownEditor/` — every relative
import is written for that location (same depth as the existing `AnalysisPanel/`,
`EditorHeader/` siblings).

```
MarkdownEditor/
├─ diagramTypes.ts                       shared types + sidecar path helper
├─ EditorHeader/
│  ├─ diagramPresets.ts                  6 presets (2 groups) + CLI/preset keys
│  └─ hooks/
│     └─ useEditorDiagramAction.ts       spawn hook (clone of the Analyze branch)
└─ DiagramGalleryPanel/
   ├─ DiagramGalleryPanel.tsx / .module.css     right panel + card list + lightbox host
   ├─ diagramSidecar.ts                  pure I/O: read / remove (agent owns append)
   ├─ useDiagramSidecar.ts               data hook: load on file change
   ├─ STORE_PATCH.md                     exact uiStore.ts additions
   ├─ DiagramCard/
   │  └─ DiagramCard.tsx / .module.css   badge · status · date·engine · render · actions
   ├─ DiagramRender/
   │  ├─ DiagramRender.tsx / .module.css  style dispatch (mermaid / ascii / plantuml)
   │  └─ MermaidView.tsx                 lazy mermaid → SVG, themed from tokens
   └─ DiagramLightbox/
      └─ DiagramLightbox.tsx / .module.css  full-res overlay, wheel-zoom + drag-pan, Esc
```

> Each React component lives in its own folder with its `.module.css` beside it.
> The plain `.ts` files (types, sidecar I/O, hook, presets) carry no styling and sit
> next to their consumers, matching the repo's existing convention.

Plus a `patched/` folder holding the three **existing** files to overwrite (full versions,
not diffs):

```
patched/
├─ store/uiStore.ts                      + diagram slot · paths · panel flag · selectors
├─ EditorHeader/EditorHeader.tsx         + third ActionPill ("Diagram") fully wired
└─ MarkdownEditor/MarkdownEditor.tsx     + mounts <DiagramGalleryPanel/>
```

## Wiring — finished, copy-paste-ready files in `patched/`

Three existing files need edits. Rather than describe diffs, `patched/` contains the
**complete** patched versions (every Diagram addition marked with a `── Diagram feature ──`
comment) — drop them straight over the originals:

| Replace | With |
|---|---|
| `src/store/uiStore.ts` | `patched/store/uiStore.ts` — `diagram` action slot, `mdEditorDiagramPaths`, panel flag, two setters, two selectors |
| `src/components/MarkdownEditor/EditorHeader/EditorHeader.tsx` | `patched/EditorHeader/EditorHeader.tsx` — third `ActionPill` ("Diagram", `Network` icon) + spawn hook + peek/preview |
| `src/components/MarkdownEditor/MarkdownEditor.tsx` | `patched/MarkdownEditor/MarkdownEditor.tsx` — mounts `<DiagramGalleryPanel/>` beside `<AnalysisPanel/>` |

The diff is purely additive — nothing existing is removed or changed. `STORE_PATCH.md`
remains as a line-by-line description of the store changes if you prefer to apply them by hand.

### How the Diagram pill behaves

The pill is one joined segment — **run │ gear │ Gallery chip** — exactly like AI Split / Analyze:

- **Run** → `SendPreviewModal` (resolved prompt) → spawn → spinner ("Diagramming…") →
  on success the sidecar path is set, which auto-opens the gallery and lights the chip.
- **Gear** → `PromptPeekModal` with the six `DIAGRAM_PRESETS` (engine + editable prompt).
- **Gallery chip** → toggles `mdEditorDiagramPanelOpen`.

### Generation entry points

Two ways to generate, both writing to the same sidecar:

- **The pill** (EditorHeader) — Run → `SendPreviewModal` confirm → spawn. This is the
  primary, preset-aware path with the prompt preview.
- **The panel** (`DiagramGalleryPanel`) — "+ New" and each card's **Regenerate** run
  directly via a panel-local `useEditorDiagramAction` instance (seeded from the persisted
  `CLI_KEY_DIAGRAM` / `PRESET_KEY_DIAGRAM`). Regenerate reuses the card's own style and
  **appends** a new card (never overwrites). These skip the confirm modal — they're quick
  in-context actions. The panel refreshes itself when a run completes (it watches the
  diagram run slot, since the file path is unchanged).

Mounted prop-less, the panel self-wires both. To route New/Regenerate through the header's
confirm-modal flow instead, pass `onNew` / `onRegenerate` / `busy` from `MarkdownEditor`.

## Dependency

`MermaidView` lazy-imports `mermaid` (`import('mermaid')`), so add it to
`studio/package.json` as a renderer dependency. The chunk (~500KB) is fetched only the
first time a Mermaid card renders, then cached at module scope.

## Contracts worth knowing

- **The agent owns appends.** The renderer reads and removes; it never appends to the
  sidecar, so two writers can't race. See `diagramSidecar.ts`.
- **Untrusted source.** Diagram source comes from an agent, so `MermaidView` initialises
  Mermaid with `securityLevel: 'strict'` and falls back to a `<pre>` on any render error
  rather than crashing the card.
- **Run state is per-file.** All in-flight state lives in `uiStore.mdEditorActions`, keyed
  by the file that started the run — a run finishing while you're on another file never
  touches the visible file's pill (same model as Split/Analyze).
