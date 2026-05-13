# fsm-configurable — Conversation Guide

Split into 4 conversations. Each produces a clean, committable set of changes.
After each conversation, **commit your changes** before starting the next.

Conv 3 and Conv 4 require `agent-architecture-refactor` Conv 4 to be DONE first.
Check `plans/agent-architecture-refactor/PROGRESS.md` before starting Conv 3.

---

## Conversation 1: pathly/ root consolidation (Phases 0a–0b)

**Stories delivered:** S0.1

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 1 (Phases 0a–0b) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:** Run `git status` to confirm a clean working tree. Run `git diff --stat` to confirm no uncommitted changes. If either check fails, stop and report.

**Before editing anything:** Read `src/pathly_data/core/skills/team.md` in full and `src/pathly_data/core/agents/orchestrator.md` in full to identify all occurrences of `plans/*/`, `pipeline-walkthrough/`, and `plans/<feature>/` that need the `pathly/` prefix added.

**Codebase files this conversation modifies:**
- `src/pathly_data/core/skills/team.md` — MODIFY: update feature detection scan from `plans/*/STATE.json` to `pathly/plans/*/STATE.json`
- `src/pathly_data/core/agents/orchestrator.md` — MODIFY: update artifact archiving destination from `pipeline-walkthrough/<feature>/artifacts/` to `pathly/pipeline-walkthrough/<feature>/artifacts/`; update feedback file path from `plans/<feature>/feedback/` to `pathly/plans/<feature>/feedback/` in the archiving rule

Scope:
- Phase 0a: team.md — update feature detection scan path (story S0.1 partial) — see IMPLEMENTATION_PLAN.md Phase 0a
- Phase 0b: orchestrator.md — update artifact archiving and feedback paths to use pathly/ prefix (story S0.1 complete) — see IMPLEMENTATION_PLAN.md Phase 0b

Rules:
- Change only the path string references described above. Do NOT restructure, add, or remove any logic.
- Do NOT touch any flow YAML files, adapter YAML files, or other skill files.

Verify:
- `grep "pathly/plans" src/pathly_data/core/skills/team.md` — must return at least one match in the feature detection section.
- `grep "pathly/pipeline-walkthrough" src/pathly_data/core/agents/orchestrator.md` — must return a match.
- `git diff --stat` — must show only team.md and orchestrator.md.

After done, update plans/fsm-configurable/PROGRESS.md Phases 0a–0b and Conv 1 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout -- <file>` and retry.
```

**Expected output:** team.md and orchestrator.md updated to use pathly/ prefix; `git diff --stat` shows exactly those two files.
**Files touched:** `src/pathly_data/core/skills/team.md`, `src/pathly_data/core/agents/orchestrator.md`

---

## Conversation 2: Create core/flows/ YAML configs (Phases 1–3)

**Stories delivered:** S1.1, S1.2, S1.3

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 2 (Phases 1–3) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:** Run `git status` to confirm a clean working tree. Run `git diff --stat` to confirm no uncommitted changes. If either check fails, stop and report.

**Before creating anything:** Confirm the `src/pathly_data/core/` directory exists by globbing it. Check whether `src/pathly_data/core/flows/` exists — if not, create the directory. Glob `src/pathly_data/core/agents/orchestrator.md` and `src/pathly_data/core/skills/team.md` to confirm those paths are live and confirm the convention for skill/agent paths used in agent_map values.

**Codebase files this conversation creates:**
- `src/pathly_data/core/flows/team.flow.yaml` — CREATE: FSM config for team pipeline
- `src/pathly_data/core/flows/debug.flow.yaml` — CREATE: FSM config for debug flow
- `src/pathly_data/core/flows/explore.flow.yaml` — CREATE: FSM config for explore flow

Scope:
- Phase 1: team.flow.yaml — states, transitions, agent_map, storage_path `pathly/plans/{topic}/`, feedback_routing (story S1.1) — see IMPLEMENTATION_PLAN.md Phase 1
- Phase 2: debug.flow.yaml — states, transitions, agent_map, storage_path `pathly/debugs/{topic}/`, feedback_routing (story S1.2) — see IMPLEMENTATION_PLAN.md Phase 2
- Phase 3: explore.flow.yaml — states, transitions, agent_map, storage_path `pathly/explorations/{topic}/`, feedback_routing (story S1.3) — see IMPLEMENTATION_PLAN.md Phase 3

