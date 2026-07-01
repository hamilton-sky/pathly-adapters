# Implementation Plan — differ-sections (surface a)

Feature: `differ-sections-fature-what-style-what-actions-w-2c50679e`
Rigor: standard

Gate rule: every conversation leaves the app in a runnable, shippable state.
No partial-done states across conversation boundaries.

---

## Phase 1 — Git baseline IPC

**Delivers:** US-1

**Goal:** Wire the `git:blob` IPC channel so the renderer can retrieve committed HEAD content of any file. This is the only piece that touches the main process and is independent of all frontend diff work.

**Files to create / modify:**

| File | Action | Notes |
|---|---|---|
| `studio/src/main/ipc/git.ts` | CREATE | `registerGitHandlers()` — `ipcMain.handle('git:blob', ...)` calling `execFile('git', ['show', 'HEAD:<relPath>'])` with `cwd: repoRoot`, `maxBuffer: 20MB`; returns `string \| null`; resolves `null` on any error |
| `studio/src/main/index.ts` | EDIT (1 line) | Import `registerGitHandlers` and call it inside `registerIpcHandlers()` at lines 287–296 |
| `studio/src/main/preload/index.ts` | EDIT (additive) | Add `git: { blob: (repoRoot, relPath) => ipcRenderer.invoke('git:blob', repoRoot, relPath) }` inside the `pathly` object |
| `studio/src/renderer/src/types/global.d.ts` | EDIT (additive) | Add `git: { blob: (repoRoot: string, relPath: string) => Promise<string \| null> }` to the `pathly` namespace |

**Implementation details:**
- `relPath` must have backslashes replaced with forward slashes before passing to git (`relPath.replace(/\\/g, '/')`)
- `maxBuffer` set to `20 * 1024 * 1024` (20 MB) — default 1 MB is insufficient for large source files
- No path-safety gate needed: `repoRoot` is supplied by the app (the project root), not user free-text
- `execFile` is used (not `exec`) to avoid shell injection

**Done when:**
- `npx tsc --noEmit` in `studio/` reports zero errors
- A throwaway renderer call `window.pathly.git.blob('/some/repo', 'src/file.py')` resolves without throwing (can be verified in devtools console with a real repo path)

---

## Phase 2 — ArtifactDiffViewer + diff wiring

**Delivers:** US-2, US-3, US-4, US-5

**Goal:** Ship surface (a) as a plain diff — no impact yet. The supervisor can open "See changes" from an artifact card and see the committed HEAD vs artifact diff. The impact blade is not wired; `ImpactPanel` is not mounted yet.

**Files to create / modify:**

| File | Action | Notes |
|---|---|---|
| `studio/src/renderer/src/components/DraftDiffViewer/ArtifactDiffViewer/ArtifactDiffViewer.tsx` | CREATE | Modal shell: fixed overlay + panel; props = `{ artifactPath, repoRoot, relPath, onClose, pushToast? }`; composes `useArtifactDiff` + `CodeDiffView`; no footer; portal to `document.body` |
| `studio/src/renderer/src/components/DraftDiffViewer/ArtifactDiffViewer/ArtifactDiffViewer.module.css` | CREATE | Dark-mode tokens per DESIGN.md; overlay backdrop, panel sizing, header row |
| `studio/src/renderer/src/components/DraftDiffViewer/ArtifactDiffViewer/useArtifactDiff.ts` | CREATE | Calls `window.pathly.git.blob(repoRoot, relPath)`, maps null to `''`, calls `useDraftDiff(relPath, artifactPath, [], { originalTextOverride: blob })` |
| `studio/src/renderer/src/components/DraftDiffViewer/useDraftDiff.ts` | EDIT | Add optional `options?: { originalTextOverride?: string }` 4th param; when provided, skip `fs.read(originalPath)` and use the override string; polling loop watches only `draftPath` (correct — HEAD does not change) |
| `studio/src/renderer/src/components/BoardMessages/MsgCard.tsx` | EDIT | Add `showDiff` boolean state (alongside existing `showDetails`); only one active at a time |
| `studio/src/renderer/src/components/BoardMessages/ArtifactModal.tsx` | EDIT | Add "See changes" button in footer (lines 153–162); only when `m.artifactPath` exists and `m.atype === 'code'`; clicking sets `showDiff(true)` |

**Implementation details:**
- `ArtifactDiffViewer` mounts only when `showDiff === true`; unmounts fully on close (no hidden state)
- Derive `repoRoot` and `relPath` from `m.artifactPath`: `repoRoot` is the project root (available from context/store); `relPath` is the artifact path relative to `repoRoot`
- When both original and draft are empty strings (after resolution), call `pushToast('Both artifact and HEAD content are empty', 'error')`
- Escape key listener inside `ArtifactDiffViewer` calls `onClose`
- `ArtifactDiffViewer.tsx` must stay at or below 90 lines; `useArtifactDiff.ts` at or below 40 lines

