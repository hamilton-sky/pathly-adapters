# Implementation Plan — Notebook Edit Actions

> Output of a PO + designer + architect consultation (2026-06-16) on what the
> Markdown notebook / editor should be able to do. Source-of-truth for the phased
> build. Each phase ships independently; lowest-risk first.

## Context

Pathly Studio edits AI agent/skill Markdown files (YAML frontmatter, **Git-tracked →
must stay byte-stable**) across two surfaces:

- **Cells view** (`MarkdownNotebook`) — body + fragment cells; move/duplicate/convert/
  delete/revert, split-into-cells, per-cell edit+preview, drag-from-catalog, undo/redo.
- **Editor view** (`Editor`) — CodeMirror 6 source editor; preview/edit/split tabs,
  find&replace, frontmatter form, commentable preview → send-to-agent → review the
  returned `.draft` as an accept/reject hunk diff (`DraftDiffViewer`).

## Guiding principle (PO)

An author is **writing a program an LLM executes literally**, not a document. Feature
value = does it help predict/control what the agent does + speed the iteration loop.
Fidelity, fragment reuse, and AI-assisted iteration score high; pretty-rendering scores
~0. The tool's real competitor is "just open the raw `.md` in VS Code" — every feature
must beat that.

## Headline decisions (all three advisors converged)

| Decision | Verdict |
|---|---|
| Adopt a block-editor library (BlockNote/Plate/Milkdown/TipTap) for cells? | **No.** Re-introduces a 2nd/3rd markdown serializer + undo stack. The cell *is* the block model — "blocks-of-markdown" is coherent. Point of no return; only revisit on a WYSIWYG pivot. |
| Where do formatting actions live? | **Edit mode**, over the textarea (true source offsets). View-mode selection over rendered HTML has no source offsets → can't safely patch. This is why the bubble-bar buttons were dead. |
| Build inline AI as a new path? | **No.** Reuse the existing `buildSendPrompt` → `claude -p` → `.draft` → `DraftDiffViewer` pipeline. Cmd+K = a *scoped* prompt + scoped diff. |
| Render layer (`marked`)? | A library pays off **here** (not the editor): `react-markdown` + remark/rehype for tables/mermaid/katex — pure render swap, zero source-of-truth impact. |

## Open product question (gates Phase 4)

Is the Cells view **"blocks of Markdown"** (cell = block, intra-cell stays source — what
the current design coherently delivers) or **Notion-style WYSIWYG inside cells**? The
answer decides whether Phase 4 (CM6-per-cell) is the ceiling or the library question
reopens. **Riskiest assumption (PO):** that authors edit in Cells view at all rather
than living in the Editor / escaping to VS Code — validate with telemetry before funding
Cells-view block UX beyond the cheap honesty fixes in Phase 1.

---

## 🔴 Phase 0 — Fix the lossy cell round-trip  *(do first; reversible)*

**The bug (architect, from reading the code):** a file that goes **Source → Cells →
Save** comes back **byte-different even if untouched** — frontmatter dropped, every
heading forced to `##`, content `.strip()`'d, blank lines normalized to `\n\n`. For
Git-tracked contracts that is data loss masquerading as a UX choice.

- `POST /skills/parse` returns `body_cells` and **silently discards frontmatter**
  (`skills.py` ~630–704).
- `POST /skills/save` rebuilds via `## {heading}\n\n{content.strip()}` joined by `\n\n`
  (`skills.py` ~844–881).

**Fix (cheapest reversible first step):**
1. `/skills/parse` also returns the **raw frontmatter block** (verbatim string, not
   parsed) and a per-cell **`headingLevel`** (count the `#{1,6}` instead of discarding).
2. `notebookStore` holds `frontmatterRaw: string` (inert) + `headingLevel` per body cell.
3. `/skills/save` accepts both; re-prepends frontmatter **byte-for-byte**, uses the stored
   heading level (`'#'.repeat(level)`), stops `.strip()`-ing, replays original spacing.
4. **Round-trip test** on real skill files: parse → save with no edits → assert byte-identical.

**Files:** `src/pathly_orchestrator/http_server/blueprints/skills.py`,
`store/notebookStore.ts`, `MarkdownNotebook/NotebookHeader/NotebookHeader.tsx`
(`handleCellsSave`), `tests/` (new round-trip test).

---

## Phase 1 — `markdownInline.ts` + un-stub bubble bar + wire dropdown  *(IN PROGRESS)*

**Stub inventory (verified):**

| Surface | Stub | Resolution |
|---|---|---|
| Cell view-mode bubble bar | Bold / Italic / Wrap-in-code | Move to **edit-mode** formatting (can patch source) |
| Cell view-mode bubble bar | Insert-as-fragment | **Needs design** (PO: name it, show what it becomes) — descope from P1 |
| ⋯ menu (body + fragment) | Duplicate | Implement `duplicateCell` in store |
| ⋯ menu (body + fragment) | Convert (to fragment / to body) | **Needs design** — body↔fragment isn't a trivial swap (fragments reference catalog entries) |

