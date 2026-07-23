# ARCHITECTURE PROPOSAL — board-differ (MVP)

_Role: architect · Feature: board-differ · Rigor: standard · 2026-07-15_

## Executive Summary

The board-differ MVP gives a headless-run supervisor a way to vet a change they did
not watch happen: open an artifact card, see the exact lines the agent changed against
committed HEAD, and see the blast-radius (callers / affected flows) of that file — all
without leaving the Command Center board. The releasable unit is **surface (a) read-only
code diff + the Impact panel shipped together**; the plain diff alone is redundant with
existing draft-triage tooling and ships nothing of product value. Technically the diff is
built first (impact renders beside it), but the milestone is one PR: diff + impact.
Every degradation path — graph off, non-code artifact, `detect_changes` failure, untracked
file — must render the diff and simply omit the Impact panel, never 500 and never block.

## MVP Scope

**In:**
- Surface (a): read-only artifact-vs-committed-HEAD line diff for code-file artifacts.
- Impact panel: `detect_changes(project)` filtered to the diffed file's path, honestly
  labeled "impact of current uncommitted changes in this file."
- A "See changes" affordance on artifact cards that carry an `artifact_path`.
- Full graceful degradation on every failure surface.

**Out (this proposal):** surfaces (b) draft-triage with accept/apply, (c) two-artifact
compare, (d) multi-file run-review, the Walkthrough artifact + `.html` export, clickable
call-graph visualisation, multi-commit baselines, and any write/mutation from the diff view.
See "Out of Scope" for the full list. These are roadmap, not MVP.

## Architecture Diagram

```
 STUDIO (renderer)                    MAIN PROCESS            FSM SERVER (:8765)
 ─────────────────                    ────────────            ──────────────────
 [Artifact card]                                              blueprints/code/query.py
   "See changes" pill                                           POST /code/query
        │ (artifactPath)                                          op:"impact"
        ▼                                                            │
 ┌──────────────────────┐                                           ▼ (lazy import)
 │   CodeDiffModal       │                                    runner/code_context_cli.py
 │  ┌────────────────┐   │   git:show-file(path,HEAD)          CliProvider.detect_changes()
 │  │ useCodeFileDiff│───┼──────────────► git.ts ──► `git show`   shells:
 │  │  baseline blob │   │   fs:read(path) ──► HEAD:<rel>         codebase-memory-mcp cli
 │  │  current text  │◄──┼──────────────────────────┘            detect_changes {repo_path}
 │  └───────┬────────┘   │                                           │
 │          ▼            │                                           ▼
 │  RawCodeDiffView ─────┼─ reuses ─► SplitDiff / UnifiedDiff   filter changed_files +
 │  (thin presenter)     │           + fileDiffUtils            impacted_symbols to target
 │  ┌────────────────┐   │           + computeLineDiff              │
 │  │  ImpactPanel   │───┼── POST /code/query {op:impact} ◄─────────┘
 │  │ (collapsible)  │   │   null → panel hidden (no error)
 │  └────────────────┘   │
 └──────────────────────┘
```

Two independent data paths converge in one modal: the **git-baseline diff** (main-process
IPC) and the **impact query** (FSM `/code/query`). Either can be null; the modal renders
whatever it has.

## Component Map

| Component | File | What changes |
|---|---|---|
| CliProvider.detect_changes | `src/pathly_orchestrator/runner/code_context_cli.py` | **new method** — shells `detect_changes`, returns raw dict or None |
| code_query impact branch | `src/pathly_orchestrator/http_server/blueprints/code/query.py` | **new routing branch** for `op:"impact"` → detect_changes + filter |
| git:show-file | `studio/src/main/ipc/git.ts` | **new IPC handler** — `git show HEAD:<rel>`, null on untracked |
| preload git.showFile | `studio/src/main/preload/index.ts` | expose `window.pathly.git.showFile` |
| global.d.ts | `studio/src/renderer/src/types/global.d.ts` | type `git.showFile` |
| useCodeFileDiff | `.../CommsPanel/CodeDiffModal/useCodeFileDiff.ts` | **new hook** — baseline blob + current text → `{original, draft}` |
| RawCodeDiffView | `.../CommsPanel/CodeDiffModal/RawCodeDiffView.tsx` (+ `.module.css`) | **new thin presenter** — two raw strings → SplitDiff/UnifiedDiff |
| ImpactPanel | `.../CommsPanel/ImpactPanel/ImpactPanel.tsx` (+ `.module.css`) | **new component** — queries impact, hides on null |
| CodeDiffModal | `.../CommsPanel/CodeDiffModal/CodeDiffModal.tsx` (+ `.module.css`) | **new modal** — combines diff + collapsible ImpactPanel |
| "See changes" action | `.../CommsPanel/cards/MsgCard/MsgCard.tsx` | **new pill**, gated on `artifactPath` + code extension |

