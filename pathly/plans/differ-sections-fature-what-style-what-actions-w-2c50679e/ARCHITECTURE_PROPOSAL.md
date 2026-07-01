# ARCHITECTURE_PROPOSAL — differ-sections (surface a)

Feature: `differ-sections-fature-what-style-what-actions-w-2c50679e`
Scope: hunk styling + per-hunk "view impact" action + `ImpactPanel` blade for **surface (a)** of the board differ (artifact vs committed git HEAD, read-only).
Rigor: standard.

> Authoritative inputs: this feature's `PO_NOTES.md`, `pathly/plans/board-differ/APPROACH.md`, and the code read during design (`useDraftDiff.ts`, `CodeDiffView.tsx`, `code_context_cli.py`, `code/query.py`, `fs.ts`, `global.d.ts`).

---

## 0. Position (read this first)

Two decisions drive everything below:

1. **Build surface (a) as a NEW top-level component (`ArtifactDiffViewer/`), not a `mode` prop on `DraftDiffViewer`.** `DraftDiffViewer` is already a full triage/apply/edit machine wired to `onApply`/`onDiscard`/`reconstruct`. Surface (a) is read-only and has none of that — bolting a `mode: 'view'` flag onto it forces surface-(a) concerns (git baseline resolution, impact blade, no footer) into a component that already does four jobs, and pushes it past the 150-line rule. Option B is the SRP-correct choice.

2. **The impact layer never touches the diff layer.** `useDraftDiff` and `CodeDiffView` stay pure diff. Impact lives in a separate `useImpact` hook + `ImpactPanel` component. The badge is injected into `CodeDiffView` via a callback prop only — `CodeDiffView` knows nothing about callers or `/code/query`.

Everything else is a consequence of these two.

```
┌──────────────────────────────────────────────────────────────┐
│ ArtifactDiffViewer  (NEW — surface a container, read-only)     │
│   originalPath = git:<relPath>   draftPath = <artifact file>   │
│                                                                │
│   ┌────────────────────────────┐   ┌───────────────────────┐ │
│   │ CodeDiffView (REUSED)       │   │ ImpactPanel (NEW blade)│ │
│   │  + onHunkFocus callback     │──►│  activeHunk → useImpact│ │
│   │  + hunk ⚠ N callers badge   │   │  POST /code/query      │ │
│   └────────────────────────────┘   └───────────────────────┘ │
│           ▲ hunks (from useDraftDiff, REUSED, unchanged)       │
└───────────┼──────────────────────────────────────────────────┘
            │ window.pathly.git.blob(root, relPath)  (NEW IPC)
            ▼
       git show HEAD:<relPath>   (main process, execFile)
```

---

## 1. Layers touched

| Layer | File | Change | Kind |
|---|---|---|---|
| Main IPC | `studio/src/main/ipc/git.ts` (NEW) | `git:blob` handler → `git show HEAD:<relPath>` | additive |
| Main wiring | `studio/src/main/index.ts` (or wherever handlers register) | call `registerGitHandlers()` | 1 line |
| Preload | `studio/src/main/preload/index.ts` | expose `pathly.git.blob(...)` | additive |
| Types | `studio/src/renderer/src/types/global.d.ts` | add `git: { blob(...) }` to `pathly` | additive |
| Renderer | `studio/.../DraftDiffViewer/ArtifactDiffViewer/` (NEW folder) | container + hook + CSS | additive |
| Renderer | `studio/.../DraftDiffViewer/ImpactPanel/` (NEW folder) | blade + CSS | additive |
| Renderer | `studio/.../DraftDiffViewer/useImpact.ts` (NEW) | `/code/query` fetch + cache | additive |
| Renderer | `CodeDiffView/CodeDiffView.tsx` | add optional `onHunkFocus` + `badgeFor` props | additive, back-compat |
| Renderer | the artifact card / board component that opens the differ | new "See changes" action → mount `ArtifactDiffViewer` | additive |
| Backend | `runner/code_context_cli.py` (`CliProvider`) | add `detect_changes(paths, repo_root)` method | additive |
| Backend | `runner/code_context.py` | expose module-level `detect_changes(...)` passthrough (mirror of `build_block`) | additive |
| Backend | `http_server/blueprints/code/query.py` | route `op == "impact"` → `detect_changes` instead of `build_block` | branch |

No FSM, no DB migration, no new HTTP route, no new transport. Every change is additive or a back-compatible branch.

---

## 2. Frontend component design

