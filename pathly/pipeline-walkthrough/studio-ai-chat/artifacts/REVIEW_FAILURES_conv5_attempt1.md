# Review Failures — Conv 5

## Status: FAILURES FOUND

---

## Failure 1 — `skillDescription` sends command string, not description text (Phase 17 violation)

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx:167`
**Rule:** ARCHITECTURE_PROPOSAL.md Phase 17 — `skillDescription` in POST /chat body must be the skill's human-readable description from skills.json
**Description:** The POST /chat body sends `skillDescription: topMatch.command` which is the CLI command string (e.g. `/pathly build`). It must instead be the description text from skills.json (the human-readable explanation of the skill). The `topMatch` object from `matchIntent()` has no `description` field — it only carries `{ skill, confidence, command }` — so the description is never forwarded to the server.

---

## Failure 2 — `isEmbedding` flag set but never read by ChatInput (MiniLM loading pill missing)

**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` (entire file)
**Rule:** ARCHITECTURE_PROPOSAL.md lines 80/151 — ChatInput must display a `◈ MiniLM` loading pill when `isEmbedding` is true
**Description:** `ChatInput` has no subscription to `isEmbedding` from chatStore and renders no MiniLM loading pill. The `isEmbedding` flag is set correctly in `ChatPanel/index.tsx` (lines 131–135) but the wiring to ChatInput is completely absent.

---

## Failure 3 — Run button disabled for UNSURE matches, blocking user interaction

**File:** `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx:42`
**Rule:** ARCHITECTURE_PROPOSAL.md Decision 5 — UNSURE matches must still be runnable; the user is warned by the amber badge, not blocked
**Description:** `<button disabled={!matched}>` disables Run for any confidence below 0.65. The architecture specifies the 0.65 threshold gates auto-approve (and the badge state) but the user should still be able to manually run an UNSURE match. Disabling the button contradicts the self-correction intent of the "Try instead" chips and the "Not this" rejection flow.

---