**Size guard:** If adding `badgeFor`/`onHunkFocus` props to `CodeDiffView` is needed in this phase, do NOT do it — that belongs to Phase 3. Phase 2 passes no badge props; `CodeDiffView` renders exactly as before.

**Done when:**
- `npx tsc --noEmit` in `studio/` passes
- A real artifact card with `atype === 'code'` shows a "See changes" button
- Clicking it opens a diff modal showing lines-added/removed against committed HEAD
- Escape and `✕` close it without error
- Artifact cards without `atype === 'code'` show no "See changes" button

---

## Phase 3 — Badge + ImpactPanel frontend

**Delivers:** US-6, US-7, US-8, US-9

**Goal:** Wire the full impact UI. The badge appears on hunk or file headers (depending on what `badgeFor` returns), clicking opens the `ImpactPanel` blade, and `useImpact` calls the backend. At the end of this phase the backend may still return `null` (Conv 4 not yet done) — the blade is simply absent. The app remains shippable.

**Files to create / modify:**

| File | Action | Notes |
|---|---|---|
| `studio/src/renderer/src/components/DraftDiffViewer/CodeDiffView/CodeDiffView.tsx` | EDIT | Add optional `onHunkFocus?: (hunk: DiffHunk) => void` and `badgeFor?: (hunk: DiffHunk) => number \| null` props; render `⚠ N callers` chip on hunk header when `badgeFor` returns non-null; chip calls `onHunkFocus` |
| `studio/src/renderer/src/components/DraftDiffViewer/CodeDiffView/HunkBadge/HunkBadge.tsx` | CREATE (conditional) | Extract badge chip if `CodeDiffView` approaches 150 lines; owns the `AlertTriangle` icon + count text + ARIA attrs |
| `studio/src/renderer/src/components/DraftDiffViewer/CodeDiffView/HunkBadge/HunkBadge.module.css` | CREATE (conditional) | Badge styles per DESIGN.md warning tokens |
| `studio/src/renderer/src/components/DraftDiffViewer/ImpactPanel/ImpactPanel.tsx` | CREATE | Props = `{ filePath, repoRoot, activeHunk }`; uses `useImpact`; renders blade (header, symbol list, callers, flows); `backendOff` → renders null |
| `studio/src/renderer/src/components/DraftDiffViewer/ImpactPanel/ImpactPanel.module.css` | CREATE | Blade animation (max-width 0→360px), header, section styles, reduced-motion guard |
| `studio/src/renderer/src/components/DraftDiffViewer/ImpactPanel/ImpactRow/ImpactRow.tsx` | CREATE | Single symbol row: name left + caller chip right + collapsible callers list |
| `studio/src/renderer/src/components/DraftDiffViewer/ImpactPanel/ImpactRow/ImpactRow.module.css` | CREATE | Row styles per DESIGN.md |
| `studio/src/renderer/src/components/DraftDiffViewer/useImpact.ts` | CREATE | `useImpact(filePath, repoRoot)` → `{ changedSymbols, callers, affectedFlows, loading, backendOff }`; POST `/code/query`; cached per `(filePath, repoRoot)` pair; placeholder normalizer awaiting real shape |
| `studio/src/renderer/src/components/DraftDiffViewer/ArtifactDiffViewer/ArtifactDiffViewer.tsx` | EDIT | Add `activeHunk` state; pass `badgeFor` + `onHunkFocus` to `CodeDiffView`; mount `ImpactPanel` with `activeHunk` |

**Implementation details (badge path decision):**
- Builder must inspect `DiffHunk` at the start of this phase. The type has `heading`/content but NO line-range fields.
- **Default (line ranges unavailable):** `badgeFor` returns `null` for every hunk; `ArtifactDiffViewer` renders a single file-header badge instead using `len(callers)` from `useImpact`. This is the zero-risk path and must ship.
- **Optional (if per-hunk anchoring is achievable cheaply):** derive a line index per hunk from the diff content; `badgeFor` matches against `changed_symbols[i].line_start/line_end`. Only pursue if it fits within the 150-line `CodeDiffView` budget.
- Builder documents which path was taken in a `DECISION.md` note in the feature plan folder.

**`useImpact` normalizer in this phase:** use a placeholder that maps any dict to a best-effort shape based on the assumed contract in ARCHITECTURE_PROPOSAL §4.4. The normalizer is replaced in Conv 5 with the verified real shape.

**`ImpactPanel` import rules (must not violate):**
- `ImpactPanel` imports nothing from `DraftDiffViewer` or `ArtifactDiffViewer` — primitive props only
- `CodeDiffView` imports nothing impact-related
- `useImpact` imports nothing from any diff component

