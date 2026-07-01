# User Stories — differ-sections (surface a)

Feature: `differ-sections-fature-what-style-what-actions-w-2c50679e`

Actors:
- **Supervisor**: the human developer / tech lead using the Pathly Command Center board

---

## Conv 1 — Git baseline IPC

### US-1: Retrieve committed git HEAD blob over IPC

As a supervisor,
I want the Electron app to fetch the committed git HEAD version of any file via IPC,
so that the diff viewer can compare the artifact against the correct baseline without
reading any disk path that might be modified by an in-flight run.

**Acceptance criteria:**
- `window.pathly.git.blob(repoRoot, relPath)` is callable from the renderer.
- Returns the UTF-8 string content of `git show HEAD:<relPath>` when the file exists in HEAD.
- Returns `null` when the file is not tracked in HEAD (new/uncommitted), without throwing.
- Returns `null` on any git subprocess error (binary absent, not a git repo, etc.), without throwing.
- `relPath` uses forward slashes internally regardless of the host OS.
- The handler is registered in the main process bootstrap (`registerGitHandlers()` in `index.ts`).
- TypeScript types compile without error: `global.d.ts` declares `pathly.git.blob` correctly.

**Delivered by:** Conv 1

---

## Conv 2 — ArtifactDiffViewer + diff wiring

### US-2: Open a read-only artifact diff from an artifact card

As a supervisor,
I want a "See changes" button in the artifact card details panel,
so that I can view the full diff of what the agent wrote compared to the committed baseline.

**Acceptance criteria:**
- ArtifactModal footer renders a "See changes" button when the message has `artifactPath` and `atype === 'code'`.
- Clicking "See changes" opens `ArtifactDiffViewer` as a portal modal overlay (`showDiff` state in `MsgCard`).
- Only one of `showDiff` / `showDetails` is active at a time; they do not stack.
- For non-code artifacts (atype != 'code'), "See changes" is absent; ArtifactModal is unaffected.
- The button is accessible: keyboard-focusable, has a visible focus ring, and `aria-label` is set.

**Delivered by:** Conv 2

### US-3: Diff pane shows artifact vs committed HEAD

As a supervisor,
I want the diff viewer to display the artifact file's content against the last committed git HEAD version of that path,
so that I understand exactly what the agent changed.

**Acceptance criteria:**
- `ArtifactDiffViewer` renders `CodeDiffView` with hunks produced by `useArtifactDiff`.
- `useArtifactDiff` calls `window.pathly.git.blob(repoRoot, relPath)` and feeds the result as `originalText` to `useDraftDiff`.
- When `git.blob` returns `null` (file not in HEAD), `originalText` is `''`; the diff shows all lines as added.
- When both original and draft are empty, a toast is surfaced via `pushToast`.
- The modal shell has: fixed overlay backdrop, `ArtifactDiffViewer` panel (header with filename + `[surface a]` label, body with `CodeDiffView`, no footer apply/reject bar).
- Escape key or the `✕` button calls `onClose`.
- `ArtifactDiffViewer` mounts as a portal to `document.body` via `createPortal`.

**Delivered by:** Conv 2

### US-4: useDraftDiff accepts an optional originalText override

As a builder,
I want `useDraftDiff` to accept an optional `originalTextOverride` parameter,
so that callers that already have the original content as a string do not need to create a temp file.

**Acceptance criteria:**
- `useDraftDiff(originalPath, draftPath, comments, options?: { originalTextOverride?: string })` signature compiles without error.
- When `originalTextOverride` is provided, `useDraftDiff` skips the `fs.read(originalPath)` call and uses the override string directly.
- When `originalTextOverride` is absent, behaviour is identical to before (no regression).
- Existing callers of `useDraftDiff` (in `DraftDiffViewer`) pass no `options` argument and continue to work.

**Delivered by:** Conv 2

### US-5: ArtifactDiffViewer modal follows Studio design tokens

As a supervisor,
I want the diff viewer modal to match the dark-mode style of the Command Center,
so that it does not look foreign in the existing UI.