Rules:
- Read `src/pathly_data/core/skills/debug.md` and `src/pathly_data/core/skills/explore.md` before writing debug.flow.yaml and explore.flow.yaml — derive agent_map values from the actual agents those files spawn today.
- Do NOT modify any existing files. This conversation creates new files only.
- agent_map values must reference real agent names that exist under `src/pathly_data/core/agents/` or real skill paths under `src/pathly_data/core/skills/`.
- All three storage_path values must use the `pathly/` prefix.
- Each flow YAML must include a top-level `version: 1` field.

Verify:
- `git diff --stat` — confirm exactly 3 new files are listed.
- `grep "storage_path" src/pathly_data/core/flows/*.flow.yaml` — confirm all three files contain the field with pathly/ prefix.

After done, update plans/fsm-configurable/PROGRESS.md Phases 1–3 and Conv 2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, delete the new files with `git checkout` or `rm` and retry.
```

**Expected output:** Three new YAML files under `src/pathly_data/core/flows/`; `git diff --stat` shows exactly those three files.
**Files touched:** `src/pathly_data/core/flows/team.flow.yaml`, `src/pathly_data/core/flows/debug.flow.yaml`, `src/pathly_data/core/flows/explore.flow.yaml`

---

## Conversation 3: Generalize orchestrator.md (Phases 4–5)

**Stories delivered:** S2.1, S2.2

**Pre-condition:** `agent-architecture-refactor` Conv 4 must be DONE. Check `plans/agent-architecture-refactor/PROGRESS.md` before pasting this prompt. If Conv 4 is not DONE, do not start this conversation.

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 3 (Phases 4–5) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:**
1. Run `git status` to confirm a clean working tree.
2. Read `plans/agent-architecture-refactor/PROGRESS.md` and confirm Conv 4 status is DONE. If it is not DONE, stop immediately and report — this conversation cannot proceed until that dependency is met.
3. Read `src/pathly_data/core/flows/team.flow.yaml` to confirm Conversation 2 has run and the flow configs exist.

**Before editing anything:** Read `src/pathly_data/core/agents/orchestrator.md` in full. Read `src/pathly_data/adapters/claude/_meta/orchestrator.yaml`. Glob `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` to determine if the codex adapter file exists.

**Codebase files this conversation modifies:**
- `src/pathly_data/core/agents/orchestrator.md` — replace hardcoded team FSM with flow_config-driven generic engine
- `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` — add flow_config input declaration
- `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` — add flow_config input declaration (skip with a PROGRESS note if file does not exist)
- `schemas/state.schema.json` — remove hardcoded team state enum and transitions block

Scope:
- Phase 4: Generalize orchestrator.md — inputs, startup read, storage_path, state list, agent_map, feedback_routing (story S2.1) — see IMPLEMENTATION_PLAN.md Phase 4
- Phase 5: Update orchestrator.yaml for both adapters — add flow_config and topic input fields (story S2.2) — see IMPLEMENTATION_PLAN.md Phase 5
- Phase 5b: Update schemas/state.schema.json — replace `current` enum with `"type": "string"`, remove `transitions` block — see IMPLEMENTATION_PLAN.md Phase 5b

Rules:
- The three flow YAML files in `src/pathly_data/core/flows/` are your reference for what the generic orchestrator must support — read them before editing orchestrator.md.
- Do NOT change `model`, `tools`, or `can_spawn` in the YAML files.
- Do NOT touch team.md, debug.md, explore.md, or any flow YAML file in this conversation.
- After editing, verify no hardcoded team state names remain as logic (not comment) lines in orchestrator.md.
- If `flow_config` path does not exist, YAML parse fails, or any required field (`states`, `transitions`, `agent_map`, `storage_path`, `feedback_routing`) is missing — write `HUMAN_QUESTIONS.md` with the specific error and stop. Do NOT proceed with FSM execution.

Verify:
- `grep -i "BUILDING\|REVIEWING\|TESTING\|RETRO" src/pathly_data/core/agents/orchestrator.md` — output must be comment lines only (lines starting with `#` or `>`).
- `grep "flow_config" src/pathly_data/core/agents/orchestrator.md` — must return at least 2 matches (inputs block + startup read).
- `grep "flow_config" src/pathly_data/adapters/claude/_meta/orchestrator.yaml` — must return the new field.
- `grep "BUILDING\|REVIEWING\|RETRO" schemas/state.schema.json` — must return no output.
- `grep "transitions" schemas/state.schema.json` — must return no output.
- `git diff --stat` — must show only orchestrator.md, the YAML adapter file(s), and state.schema.json.

