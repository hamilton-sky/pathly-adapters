---
name: Retro
---
# Provider-Agnostic Telemetry — Retrospective

**Feature:** provider-agnostic-telemetry
**Date:** 2026-06-11
**Stories delivered:** 10 (S1.1–S4.1) · 42 acceptance criteria · 4 builder conversations · 4 reviewer passes · 1 tester fix cycle

---

## What Went Well

**Clear architecture and phased delivery:** The feature was well-scoped into 4 conversations with clear responsibility boundaries (registry + endpoint, DB schema, stop hook cleanup, frontend fetch). Each conversation's acceptance criteria were explicit and testable. The architectural decision to thread `cost_source` through telemetry.py → DB → eventlog → activity.jsonl → OTel spans created a clean signal propagation path with no upward imports violating layer rules. DRY and naming conventions were caught early in review and fixed inline — no rework cycles. All 42 acceptance criteria passed on first pass post-fix.

**Reviewer-builder feedback loop:** The 4-reviewer-pass discipline surfaced 3 actionable issues (_ADAPTER_PREFIXES DRY violation, `all_providers()` shape mismatch, missing `cost_source` in `_append_agent_done_event`) and all were resolved within the same conversation build phase. No review → rebuild → re-review cycles needed. Pre-existing fixes (Conv 2 telemetry.py provider/cost_source propagation) were confirmed rather than reworked.

**Edge case coverage:** EDGE_CASES.md mapped 5 categories with specific handlers tied to phases. The tester fix cycle (S4.1 cost_source badge missing in UI) was caught quickly and resolved without blocking other work.

---

## What Was Hard or Surprising

**Provider-agnostic model inference complexity:** Inferring the provider from a model string using `_ADAPTER_PREFIXES` and longest-prefix matching required careful handling of unknown/empty models and version suffix mismatches. The conditional logic for `"unpriced"` vs `"estimated"` cost_source required multiple review passes.

**Dual-write removal and fallback chain:** Removing EVENTS.jsonl patching from the stop hook while maintaining a safe fallback (HTTP → DB, never JSONL) required understanding the existing HTTP → eventlog → EVENTS.jsonl flow. Moving the fallback entirely to DB meant rethinking stop hook recovery when the FSM server is unreachable.

**Frontend race condition (EC-5.1):** `fetchPricingTable()` on mount created a timing issue — if Studio opens before the FSM server starts, the fetch fails silently and cells show `—`. This required defensive null-handling and graceful degradation that wasn't immediately apparent from the story text.

**Cost confidence / cache token columns:** Adding provider + cost_source + cache token columns to the DB schema felt like scope creep initially but was essential for the three-way `cost_source` distinction. The realization that cache token data required schema changes (even though cost computation was out of scope) came mid-plan.

---

## What We'd Do Differently Next Time

**Separate provider inference logic into its own testable module earlier:** `_ADAPTER_PREFIXES` logic should have been extracted and unit-tested independently before being wired into the registry and OTel export.

**Document cost_source state machine upfront:** Define a formal state machine for the three cost_source values with explicit transition rules and examples — this would have prevented the ambiguity around zero cost and model misses that required multiple review passes.

**Frontend fetch timing as a formal acceptance criterion:** Treat EC-5.1 (Studio opens before FSM server) as an explicit story, not an edge case. It deserves test coverage and a UX design decision in the planner phase.

**Cost computation vs. cost schema as two separate features:** The plan combined "compute cost from tokens" with "store cost_source metadata," creating confusion about scope (cache token pricing landed in schema but not computation). A cleaner split: Feature 1 = registry + cost_source metadata; Feature 2 = cache token accounting (follow-up).

**Checkpoint after Conv 2 before doing Conv 3–4:** Add a brief checkpoint to verify DB migration and EVENTS.jsonl schema on real data before removing stop hook patching. This would have caught missing transitions earlier than the tester cycle.
