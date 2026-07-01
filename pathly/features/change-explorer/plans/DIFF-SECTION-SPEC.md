# Diff Section — Architecture & Recommendations (umbrella spec)

> **Status:** recommendation / pre-pipeline design. No implementation yet.
> **Author note:** This is the umbrella architecture for a full-screen "Diff
> section" in Pathly Studio that handles **all** project diffs — code and
> markdown, git changes and agent proposals — with view **and** accept/apply.
>
> **Relationship to the other docs in this folder:**
> - [`SPEC.md`](./SPEC.md) (ChangeExplorer) = **Phase 1** of this: the read-only,
>   git-backed, full-screen diff *viewer*. Everything in it stands; this doc wraps
>   it and adds the layers it doesn't cover (staging/apply, proposals source, the
>   prose-vs-code model split, the shared-primitives extraction).
> - This doc does **not** replace `SPEC.md` — it sequences it.

---

## 1. What the user asked for

A dedicated **full-screen section** (like the Notebook, *not* a modal) that:

1. Controls **all** diffs in the project — including **code**, not just markdown.
2. Offers a **VS Code-style** diff (split/unified) **plus** the accept/reject
   capability we already have for markdown drafts.
3. Because it's a whole section (persistent, full viewport) rather than a modal,
   it can host **more** than the modal can: a changed-file list, multiple diff
   sources, per-hunk staging, search, "send hunk to agent", etc.

**Decided diff source:** *Both — git working-tree backbone + agent/pipeline
proposals*, phased (git first, proposals second).

**Already shipped (context):** the markdown draft modal
([`DraftDiffViewer`](../../../studio/src/renderer/src/components/Editor/DraftDiffViewer/))
gained an editable result pane (Cards · List · Code · ✎ Edit). That modal is the
*inline, single-file, "approve this one agent draft"* flow and **stays as-is** —
it is not what this section replaces.

---

## 2. The principle that shapes everything: prose ≠ code

This is the single most important design call. There are **two different accept
models**, and they must not be merged:

| | Markdown / prose | Code |
|---|---|---|
| Right unit of accept | **Section** (split on `##` headings) | **Line / hunk** (git `@@` hunk) |
| Why | A reworded paragraph = remove-line + add-line pair that is *one* semantic change; per-line accept produces broken half-sentences | A line is a meaningful unit; per-hunk staging is the universal standard (git add -p, VS Code) |
| Today's home | `useDraftDiff` + `reconstruct()` in the Editor modal | **does not exist yet** |

**Recommendation:** the Diff section's **core is a line/hunk staging engine**
(git-style), with the markdown section-accept model kept as a *specialization*
that lives where it already works (the Editor modal). **Do not** try to make one
component or one model serve both — that is the central trap.

---

## 3. Layering — what is shared, what stays separate, what is new

| Piece | Where it goes | Why |
|---|---|---|
| `SplitDiff`, `UnifiedDiff`, `fileDiffUtils` (`toSplitRows`/`toUnifiedRows`), `computeLineDiff`, `StatusBadge`, `ViewToggle` | **Promote to `shared/diff/`** | Pure presentational / transform code. `change-explorer` is now a concrete **second consumer**, so this is no longer speculative — it's the YAGNI trigger firing. |
| Section-accept model: `useDraftDiff`, `reconstruct`, `parseIntoSections` | **Stays in `Editor/DraftDiffViewer/`** | Prose-specific; **not valid for code**. No reason to generalize it. |
| **New** line/hunk staging engine + diff-source abstraction + apply semantics | **New `DiffSection/` feature** | Code-appropriate model the modal cannot provide. |
| Markdown draft modal (`DraftDiffViewer` + `DraftEditView`) | **Unchanged** | Right tool for its narrow inline job. |

### 3.1 The `shared/diff/` extraction (do this first, it's safe)

Move the **dumb renderers and pure transforms** — the things that don't know about
any accept model — out of `Editor/DraftDiffViewer/` into `shared/diff/`:

```
shared/diff/
  SplitDiff/        SplitDiff.tsx + .module.css      (pure: SplitRow[] -> rows)
  UnifiedDiff/      UnifiedDiff.tsx + .module.css     (pure: UnifiedRow[] -> rows)
  ViewToggle/       ViewToggle.tsx + .module.css      (split/unified segmented control)
  StatusBadge/      StatusBadge.tsx + .module.css
  lineDiff.ts       computeLineDiff (line-level diff algorithm)
  rows.ts           toSplitRows / toUnifiedRows / diffStats   (from fileDiffUtils)
  types.ts          SplitRow, UnifiedRow, DiffLine, FileDiffStats, SplitCellType
  index.ts          barrel
```

- `Editor/DraftDiffViewer/` then **imports from `shared/diff/`** instead of owning
  these. Its `index.ts` can re-export for backward compat during migration.
- The **stateful** accept logic (`useDraftDiff`, `reconstruct`, `CodeDiffView`,
  `DraftEditView`, the Cards/List/triage components) **does not move** — it's
  prose-specific.
- This keeps the rule from `studio/CLAUDE.md` intact: a component used by 2+
  features lives in `shared/`; single-feature components stay in their folder.

> Without this, `ChangeExplorer`/`DiffSection` would reach into
> `Editor/DraftDiffViewer/` internals — a cross-feature import that `shared/`
> exists to prevent.

---

## 4. Diff sources — "Both", as an abstraction

The section reviews more than one kind of change, so define **one interface** that
every source implements. The UI (file list + diff pane + staging) is written once
against this interface; sources plug in behind it.

```ts
// shape, not final
interface DiffSource {
  id: 'git' | 'draft' | 'proposal'
  label: string
  /** All changed files for this source. */
  listChanges(): Promise<ChangedFile[]>
  /** Apply the user's accept decisions for one file (semantics vary per source). */
  apply(file: ChangedFile, decisions: HunkDecision[]): Promise<void>
  /** Optional: live updates (git polling during a run; fs watch on .draft). */
  subscribe?(onChange: () => void): () => void
}

interface ChangedFile {
  path: string                       // relative, forward slashes
  status: 'M' | 'A' | 'D' | 'R'
  language: 'markdown' | 'code' | 'other'   // selects the accept model + lens
  originalContent: string | null    // null for added
  proposedContent: string | null    // null for deleted; working-tree OR draft OR agent output
  additions: number
  deletions: number
}
```

### Apply semantics differ per source — this is why the abstraction matters