After done, update plans/fsm-configurable/PROGRESS.md Phases 4–5 and Conv 3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout` on affected files and retry.
```

**Expected output:** orchestrator.md is a generic FSM engine; orchestrator.yaml declares flow_config; `git diff --stat` shows only those files.
**Files touched:** `src/pathly_data/core/agents/orchestrator.md`, `src/pathly_data/adapters/claude/_meta/orchestrator.yaml`, `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` (if exists)

---

## Conversation 4: Update skill launchers (Phases 6–8)

**Stories delivered:** S3.1, S3.2, S3.3

**Pre-condition:** Conv 3 of this feature must be DONE. `agent-architecture-refactor` Conv 4 must be DONE.

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 4 (Phases 6–8) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:**
1. Run `git status` to confirm a clean working tree.
2. Read `plans/fsm-configurable/PROGRESS.md` — confirm Conv 3 is DONE. If not, stop and report.
3. Read `plans/agent-architecture-refactor/PROGRESS.md` — confirm Conv 4 is DONE. If not, stop and report.

**Before editing anything:** Read each of the three skill files in full before modifying any of them:
- `src/pathly_data/core/skills/team.md`
- `src/pathly_data/core/skills/debug.md`
- `src/pathly_data/core/skills/explore.md`

Also read all three flow YAML files to confirm the flow_config paths you will inject are correct:
- `src/pathly_data/core/flows/team.flow.yaml`
- `src/pathly_data/core/flows/debug.flow.yaml`
- `src/pathly_data/core/flows/explore.flow.yaml`

**Codebase files this conversation modifies:**
- `src/pathly_data/core/skills/team.md` — add flow_config parameter to existing orchestrator spawn block
- `src/pathly_data/core/skills/debug.md` — replace inline FSM steps with orchestrator spawn
- `src/pathly_data/core/skills/explore.md` — replace inline three-phase spawning with orchestrator spawn

Scope:
- Phase 6: team.md — add `flow_config: src/pathly_data/core/flows/team.flow.yaml` to the orchestrator spawn block (story S3.1) — see IMPLEMENTATION_PLAN.md Phase 6
- Phase 7: debug.md — replace inline FSM with orchestrator spawn passing debug flow config (story S3.2) — see IMPLEMENTATION_PLAN.md Phase 7
- Phase 8: explore.md — replace inline spawning with orchestrator spawn passing explore flow config (story S3.3) — see IMPLEMENTATION_PLAN.md Phase 8

Rules:
- Each file must remain runnable after this conversation — no half-replaced files.
- Keep argument parsing, topic/symptom detection, and any setup logic in debug.md and explore.md. Remove only the inline FSM state-transition steps.
- The orchestrator spawn block format must match the pattern already in team.md after agent-architecture-refactor Conv 4.
- Do NOT touch orchestrator.md, flow YAML files, or any other file.

Verify:
- `grep "flow_config" src/pathly_data/core/skills/team.md` — returns `src/pathly_data/core/flows/team.flow.yaml`.
- `grep "flow_config" src/pathly_data/core/skills/debug.md` — returns `src/pathly_data/core/flows/debug.flow.yaml`.
- `grep "flow_config" src/pathly_data/core/skills/explore.md` — returns `src/pathly_data/core/flows/explore.flow.yaml`.
- `grep "orchestrator" src/pathly_data/core/skills/debug.md` — returns the spawn instruction.
- `grep "orchestrator" src/pathly_data/core/skills/explore.md` — returns the spawn instruction.
- `git diff --stat` — shows only team.md, debug.md, explore.md.

