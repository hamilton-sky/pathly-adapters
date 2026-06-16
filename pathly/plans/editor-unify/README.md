# editor-unify — one editor experience for all markdown (P2, deferred)

**Goal:** every `.md` file (doc/plan/artifact AND skill) opens in **one** surface with the
**full toolbar**. The only context-aware piece is the **Export ▾ dropdown**.

> **Status: DONE — both halves shipped and verified in the running app (2026-06-16).**
>
> - **Half A — Export ▾ dropdown.** `NotebookHeader/ExportMenu/` replaces the single
>   "Export Skill" button with **Save as… · Download a copy · Copy to clipboard ·
>   Install skill → adapters** (Install gated to skills/agents by path). New
>   `fs:saveDialog` IPC (main `index.ts` + preload + `global.d.ts`) wraps Electron
>   `dialog.showSaveDialog`; Copy reuses the existing `clipboard.write` IPC. The
>   standalone Save button + Ctrl+S stay as the primary save (Save intentionally not
>   duplicated in the menu).
> - **Half B — every md routes to one notebook + rename.** The Sidebar already routed
>   all `.md` to the notebook; `ArtifactModal` "Open in editor" now does too for md
>   (non-md → plain editor). The whole surface was renamed off "skill": folder
>   `SkillNotebook/` → `MarkdownNotebook/`, `SkillNotebookPanel` →
>   `MarkdownNotebookPanel`, store `skillNotebookStore`/`useSkillNotebookStore` →
>   `notebookStore`/`useNotebookStore`, uiStore `skillNotebookPath`/`…ViewMode` →
>   `notebookPath`/`notebookViewMode`, `activePanel` value `'skill-notebook'` →
>   `'notebook'`. User-facing copy went generic: landing = "Markdown Notebook", Ctrl+4
>   tooltip = "Markdown notebook", Split/Analyze/Save labels = "document", and the
>   header breadcrumb shows just the document name (path segments removed).
>
> Note: renaming the folder while the Vite dev server is live throws a stale
> "Failed to resolve import …/MarkdownNotebook" overlay — a full dev-server restart
> clears it (the files are correct on disk).

---

## Current architecture (verified)
Two components, routed by `activePanel` in `studio/src/renderer/src/App.tsx`:
- `activePanel === 'editor'` → `<Editor>` — the plain doc editor (Preview/Edit/Split/Source/Save).
- `activePanel === 'skill-notebook'` → `<SkillNotebookPanel>` — the full surface:
  `NotebookHeader` (Visual ⇄ Source · Analyze · Report · Review draft · **Export Skill**) +
  a cells view, and in **'editor' view it EMBEDS `<Editor>`** (`SkillNotebook.tsx:37`).

So the full toolbar lives in `SkillNotebook/`, NOT `Editor/`. The doc "Open in editor"
(`ArtifactModal.openInEditor` → `setActivePanel('editor')`) routes to the plain editor.

## The change
1. **Route every md file through `SkillNotebookPanel`.** Change the doc-open paths
   (`ArtifactModal` "Open in editor", `EditorLauncher`, anything that does
   `setActivePanel('editor')` for a markdown file) to instead
   `setSkillNotebookPath(path)` + `setActivePanel('skill-notebook')`.
2. **Safety net:** the cells view must parse an arbitrary (non-skill) doc. If it doesn't
   render cleanly, **default docs to the notebook's `'editor'` view mode** (the embedded
   `<Editor>`, which already works for any md). Never leave a doc in a broken cells view.
3. **Export ▾ dropdown** in `NotebookHeader` — replace the single "Export Skill" button:
   ```
     Export ▾
       ├─ Save                     (all)  — write to the current file (existing save)
       ├─ Save as…                 (all)  — native save dialog → write to chosen path
       ├─ Download a copy          (all)  — copy to Downloads / chosen location
       ├─ Copy to clipboard        (all)  — copy the md content
       └─ Install skill → adapters (skills/agents ONLY)  — the existing "Export Skill"
   ```
   The only context-gated item is **Install skill → adapters** (compose + write to the
   adapter dirs); everything else applies to any md.
4. **Drop the `derivedType`-based routing split** — one path for all md.

## Implementation notes
- **Save as… / Download a copy** need a main-process IPC using Electron `dialog.showSaveDialog`
  + `fs.writeFileSync` — register in `src/main/ipc/`, preload, `global.d.ts` (the IPC pattern).
- **Copy to clipboard** = renderer clipboard (`navigator.clipboard.writeText` or Electron `clipboard`).
- **Install skill → adapters** = find the current "Export Skill" handler in `NotebookHeader.tsx`;
  keep it, move it under the dropdown, gate to `derivedType in ('skill','agent')`.
- Follow studio/CLAUDE.md UI rules; reuse the existing dropdown pattern if one exists
  (e.g. `TypePicker` in the comms panel opens upward) — match it.

## Verify (MUST be interactive)
- Renderer + main typecheck (`tsc -p tsconfig.web.json` / `tsconfig.node.json`).
- In the running app: open a **doc** (e.g. an artifact's "Open in editor") → confirm it
  lands in the notebook, cells render (or falls back to editor view), and the Export
  dropdown's Save / Save-as / Download / Copy all work.
- Open a **skill** → confirm "Install skill → adapters" still installs correctly.

## Why one editor
The cell/notebook model + Preview/Source/Analyze/Review-draft all operate on *markdown*,
not on *skill-ness*. Only **installing to adapters** is skill-specific — so it's the one
dropdown item that's gated. Everything else is shared. (See the chat discussion that led here.)
