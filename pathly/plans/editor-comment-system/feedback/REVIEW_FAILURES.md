# REVIEW_FAILURES — editor-comment-system

## Blockers (must fix before merge)

### 1. Missing `type` on tab and action buttons — `index.tsx`

**File:** `studio/src/renderer/src/components/Editor/index.tsx`
**Lines:** 245-250, 260, 266-271
**Rule:** Every `<button>` must have an explicit `type="button"` (or `type="submit"`). No exceptions. (studio/CLAUDE.md — Buttons section)
**Description:** Five buttons in the toolbar section have no `type` attribute: the three tab buttons in `tabs.map(...)`, the inline "Edit source" button, and the Save button. Browsers default to `type="submit"`, which can trigger unintended form submissions.

Affected buttons:
- Line 245: `<button className={tab === t_ ? styles.tabActive : styles.tab} onClick={...}>` (×3, inside map)
- Line 260: `<button className={styles.tab} onClick={() => setTab('edit')}>` (Edit source)
- Line 266: `<button className={...} onClick={() => void performSave(body, config)}>` (Save)

---

### 2. Reopen button silently no-ops — `useComments.ts:75`

**File:** `studio/src/renderer/src/components/Editor/useComments.ts`
**Line:** 75
**Rule:** Layer contract — component behavior must match its declared intent. The `RotateCcw` "Reopen comment" button exists and is wired to `onResolve`; `onResolve` maps to the `resolve` callback which unconditionally sets `resolved: true`. Clicking Reopen has no effect because the comment is already `resolved: true`.
**Description:** `resolve` hard-codes `{ ...c, resolved: true }` instead of toggling. The reopen path requires `resolved: false`. Fix: toggle (`!c.resolved`) or add a separate `reopen` callback.

---

### 3. `index.tsx` exceeds 150-line hard limit

**File:** `studio/src/renderer/src/components/Editor/index.tsx`
**Rule:** Hard limit ~150 lines per component file. Exceeded files must extract the next logical sub-section into its own file. (studio/CLAUDE.md — Single responsibility section)
**Description:** File is 373 lines. The frontmatter parsing block (lines 24-74, ~50 lines of pure utility functions with no React dependency) and the `Editor` component render body (lines 232-371) are prime extraction candidates.
