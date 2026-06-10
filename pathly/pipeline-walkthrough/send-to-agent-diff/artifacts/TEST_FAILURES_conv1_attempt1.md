# TEST_FAILURES — send-to-agent-diff

Generated: 2026-06-10

---

## Test suite baseline

Existing tests (unrelated to this feature): 3 failures in `useFlowFile.test.ts` — pre-existing regressions not introduced by this feature. `validateFlow.test.ts` all pass.

---

## Test plan

### US-1: Draft instead of overwrite

**Story 1.1**
Criterion: "Send to Agent" spawns Claude with prompt writing `<filepath>.draft` not `<filepath>`
Test: Read `commentUtils.ts:buildSendPrompt` — last line of returned array
Status: PASS
Notes: `commentUtils.ts:34` — `Write the complete revised content to: ${norm}.draft`

**Story 1.2**
Criterion: Original file unchanged while agent runs
Test: Read `CommentsPanel.tsx:handleSendToAgent` and `Editor/index.tsx` — no write to original during spawn
Status: PASS
Notes: `CommentsPanel.tsx:88` spawns terminal; no write to original path occurs. Original is only written on Apply (`Editor/index.tsx:225`).

**Story 1.3**
Criterion: When terminal exits, Studio checks for `.draft` and surfaces diff viewer if it exists
Test: Read `CommentsPanel.tsx:handleSendToAgent` — `terminal.onExit` handler
Status: PASS
Notes: `CommentsPanel.tsx:80-85` — subscribes to `terminal.onExit`, reads `norm + '.draft'`, calls `onDraftReady(norm + '.draft')` if content is non-null/non-empty. Editor wires `onDraftReady={setDraftPath}` which triggers the viewer (`Editor/index.tsx:353`).

---

### US-2: Section-level diff viewer

**Story 2.1**
Criterion: Viewer shows every section changed/added/removed; unchanged not shown
Test: Read `DraftHunkList.tsx:12` — filter logic; `useDraftDiff.ts` — status assignment
Status: PASS
Notes: `DraftHunkList.tsx:12` filters to `h.status !== 'unchanged'`. `useDraftDiff.ts:65-70` assigns status correctly.

**Story 2.2**
Criterion: Content before first `## ` treated as implicit preamble section
Test: Read `useDraftDiff.ts:parseIntoSections`
Status: PASS
Notes: `useDraftDiff.ts:24-25` — content that does not start with `## ` is assigned `heading: '__preamble__'`. `DraftHunkCard.tsx:33` renders it as "Preamble".

**Story 2.3**
Criterion: Each changed section shows old/new text in a collapsed card (expandable)
Test: Read `DraftHunkCard.tsx` — default `expanded = false`, expansion on click
Status: PASS
Notes: `DraftHunkCard.tsx:26` initializes `expanded = false`. Clicking `.cardBody` toggles `expanded`. `DiffCodeBlock` is rendered inside `{expanded && ...}` at line 56.

**Story 2.4**
Criterion: Single toggle chip per hunk (one control pattern for all three types)
Test: Read `DraftHunkCard.tsx` — toggle chip rendering
Status: PASS
Notes: `DraftHunkCard.tsx:62-70` — single `<button className={styles.toggleChip}>` for all three types; label varies via `toggleLabel()` but the control is identical.

**Story 2.5**
Criterion: Type badge (ADDED/REMOVED/CHANGED) + colored left border on every hunk card
Test: Read `DraftHunkCard.tsx:12-17`, `DraftHunkCard.module.css`
Status: FAIL
Notes: Type badge is present and correct (`DraftHunkCard.tsx:49` renders `{BADGE_LABEL[hunk.status]}`). However the criterion specifies a **colored left border** — the CSS implementation uses a full colored border on all four sides (`DraftHunkCard.module.css:10-18`), not a left-only accent border. This is a styling divergence from the spec.

**Story 2.6**
Criterion: Zero-diff → no viewer, toast notification shown
Test: Read `DraftDiffViewer.tsx:47-58` — zero totalChanged handling
Status: FAIL
Notes: Two violations:
1. **Viewer still appears** — `DraftDiffViewer.tsx:47-58` renders an inline state message ("No changes detected — draft is identical") inside the modal overlay rather than suppressing the viewer entirely. The criterion requires the viewer not to appear at all.
2. **No toast notification** — no toast/notification is dispatched anywhere in the zero-diff path. The notification store (`notificationStore.ts`) has no dispatch API used in this component. There is no call to any toast library or store method in `DraftDiffViewer.tsx`.

---

### US-3: Selective acceptance

**Story 3.1**
Criterion: Toggling one hunk does not affect others
Test: Read `useDraftDiff.ts:toggle`
Status: PASS
Notes: `useDraftDiff.ts:77-79` — `toggle` maps over all hunks and only flips `accepted` for the matching `id`. Other hunks are returned unchanged.

**Story 3.2**
Criterion: Live preview panel shows file as it will look after applying current selections
Test: Read `DraftPreviewPanel.tsx`, `useDraftDiff.ts:reconstruct`, `DraftDiffViewer.tsx:64`
Status: FAIL
Notes: The "Result" tab in `DraftPreviewPanel.tsx` calls `content` which is `diff.reconstruct()` passed from `DraftDiffViewer.tsx:64`. However, `reconstruct` in `useDraftDiff.ts:30-41` has a bug: when an **added** hunk is toggled off (`accepted = false`), the filter at line 32 (`h.status !== 'removed' || h.accepted`) does NOT exclude it (status is 'added', not 'removed'). The content then falls to `h.originalContent ?? ''` which is `null ?? ''` = `''`, producing a `## HeadingName\n\n` entry with empty content in the output. This means the preview (and Apply) would include empty ghost sections for rejected "added" hunks, misrepresenting the final file.

