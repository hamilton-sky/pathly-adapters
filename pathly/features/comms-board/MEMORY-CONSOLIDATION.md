# Memory Consolidation — design + status

Addresses the two honest memory gaps (an external review, 2026-06-22): the board only
*accumulated and ranked* — no dedup, no synthesis — and the 💡 semantic channel filled
its k slots regardless of match quality. Deliberately **does not** chase importance-scoring
or decay/forgetting: for a *coding* substrate you supersede decisions explicitly, you don't
let them fade. Reflective-memory frameworks (Generative Agents / Mem0 / Letta) optimize for
open-ended conversational agents; the value ranking here is different.

## Scope

| Piece | What | Status |
|---|---|---|
| **#4 — relevance threshold** | `_SEMANTIC_MAX_DISTANCE` cosine cutoff drops weak semantic hits; `_CONTEXT_CHAR_BUDGET` caps the 💡 body. `_distance` now flows through `search_by_embedding`→`search_by_hybrid`→`retrieve_board_context`. | ✅ done |
| **#2a — deterministic dedup** | `dedupe_board` supersedes near-identical free-form notes (keep newest, cosine < `max_distance`≈0.08). `POST /comms/consolidate`. **Structural/governance types protected** (goal/task/decision/escalation/question/answer never touched). Idempotent. | ✅ done |
| **#2b — reflection synthesis** | LLM pass: synthesize a scope's free-form notes into ONE durable note, supersede the raw ones. | 🔜 building |

## #2b — locked design (confirmed 2026-06-22)

- **Output = a findable note**, NOT governance. The synthesis is posted as `type="discovery"`
  ("📝 Consolidated: …") so it surfaces via the 💡 channel and competes on relevance like
  everything else — keeps the always-on governance block clean.
- **It supersedes the raw notes it summarizes** — but only **free-form types** (same
  `_DEDUP_PROTECTED_TYPES` guard as dedup). It may *reference* decisions/tasks in the prose
  but never supersedes a decision/goal/task. The DAG + governance stay intact.
- **Manual trigger only.** `POST /comms/consolidate {mode}`: `mode="dedup"` (default) =
  deterministic only (today's behavior); `mode="full"` (or `"reflect"`) = dedup THEN spawn a
  board agent with the `planning/consolidate` skill. No auto-spawn on goal-drain (no surprise
  LLM cost) — that stays a possible later opt-in.
- **Per-scope** synthesis (the board's notes for the active scope), reusing the existing
  single-agent board-run spawn (`/comms/run` path) + board context injection.

## Not in this phase (explicitly)

- Importance scoring, decay/forgetting — rejected for this domain.
- Mid-run "live pull" of governance — the pull endpoints (`/section`, `/comms/search`,
  catalog) already exist and the loop model re-injects per task; a narrow `/comms/governance`
  refresh is a separate small follow-on, not consolidation.