Reused as-is (no change): `SplitDiff/`, `UnifiedDiff/`, `fileDiffUtils.ts`
(`fileDiffOps`, `toSplitRows`, `toUnifiedRows`, `diffStats`), `diffUtils.ts`
(`computeLineDiff`) — all under `components/Editor/DraftDiffViewer/`.

## Backend Changes

### 1. `runner/code_context_cli.py` — `CliProvider.detect_changes`

New method, sibling to the existing `_run`/`_file_section` shell-out helpers:

```python
def detect_changes(self, project_root: str) -> dict | None:
    """Working-tree-vs-HEAD change set for the whole repo, or None on failure.
    Never raises — a shell/parse miss degrades to None so the impact panel
    simply hides. NOT cached: the working tree changes constantly."""
    # shells: codebase-memory-mcp cli detect_changes '{"repo_path": <root>}'
    # parse stdout JSON → {changed_files: [...], impacted_symbols: [...], depth: N}
    # any exception / non-zero exit / unparseable stdout → return None
```

- Reuses the existing `_run` subprocess plumbing already in `CliProvider`.
- **No caching** — unlike `_file_section` (which caches non-empty graph sections), the
  working tree mutates on every edit, so a cache would go stale immediately.
- Layer-legal: this is the only place that shells out for `detect_changes`; `http_server`
  never shells directly.

### 2. `blueprints/code/query.py` — `op:"impact"` routing branch

Today every `op` funnels through `build_block → query_graph`, so `op:"impact"` behaves
like `op:"callers"`. Add a branch **before** the generic `build_block` path:

```
if op == "impact":
    if not _is_code_file(target):            return null   # non-code → no panel
    changes = provider.detect_changes(project_root)
    if changes is None:                       return null   # graph off / failure
    hit = _filter_to_target(changes, target)  # changed_files ∩ target, symbols for target
    if not hit:                               return null   # file not in change set
    return hit  (as the `result` block)
else:
    <existing build_block path — byte-identical, no behavior change>
```

- `_is_code_file` = shared extension check (see decision 7) — reused by the frontend gate
  in spirit, enforced here as the authoritative server-side guard.
- `_filter_to_target` normalizes both the `detect_changes` paths and `target` to
  repo-relative forward-slash form before intersecting (Windows-path safety, risk 4).
- Every non-hit returns the existing safe-null envelope (`{"ok": true, "result": null,
  ...}`) — the never-500 contract already in place is preserved verbatim.
- Role gating already routes `reviewer`/`architect`/`builder` to the `full` tier, which
  includes `impact` — no gate change needed. The frontend calls with `role:"reviewer"`.
- **Estimated size: ~60–100 LOC** across the provider method + branch + filter helpers.

**Line-budget guard:** `query.py` is currently **311 lines** — under the 400-line SRP
limit but close. Put `_is_code_file` and `_filter_to_target` in
`blueprints/code/_helpers.py` (new, per the shared-helper rule) rather than inline, so
the route file gains only the branch itself (~15–20 lines) and stays comfortably under 400.

## Main Process IPC

### `studio/src/main/ipc/git.ts` — `git:show-file`

New handler alongside the existing `git:commit-board`, reusing the same
`promisify(execFile)` runner:

```ts
ipcMain.handle('git:show-file',
  async (_e, projectPath: string, relPath: string, ref = 'HEAD'):
    Promise<{ content: string | null }> => {
    // guard: root present, relPath has no '..' traversal
    // normalize relPath to forward slashes (git wants POSIX paths, even on Windows)
    // run('git', ['show', `${ref}:${rel}`], { cwd: root })
    //   success → { content: stdout }
    //   non-zero exit (untracked / path not in ref) → { content: null }  ← all-additions
    //   guard fail / unexpected → { content: null }
  })
```

- **Untracked file → `{ content: null }`**, not an error: the hook treats null baseline as
  an empty string, so the diff renders as all-additions (constraint 2).
