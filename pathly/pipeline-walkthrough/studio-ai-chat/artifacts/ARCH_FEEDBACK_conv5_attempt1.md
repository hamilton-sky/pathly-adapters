# Architecture Feedback — Conv 5

## Status: VIOLATIONS FOUND

---

## Violation 1 — Lib layer calling store mutator directly

**File:** `studio/src/renderer/src/lib/embedRouter.ts:42`
**Rule:** Three-layer contract — lib modules must not call store mutators directly
**Description:** `preEmbedSkills()` calls `useChatStore.getState().setEmbedReady(true)` inside the lib layer. The lib layer should return a resolved value or emit a callback; the store transition belongs in the calling component (ChatPanel) where `preEmbedSkills` is invoked.

---

## Violation 2 — `MatchResult` type exported from store, imported by lib

**File:** `studio/src/renderer/src/lib/embedRouter.ts:3`
**Rule:** Three-layer contract — lib must not import from store layer
**Description:** `embedRouter.ts` imports `MatchResult` from `../store/chatStore`. Types that cross layers should live in a shared `types/` file, not in the store layer. This inverts the dependency direction (lib → store).
**Note:** Flagged as acceptable by the pre-review scout only if no shared types file exists — `studio/src/renderer/src/types/css.d.ts` exists (types dir is present), making this a real violation.

---
