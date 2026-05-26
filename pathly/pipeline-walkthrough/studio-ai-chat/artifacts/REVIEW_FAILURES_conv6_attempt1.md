# Conv 6 Review Failures — studio-ai-chat

Files reviewed:
- `studio/src/renderer/src/data/studioSchema.ts` (CREATED)
- `studio/src/renderer/src/lib/pathlyContext.ts` (MODIFIED)

---

## VIOLATION V1 — Layer contract: lib imports from data/

**File:** `studio/src/renderer/src/lib/pathlyContext.ts:2`
**Rule:** ARCHITECTURE_PROPOSAL.md — Layer Contract — "LIB (src/lib/) — May import: types ONLY"
**Description:** `pathlyContext.ts` imports `getStudioSchema` and `StudioElement` from `../data/studioSchema`. The `data/` layer is not a permitted import source for `lib/` modules. Only `src/types/` is permitted.

**Required fix:**
- Move `StudioElement` interface to `src/types/` (e.g. `src/types/studio.ts` or append to `src/types/chat.ts`).
- `pathlyContext.ts` must import `StudioElement` from `../types/studio` (or `../types/chat`).
- Either move `getStudioSchema()` to `src/lib/studioSchema.ts` (making it a lib module that holds the data inline), or keep `STUDIO_SCHEMA` in `src/data/studioSchema.ts` but have `pathlyContext.ts` reach it only through a lib intermediary that is permitted to cross into data.

---

## VIOLATION V2 — Type placement: StudioElement defined in data/ instead of types/

**File:** `studio/src/renderer/src/data/studioSchema.ts:1–7`
**Rule:** ARCHITECTURE_PROPOSAL.md — Layer Contract Rule 3 — "Types that cross layers live in src/types/chat.ts. Both store and lib import from types/, never from each other."
**Description:** `StudioElement` is a cross-layer interface consumed by `PathlyContext` (lib), and will be consumed by components and store. It must be defined in `src/types/`, not in `src/data/`.

---

## VIOLATION V3 — Schema count: 30 elements present, 32 required

**File:** `studio/src/renderer/src/data/studioSchema.ts`
**Rule:** Conv 6 contract — "CREATED: static Studio UI schema with 32 elements"
**Description:** `STUDIO_SCHEMA` contains 30 entries, not 32. Count by section: TopBar (10) + Sidebar (4) + FlowEditor (9) + Modal (2) + Panel (1) + BottomNav (2) + ChatPanel (2) = 30. Two elements are missing. The missing elements must be identified and added.

---

## Warnings (non-blocking)

**W1 — Unsafe cast on API response**
**File:** `studio/src/renderer/src/lib/pathlyContext.ts:20`
**Concern:** `as { current_state?: string; feature?: string }` silently accepts any shape from the API. If the server returns unexpected data, the cast succeeds and downstream consumers receive `undefined` without a TypeScript error. Consider a runtime narrowing check.

---

## Pass

- No `any` types in either file.
- `PathlyContext` interface includes `studioSchema: StudioElement[]`.
- `buildPathlyContext()` returns `studioSchema` in both success and fallback paths.
- No hardcoded credentials or secrets.
- No store imports or store mutator calls in `pathlyContext.ts`.