- **Forward-slash relative paths only** — `git show HEAD:<path>` requires POSIX,
  repo-relative paths; an absolute Windows path fails (risk 4). The renderer passes the
  `artifact_path` value (already stored as a relative-ish path); the handler normalizes.
- Never throws — mirrors `commit-board`'s best-effort contract.

### `preload/index.ts` + `global.d.ts`

Extend the existing `git:` namespace (line ~148) with:

```ts
git: {
  commitBoard: (...) => ...,
  showFile: (projectPath, relPath, ref?) =>
    ipcRenderer.invoke('git:show-file', projectPath, relPath, ref),  // NEW
}
```

Add the matching `showFile` signature to `window.pathly.git` in `global.d.ts`.

## Frontend Changes

### 1. `useCodeFileDiff.ts` (new hook — data only)

`CodeDiffModal/useCodeFileDiff.ts`

- Input: `{ projectPath, artifactPath }`.
- `window.pathly.git.showFile(projectPath, artifactPath)` → **baseline** (null → `''`).
- `window.pathly.fs.read(<abs path>)` → **current** working-tree content.
- Returns `{ original: string, draft: string, loading, error }` — two raw strings, NOT
  `DiffHunk[]`. It does **not** compute the diff itself; the presenter does, so the hook
  stays a pure data hook (studio hook rule: data hooks return data, no diff logic).

### 2. `RawCodeDiffView.tsx` (new thin presenter)

`CodeDiffModal/RawCodeDiffView.tsx`

**Why new, not `CodeDiffView` directly:** `CodeDiffView` takes `hunks: DiffHunk[]` and its
`useMemo` calls `buildDocument(hunks, side)`, which reconstructs a **markdown document from
`## `-heading sections**. Feeding it code would require faking markdown hunks. Instead
reuse the layer directly beneath it — which already operates on raw strings:

```
original, draft (strings)
   → fileDiffOps(original, draft)        // = computeLineDiff, line-level
   → toSplitRows(ops) / toUnifiedRows(ops)
   → <SplitDiff rows={...}/> | <UnifiedDiff rows={...}/>
   + diffStats(ops) for the +N/−N header
```

`RawCodeDiffView` is essentially `CodeDiffView` with `buildDocument` removed and two string
props in place of `hunks` — ~45 lines, split/unified toggle preserved, read-only. All the
heavy lifting (`SplitDiff`, `UnifiedDiff`, `fileDiffUtils`, `computeLineDiff`) is imported
unchanged from `Editor/DraftDiffViewer/`.

### 3. `ImpactPanel.tsx` (new)

`ImpactPanel/ImpactPanel.tsx` (+ `.module.css`)

- Prop: `filePath: string`.
- On mount: `POST /code/query { op:"impact", target: filePath, role:"reviewer",
  project_root, scope:"(interactive)" }` — parenthesized scope so it is **not** board-logged
  (no board noise from a UI hover).
- Renders `⚠ N callers affected` with an expandable list of callers / impacted symbols.
- **`result: null` or empty → render nothing** (component returns null). Loading → spinner.
- Never surfaces an error state to the user — a failed/absent query is indistinguishable
  from "no impact panel," by design (graceful degradation).

### 4. `CodeDiffModal.tsx` (new)

`CodeDiffModal/CodeDiffModal.tsx` (+ `.module.css`)

- Props: `{ projectPath, artifactPath, onClose }`.
- Layout: `RawCodeDiffView` (primary, fed by `useCodeFileDiff`) with `ImpactPanel`
  **collapsible and subordinate** beneath/beside it (per Designer recommendation — impact
  is context, the diff is the subject).
- Opens only for code-file artifacts; the pill gate (below) is the entry guard, and the
  modal itself is the diff surface. For a non-code artifact the pill never appears, so the
  modal is never reached for markdown — but if reached, it shows the text diff and no panel.

### 5. "See changes" action on the artifact card

`cards/MsgCard/MsgCard.tsx`

- Render a "See changes" pill **only when** `m.artifactPath` is set **and**
  `isCodeFile(m.artifactPath)` is true (shared extension check).
- On click: open `CodeDiffModal` with `{ projectPath, artifactPath: m.artifactPath }`.
- Hidden (not disabled-and-visible) when the artifact is non-code or the feature flag is
  off — a supervisor should not see a dead control.

## Data Flow — "See changes" interaction