After done, update plans/fsm-configurable/PROGRESS.md Phases 6–8, Conv 4, and overall status to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout` on affected files and retry.
```

**Expected output:** All three skill files delegate to orchestrator with their respective flow configs; `git diff --stat` shows exactly those three files.
**Files touched:** `src/pathly_data/core/skills/team.md`, `src/pathly_data/core/skills/debug.md`, `src/pathly_data/core/skills/explore.md`

---

## Conversation 4b: Sub-skill cleanup + transition_rules (Phases 8a–8c)

**Stories delivered:** S3.4

**Pre-condition:** Conv 4 of this feature must be DONE. Conv 3 must be DONE.

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 4b (Phases 8a–8c) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:**
1. Run `git status` to confirm a clean working tree.
2. Read `plans/fsm-configurable/PROGRESS.md` — confirm Conv 3 and Conv 4 are DONE. If not, stop and report.

**Before editing anything:** Read all five files in full:
- `src/pathly_data/core/flows/team.flow.yaml`
- `src/pathly_data/core/skills/team/build.md`
- `src/pathly_data/core/skills/team/review.md`
- `src/pathly_data/core/skills/team/test.md`
- `src/pathly_data/core/agents/orchestrator.md`

**Codebase files this conversation modifies:**
- `src/pathly_data/core/flows/team.flow.yaml` — add transition_rules section
- `src/pathly_data/core/skills/team/build.md` — remove STATE.json transition write
- `src/pathly_data/core/skills/team/review.md` — remove routing logic; replace with MORE_CONVS_NEEDED.md artifact write
- `src/pathly_data/core/skills/team/test.md` — remove STATE.json transition write; preserve internal fix loop
- `src/pathly_data/core/agents/orchestrator.md` — add transition_rules evaluation after each sub-agent returns

Scope:
- Phase 8a: team.flow.yaml — add transition_rules covering BUILDING, REVIEWING, TESTING (story S3.4 partial) — see IMPLEMENTATION_PLAN.md Phase 8a
- Phase 8b: strip STATE.json transition writes from build.md, review.md, test.md — see IMPLEMENTATION_PLAN.md Phase 8b
- Phase 8c: orchestrator.md — add artifact-based transition_rules evaluation loop; add ownership comment — see IMPLEMENTATION_PLAN.md Phase 8c

Rules:
- Do NOT remove the PROGRESS.md update from review.md — marking Conv N as DONE is reporting, not routing.
- Do NOT touch the internal fix loop inside test.md — only the final "Transition state → RETRO" line is removed.
- Do NOT touch debug.flow.yaml or explore.flow.yaml — transition_rules are only needed for team flow now.
- Orchestrator.md already reads flow_config generically after Conv 3 — add transition_rules support as an extension to the existing FSM loop, not a rewrite.
- Sub-skills must each end with: "Return. Orchestrator determines next state from transition_rules."
- **Write-or-delete rule (critical):** Every transition artifact must be explicitly managed each run. If the condition is true: write the file. If the condition is false: delete the file if it exists. Never leave a stale artifact from a previous run. Specifically:
  - review.md: write MORE_CONVS_NEEDED.md if more TODO convs, else delete it; write REVIEW_FAILURES.md if failures found, else delete it.
  - test.md: write TEST_FAILURES.md if tests still failing after fix loop, else delete it.
  Reason: orchestrator reads artifact presence AFTER the sub-skill returns. A stale file from the previous run causes wrong routing with no error.

