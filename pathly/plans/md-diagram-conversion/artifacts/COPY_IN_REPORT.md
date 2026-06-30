# Copy-in Report — md-diagram-conversion (Task 1)

**Run:** manual / supervised (Claude Code), after the prior headless run failed with `terminal_spawn_timeout`.
**Date:** 2026-06-30
**Branch:** `master` (working tree, uncommitted). Feature's intended branch `claude/md-diagram-conversion-wze4x3` does not exist locally — not created/committed/pushed.
**Result:** ✅ PASS — both typecheck gates exit 0; all spot-checks pass.

---

## What was done

### NEW files copied → `studio/src/renderer/src/components/MarkdownEditor/`
(Note: the original task path `studio/src/components/MarkdownEditor/` was wrong — it dropped the `renderer/src` segment. Corrected.)

- `diagramTypes.ts`
- `EditorHeader/diagramPresets.ts`
- `EditorHeader/hooks/useEditorDiagramAction.ts`
- `DiagramGalleryPanel/DiagramGalleryPanel.tsx` + `.module.css`
- `DiagramGalleryPanel/diagramSidecar.ts`
- `DiagramGalleryPanel/useDiagramSidecar.ts`
- `DiagramGalleryPanel/DiagramCard/DiagramCard.tsx` + `.module.css`
- `DiagramGalleryPanel/DiagramRender/DiagramRender.tsx` + `.module.css`
- `DiagramGalleryPanel/DiagramRender/MermaidView.tsx`
- `DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx` + `.module.css`

`STORE_PATCH.md` and `README.md` were intentionally NOT copied into source.

### EXISTING files overwritten with `patched/` versions (drift-checked first)
- `store/uiStore.ts` — +42 / −2 (the 2 removals = `setMdEditorAction` action-union widening `'split'|'analyze'` → `+'diagram'` and a reworded doc comment; no live logic dropped)
- `components/MarkdownEditor/EditorHeader/EditorHeader.tsx` — +114 / −4 (union widenings for the 3rd pill; no live logic dropped)
- `components/MarkdownEditor/MarkdownEditor.tsx` — +7 / −0 (purely additive; mounts `<DiagramGalleryPanel/>`)

Drift verification: `git diff 4be9acaa..HEAD` showed the only post-snapshot change to these three files was `uiStore`'s `activePanel` line, which the patched copy already reflects (`'command-center'`). No clobber.

### Dependency
- `npm install mermaid` → **`mermaid@^11.16.0`** added to `studio/package.json` dependencies (+59 transitive packages). Lazy-imported by `MermaidView.tsx` (`import('mermaid')`), module-cached.

---

## Gates & spot-checks

| Check | Result |
|---|---|
| Baseline `npm run typecheck` (pre-change) | EXIT 0 (clean baseline — post-copy errors attributable to the change) |
| `npm run typecheck` (`tsc -p tsconfig.web.json`, post-copy) | **EXIT 0** |
| `tsc --noEmit -p tsconfig.node.json` | **EXIT 0** |
| Hex in `MermaidView.tsx` (reconciled rule) | ✅ all 7 hex literals are `tokenValue(cs,'--token','#fallback')` fallback args; **zero** standalone/primary hex |
| `type="button"` — `DiagramCard.tsx` | ✅ 4/4 |
| `type="button"` — `DiagramLightbox.tsx` | ✅ 2/2 |

---

## Divergences carried forward (for Phase 7 review)

1. **Prompt path is not fragment-composed.** `useEditorDiagramAction.ts` resolves prompts via `resolvePrompt` over `DIAGRAM_PRESETS`, NOT `composeClientSkill`. This contradicts `ARCHITECTURE_PROPOSAL.md` (which promised the "compose via fragments / true sibling" path) and the repo's "every prompt flows through fragments" direction. Treat `md-diagram-feature/` as as-built; `ARCHITECTURE_PROPOSAL.md` is partially superseded. Flagged for adjudication.
2. **CLI keys relocated.** `CLI_KEY_DIAGRAM` / `PRESET_KEY_DIAGRAM` / `STORAGE_KEY_DIAGRAM` live in `EditorHeader/diagramPresets.ts`, not `editorCli.ts`. No edits to `editorCli.ts` or `services/skillCompose.ts` were needed (the architecture's planned edits there are moot).
3. **File-length budget:** `useEditorDiagramAction.ts` ≈ 174 lines (renderer budget ≤150); patched `EditorHeader.tsx` ≈ 550 lines (over the 400-line hard cap, pre-existing). Recorded for the reviewer; not blocking.

## Not done here (by scope)
- No git commit / branch / push (manual supervision; left to the user).
- Runtime behavior (spawn, render, lightbox, persistence, theme flip) NOT exercised — requires a running Studio. Deferred to Phase 8 (Task 3), which should mark those MANUAL-REQUIRED.
