## Review Failures — Conv 3 (studio-v2)

Reviewed files:
- `studio/src/renderer/src/hooks/useProjectFiles.ts`
- `studio/src/renderer/src/components/Sidebar.tsx`

---

### VIOLATION 1 — `handleNewItem` builds path without null-guarding `projectPath`

**File:** `studio/src/renderer/src/components/Sidebar.tsx:93`
**Rule:** S3 acceptance criterion — no crash when `projectPath` is empty; null guard on API calls.
**Description:** `handleNewItem` computes `dir: \`${projectPath}/${section.dir}\`` unconditionally. The "+ new" button (line 191) and "+ new template" button (line 157) are both inside Section A, which renders regardless of `projectPath`. A user can expand Flows/Skills/Agents/Templates (all default `open: false` but toggleable) and click "+ new" with no project open. `projectPath` is `undefined` or `null` at that point, so `dir` becomes `"undefined/src/pathly_data/core/skills"` (or similar). That string is passed to `NewItemDialog`, which will attempt a filesystem write to an invalid path — a runtime error. The fix is to guard `handleNewItem` with an early return when `!projectPath`, or to hide the "+ new" buttons in Section A when `projectPath` is falsy.

---

### WARNINGS (non-blocking)

**Warning 1 — PLAN header renders `[no topic]` when `activeTopic` is null**
**File:** `studio/src/renderer/src/components/Sidebar.tsx:208`
**Severity:** Non-blocking
**Description:** When `projectPath` is set but `activeTopic` is null (no plan selected), the PLAN section header renders `[no topic]` and the body shows "No conversations". This is cosmetically odd but does not crash and no acceptance criterion forbids it. Worth a future UX pass.

---

### PASS

- S3: PATHLY_SECTIONS (`useProjectFiles.ts`) do not call `listDir`/`listDirs` when `projectPath` is empty — the inner loop uses `continue` to set empty items and skip API calls. No crash path.
- S3: The `if (!projectPath) return` early guard (line 76) is placed after the PATHLY_SECTIONS loop, so Section A state is always initialised.
- S4: Section B (Plans + Debugs + Explorations + divider) is entirely wrapped in `{projectPath && (<> ... </>)}` at `Sidebar.tsx:200-283`. No orphaned separator when `projectPath` is unset.
- S4: Plans conversations render using `conv.num`, `conv.title`, `conv.status`, matching the `ConvRow` interface in `types/index.ts:15-19`.
- Return shape of `useProjectFiles` unchanged — still `{ sections, setSections, loadItems }`. Only one caller exists (`Sidebar.tsx`).
- Silent-catch pattern preserved in `useProjectFiles.ts` (lines 67-73, 93-95) and `usePlanConversations.ts` (line 73).
- `usePlanConversations` null-guards `projectPath` and `activeTopic` before calling `readFile`.