**Build:**
1. New `components/shared/markdownInline.ts` — pure transforms
   `toggleBold/toggleItalic/toggleCode(text, selStart, selEnd) → { text, selStart, selEnd }`
   (wrap if unwrapped, unwrap if already wrapped). Unit-testable, no React.
2. `notebookStore` — add `duplicateCell(cellId)` (clone with new id, `isSystem:false`,
   insert after source). Wire ⋯ Duplicate in `BodyCell` + `FragmentCell`.
3. `BodyCell` edit/split mode — a thin formatting toolbar (Bold/Italic/Code) above the
   textarea + `Ctrl/⌘+B / I / `` `` `` shortcuts, applied to `draft` via `markdownInline`,
   restoring the selection. Remove the dead view-mode formatting buttons (keep "New cell
   from selection").
4. Same `markdownInline` module is the dispatch target for the **Editor** view's CM6
   formatting shortcuts (supersedes `editor-notebook-enhancements` B1).

**Anti-divergence rule:** one transform module, two dispatch sites (CM6 transaction in
Editor; `draft` string + `updateBodyCell` in cells). No per-view serializer.

**Files:** `components/shared/markdownInline.ts` (new),
`store/notebookStore.ts`, `MarkdownNotebook/BodyCell/BodyCell.tsx` (+`.module.css`),
`MarkdownNotebook/FragmentCell/FragmentCell.tsx`, later `Editor/MarkdownEditor.tsx`.

---

## Phase 2 — Cmd+K inline AI (reuse the draft-diff pipeline)

Do **not** build a parallel AI path. Comment→Send = whole-file, multi-annotation,
full-file diff. **Cmd+K = selection-scoped**, inline prompt → loading → inline
accept/reject. Cmd+K **must never write a `.draft` file** (reserved for the comment flow).

- **Editor view (natural fit):** `Cmd+K` opens a prompt anchored to the CM6 selection;
  new `buildInlineEditPrompt(filePath, fullBody, selectedText, instruction)` in
  `commentUtils.ts`; reuse the exact spawn block from `handleModalSendNow`
  (`addTab`→`openTab`→`terminal.spawn(['claude','-p',…])`); reuse `DraftDiffViewer`.
- **Cell view:** same prompt builder scoped to the cell; on accept apply via
  `updateBodyCell` (lands in cell undo) instead of opening `DraftDiffViewer`.

**Files:** `Editor/commentUtils.ts`, `Editor/index.tsx`, `Editor/MarkdownEditor.tsx`
(add `getSelectionRange`), `MarkdownNotebook/BodyCell/BodyCell.tsx`.

---

## Phase 3 — Rendering upgrade  *(optional, product-driven)*

Only if GFM tables / callouts / Mermaid / KaTeX are needed. Swap the 17-line
`marked()` renderer for `react-markdown` + `remark-gfm` (+ `remark-directive`,
`rehype-pretty-code`/Shiki, `rehype-mermaid` lazy, `remark-math`/`rehype-katex`).
Pure render layer — no source-of-truth impact. Lazy-load Mermaid/KaTeX in Electron.

**Files:** `components/shared/MarkdownRenderer/MarkdownRenderer.tsx` + deps.

---

## Phase 4 — Cell = mini-CodeMirror instance  *(later; gated on the open question)*

Replace the cell textarea with a small `EditorView` to unify the edit substrate so
`markdownInline` dispatches identically in both views and enables in-cell syntax
highlighting / live preview. Contained to `BodyCell`; still reversible. Only the
library-adoption question is a true point of no return — **recommended against.**

**Files:** `MarkdownNotebook/BodyCell/BodyCell.tsx` (extract a `CellEditor`).

---

## Sequencing summary

```
Phase 0  round-trip fix          REVERSIBLE, do first — correctness bug
Phase 1  inline format + dropdown INCREMENTAL — honesty fixes (this turn)
Phase 2  Cmd+K inline AI          INCREMENTAL — reuse draft-diff pipeline
Phase 3  render upgrade           INCREMENTAL, optional — pure render layer
Phase 4  cell = CM6              LARGER, reversible — gated on open question
NEVER    adopt block-editor lib   point of no return
```

## Cross-references

- `pathly/plans/editor-notebook-enhancements/` — earlier polish plan (PLANNING, unbuilt).
  Its **B1 formatting shortcuts** is subsumed by this Phase 1; A1/A3/A4 tooltip actions,
  fullscreen, cell-collapse, fragment-hover remain its own scope.
- `pathly/plans/storage-path-alignment/README.md` — why this plan lives under
  `pathly/plans/` (new `pathly/<topic>/` root is parked/unused).
