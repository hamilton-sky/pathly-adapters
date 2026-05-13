# fsm-configurable — Conversation Guide

Split into 3 conversations. Each produces a clean, committable set of changes.
After each conversation, **commit your changes** before starting the next.

Conv 2 and Conv 3 require `agent-architecture-refactor` Conv 4 to be DONE first.
Check `plans/agent-architecture-refactor/PROGRESS.md` before starting Conv 2.

---

## Conversation 1: Create core/flows/ YAML configs (Phases 1–3)

**Stories delivered:** S1.1, S1.2, S1.3

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 1 (Phases 1–3) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:** Run `git status` to confirm a clean working tree. Run `git diff --stat` to confirm no uncommitted changes. If either check fails, stop and report.

**Before creating anything:** Confirm the `src/pathly_data/core/` directory exists by globbing it. Check whether `src/pathly_data/core/flows/` exists — if not, create the directory. Glob `src/pathly_data/core/agents/orchestrator.md` and `src/pathly_data/core/skills/team.md` to confirm those paths are live and confirm the convention for skill/agent paths used in agent_map values.

**Codebase files this conversation creates:**
- `src/pathly_data/core/flows/team.flow.yaml` — CREATE: FSM config for team pipeline
- `src/pathly_data/core/flows/debug.flow.yaml` — CREATE: FSM config for debug flow
- `src/pathly_data/core/flows/explore.flow.yaml` — CREATE: FSM config for explore flow

Scope:
- Phase 1: team.flow.yaml — states, transitions, agent_map, storage_path, feedback_routing (story S1.1) — see IMPLEMENTATION_PLAN.md Phase 1
- Phase 2: debug.flow.yaml — states, transitions, agent_map, storage_path, feedback_routing (story S1.2) — see IMPLEMENTATION_PLAN.md Phase 2
- Phase 3: explore.flow.yaml — states, transitions, agent_map, storage_path, feedback_routing (story S1.3) — see IMPLEMENTATION_PLAN.md Phase 3

Rules:
- Read `src/pathly_data/core/skills/debug.md` and `src/pathly_data/core/skills/explore.md` before writing debug.flow.yaml and explore.flow.yaml — derive agent_map values from the actual agents those files spawn today.
- Do NOT modify any existing files. This conversation creates new files only.
- agent_map values must reference real agent names that exist under `src/pathly_data/core/agents/` or real skill paths under `src/pathly_data/core/skills/`.

Verify: run `git diff --stat` and confirm exactly 3 new files are listed. Run `grep "storage_path" src/pathly_data/core/flows/*.flow.yaml` to confirm all three files contain the field.

After done, update plans/fsm-configurable/PROGRESS.md Phases 1–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, delete the new files with `git checkout` or `rm` and retry.
```

**Expected output:** Three new YAML files under `src/pathly_data/core/flows/`; `git diff --stat` shows exactly those three files.
**Files touched:** `src/pathly_data/core/flows/team.flow.yaml`, `src/pathly_data/core/flows/debug.flow.yaml`, `src/pathly_data/core/flows/explore.flow.yaml`

---

## Conversation 2: Generalize orchestrator.md (Phases 4–5)

**Stories delivered:** S2.1, S2.2

**Pre-condition:** `agent-architecture-refactor` Conv 4 must be DONE. Check `plans/agent-architecture-refactor/PROGRESS.md` before pasting this prompt. If Conv 4 is not DONE, do not start this conversation.

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 2 (Phases 4–5) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:**
1. Run `git status` to confirm a clean working tree.
2. Read `plans/agent-architecture-refactor/PROGRESS.md` and confirm Conv 4 status is DONE. If it is not DONE, stop immediately and report — this conversation cannot proceed until that dependency is met.
3. Read `src/pathly_data/core/flows/team.flow.yaml` to confirm Conversation 1 has run and the flow configs exist.

**Before editing anything:** Read `src/pathly_data/core/agents/orchestrator.md` in full. Read `src/pathly_data/adapters/claude/_meta/orchestrator.yaml`. Glob `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` to determine if the codex adapter file exists.

**Codebase files this conversation modifies:**
- `src/pathly_data/core/agents/orchestrator.md` — replace hardcoded team FSM with flow_config-driven generic engine
- `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` — add flow_config input declaration
- `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` — add flow_config input declaration (skip with a PROGRESS note if file does not exist)

Scope:
- Phase 4: Generalize orchestrator.md — inputs, startup read, storage_path, state list, agent_map, feedback_routing (story S2.1) — see IMPLEMENTATION_PLAN.md Phase 4
- Phase 5: Update orchestrator.yaml for both adapters — add flow_config and topic input fields (story S2.2) — see IMPLEMENTATION_PLAN.md Phase 5

Rules:
- The three flow YAML files in `core/flows/` are your reference for what the generic orchestrator must support — read them before editing orchestrator.md.
- Do NOT change `model`, `tools`, or `can_spawn` in the YAML files.
- Do NOT touch team.md, debug.md, explore.md, or any flow YAML file in this conversation.
- After editing, verify no hardcoded team state names remain as logic (not comment) lines in orchestrator.md.

Verify:
- `grep -i "BUILDING\|REVIEWING\|TESTING\|RETRO" src/pathly_data/core/agents/orchestrator.md` — output must be comment lines only (lines starting with `#` or `>`).
- `grep "flow_config" src/pathly_data/core/agents/orchestrator.md` — must return at least 2 matches (inputs block + startup read).
- `grep "flow_config" src/pathly_data/adapters/claude/_meta/orchestrator.yaml` — must return the new field.
- `git diff --stat` — must show only orchestrator.md and the YAML adapter file(s).

