# Enforcement Gates — Retrospective

> Feature complete: 2026-05-25 · 2 conversations · 54 tests · 0 regressions

## What Went Well

- **Layered architecture was sound**: `run_gates()` in `fsm.py` (zero LLM imports) kept the FSM engine clean while `fsm_ops.py` handled only wiring — minimal coupling made Phase 2 integration straightforward.
- **Fail-fast design matched existing contract**: Stopping on first failure and routing a single feedback file plugged directly into the existing `_blocked_response()` / `route_feedback()` helpers without modification.
- **Line-1 exact match sentinel**: The `RESULT: PASS` first-non-blank-line check prevented false passes where the marker was buried in a failure explanation — baked in from Phase 1.
- **GATE_SKIPPED surfaced enforcement gaps**: Emitting a `GATE_SKIPPED` event (rather than silently passing) when `conv_start_sha` was absent or no scope was declared gave operators visibility into unenforced gates.
- **All tests green in two conversations**: Conv 1 tests (15) and Conv 2 tests (5) passed without regressions against the existing 33+6 suite.

## What Was Difficult

- **`conv_start_sha` absent required unplanned prerequisite work**: Phase 4 assumed the orchestrator was already writing this key to `STATE.json`; it wasn't. Conv 2 had to add it before scope_gate could function. The cross-feature dependency wasn't visible until Phase 4.
- **`VERIFY.md` assumed but not auto-created**: The verify_gate expects `VERIFY.md` to exist before `complete_stage` runs. The pipeline had no built-in mechanism to create it — builders had to write it manually. The `REVIEW_FAILURES.md` feedback file didn't explain *where* to write the artifact.
- **STATE.json state inconsistency**: A stale state from a previous session put `STATE.json` in PLANNING when it should have been BUILDING. Required manual correction of `STATE.json` and creation of `VERIFY.md` before the FSM could advance cleanly.
- **Timestamp field naming**: The EVENTS.jsonl event schema wasn't explicit about `ts` vs `timestamp`. The tester caught the mismatch; fix was to add test assertions for the canonical `ts` field name rather than renaming across the codebase.

## What We'd Do Differently

1. **Pre-flight manifest scan before Phase 1**: Check all assumed keys (conv_start_sha, STATE.json shape, event field names) and patch gaps as standalone prerequisites — not mid-phase discoveries.
2. **Auto-create or document artifact requirements**: If a gate requires an artifact (VERIFY.md, CONVERSATION_PROMPTS.md), provide a template or add a builder-facing note explaining *where* to write it and in what format.
3. **Hardcode scope-file parsing rules**: Instead of "lines starting with `-` or backtick," specify the exact regex in the plan so the parser is unambiguous and testable in isolation.
4. **Embed event schema in IMPLEMENTATION_PLAN**: List exact fields for each event type (GATE_FAILED, GATE_SKIPPED) and cross-reference existing events to avoid naming surprises.
5. **Test artifact absence with builder feedback path**: Phase 1 base tests should verify the feedback file instructs the builder *where* to write the missing artifact, closing the UX loop.
6. **Add YAML comments documenting gate ordering semantics**: Explain fail-fast ordering and the `route_feedback` contract in team.flow.yaml so future maintainers understand the design assumption.
