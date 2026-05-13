# fsm-configurable — Edge Cases

## EC-1: flow_config path does not exist at runtime

**Scenario:** An orchestrator spawn receives a `flow_config` path that does not resolve to a real file (typo, missing file, wrong working directory).

**Risk:** Orchestrator silently uses defaults or crashes mid-run, leaving STATE.json in an inconsistent state.

**Mitigation:** Orchestrator startup must verify the flow_config file exists before reading it. If the file is missing, orchestrator must stop immediately and write a HUMAN_QUESTIONS.md entry naming the bad path. Builder must add this check in Phase 4.

**Acceptance check:** The orchestrator startup section in orchestrator.md must include a "verify flow_config exists" step before parsing.

---

## EC-2: flow_config is missing a required field

**Scenario:** A flow YAML file exists but omits `storage_path`, `agent_map`, or `feedback_routing`.

**Risk:** Orchestrator reads a partial config and proceeds with undefined behaviour (wrong storage path, no routing).

**Mitigation:** The orchestrator startup read must check for all required top-level keys (`storage_path`, `states`, `transitions`, `agent_map`, `feedback_routing`) and stop with an error if any are absent.

**Acceptance check:** Phase 4 implementation notes in IMPLEMENTATION_PLAN.md specify required keys; builder must validate presence before using any config value.

---

## EC-3: agent-architecture-refactor Conv 4 not yet complete when Conv 2 starts

**Scenario:** Builder starts Conv 2 before `agent-architecture-refactor` Conv 4 is DONE. The orchestrator.md at that point lacks the FSM sections this feature needs to generalize.

**Risk:** Builder overwrites the wrong version of orchestrator.md; changes conflict when Conv 4 later lands.

**Mitigation:** Conv 2 prompt explicitly requires reading `plans/agent-architecture-refactor/PROGRESS.md` and stopping if Conv 4 is not DONE. Noted in IMPLEMENTATION_PLAN.md as a hard pre-condition.

**Acceptance check:** Conv 2 prompt in CONVERSATION_PROMPTS.md contains the stop instruction.

---

## EC-4: debug.md or explore.md retain partial inline logic after Conv 3

**Scenario:** Builder rewrites only part of the inline FSM in debug.md or explore.md, leaving some steps delegated inline and others via orchestrator.

**Risk:** Two parallel execution paths exist; state tracking is incomplete.

**Mitigation:** Each file must be read in full before editing. The done-when grep checks in Phase 7 and Phase 8 verify no state-transition step names remain in inline logic.

**Acceptance check:** IMPLEMENTATION_PLAN.md Phase 7 and Phase 8 grep checks cover all debug and explore state names.

---

## EC-5: `{topic}` placeholder not substituted in storage_path

**Scenario:** Orchestrator reads `storage_path: debugs/{topic}/` from the YAML but forgets to substitute the `{topic}` variable before creating the directory or writing STATE.json.

**Risk:** STATE.json is written to a literal directory named `debugs/{topic}/` rather than `debugs/login-timeout/`.

**Mitigation:** Phase 4 implementation note specifies "substituting `{topic}` with the received topic value" as an explicit step. Builder must verify substitution occurs before any file write.

**Acceptance check:** The done-when check for Phase 4 includes verifying the storage_path line references the config-derived value (implying substitution logic must exist in the startup block).

---

## EC-7: malformed flow YAML is written to disk without validation

**Scenario:** `materialize_flows()` copies a flow YAML that is missing a required field (e.g., `agent_map`) to `~/.claude/agents/`. The file is installed successfully. When the user runs `/pathly team`, orchestrator reads the YAML, finds no `agent_map`, and silently routes nothing or crashes mid-run.

**Risk:** Broken installed state with no install-time error. User sees a runtime failure with no obvious cause.

**Mitigation:** `_validate_flows()` in `materialize.py` runs before any file is written. It checks all five required keys (`storage_path`, `states`, `transitions`, `agent_map`, `feedback_routing`) and raises `ValueError` listing every missing key across every flow file. `pathly-setup` fails before touching disk if any YAML is malformed.

**Acceptance check:** Phase 9 implementation includes `_validate_flows` call inside `materialize_flows`, before the `materialize()` call. Builder must also add a unit test: `test_materialize_flows_rejects_malformed_yaml` in `test_setup.py` or a new `test_materialize_flows.py`.

---

## EC-6: codex adapter orchestrator.yaml does not exist

**Scenario:** `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` does not exist (the codex adapter may not have this file yet).

**Risk:** Phase 5 silently skips the codex update and the gap is not recorded.

**Mitigation:** Phase 5 instructions say to skip with a note if the file does not exist. The PROGRESS.md Phase 5 row must record the outcome (updated or skipped with reason).

**Acceptance check:** CONVERSATION_PROMPTS.md Conv 2 prompt includes "skip with a PROGRESS note if file does not exist".

---

## EC-8: orchestrator.md exceeds maintainable size after Conv 3

**Scenario:** After agent-architecture-refactor Conv 4 enriches orchestrator.md with FSM sections AND fsm-configurable Conv 3 replaces hardcoded states with config-driven logic, orchestrator.md may grow past ~400 lines. Natural language "code" at that size becomes hard to reason about — sections contradict each other, builders skip content, and LLMs hallucinate from middle sections.

**Risk:** Silent correctness regressions in orchestrator behavior as the file grows; builders miss contradictions between old and new sections.

**Mitigation:** At the end of Phase 4 (orchestrator generalization), builder must count approximate line length and record it in the PROGRESS.md Phase 4 row. If orchestrator.md exceeds 400 lines, flag it as a warning — do not block Conv 4, but do not ignore it. The planned resolution is `plans/fsm-transition-actions`, which moves hardcoded side-effect logic (git commits, PROGRESS.md updates, artifact archiving) into the flow YAMLs under a `transition_actions` key, reducing orchestrator.md to ~150 lines. That plan must run after this one completes.

**Acceptance check:** PROGRESS.md Phase 4 row includes the line count after editing. If count > 400, a note referencing `plans/fsm-transition-actions` is added.