### 2.1 Chosen: Option B — `ArtifactDiffViewer`

New folder alongside the other views inside `DraftDiffViewer/`:

```
DraftDiffViewer/
  ArtifactDiffViewer/
    ArtifactDiffViewer.tsx        # container: modal shell + CodeDiffView + ImpactPanel
    ArtifactDiffViewer.module.css
    useArtifactDiff.ts            # resolves git: baseline, feeds useDraftDiff
  ImpactPanel/
    ImpactPanel.tsx
    ImpactPanel.module.css
  useImpact.ts                    # /code/query fetch + cache (no React DOM)
```

**Props:**
```ts
interface ArtifactDiffViewerProps {
  artifactPath: string   // disk path of the artifact file (the "draft"/after side)
  repoRoot: string       // git repo root — for git:blob + impact repo_path
  relPath: string        // artifact path RELATIVE to repoRoot — the git HEAD target
  onClose: () => void
  pushToast?: (message: string, kind?: 'info' | 'success' | 'error') => void
}
```
No `onApply` / `onDiscard` / `comments` — surface (a) is read-only, that is the whole point of splitting.

**Why not reuse `DraftDiffViewer`'s modal shell:** the shell is ~20 lines (backdrop + header + `ViewToggle`). Surface (a) has no view toggle (it is always the code view) and no footer. Duplicating the ~15-line backdrop/header is cheaper than parameterizing the existing shell with conditionals. Keep them independent.

### 2.2 Baseline resolution — `useArtifactDiff`

`useDraftDiff` reads BOTH sides via `window.pathly.fs.read()` — disk files. Surface (a)'s "before" is the committed HEAD blob, which is not on disk. Rather than teach `useDraftDiff` about git (which would pollute the pure diff hook), `useArtifactDiff` resolves the HEAD blob to text FIRST, writes it nowhere, and passes it into the diff as text.

Problem: `useDraftDiff` takes two *paths*, not two *strings*. Two options:

- **B1 (recommended): add a thin text-input path to `useDraftDiff`.** Give `useDraftDiff` an optional pre-resolved `originalText?: string` that, when provided, is used instead of `fs.read(originalPath)`. Minimal (~4 lines), keeps the git concern out of the hook, and the polling loop still watches only `draftPath` (correct — HEAD doesn't change while the modal is open).
- **B2: virtual `git:<relPath>` URI resolved inside `fs.read`.** Rejected — overloads the fs bridge channel with git semantics and spreads the git dependency into the fs layer. Violates SRP at the IPC boundary.

Go with **B1**. `useArtifactDiff` does: `blob = await window.pathly.git.blob(repoRoot, relPath)` → `useDraftDiff(relPath, artifactPath, [], { originalText: blob ?? '' })`. A `null` blob (uncommitted/new file) becomes `''` — the diff renders as an all-added file. See risk 2.

### 2.3 `CodeDiffView` changes — badge injection only

`CodeDiffView` stays diff-only. Add two OPTIONAL props (both undefined by default → existing callers unaffected):

```ts
interface Props {
  hunks: DiffHunk[]
  fileName?: string
  defaultLayout?: Layout
  onHunkFocus?: (hunk: DiffHunk) => void        // NEW — parent tracks active hunk
  badgeFor?: (hunk: DiffHunk) => number | null   // NEW — caller count, or null = no badge
}
```

- `badgeFor(hunk)` returns the caller count for a hunk or `null`. When non-null, `CodeDiffView` renders a `⚠ {n} callers` chip on that hunk's header row. `CodeDiffView` does not know where the number comes from.
- Clicking the chip (or the hunk header) calls `onHunkFocus(hunk)`. The parent sets `activeHunk`, which drives `ImpactPanel`.

> Note on the current `CodeDiffView`: it reconstructs whole original/draft documents and renders `SplitDiff`/`UnifiedDiff` rows — it does not currently render per-hunk header rows. Adding a per-hunk badge means the diff must expose hunk boundaries in the rendered output. **This is the single largest piece of frontend work** and is called out in `useViewMode`/`fileDiffUtils` territory. If per-hunk anchoring in `SplitDiff`/`UnifiedDiff` proves too invasive within the 150-line budget, fall back to **file-header-level badge** (see §2.5) which requires no row-level change. Builder must scope this in Conv 2 before committing to per-hunk.

### 2.4 `ImpactPanel` (new blade)

```ts
interface ImpactPanelProps {
  filePath: string          // relPath (target for /code/query)
  repoRoot: string
  activeHunk: DiffHunk | null
}
```
- Uses `useImpact(filePath, repoRoot)` which fetches once per file (impact is file-scoped; see §7 decision 3) and returns `{ changedSymbols, callers, affectedFlows, loading, backendOff }`.
- Renders a blade: per changed symbol → `name  ⚠ {caller_count} callers`; an `affects flow: …` line; nothing else.
- **Graceful degradation:** `backendOff` (result was `null`) → render `null` (component absent, not an error state). Matches the mandatory PO constraint.
- `activeHunk` scrolls/highlights the matching symbol in the blade when per-symbol data is available; with file-level data it is ignored.

### 2.5 Badge granularity — two render paths

```
per-symbol data available          per-file data only (fallback)
──────────────────────────         ────────────────────────────
match hunk.line range ─┐           badge on CodeDiffView file
to symbol.line range   │           header bar (§CodeDiffView
                       ▼           .bar), NOT per hunk
⚠ N on that hunk header
```
The `badgeFor` callback encapsulates this: with per-symbol data it matches line ranges; with per-file data it returns `null` for every hunk and the file-header badge is rendered by `ArtifactDiffViewer` instead. One switch, decided by the shape `useImpact` returns.

> Caveat: current `DiffHunk` (section-based, from `useDraftDiff`) carries `heading`/content, **not line ranges**. Per-symbol line-range matching needs a line index per hunk. If that is not cheaply derivable, per-symbol matching degrades to file-level badge automatically. Builder verifies in Conv 2.

---

## 3. Dependency direction (import rules)

```
ArtifactDiffViewer ──► useArtifactDiff ──► useDraftDiff (unchanged)
        │                     └────────► window.pathly.git.blob
        ├──► CodeDiffView (unchanged internals; +2 optional props)
        └──► ImpactPanel ──► useImpact ──► POST /code/query
```

Hard rules the builder must not violate:
- `ImpactPanel` imports **nothing** from `DraftDiffViewer` / `ArtifactDiffViewer`. It takes primitive props only (`filePath`, `repoRoot`, `activeHunk`).
- `CodeDiffView` imports **nothing** impact-related. Badge data arrives via `badgeFor`/`onHunkFocus` props.
- `useDraftDiff` gains at most the optional `originalText` input (B1). No impact, no git awareness.
- `useImpact` imports nothing from any diff component — it is a data hook returning data only (no setters exposed), per the Studio data-hook rule.
- `ArtifactDiffViewer` is the ONLY place that knows about both diff and impact — it is the composition root.

---

## 4. Backend `op: "impact"` wiring

### 4.1 `CliProvider.detect_changes` (in `code_context_cli.py`)

New method mirroring the safety contract of `build_block` (never raises, deadline-bounded, degrades to `None`):

```python
def detect_changes(self, paths: list[str], repo_root: str) -> dict | None:
    if not paths or not repo_root:
        return None
    exe = shutil.which(self.tool)
    if not exe:
        return None                       # binary not installed -> safe no-op
    payload = json.dumps({"repo_path": repo_root, "paths": list(paths)})
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        out = _await_or_empty(
            pool.submit(self._run, exe, ["cli", "detect_changes", payload])
        )
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    try:
        data = json.loads(out) if out else None
    except Exception:
        return None
    return data if isinstance(data, dict) else None
```
Reuses `_run`, `_await_or_empty`, and the same `_CLI_TIMEOUT_S` deadline. Same "cli binary present?" gate as `build_block`, so risk 1 is covered by construction. `_run` returns a JSON string; parse to dict here so the route gets structured data (not the text block `build_block` returns).

### 4.2 `code_context.py` module passthrough

Add a module-level `detect_changes(paths, repo_root) -> dict | None` next to `build_block` that resolves the provider and delegates, wrapped in the same never-raise try/except returning `None`. This keeps the route talking to `runner.code_context` (the sanctioned downward import), not directly to `CliProvider`.

### 4.3 `code/query.py` — branch on `op == "impact"`

Today every op flows into `build_block` (which only ever runs `query_graph`). Split the impact op off before that call:

```python
if op.strip().lower() == "impact":
    repo_root = str(data.get("project_root") or data.get("repo_root") or "")
    result = _cc.detect_changes([target], repo_root)   # dict | None
else:
    block = _cc.build_block(scope, [target], role, budget)
    result = block or None
```
Everything around it is untouched: the role gate (`_gate`) already lists `impact` in the `full` tier (`architect/builder/reviewer/explorer`); the content-hash cache keys on `(op, target, chash)` so impact caches correctly per file; `_log_query` and the never-500 wrapper still apply. **One behavioral note:** `result` for `impact` is now a JSON object, not a string — the response envelope's `result` field becomes an object for this op. The frontend already expects an object shape; no other op consumer is affected.

### 4.4 Response shape (the contract the badge reads)

```jsonc
{
  "ok": true,
  "op": "impact",
  "target": "src/pathly_orchestrator/runner/code_context_cli.py",
  "backend": "cli",
  "cached": false,
  "result": {
    "changed_symbols": [
      { "name": "build_block", "file": "...", "line_start": 75, "line_end": 104, "caller_count": 3 }
    ],
    "affected_flows": ["runner prompt assembly"],
    "callers": ["get_provider", "code_query", "build_prompt"]
  }
}
```
Badge count = `changed_symbols[i].caller_count` (per-symbol path) OR `len(result.callers)` (file-level fallback). `result === null` → panel absent.

> The exact `detect_changes` output keys are the #1 open decision (§7). The route should pass the tool's JSON through mostly untranslated; the frontend normalizes. If the tool's keys differ, adapt the frontend normalizer in `useImpact`, not the route — keep the route a thin passthrough.

---

## 5. Git baseline IPC

New file `studio/src/main/ipc/git.ts`:

```ts
import { ipcMain } from 'electron'
import { execFile } from 'child_process'

export function registerGitHandlers(): void {
  ipcMain.handle('git:blob', async (_e, repoRoot: string, relPath: string): Promise<string | null> => {
    return new Promise((resolve) => {
      execFile('git', ['show', `HEAD:${relPath.replace(/\\/g, '/')}`],
        { cwd: repoRoot, maxBuffer: 20 * 1024 * 1024 },
        (err, stdout) => resolve(err ? null : stdout))
    })
  })
}
```
- `null` on ANY error — including "file not in HEAD" (new/uncommitted file). Caller treats `null` as empty baseline → all-added diff (risk 2).
- `relPath` is forward-slashed: git addresses blobs with `/` even on Windows.
- `maxBuffer` raised (default 1 MB is too small for large source files).
- No path-safety gate like `fs.ts` needs — git only reads its own repo tree, and `repoRoot` is supplied by the app (the project root), not user free-text. (If the board ever lets a user type an arbitrary repoRoot, add an `isWithin(repoRoot, home)` check mirroring `fs.ts`.)

Preload (`preload/index.ts`), inside the `pathly` object:
```ts
git: {
  blob: (repoRoot: string, relPath: string): Promise<string | null> =>
    ipcRenderer.invoke('git:blob', repoRoot, relPath),
},
```

Types (`global.d.ts`), inside `pathly`:
```ts
git: {
  blob: (repoRoot: string, relPath: string) => Promise<string | null>
}
```

Register `registerGitHandlers()` where the other `registerXHandlers()` are called in the main process bootstrap.

---

## 6. File size + SRP compliance

| File | Est. lines | Responsibility | Risk |
|---|---|---|---|
| `git.ts` | ~20 | one IPC handler | none |
| `ArtifactDiffViewer.tsx` | ~90 | modal shell + compose CodeDiffView + ImpactPanel | ok |
| `useArtifactDiff.ts` | ~40 | resolve git baseline, feed useDraftDiff | none |
| `ImpactPanel.tsx` | ~80 | render blade (symbols/callers/flows) | ok |
| `useImpact.ts` | ~70 | fetch /code/query, normalize, cache, `backendOff` | none |
| `CodeDiffView.tsx` (edit) | 68 → ~110 | +badge render +onHunkFocus | **watch 150** |
| `code_context_cli.py` (edit) | 178 → ~205 | +detect_changes | ok (<400) |
| `code_context.py` (edit) | ~230 → ~250 | +module passthrough | ok |
| `code/query.py` (edit) | 228 → ~245 | +impact branch | ok (<400) |

**Flags:**
- If `CodeDiffView` per-hunk badge rendering pushes it near 150, extract a `HunkBadge/` sub-component (own folder + CSS per Studio rule) and/or a `useHunkBadges` helper. Do not inline styles for the badge — new `.module.css` classes with `data-status` if it has states.
- `ImpactPanel` per-symbol row → extract `ImpactRow/` if it grows past ~120.

---

## 7. Open decisions (working assumption + what builder verifies)

1. **`detect_changes` CLI contract** — *Assumption:* `codebase-memory-mcp cli detect_changes '{"repo_path": <root>, "paths": [<file>]}'`, diffs vs HEAD internally, returns `{changed_symbols, affected_flows, callers}`.
   *Verify before Conv 4 (backend):* run `codebase-memory-mcp cli detect_changes --help` (or read its README) to confirm (a) arg name (`paths` vs `files` vs a diff string), (b) whether it reads the working tree itself or needs a diff, (c) exact output keys. Adapt only `useImpact`'s normalizer + the payload dict in `detect_changes` — not the route logic.

2. **Per-symbol vs per-file granularity** — *Assumption:* per-symbol preferred (`caller_count` per symbol) → hunk-level badge. *Fallback:* per-file → single badge on the file header. *Verify in Conv 2/4:* inspect a real `detect_changes` response; also confirm `DiffHunk` can expose a line range for symbol→hunk matching. If either is missing, ship the file-header badge (still valuable, no line-range dependency).

3. **Whole path list vs single file** — *Decision (resolved):* surface (a) is always ONE artifact at a time, so `paths` is always `[relPath]`. Pass the single file. No multi-file batching needed; revisit only for surface (c).

4. **Expand/collapse + active-hunk state** — *Decision (resolved):* stateless, reset on each open. `activeHunk` initializes `null` (blade shows the file-level summary until a hunk is focused). No persistence.

5. **Baseline = committed HEAD** — *Decision (resolved, per APPROACH):* `git show HEAD:<path>`. Multi-commit runs are out of scope for surface (a).

---

## 8. Key risks

1. **`detect_changes` not yet callable from `code_context_cli.py`.**
   *Impact:* the whole ImpactPanel is dead without it. *Mitigation:* add `CliProvider.detect_changes` FIRST (Conv 4), gated by the exact same `shutil.which(self.tool)` check as `build_block`, returning `None` when absent. The frontend already treats `null` as "backend off → panel absent", so an un-wired backend degrades to a plain diff — never an error. Depends on `code-intel-foundation` being merged (PO constraint); if not merged, the op returns `null` and the feature still ships the diff.

2. **`git show HEAD:<path>` for a file not in HEAD (new/uncommitted).**
   *Impact:* git errors, no baseline. *Mitigation:* `git:blob` returns `null` on error; `useArtifactDiff` maps `null → ''`; the diff renders as an all-added file. Correct semantics — a brand-new artifact genuinely is "all added" vs HEAD. Surface a toast only if BOTH sides are empty.

3. **`CodeDiffView` per-hunk badge exceeds the 150-line rule / per-hunk anchoring is hard.**
   *Impact:* the current `CodeDiffView` renders reconstructed split/unified rows with no per-hunk header seam, and `DiffHunk` lacks line ranges. Retrofitting per-hunk badges may be invasive. *Mitigation:* (a) prefer the file-header badge as the baseline deliverable — zero row-level change, satisfies "hunk-level ⚠ N callers" at file granularity; (b) if per-hunk is pursued, extract `HunkBadge/` to stay under 150; (c) scope this explicitly in Conv 2 before committing. Do NOT let badge work bloat `CodeDiffView` past the limit.

---

## 9. Suggested build order (conversation-by-conversation)

1. **Conv 1 — git baseline IPC.** `git.ts` + preload + `global.d.ts`. Independent, testable via a throwaway renderer call.
2. **Conv 2 — `ArtifactDiffViewer` + `useArtifactDiff` (diff only, no impact).** Reuse `CodeDiffView` as-is; wire the "See changes" action on the artifact card. Ships surface (a) plain diff. **Scope the per-hunk vs file-header badge decision here.**
3. **Conv 3 — `CodeDiffView` badge/focus props + `ImpactPanel` + `useImpact` (frontend only, backend may still return null).** Panel is absent until backend lands — safe.
4. **Conv 4 — backend `op:"impact"` wiring.** `CliProvider.detect_changes` + `code_context` passthrough + `code/query.py` branch. **Verify the CLI contract (decision 1) before writing the payload.**
5. **Conv 5 — normalize + granularity fallback.** Reconcile real `detect_changes` output shape in `useImpact`; wire per-symbol or file-level badge per what the tool actually returns.

Gate between Conv 3 and Conv 4: nothing breaks if backend is unwired — panel is simply absent. This ordering means every conversation leaves the app in a shippable state.