After done, update plans/fsm-configurable/PROGRESS.md Phases 4–5 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout` on affected files and retry.
```

**Expected output:** orchestrator.md is a generic FSM engine; orchestrator.yaml declares flow_config; `git diff --stat` shows only those files.
**Files touched:** `src/pathly_data/core/agents/orchestrator.md`, `src/pathly_data/adapters/claude/_meta/orchestrator.yaml`, `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` (if exists)

---

## Conversation 3: Update skill launchers (Phases 6–8)

**Stories delivered:** S3.1, S3.2, S3.3

**Pre-condition:** Conv 2 of this feature must be DONE. `agent-architecture-refactor` Conv 4 must be DONE.

**Prompt to paste:**
```
Read plans/fsm-configurable/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-configurable Conversation 3 (Phases 6–8) from plans/fsm-configurable/IMPLEMENTATION_PLAN.md.

**Pre-flight:**
1. Run `git status` to confirm a clean working tree.
2. Read `plans/fsm-configurable/PROGRESS.md` — confirm Conv 2 is DONE. If not, stop and report.
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
- Phase 6: team.md — add `flow_config: core/flows/team.flow.yaml` to the orchestrator spawn block (story S3.1) — see IMPLEMENTATION_PLAN.md Phase 6
- Phase 7: debug.md — replace inline FSM with orchestrator spawn passing debug flow config (story S3.2) — see IMPLEMENTATION_PLAN.md Phase 7
- Phase 8: explore.md — replace inline spawning with orchestrator spawn passing explore flow config (story S3.3) — see IMPLEMENTATION_PLAN.md Phase 8

Rules:
- Each file must remain runnable after this conversation — no half-replaced files.
- Keep argument parsing, topic/symptom detection, and any setup logic in debug.md and explore.md. Remove only the inline FSM state-transition steps.
- The orchestrator spawn block format must match the pattern already in team.md after agent-architecture-refactor Conv 4.
- Do NOT touch orchestrator.md, flow YAML files, or any other file.

Verify:
- `grep "flow_config" src/pathly_data/core/skills/team.md` — returns `core/flows/team.flow.yaml`.
- `grep "flow_config" src/pathly_data/core/skills/debug.md` — returns `core/flows/debug.flow.yaml`.
- `grep "flow_config" src/pathly_data/core/skills/explore.md` — returns `core/flows/explore.flow.yaml`.
- `grep "orchestrator" src/pathly_data/core/skills/debug.md` — returns the spawn instruction.
- `grep "orchestrator" src/pathly_data/core/skills/explore.md` — returns the spawn instruction.
- `git diff --stat` — shows only team.md, debug.md, explore.md.

After done, update plans/fsm-configurable/PROGRESS.md Phases 6–8 and overall status to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout` on affected files and retry.
```

**Expected output:** All three skill files delegate to orchestrator with their respective flow configs; `git diff --stat` shows exactly those three files.
**Files touched:** `src/pathly_data/core/skills/team.md`, `src/pathly_data/core/skills/debug.md`, `src/pathly_data/core/skills/explore.md`