**Acceptance criteria:**
- `ArtifactDiffViewer.module.css` uses only CSS custom properties from `DESIGN.md` color tokens (or equivalent Studio-global tokens where they overlap).
- No inline styles in the component TSX.
- The modal panel is `width: min(90vw, 1200px)`, `height: min(85vh, 900px)`, backdrop has `rgba(0,0,0,0.55)` + `blur(4px)`.
- No Tailwind or external CSS libraries are used.
- File `ArtifactDiffViewer.tsx` is at most 90 lines; `useArtifactDiff.ts` is at most 40 lines.

**Delivered by:** Conv 2

---

## Conv 3 — Badge + ImpactPanel frontend

### US-6: Per-hunk or file-header caller-count badge on the diff

As a supervisor,
I want to see a `⚠ N callers` badge on a hunk (or on the file header as a fallback) when impact data is available for the changed code,
so that I can immediately see which hunks are high-risk before diving into the details.

**Acceptance criteria:**
- `CodeDiffView` accepts optional `badgeFor?: (hunk: DiffHunk) => number | null` and `onHunkFocus?: (hunk: DiffHunk) => void` props (both undefined-safe; existing callers unchanged).
- When `badgeFor(hunk)` returns a non-null number N, a `⚠ N callers` chip renders in that hunk's header row, right-aligned.
- When `badgeFor(hunk)` returns `null`, no chip renders for that hunk.
- If per-hunk matching is not possible (DiffHunk lacks line ranges), the builder falls back to a file-header badge — decided and documented by the end of Conv 3.
- The chip uses `color: var(--color-warning)`, `background: var(--color-warning-dim)`, `border-radius: 4px`, Lucide `AlertTriangle` icon (16px).
- Chip has `role="button"`, `aria-label="View impact: N callers affected"`, keyboard-focusable.
- Clicking the chip calls `onHunkFocus(hunk)`.
- `CodeDiffView.tsx` remains at or below 150 lines; extract `HunkBadge/` sub-component if needed.

**Delivered by:** Conv 3

### US-7: ImpactPanel blade shows changed symbols, callers, and affected flows

As a supervisor,
I want a blade panel to appear on the right when I click a badge,
so that I can see which symbols were changed, how many callers they have, and which flows are affected.

**Acceptance criteria:**
- `ImpactPanel` renders as a blade (`width: 360px`) pinned to the right inside the `ArtifactDiffViewer` panel; uses `position: absolute`, right-aligned.
- Blade animates in: `translateX(100%) → translateX(0)`, 220ms ease-out; out: 160ms ease-in; collapses to `opacity 100ms` under `prefers-reduced-motion`.
- Blade header shows "Impact — `<filename>`" + a close `✕` button (`aria-label="Close impact panel"`).
- Symbol list: each symbol row shows `<name>` (monospace) left + `⚠ {N} callers` chip right.
- Callers list collapses under each symbol row; toggle on symbol row click; indented 24px.
- Affected flows section shows each flow name as a plain chip.
- When `backendOff` is true, `ImpactPanel` renders `null` (blade is absent, no error shown).
- `ImpactPanel.tsx` is at most 80 lines; extract `ImpactRow/` sub-component if symbol list body exceeds ~40 lines.

**Delivered by:** Conv 3

### US-8: Active hunk highlights matching symbol in blade

As a supervisor,
I want the relevant symbol row to be highlighted in the blade when I focus a specific hunk,
so that I can see the direct connection between the diff line I'm reviewing and the impact.

**Acceptance criteria:**
- When `activeHunk` is set and per-symbol data is available, the matching symbol row gets `background: var(--color-accent-dim)` + `border-left: 3px solid var(--color-accent)`.
- When `activeHunk` is `null`, no row is highlighted (blade shows file-level summary).
- With file-level-only data (no per-symbol granularity), `activeHunk` has no visual effect on the blade (acceptable degradation).

**Delivered by:** Conv 3

### US-9: useImpact hook fetches /code/query and returns structured data

As a builder,
I want a `useImpact` hook that calls `POST /code/query` with `op:"impact"` and normalizes the response,
so that components can consume impact data without knowing about the backend protocol.

**Acceptance criteria:**
- `useImpact(filePath, repoRoot)` returns `{ changedSymbols, callers, affectedFlows, loading, backendOff }`.
- Fetches once per `(filePath, repoRoot)` pair; result is cached for the lifetime of the component.
- `backendOff` is `true` when the backend returns `null` result, a network error, or a non-2xx response.
- `loading` is `true` while the request is in-flight; `false` afterwards.
- `useImpact` imports nothing from any diff component.
- `useImpact.ts` is at most 70 lines.
- When Conv 4 is not yet complete, `backendOff` will be `true` (backend returns null) — this is the expected degraded state for Conv 3.

