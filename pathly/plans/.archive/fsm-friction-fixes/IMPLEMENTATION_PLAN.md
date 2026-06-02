# IMPLEMENTATION_PLAN — fsm-friction-fixes

Three independent conversations, one per story. Order: Conv 1 → Conv 2 → Conv 3.
Conv 1 first because a reliable server makes iterating on Conv 2 and Conv 3 less painful.

Stories delivered: S1 (Conv 1), S2 (Conv 2), S3 (Conv 3).

---

## Conversation 1 — FSM server auto-start

**Stories:** S1 (AC-S1-1 through AC-S1-6)

**Files to touch:**
- `src/pathly_orchestrator/fsm_http_client.py` — rewrite `ensure_server_running` (lines 92–105) and `_start_server` (lines 77–89)
- `src/pathly_orchestrator/http_server.py` — add fast `/health` short-circuit (currently lines 251–266)
- `src/pathly_data/core/skills/utilities/fsm-call.md` — collapse steps 2–3 into single instruction, remove `&` fallback
- `tests/` — rewrite server startup tests to exercise the poll loop, PID file, and platform flags

**Constraints:**
- No new `pathly-fsm-call` CLI flags. Internal fix only.
- After editing `fsm-call.md` run `pathly-setup claude --apply` and `python -m build`.
- Do not push to master without explicit user request.
- Scope gate: since `_is_exempt` for `src/pathly_orchestrator/` is still in place in Conv 1, this conversation can self-verify. Conv 2 removes that exemption.

**Risks:** Low. No STATE.json schema changes. No test rewrites required for Conv 2 or Conv 3 tests. The PID-file path (`platformdirs` or `pathlib` user-cache) must be verified to exist on all three platforms.

---

## Conversation 2 — Scope gate preexisting-dirty snapshot

**Stories:** S2 (AC-S2-1 through AC-S2-7)

**Files to touch:**
- `src/pathly_orchestrator/fsm_ops.py` — add `build_baseline` snapshot in `next_action` (stamps near lines 349–353); add `build_baseline` clear in `complete_stage` (near line 539)
- `src/pathly_orchestrator/fsm.py` — rewrite `_scope_clean` signature and body (lines 363–436); update `run_gates` to read `build_baseline.preexisting_dirty` instead of `conv_start_sha` (lines 439–509); remove `_is_exempt` exemption for `src/pathly_orchestrator/` (lines 424–429)
- `tests/test_gates.py` — rewrite `test_scope_gate_pass` (line 229), `test_scope_gate_fail_undeclared_path` (line 256), `test_scope_gate_no_baseline_sha` (line 313)

**Constraints:**
- `CONVERSATION_PROMPTS.md` for this conversation must explicitly declare `src/pathly_orchestrator/fsm.py` and `src/pathly_orchestrator/fsm_ops.py` in scope. After Conv 2 ships, the `src/pathly_orchestrator/` exemption is gone — these paths must be declared or the gate will fail future builds.
- No STATE.json auto-migration. Legacy plans with no `build_baseline` emit `GATE_SKIPPED reason=no_build_baseline`.
- Exemptions for `pathly/plans/` and `*.tsbuildinfo` remain unchanged.
- Do not push to master without explicit user request.

**Risks:** Medium. Touches 3 existing tests (rewrite required, not delete). Removing `_is_exempt` for `src/pathly_orchestrator/` is a behavior change that must be verified across all adapter scenarios. Verify `test_scope_gate_no_declared_scope` (line 292) still passes untouched.

---

## Conversation 3 — Multi-conversation routing (on_state_counter)

**Stories:** S3 (AC-S3-1 through AC-S3-7)

**Files to touch:**
- `src/pathly_orchestrator/fsm_ops.py` — add `_count_planned_convs` helper; add `convs_total`/`convs_done` stamping in `next_action`; add warning event on row-count mismatch
- `src/pathly_orchestrator/fsm.py` — add `on_state_counter` level to `evaluate_transition_rules` (after line 176 of eventlog.py's `evaluate_transition_rules`); extend `update_progress` action to increment `convs_done` on `mark: conv_done`
- `src/pathly_data/core/flows/team.flow.yaml` — rewrite REVIEWING block to add `on_state_counter`; keep `on_artifact: MORE_CONVS_NEEDED.md` fallback
- `src/pathly_data/core/skills/team/review.md` — remove line 177 instruction to write `MORE_CONVS_NEEDED.md`
- `tests/` — add new `on_state_counter` evaluator tests (4 cases: condition met, unmet, missing field, malformed op)

**Constraints:**
- `CONVERSATION_PROMPTS.md` for this conversation must explicitly declare `src/pathly_orchestrator/fsm.py` and `src/pathly_orchestrator/fsm_ops.py` in scope (exemption was removed in Conv 2).
- After editing `review.md` run `pathly-setup claude --apply` and `python -m build` to propagate to codex and copilot adapters.
- `MORE_CONVS_NEEDED.md` artifact path must remain in `team.flow.yaml` for this release (backwards-compat window).
- STATE.json additions are additive: `convs_total` and `convs_done` are new keys; no existing reader is modified.
- Do not push to master without explicit user request.

**Risks:** Medium-high. New rule level in `evaluate_transition_rules` is new evaluator code with higher blast radius. `team.flow.yaml` change affects all features using the standard team flow. The `review.md` skill change requires adapter sync. Verify `test_next_action_initial_state` (line 63 in `test_fsm_ops.py`) still passes after `convs_total`/`convs_done` are added to STATE.json.
