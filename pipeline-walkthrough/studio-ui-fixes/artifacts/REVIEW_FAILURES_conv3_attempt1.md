# REVIEW_FAILURES — studio-ui-fixes conversation 3

## Blocking Violations

### F1 — Unsafe type cast hides incompatible PathlyItemType values
**File:** `studio/src/renderer/src/components/Sidebar.tsx:271`
**Rule violated:** Type-driven UI branching (Decision 4) — debug/explore sections reuse the template branch, so `newItemTarget.type` can be `'debug'` or `'explore'`. Casting to `'skill' | 'agent' | 'template'` silences TypeScript and passes an out-of-contract value to `NewItemDialog`, whose `Props.type` is `'skill' | 'agent' | 'template'` (NewItemDialog.tsx:7). This is a runtime-unsafe type lie.
**Evidence:** `newItemTarget.type as 'skill' | 'agent' | 'template'` at line 271; `PathlyItemType` is `'flow' | 'skill' | 'agent' | 'template' | 'debug' | 'explore'` (types/index.ts:1); `NewItemDialog` Props.type excludes debug/explore (NewItemDialog.tsx:7).
**Required fix:** Guard `handleNewItem` so it does not open `NewItemDialog` for debug/explore sections, OR extend `NewItemDialog.Props.type` to accept debug/explore (whichever the plan intends). The cast must be removed.

---

### F2 — "new template" button label shown for debug and explore sections
**File:** `studio/src/renderer/src/components/Sidebar.tsx:182`
**Rule violated:** Decision 4 — debug/explore must reuse the template rendering branch with no new rendering code, but the button text hardcodes "template" and therefore misleads users of debug/explore sections.
**Evidence:** Line 182 renders `+ new template` inside the unified branch that covers `section.type === 'template' || section.type === 'debug' || section.type === 'explore'` (line 142). The label is unconditional.
**Required fix:** Make the button label conditional on `section.type`, or use a generic label (e.g. `+ new item`) that applies correctly to all three section types.

---

### F3 — `parseProgressMd` duplicated in PlanBoard.tsx; `ConvRow` locally redeclared instead of imported
**File:** `studio/src/renderer/src/components/PlanBoard.tsx:7–47`
**Rule violated:** Decision 3 — `PROGRESS.md` parser is a defined utility. Architecture Decision 2 analogously treats pure helpers as file-level utilities in a single location. Duplicating the function and re-declaring a type that already exists in `types/index.ts` (ConvRow at line 15) breaks the single-source-of-truth contract.
**Evidence:**
- `parseProgressMd` in `usePlanConversations.ts` lines 6–27 is byte-for-byte identical to `PlanBoard.tsx` lines 26–47.
- `ConvRow` is declared locally at `PlanBoard.tsx:7–11` but is already exported from `types/index.ts:15–19`.
- `usePlanConversations.ts` correctly imports `ConvRow` from `'../types'` (line 4); PlanBoard does not import it at all.
**Required fix:** Remove the duplicate `parseProgressMd` from `PlanBoard.tsx` and import it from `usePlanConversations` or extract it to a shared utility. Remove the local `ConvRow` declaration and import the canonical one from `../types`.