**Story 3.3**
Criterion: Preview updates immediately when any toggle changes
Test: Read `DraftDiffViewer.tsx:64` — reconstruct called in render; `useDraftDiff.ts:toggle` sets state
Status: PASS
Notes: `diff.reconstruct()` is called inline during render at `DraftDiffViewer.tsx:64`. Since `toggle` calls `setHunks(...)` which triggers a re-render, the preview content is recomputed on each toggle synchronously.

---

### US-4: Apply, close, or discard draft

**Story 4.1**
Criterion: Apply reconstructs file from selections, writes to original path via `fs:write` (atomic `.tmp` rename internally), deletes `.draft`, closes viewer, editor reloads
Test: Read `Editor/index.tsx:handleDiffApply`, `ipc/fs.ts:fs:write`
Status: PASS (with caveat)
Notes: `Editor/index.tsx:223-232` — writes via `window.pathly.fs.write(effectivePath, newContent)`, deletes `.draft`, sets `draftPath(null)`, re-parses and sets `config`/`body`. IPC handler `fs.ts:57-64` does atomic `.tmp` rename. Caveat: the bug in AC3.2 (rejected added hunks) means the reconstructed content passed to Apply may contain empty sections, but the Apply mechanism itself is correct.

**Story 4.2**
Criterion: Close keeps `.draft` on disk; re-opening same file re-renders viewer
Test: Read `Editor/index.tsx:392`, `useEffect` at line 131
Status: PASS
Notes: `onClose={() => setDraftPath(null)}` at `Editor/index.tsx:392` closes the viewer without deleting `.draft`. When the user re-selects the file, the `useEffect` at line 131 runs on `effectivePath` change, reads `effectivePath + '.draft'` (line 141-144), and calls `setDraftPath(draft)` if non-empty — re-surfacing the viewer.

**Story 4.3**
Criterion: Discard shows inline confirmation before deleting `.draft`; uses `var(--red)`; no `window.confirm()`
Test: Read `DraftDiffFooter.tsx`, `DraftDiffFooter.module.css`
Status: PASS
Notes: `DraftDiffFooter.tsx:21-37` — `showConfirm` state gates a confirmation row with "Yes, discard" / "Cancel". `window.confirm()` is not used. CSS `.btnDiscard` uses `color: var(--red)` (`DraftDiffFooter.module.css:50`), `.btnDanger` uses `background: var(--red)` (line 62).

**Story 4.4**
Criterion: CTA shows exact counts "Apply N of M changes" — N = accepted non-unchanged hunks, M = total non-unchanged hunks
Test: Read `DraftDiffFooter.tsx:57-61`, `useDraftDiff.ts:84-87`
Status: PASS
Notes: Button text is `Apply {acceptedCount} of {totalChanged} changes` (`DraftDiffFooter.tsx:58`). `acceptedCount` = `nonUnchanged.filter(h => h.accepted).length` and `totalChanged` = `nonUnchanged.length` in `useDraftDiff.ts:84-86`.

**Story 4.5**
Criterion: If `.draft` disappears unexpectedly while viewer is open, viewer closes gracefully with an error message
Test: Read `useDraftDiff.ts`, `DraftDiffViewer.tsx` — error state and recovery
Status: FAIL
Notes: The error state in `useDraftDiff.ts:74` only fires if the initial `Promise.all` read fails. If `.draft` disappears **after** the viewer loads (i.e., while the user is reviewing), there is no watch/poll mechanism to detect this. No `window.pathly.watch` or interval is used in `useDraftDiff.ts`. The viewer will remain open with stale data and Apply would likely fail silently (or succeed with a stale write, then a failed `fs:delete`). The graceful error path exists for load-time failures only, not for post-load disappearance.

**Story 4.6**
Criterion: "You have N unreviewed sections" warning in footer when hunks never expanded
Test: Read `DraftDiffFooter.tsx:41-43`, `useDraftDiff.ts:87`
Status: FAIL
Notes: The warning is shown at `DraftDiffFooter.tsx:41-43` and `unreviewedCount` is computed correctly (`useDraftDiff.ts:87`). However, the criterion requires the specific wording **"You have N unreviewed sections"**. The actual rendered text is `"{unreviewedCount} sections not yet reviewed"` — the prefix "You have" is absent and the suffix wording differs. This is a direct wording mismatch against the acceptance criterion.

---

## Summary of failures

| Criterion | Status | File:Line |
|---|---|---|
| AC2.5 — colored left border | FAIL | `DraftHunkCard.module.css:10-18` — full border, not left-only |
| AC2.6 — zero-diff: no viewer + toast | FAIL | `DraftDiffViewer.tsx:47-58` — viewer appears; no toast dispatched |
| AC3.2 — preview/apply correctness for rejected "added" hunks | FAIL | `useDraftDiff.ts:32-36` — rejected added hunks produce empty sections |
| AC4.5 — draft disappears unexpectedly while viewer open | FAIL | `useDraftDiff.ts` — no post-load watch mechanism |
| AC4.6 — warning wording | FAIL | `DraftDiffFooter.tsx:42` — text is `"{N} sections not yet reviewed"`, criterion requires `"You have N unreviewed sections"` |
