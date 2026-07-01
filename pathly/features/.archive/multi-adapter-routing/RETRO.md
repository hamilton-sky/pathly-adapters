# Retro — multi-adapter-routing

**Date:** 2026-06-01 | **Rigor:** standard | **Result:** DONE

---

## What went well

**Architecture held end-to-end.**
The core design decision — FSM stays passive, `preferred_adapter` is an opaque string copy, no adapter imports — held from Phase 1 through Phase 11 without any violations. The reviewer confirmed this explicitly in the Conv 2 review. When a design decision is stated as an invariant in the implementation plan and the reviewer is asked to check it, it stays clean.

**Clean dependency chain across 4 conversations.**
The plan's critical path (Conv 1 → 2 → 3, with Conv 4 able to run after Conv 1) was respected. All 11 phases completed in order. No conversation required rework from a prior conversation's design choice.

**Reviewer caught a missing edge-case test before merge.**
During Conv 2, the reviewer identified that `test_validate_adapter_map_unknown_adapter_value_fails` covered a state-key override but not the `"default"` key's own value — a meaningful regression gap. Catching this in the review cycle rather than in testing (or production) is the system working correctly.

**Backward compatibility preserved throughout.**
Flows without `adapter_map` continue to behave identically. The `_KNOWN_OPTIONAL_FLOW_KEYS` registration, the `""` default for `preferred_adapter`, and the `generateYaml` zero-diff path for default-claude-no-overrides were all confirmed passing.

**Precedence slot reserved without over-engineering.**
Per-feature STATE.json override (precedence slot 1) was reserved as a commented hook only. No speculative code was written. When it gets implemented, it will be purely additive.

---

## What was difficult

**GATE_FAILED on first REVIEWING → TESTING transition (Conv 2).**
The event log shows a `GATE_FAILED` on `require_artifact` followed by a human-resolution step before the transition could proceed. The gate fired because a required artifact was missing after the review. This caused a pipeline stall and a manual unblock. The pattern is consistent with the lesson from `enforcement-gates` — gate feedback must tell the builder exactly what to write and where.

**Builder token telemetry gap.**
All four builder conversations logged `tokens_in: 0, tokens_out: 0, cost_usd: 0.0`. Only the reviewer and tester captured real token data. The stop hook or builder agent is not recording usage, so the actual build cost is unknown. Total captured cost is $1.02 (reviewer ×3 + tester ×1), but true cost is higher.

**Conv 3 (Studio wizard) had the highest phase density.**
Phases 7, 8, and 9 touched `utils.ts`, a new component + CSS, `FlowWizard.tsx`, `draftUtils.ts`, and `types.ts` — five files across one conversation. While it completed successfully, this is near the upper bound of reliable single-conversation scope, especially for TypeScript components where a typecheck failure can cascade.

---

## What to improve next time

**Fix builder token telemetry before the next feature.**
Four consecutive builder conversations with zero tokens recorded means cost tracking is broken for the most expensive pipeline stage. Investigate the stop hook `src/pathly_hooks/stop_telemetry.py` — confirm it fires after builder sessions and that the AGENT_DONE event is written with real counts.

**Gate feedback must include artifact path and format.**
When a `require_artifact` gate fails, the generated feedback file should include: (a) the exact path to write, (b) the required first line or schema, and (c) an example. Without this, the human unblock step is always needed. This is a direct application of the `enforcement-gates` lesson already in LESSONS_CANDIDATE.md.

**Studio wizard conversations should be planned as a mini-track.**
Phases 7-9 should be split into two conversations: (a) `utils.ts` + typecheck; (b) component + wiring + full typecheck + visual confirm. A typecheck gate between them would catch TS errors before the wiring step adds more surface area. The current plan bundled all three phases because Conv 3 was labeled "Studio wizard" as a unit, which obscured the actual file count.

---

## Metrics

| Metric | Value |
|---|---|
| Conversations | 4 |
| Stories | 4 (S1-S4) — all DONE |
| Phases | 11 (Phase 0 through Phase 11) — all DONE |
| Tests added | 14 new tests |
| Tests passing | 237 |
| Reviewer passes | 3 (Conv 2, 3, 4) |
| Gate failures | 1 (GATE_FAILED require_artifact, Conv 2→3 transition) |
| Human unblocks | 1 |
| Captured cost | $1.02 (reviewer + tester only; builder tokens not recorded) |
| Total wall time | ~3,287 seconds across all agents |