```
1. Supervisor clicks "See changes" on an artifact card (m.artifactPath set, code file).
2. CodeDiffModal mounts with { projectPath, artifactPath }.
3. useCodeFileDiff fires two calls in parallel:
     a. git.showFile(projectPath, artifactPath) → baseline blob (or null → '')
     b. fs.read(abs(artifactPath))              → current working-tree text
4. Hook returns { original, draft }. RawCodeDiffView computes line diff and renders
   Split/Unified. Supervisor sees exact changed lines vs committed HEAD.
5. In parallel, ImpactPanel POSTs /code/query {op:"impact", target: artifactPath}.
     - Server: op==impact → CliProvider.detect_changes(project_root)
       → codebase-memory-mcp cli detect_changes → {changed_files, impacted_symbols}
       → filter to artifactPath → return callers/symbols block  (or null)
6. ImpactPanel renders "⚠ N callers affected" + list, OR renders nothing if null/empty.
7. Supervisor makes a continue/block/escalate decision from real lines + real blast radius.
   No mutation occurs anywhere in this flow.
```

Failure branches (all render the diff, omit only the panel): untracked file → step 3a null
→ all-additions diff; graph off / detect_changes fail → step 5 null → no panel; non-code
artifact → pill never shown (step 1 never happens).

## Dependency Direction Enforcement

```
db/        → (nothing internal)
runner/    → db/                       CliProvider.detect_changes lives HERE (shells out)
http_server/ → all (lazy in handler)   code/query.py imports runner.code_context lazily
```

- `detect_changes` shelling out is in **`runner/code_context_cli.py`** only — never in the
  HTTP handler (constraint 4). `query.py` reaches it via the already-lazy
  `from pathly_orchestrator.runner import code_context` import inside the route function.
- Studio side: renderer never shells git — it goes renderer → preload (contextBridge) →
  `ipcMain` handler in `main/ipc/git.ts`. The renderer has no `child_process` access.
- Shared frontend helper (`isCodeFile`) is defined once and imported, never copy-pasted
  (studio SRP rule); the server's `_is_code_file` is the authoritative twin.

## Key Decisions

