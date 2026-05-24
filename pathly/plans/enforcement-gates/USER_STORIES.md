# Enforcement Gates — User Stories

## Context

Pathly runs on both Claude Code and Codex. Hook-based enforcement only fires under Claude Code,
creating a "hook parity gap" — rules enforced via hooks are invisible to Codex. The FSM server
(`fsm.py` / `fsm_ops.py`) is the only enforcement layer both tools share via `POST /complete_stage`.
This feature adds **gates**: checkpoints the FSM runs before accepting a state transition, blocking
advancement and routing a feedback file if proof of work is missing or invalid.

## Stories

### Story S1: verify_gate on BUILDING→REVIEWING

**As a** pipeline operator, **I want** the FSM to block `BUILDING→REVIEWING` unless `VERIFY.md`
exists and contains `RESULT: PASS` on its first non-blank line, **so that** a builder cannot
claim success without running the verify step.

**Acceptance Criteria:**
- [ ] When `VERIFY.md` is absent, `complete_stage` returns a blocked response and does not advance state.
- [ ] When `VERIFY.md` exists but its first non-blank line is not exactly `RESULT: PASS`, the gate fails.
- [ ] When `VERIFY.md` first non-blank line is `RESULT: PASS`, the gate passes and the transition proceeds.
- [ ] On failure, `REVIEW_FAILURES.md` is written to the feedback dir and a `GATE_FAILED` event is appended.
- [ ] A second `complete_stage` call after the agent writes a passing `VERIFY.md` advances to `REVIEWING`.

**Edge Cases:**
- `RESULT: PASS` buried inside a failure explanation does not satisfy the gate (line-1 sentinel, not substring).
- `VERIFY.md` present but empty: gate fails.

**Delivered by:** Phases 1–3 → Conversation 1

---

### Story S2: require_artifact on REVIEWING→TESTING

**As a** pipeline operator, **I want** the FSM to block `REVIEWING→TESTING` unless `REVIEW.md`
exists, **so that** unreviewed work cannot advance to the test stage.

**Acceptance Criteria:**
- [ ] When `REVIEW.md` is absent, `complete_stage` returns a blocked response and does not advance state.
- [ ] On failure, `HUMAN_QUESTIONS.md` is written to the feedback dir and a `GATE_FAILED` event is appended.
- [ ] When `REVIEW.md` exists, the gate passes.

**Edge Cases:**
- `REVIEW.md` is a zero-byte file: gate passes (existence check only — content validation is out of scope).

**Delivered by:** Phases 1–3 → Conversation 1

---

### Story S3: scope_gate on BUILDING→REVIEWING

**As a** pipeline operator, **I want** the FSM to block `BUILDING→REVIEWING` if the working-tree
diff contains files outside the declared scope in `CONVERSATION_PROMPTS.md`, **so that** scope
drift is caught at the handoff, not discovered during review.

**Acceptance Criteria:**
- [ ] A diff touching only declared files: gate passes.
- [ ] A diff touching any undeclared path: gate fails, `SCOPE_VIOLATION.md` written, `GATE_FAILED` event appended.
- [ ] When no file list is declared in `CONVERSATION_PROMPTS.md`, the gate emits a `GATE_SKIPPED` event and passes (does not silently no-op — the skip is surfaced).
- [ ] The diff baseline is pinned to the commit SHA recorded at conversation start, not HEAD, to avoid seeing prior-conversation commits.

**Edge Cases:**
- No `CONVERSATION_PROMPTS.md` at all → treated as no declared scope → `GATE_SKIPPED` emitted.
- Conversation start SHA missing from state → falls back to HEAD with a `GATE_SKIPPED` event (not a hard error).

**Delivered by:** Phases 4–6 → Conversation 2

---

### Story S4: Gate failures use existing feedback routing

**As a** pipeline operator, **I want** gate failures to write feedback files and emit `GATE_FAILED`
events so that the existing `feedback_routing` machinery routes failures to the correct agent
without any new routing code.

**Acceptance Criteria:**
- [ ] A gate failure writes the `on_fail` file to the `feedback/` dir.
- [ ] A `GATE_FAILED` event is appended to `EVENTS.jsonl` with `gate`, `transition`, and `timestamp` fields.
- [ ] `STATE.json` is not modified on a gate failure (state does not advance).
- [ ] The blocked response is structurally identical to an existing feedback-blocked response.

**Delivered by:** Phases 1–3 → Conversation 1 (require_artifact, verify_gate); Phases 4–5 → Conversation 2 (scope_gate)

---

### Story S5: Gates declared in flow YAML

**As a** pipeline operator, **I want** gate rules declared in the flow YAML under a `gates:` key,
**so that** adding or changing a gate does not require editing Python code.

**Acceptance Criteria:**
- [ ] `team.flow.yaml` contains a `gates:` section keyed by transition (`FROM->TO`) or wildcard (`->TO`).
- [ ] Each gate entry has `type`, `artifact` or `scope_file` (as appropriate), and `on_fail` fields.
- [ ] An unknown `type` value causes `run_gates()` to raise `RuntimeError` (not silently skip).
- [ ] Removing a gate entry from the YAML disables that gate without any code change.

**Delivered by:** Phase 3 → Conversation 1