Verify:
- `grep "transition_rules" src/pathly_data/core/flows/team.flow.yaml` — returns the new section.
- `grep "Transition state" src/pathly_data/core/skills/team/build.md` — no output.
- `grep "Transition state" src/pathly_data/core/skills/team/review.md` — no output.
- `grep "Transition state" src/pathly_data/core/skills/team/test.md` — no output.
- `grep "MORE_CONVS_NEEDED" src/pathly_data/core/skills/team/review.md` — returns both write and delete instructions.
- `grep "delete.*REVIEW_FAILURES\|REVIEW_FAILURES.*delete" src/pathly_data/core/skills/team/review.md` — returns a match.
- `grep "delete.*TEST_FAILURES\|TEST_FAILURES.*delete" src/pathly_data/core/skills/team/test.md` — returns a match.
- `grep "transition_rules" src/pathly_data/core/agents/orchestrator.md` — returns the evaluation logic.
- `grep "only entity" src/pathly_data/core/agents/orchestrator.md` — returns the ownership comment.
- `git diff --stat` — shows only team.flow.yaml, build.md, review.md, test.md, orchestrator.md.

After done, update plans/fsm-configurable/PROGRESS.md Phases 8a–8c and Conv 4b to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout -- <file>` and retry the affected phase only.
```

**Expected output:** Sub-skills write artifacts only; orchestrator evaluates transition_rules to route FSM; `git diff --stat` shows exactly those 5 files.
**Files touched:** `src/pathly_data/core/flows/team.flow.yaml`, `src/pathly_data/core/skills/team/build.md`, `src/pathly_data/core/skills/team/review.md`, `src/pathly_data/core/skills/team/test.md`, `src/pathly_data/core/agents/orchestrator.md`

---

## Conversation 5: Materialize flow YAMLs during pathly-setup (Phase 9)

**Stories delivered:** S4.1

**Pre-condition:** Conv 4 of this feature must be DONE (flow YAML files must exist at `src/pathly_data/core/flows/`).

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 5 (Phase 9) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:**
1. Run `git status` to confirm a clean working tree.
2. Read `plans/fsm-configurable/PROGRESS.md` — confirm Conv 4 is DONE. If not, stop and report.
3. Glob `src/pathly_data/core/flows/*.flow.yaml` — confirm all three flow files exist.

**Before editing anything:** Read the following files in full:
- `src/install_cli/resources.py`
- `src/install_cli/stitch.py`
- `src/install_cli/materialize.py`
- `src/install_cli/setup_command.py`

**Codebase files this conversation modifies:**
- `src/install_cli/resources.py` — add `core_flows_path()` helper
- `src/install_cli/stitch.py` — add `flows_dest` parameter to `stitch_skill()`
- `src/install_cli/materialize.py` — add `materialize_flows()` function
- `src/install_cli/setup_command.py` — call `materialize_flows`; pass `flows_dest=dest` to `stitch_skill`

Scope: Phase 9 from IMPLEMENTATION_PLAN.md — four changes across four files.

Rules:
- `stitch_skill()` signature change must be backward-compatible: `flows_dest` is a keyword-only parameter with default `None`. When `None`, behaviour is identical to today.
- The replacement in `stitch_skill` uses `.as_posix()` on `flows_dest` so the path in skill text always uses forward slashes, regardless of OS.
- `materialize_flows()` must use the existing `materialize()` function — do not duplicate manifest logic.
- Do NOT change `stitch_agent()`, `uninstall()`, or any other function.
- Do NOT touch any `pathly_data` files or plan files.

Verify:
- `grep "core_flows_path" src/install_cli/resources.py` — returns the function definition.
- `grep "flows_dest" src/install_cli/stitch.py` — returns the parameter in `stitch_skill`.
- `grep "materialize_flows" src/install_cli/materialize.py` — returns the function definition.
- `grep "materialize_flows" src/install_cli/setup_command.py` — returns at least 2 lines (import + call).
- `grep "flows_dest=dest" src/install_cli/setup_command.py` — returns the updated `stitch_skill` call.
- `git diff --stat` — shows only the 4 listed files.

After done, update plans/fsm-configurable/PROGRESS.md Phase 9 and Conv 5 to DONE, and overall Status to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout -- <file>` and retry.
```

**Expected output:** `pathly-setup --apply` materializes `*.flow.yaml` files alongside agent files; stitched skill files contain the absolute installed path instead of `src/pathly_data/core/flows/`.
**Files touched:** `src/install_cli/resources.py`, `src/install_cli/stitch.py`, `src/install_cli/materialize.py`, `src/install_cli/setup_command.py`