1. **Reuse the render layer BELOW `CodeDiffView`, not `CodeDiffView` itself.**
   `CodeDiffView.useMemo` calls `buildDocument(hunks)` which assumes markdown `## `-section
   structure — wrong grain for code. Instead `RawCodeDiffView` reuses `SplitDiff`,
   `UnifiedDiff`, `fileDiffUtils` and `computeLineDiff` on two raw strings.
   *Trade-off:* one new ~45-line presenter instead of zero, but it avoids faking markdown
   hunks and keeps `CodeDiffView` single-purpose (Open/Closed — extend by adding a file).
   *(This refines the brief's "reuse CodeDiffView" — the reusable seam is one level down.)*

2. **Do NOT reuse `useDraftDiff` / `DraftDiffViewer`.** `useDraftDiff` diffs markdown by
   `## ` headings (section grain); `DraftDiffViewer` is the accept/reject draft-triage modal
   (surface b). Both fight code-file line-diff needs. *Trade-off:* no shared modal wrapper,
   but the read-only board diff has different affordances (no accept/apply) so sharing would
   couple two divergent workflows.

3. **`detect_changes` = whole-working-tree vs HEAD, then filter by file.** The tool has no
   per-file targeting; we call it project-wide and intersect `changed_files` /
   `impacted_symbols` with the target path. *Trade-off:* one broad shell call per panel open
   (no cache) instead of a targeted query — acceptable because it fires on an explicit user
   click, not in a hot loop.

4. **Honest labeling — "impact of current uncommitted changes in this file."** The panel must
   never claim per-hunk or hypothetical impact the tool cannot compute (out-permanently
   constraint). *Trade-off:* less precise than a hunk-level graph, but truthful; per-hunk
   impact is deferred engine work, explicitly out of scope.

5. **One-way data flow, zero mutation in MVP.** Card → modal → hook + panel; nothing writes.
   *Trade-off:* the supervisor can vet but not act-in-place (no accept/apply) — that is
   surface (b), intentionally deferred; the MVP proves the vet loop first.

6. **Layer boundary: `detect_changes` shells from CliProvider only.** *Trade-off:* the HTTP
   handler must round-trip through the runner import rather than shelling directly — slightly
   more indirection, but it preserves the `http_server → runner → db` direction and keeps
   the shell-out testable in one place.

7. **Server-side `_is_code_file` is authoritative; the frontend gate is a UX mirror.** The
   pill hides for non-code files, but the server independently returns null for a non-code
   `op:"impact"` target — so a stale/forced client can never make the panel claim impact on a
   markdown file. *Trade-off:* the extension list is maintained in two languages (TS + Py);
   both are tiny and unlikely to churn.

## Risks (prioritized)

1. **[HIGH] `detect_changes` output shape is unverified.** The exact JSON of
   `codebase-memory-mcp cli detect_changes` (`changed_files`/`impacted_symbols` field names,
   path format — absolute vs repo-relative) is assumed, not confirmed. If it differs, the
   `_filter_to_target` intersection silently returns nothing → panel always hidden (fails
   safe, but the feature is dead). *Mitigation:* **first build step** is a throwaway probe —
   run the CLI against this repo, capture real output, pin the parser to it. Make
   `_filter_to_target` tolerant of both absolute and relative path forms (mirror the defensive
   multi-layout approach already used for codex token parsing).

2. **[MED] Artifact path ≠ current on-disk path.** `comms_artifacts.artifact_path` may not
   match the working-tree file at view time (renamed, moved, multi-file run). MVP assumes the
   common case: a fresh headless run touched one file and posted it. *Mitigation:* if
   `fs.read` returns null (file gone) show a clear "artifact file not found on disk" empty
   state, not a crash; multi-file runs are surface (d), a named fast-follow.

3. **[MED] Windows path handling for `git show`.** `git show HEAD:<path>` needs
   forward-slash, repo-relative paths; an absolute `C:\...` path fails and the diff shows
   all-additions (a lie). *Mitigation:* normalize to POSIX-relative in **both** the git
   handler and `_filter_to_target`; add a unit test with a backslash input.

4. **[LOW] `query.py` approaching the 400-line SRP limit (currently 311).** Adding the
   branch inline risks pushing it over. *Mitigation:* put `_is_code_file` /
   `_filter_to_target` in a new `blueprints/code/_helpers.py`; the route file gains only
   ~15–20 lines.

5. **[LOW] DraftDiffViewer redundancy audit (constraint 5).** Confirm at build-start that
   `change-explorer`/`DraftDiffViewer` do not already surface an Impact panel. Pre-scout says
   `ImpactPanel` exists nowhere — so this is expected to be a no-op audit, not a blocker, but
   it must be the first BUILD action per the consultation decision.

## Out of Scope for This Proposal

- Surface (b): draft-triage with accept/reject/apply controls.
- Surface (c): two-artifact compare with a file picker.
- Surface (d): multi-file run-review panel ("Review changes" from a run card) — agreed
  fast-follow.
- Any write/mutation from the diff view.
- Clickable/navigable call-graph visualisation.
- Per-hunk or hypothetical impact (requires new engine work; out permanently for v1).
- Multi-commit baselines / run-start SHA persistence (default is committed HEAD; revisit if
  team runs regularly span commits — noted as open question 1).
- The Walkthrough artifact (single-agent graph-fed narrative) — rollout step 5.
- Walkthrough `.html` export — rollout step 6.

## Rollout Order

1. **Probe `detect_changes`** — run `codebase-memory-mcp cli detect_changes` against this
   repo, capture real output shape, pin the parser (retires risk 1). Also run the constraint-5
   redundancy audit here.
2. **Backend** — `CliProvider.detect_changes` + `op:"impact"` branch + `code/_helpers.py`
   filter/extension helpers. Unit-test the filter against the probe output.
3. **Main-process IPC** — `git:show-file` handler + preload + `global.d.ts`. Test untracked
   (null) and tracked (blob) and a backslash path.
4. **Diff pipeline (internal build-first)** — `useCodeFileDiff` + `RawCodeDiffView` reusing
   SplitDiff/UnifiedDiff/fileDiffUtils. Renders a correct read-only line diff standalone.
5. **Impact panel** — `ImpactPanel` against `/code/query`; verify null-hides on graph-off.
6. **Assemble + ship together** — `CodeDiffModal` (diff + collapsible ImpactPanel) + the
   "See changes" pill on `MsgCard`. **This is the shippable milestone** — diff and impact land
   in one PR; do not cut a release after step 4.
7. **Post-ship** — dogfood on one real headless run (open question 2): did the panel ever
   flip a continue→block decision? Feed into the surface (d) roadmap.
</content>
</invoke>