**Done when:**
- `npx tsc --noEmit` passes
- When backend is not wired (returns null): "See changes" opens, diff renders, blade is absent — no console error
- When backend is wired (a stub or real): clicking a badge (or file-header badge) opens the blade with the symbol list
- `prefers-reduced-motion` media query: blade appears with opacity only, no translate

---

## Phase 4 — Backend op:"impact" wiring

**Delivers:** US-10, US-11

**Goal:** Wire the Python backend so `POST /code/query { "op": "impact" }` calls `detect_changes` on the CLI provider and returns a structured result. This unlocks real data for the `ImpactPanel`.

**Prerequisite:** Verify `codebase-memory-mcp cli detect_changes` contract before writing the payload (run `codebase-memory-mcp cli detect_changes --help` or inspect its docs). Confirm: arg name (`paths` vs `files`), whether it reads working tree or needs an explicit diff, exact output keys. If binary is absent, the feature still works (degrades to null).

**Files to modify:**

| File | Action | Notes |
|---|---|---|
| `src/pathly_orchestrator/runner/code_context_cli.py` | EDIT | Add `detect_changes(self, paths: list[str], repo_root: str) -> dict \| None` method to `CliProvider`; mirrors `build_block` safety contract (never raises, deadline-bounded via `_await_or_empty` + `_CLI_TIMEOUT_S`, degrades to None) |
| `src/pathly_orchestrator/runner/code_context.py` | EDIT | Add module-level `detect_changes(paths, repo_root) -> dict \| None` passthrough next to `build_block`; resolves provider and delegates; wrapped in try/except returning None |
| `src/pathly_orchestrator/http_server/blueprints/code/query.py` | EDIT | Add `if op.strip().lower() == "impact":` branch before the existing `build_block` call; calls `_cc.detect_changes([target], repo_root)` and sets `result`; for all other ops, flow is unchanged |

**Implementation details:**

`CliProvider.detect_changes` skeleton (per ARCHITECTURE_PROPOSAL §4.1):
```python
def detect_changes(self, paths: list[str], repo_root: str) -> dict | None:
    if not paths or not repo_root:
        return None
    exe = shutil.which(self.tool)
    if not exe:
        return None
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

- Adjust `["cli", "detect_changes", payload]` args to match the real CLI contract verified in the prerequisite step
- `result` for `impact` op is now a JSON object (not a string) — the response envelope `result` field becomes an object; no other op consumer is affected
- `_gate` in `query.py` already lists `impact` in the `full` tier — no gate change needed
- Content-hash cache in `query.py` keys on `(op, target, chash)` — impact caches correctly; no change needed

**Done when:**
- `python -m pytest tests/ -q` passes
- `curl -s -X POST http://127.0.0.1:8765/code/query -H 'Content-Type: application/json' -d '{"op":"impact","target":"src/pathly_orchestrator/runner/code_context_cli.py","project_root":"/path/to/repo"}'` returns `{"ok": true, "result": {...}}` or `{"ok": true, "result": null}` (never 5xx)
- An existing op (`"query"`) still returns its previous shape — no regression

---

## Phase 5 — Normalize + E2E verify

**Delivers:** US-12, US-13

**Goal:** Replace the placeholder normalizer in `useImpact` with the mapping that matches the real `detect_changes` output shape; verify the full end-to-end path and all degradation paths.

**Files to modify:**

| File | Action | Notes |
|---|---|---|
| `studio/src/renderer/src/components/DraftDiffViewer/useImpact.ts` | EDIT | Replace placeholder normalizer with verified mapping; handle both per-symbol (→ `changedSymbols`) and per-file (→ `callers` only) output shapes; `badgeFor` logic follows from which shape is present |
| `studio/src/renderer/src/components/DraftDiffViewer/ArtifactDiffViewer/ArtifactDiffViewer.tsx` | EDIT (if needed) | Adjust `badgeFor` logic if the real shape changes the per-hunk vs file-header decision |

**Verification steps (builder must run all):**
1. Open "See changes" on a code artifact card in a running Studio instance.
   - Diff renders correctly.
   - If CLI installed: ImpactPanel blade appears with real symbol data.
   - If CLI absent: blade is absent, no error shown.
2. Open "See changes" on a code artifact whose path is not in git HEAD (new file).
   - Diff shows all lines as added.
   - No crash or console error.
3. Open artifact card where `atype !== 'code'` (e.g. a plan markdown artifact).
   - "See changes" button is absent from the ArtifactModal footer.
4. With CLI installed but `detect_changes` returning null (simulate by passing a bad path):
   - Blade absent, diff intact, no visible error.
5. `npx tsc --noEmit` in `studio/` passes with zero errors.
6. `python -m pytest tests/ -q` passes.

**Done when:** All 6 verification steps above pass. No console errors across any degradation path.
