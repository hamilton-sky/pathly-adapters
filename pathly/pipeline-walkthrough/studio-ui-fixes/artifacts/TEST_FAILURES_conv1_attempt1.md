# TEST_FAILURES — studio-ui-fixes

Generated: 2026-05-18

## Story S4, Criterion 4 — FAIL

**Criterion:** Sections are hidden if the directory does not exist (no crash).

**What failed:**
In `Sidebar.tsx` lines 144–190, the DEBUGS and EXPLORATIONS section headers are rendered even when the corresponding directory does not exist. When `listDirs` throws (directory missing), `useProjectFiles.ts` catches the error and leaves `subdirs` as `undefined`, which the sidebar treats as `[]`. The `hasMatch` guard at line 146–147 only hides the section when a filter is active AND no files match — it does not hide the section when `subdirs` is empty with no filter applied.

**Expected:** When `pathly/debugs/` or `pathly/explorations/` does not exist, the corresponding section header should not appear in the sidebar at all.

**Actual:** An empty, collapsible section header (DEBUGS / EXPLORATIONS) is rendered with no items inside.

**Location:**
- `studio/src/renderer/src/components/Sidebar.tsx`, line 146–147
- `studio/src/renderer/src/hooks/useProjectFiles.ts`, line 57–59

**Fix hint:** In `useProjectFiles.ts`, track whether the directory was found vs. errored (e.g., set `subdirs` to `null` on error). In `Sidebar.tsx`, skip rendering the section when `subdirs` is `null` (directory missing) vs. `[]` (directory exists but empty).
