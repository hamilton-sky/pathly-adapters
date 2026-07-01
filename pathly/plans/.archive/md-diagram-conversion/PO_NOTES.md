# PO Notes — md-diagram-conversion

_Last updated: 2026-06-29_

## Who Is This For

Studio users who work with Markdown files and want AI-generated visual explanations of
their content — primarily developers and technical writers already using the Pathly Studio
Markdown editor. They use AI Split and AI Analyze today; this adds a third action with the
same familiar shape.

## Definition of Success

A working **Diagram** action appears in the MD editor header alongside Split and Analyze.
Clicking Run generates a diagram (Mermaid rendered as SVG, ASCII in `<pre>`, PlantUML as
source-only). Multiple diagrams accumulate in a sidecar gallery (`.diagrams.json`) and
survive file reload. Users can view full-resolution (lightbox with zoom/pan), regenerate,
and delete individual cards. `npm run typecheck` is clean and no existing editor actions
regress.

## Out of Scope

- PlantUML / D2 live rendering (needs a bundled render engine — deferred).
- Inserting generated diagrams back into the MD body (sidecar-only in v1).
- Per-model configuration picker (tracked as `ai-action-config`; the Diagram action will
  inherit it automatically when that shared layer lands).
- New IPC channels — sidecar read/write reuses existing `window.pathly.fs.read/write/delete`.

## Constraints

- **Reuse, do not rebuild:** Diagram is a new consumer of the existing AI-action
  infrastructure (engine picker, `PromptPeekModal`, spawn pipeline, `SplitPill` pattern).
  It contributes only `diagramPresets.ts` and its own output handling.
- **File size:** every renderer file ≤ 150 lines (gallery is pre-split into Panel / Card /
  Render / MermaidView / Lightbox).
- **CSS:** no inline styles; all in `.module.css` using `tokens.css` vars.
- **Branch:** `claude/md-diagram-conversion-wze4x3`. No PR unless explicitly requested;
  never push to master.
- **TypeScript:** `npm run typecheck` (renderer) + `tsc --noEmit -p studio/tsconfig.node.json`
  must both be clean before the feature is considered done.
- **New dependency:** `mermaid` package added to `studio/package.json` (render dep).

## Open Questions

None — SPEC.md covers all four dimensions explicitly. Proceeding on the assumptions stated above.
