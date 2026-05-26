# Review Failures — studio-ai-chat Conv 4

## Status: BLOCKED

---

## Violation 1 — Dead state field in chatStore
**File:** `studio/src/renderer/src/store/chatStore.ts` (lines 12–15, 25, 34, 46, 64)
**Rule:** No dead code in store — every field and action must have at least one consumer outside the store itself.
**Description:** `matchState` (field, type `MatchState`) and `setMatchState` (action) are defined and initialised but are never read or called anywhere in the codebase. Only `currentMatch` / `setCurrentMatch` are used. The dead field inflates the store interface and creates ambiguity about which field represents the active match.

---

## Violation 2 — Hardcoded localhost URLs
**File:** `studio/src/renderer/src/lib/pathlyContext.ts` line 14
**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx` line 120
**Rule:** No magic literals for service addresses; network coordinates belong in a shared config constant.
**Description:** Both files hard-code `http://127.0.0.1:8765` as a bare string literal. If the port changes, two files must be updated manually and it is easy to miss one. A single `PATHLY_API_BASE` constant (e.g. in `lib/config.ts`) must be the single source of truth for this address.

---

## Violation 3 — ConductorHeader owns terminal and UI store subscriptions (layer violation)
**File:** `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` lines 2–3, 8–9, 50–56
**Rule:** Architecture §Component Architecture — `ConductorHeader` responsibility is "Title, Manual/Auto toggle, CLI status pills". It must not own cross-cutting subscriptions; the parent (`ChatPanel`) owns store access and passes derived props down.
**Description:** `ConductorHeader` directly imports and subscribes to `terminalStore` (to derive `hasClaudeTab`/`hasCodexTab`) and to `uiStore` (to call `toggleChat`). Both subscriptions cause `ConductorHeader` to re-render on every terminal or UI state change and couple a leaf presentational component to two stores. Per the architecture the parent should derive these values and pass `hasClaudeTab: boolean`, `hasCodexTab: boolean`, and `onToggleChat: () => void` as explicit props.

---

## Violation 4 — Run button not guarded by 65% confidence threshold
**File:** `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` lines 42–44
**Rule:** ARCHITECTURE_PROPOSAL.md Decision 5 + Risks section: "auto-approve is disabled for matches below 65% confidence regardless of setting."
**Description:** The `matched` flag (line 15, `confidence >= 0.65`) is used only for CSS class names and badge text. The Run `<button>` (line 42) is rendered and enabled unconditionally for all confidence levels. A match with confidence 0.30 presents an active Run button identical to one at 0.90. Decision 5 requires that either the button is disabled/hidden when `confidence < 0.65`, or the parent passes a disabled prop derived from that threshold before invoking `onRun`.

---

## Must Fix Before Merging
All four violations above are blocking. Violations 3 and 4 are architectural; violations 1 and 2 are structural/maintainability rules that were explicitly pre-flagged by the scout.