| Source | `listChanges()` | `apply()` |
|---|---|---|
| **git** (working tree vs HEAD) | `git status` + `git diff HEAD` | stage accepted hunks (`git apply --cached` of a built patch) / revert rejected / optional commit |
| **draft** (`<file>.draft`) | scan for sibling `.draft` files | write reconstructed/edited result to the real file, delete `.draft` (today's modal behavior, hoisted to the section) |
| **proposal** (pipeline output) | read builder/reviewer staged output | write accepted files; report back to FSM (`/runner/...`) |

---

## 5. Phasing & gates

| Phase | Scope | Source | Gate |
|---|---|---|---|
| **0 — Extract** | Move presentational primitives to `shared/diff/`; repoint the Editor modal | — | typecheck green; modal still works unchanged |
| **1 — Git viewer** | The existing [`SPEC.md`](./SPEC.md): full-screen panel, FileList + diff pane, `git:diff` IPC, manual refresh, live polling tied to `runnerStore.status` | git | shows real working-tree diffs; LIVE badge during runs |
| **2 — Staging engine** | Line/hunk model + per-hunk accept gutter on **code**; `git:apply`/`git:stage` IPC; build & apply patches | git | accept a subset of hunks, see them staged/reverted in real git |
| **3 — Proposals source** | `.draft` + pipeline output behind the same `DiffSource` interface; markdown files use section-accept lens, code uses hunk lens | draft + proposal | review & apply an agent draft from the section (parity with the modal) |
| **4 — Polish** | Search-in-diff, "send hunk to agent", run-scoped diff (snapshot before/after), keyboard nav | all | — |

> Phases 0–1 are low-risk and high-value on their own. The staging engine (2) is
> the substantial build. Treat each phase as its own pipeline pass
> (STORM→PLAN→DESIGN→BUILD) rather than one mega-feature.

---

## 6. Where it lives (UI shell)

Follows `change-explorer/SPEC.md`:

- New top-level panel `'diff-section'` (or keep `'change-explorer'` as the panel id
  and grow it) in `store.ts`'s `activePanel` union + `App.tsx` `MainPanel()`.
- Sidebar nav button + keyboard shortcut (the existing SPEC proposes **Ctrl+6**).
- Layout: **source switcher** (git / drafts / proposals) → **FileList** (left,
  changed files with status + ±N) → **DiffPane** (right: `ViewToggle` split/unified
  + per-hunk accept gutter for code, or the section/markdown lens for prose).
- Full viewport, persistent — survives navigation, unlike the modal.

---

## 7. Component tree (target, after Phase 3)

```
shared/diff/                         <- Phase 0 (see §3.1)

studio/src/renderer/src/components/DiffSection/
  index.ts
  DiffSection.tsx                    panel shell: SourceSwitcher + FileList + DiffPane
  DiffSection.module.css
  SourceSwitcher/                    git | drafts | proposals
  FileList/                          changed-file list (status badge, ±N, language icon)
  DiffPane/                          ViewToggle + diff body; routes by file.language
    HunkGutter/                      per-hunk accept/reject (CODE lens)
    ProseLens/                       section-accept reuse for MARKDOWN files
  sources/
    gitSource.ts                     DiffSource over git:diff / git:apply
    draftSource.ts                   DiffSource over <file>.draft
    proposalSource.ts                DiffSource over pipeline output
  hooks/
    useDiffSource.ts                 selected source -> ChangedFile[] (+ live subscribe)
    useHunkStaging.ts                line/hunk decisions + patch building
```

---

## 8. Main-process / IPC additions

Builds on `change-explorer`'s `git:diff` (Phase 1). New for staging (Phase 2):

```ts
// studio/src/main/ipc/git.ts  (extend)
ipcMain.handle('git:apply',  (_e, projectRoot, patch: string, cached: boolean) => ...) // git apply [--cached]
ipcMain.handle('git:status', (_e, projectRoot) => ...)                                  // incl. untracked
```

Register in the main ipc index, the preload contextBridge (`window.pathly.git.*`),
and `renderer/src/types/global.d.ts` — per the IPC pattern in `studio/CLAUDE.md`.

---

## 9. Open questions / decisions still needed

1. **Staging granularity for code v1** — per-hunk only, or per-line within a hunk?
   (Recommend per-hunk first; per-line is a later refinement.)
2. **Git index vs patch-only** — does "accept" stage into the real git index
   (`git apply --cached`), or just produce a working-tree edit? (Recommend staging
   into the index so it composes with the user's normal git flow.)
3. **Untracked / new files** — supplement `git diff HEAD` with `git status --short`
   to surface new files (the existing SPEC flags this for Phase 2).
4. **Large / binary files** — truncate or show a "binary / N lines, not shown" stub.
5. **Run-scoped diff** — snapshot before a run to show "exactly what this run
   changed" (existing SPEC Phase 3 idea); deferred.
6. **Panel identity** — grow `change-explorer` in place, or new `diff-section`
   panel that absorbs it? (Recommend grow in place to avoid a second nav entry.)

---

## 10. Non-goals

- Replacing the inline markdown draft modal — it stays for the single-file
  "approve this draft while editing it" flow.
- A general merge-conflict resolver (3-way merge) — out of scope for now.
- Generalizing the prose section-accept model onto code — explicitly rejected (§2).
```