**Delivered by:** Conv 3

---

## Conv 4 — Backend op:"impact" wiring

### US-10: Backend routes op:"impact" to detect_changes and returns structured data

As a supervisor,
I want the `/code/query` endpoint to handle `op:"impact"` by calling `detect_changes` on the changed file,
so that the frontend can retrieve caller-count data for the open artifact.

**Acceptance criteria:**
- `POST /code/query { "op": "impact", "target": "<relPath>", "project_root": "<root>" }` returns HTTP 200.
- Response body: `{ "ok": true, "op": "impact", "target": "...", "result": <dict or null>, ... }`.
- When `detect_changes` returns a dict, `result` is that dict (the tool's JSON passed through).
- When `detect_changes` returns `None` (binary absent, CLI error, timeout), `result` is `null`.
- The response never returns HTTP 5xx for `op:"impact"` — errors degrade to `result: null`.
- `query.py` branches on `op.strip().lower() == "impact"` before the existing `build_block` call; all other ops are unaffected.
- Content-hash cache applies to impact queries the same as other ops.

**Delivered by:** Conv 4

### US-11: CliProvider.detect_changes is deadline-bounded and never raises

As a builder,
I want `CliProvider.detect_changes` to be safe to call from a Flask route without risking a hang or exception propagation,
so that a slow or absent CLI binary cannot block the HTTP server.

**Acceptance criteria:**
- `CliProvider.detect_changes(paths, repo_root)` is a method on `CliProvider` in `code_context_cli.py`.
- Returns `None` immediately when `paths` is empty, `repo_root` is falsy, or `shutil.which(self.tool)` is `None`.
- Uses `_await_or_empty` with the same `_CLI_TIMEOUT_S` deadline as `build_block`.
- Returns `None` on any subprocess error, JSON parse failure, or non-dict result.
- A module-level `detect_changes(paths, repo_root)` passthrough exists in `code_context.py`, mirroring `build_block`'s pattern (resolves provider, delegates, wraps in try/except returning None).
- `code_context_cli.py` remains at or below 400 lines after the addition.

**Delivered by:** Conv 4

---

## Conv 5 — Normalize + E2E verify

### US-12: useImpact normalizer adapts to real detect_changes output shape

As a supervisor,
I want the ImpactPanel to correctly display data once the backend is wired,
so that real caller counts and affected flows appear without a separate frontend change after Conv 4 lands.

**Acceptance criteria:**
- Builder runs `codebase-memory-mcp cli detect_changes` to capture the real output shape before modifying `useImpact`.
- `useImpact` normalizer maps the tool's actual output keys to `{ changedSymbols, callers, affectedFlows }`.
- If the tool returns per-symbol objects with `caller_count`, `changedSymbols` is populated and `badgeFor` can return per-hunk values (or falls back to file-level if line ranges are unavailable).
- If the tool returns only file-level data (no `changed_symbols` array), `callers` is populated from the file-level array and `badgeFor` returns `null` for all hunks (file-header badge used instead).
- End-to-end: opening "See changes" on a real artifact card in a running Studio instance shows the ImpactPanel blade with real data (or gracefully absent if the CLI is not installed).

**Delivered by:** Conv 5

### US-13: Graceful degradation works end-to-end

As a supervisor,
I want the differ to function as a plain diff viewer when the code graph is unavailable,
so that I can still review artifact changes during runs where codebase-memory-mcp is not installed or returns an error.

**Acceptance criteria:**
- When `codebase-memory-mcp` is absent (binary not found): "See changes" opens, diff renders, ImpactPanel blade is absent, no error message shown to the user.
- When the backend returns `null` for `op:"impact"`: same result — blade absent, diff intact.
- When `git:blob` returns `null` (file not in HEAD): diff shows all lines as added; no crash.
- When artifact `atype` is not `'code'` (e.g. markdown): "See changes" button is absent from the ArtifactModal footer.
- None of the above degradation paths produce a visible error state or console exception.

**Delivered by:** Conv 5
