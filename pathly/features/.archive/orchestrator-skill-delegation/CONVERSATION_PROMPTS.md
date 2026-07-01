# orchestrator-skill-delegation — Conversation Guide

Split into 3 conversations. Each produces files that can be reviewed in isolation.

---

## Conversation 1: Create commit and archive-artifacts skills (Phases 1–4)

**Stories delivered:** S1, S2

**Prompt to paste:**
```
Read plans/orchestrator-skill-delegation/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-skill-delegation Conversation 1 (Phases 1–4) from plans/orchestrator-skill-delegation/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_data/core/skills/commit.md` — CREATE
- `src/pathly_data/adapters/claude/_meta/commit_skill.yaml` — CREATE (read an existing _skill.yaml for the pattern first)
- `src/pathly_data/core/skills/archive-artifacts.md` — CREATE
- `src/pathly_data/adapters/claude/_meta/archive-artifacts_skill.yaml` — CREATE

Scope:
- Phase 1: Create commit.md skill with input contract (message, storage_path, topic), feedback-file guard, git add -A + git commit, ACTION_DONE event append
- Phase 2: Create commit adapter meta YAML — filename: pathly-commit/SKILL.md
- Phase 3: Create archive-artifacts.md skill with input contract (storage_path, topic, conv), copy logic, ACTION_DONE event append
- Phase 4: Create archive-artifacts adapter meta YAML — filename: pathly-archive-artifacts/SKILL.md

Architectural rules:
- These are skill spec files (markdown), not Python. Write them as agent behavior specs following the style of existing skills in src/pathly_data/core/skills/.
- The commit skill guard (check feedback files before committing) belongs IN the skill, not in the orchestrator.
- Do NOT touch orchestrator.md or any flow YAML in this conversation.

Verify: `pytest src/` — record any failures as pre-existing baseline, do not fix them.
After done, update plans/orchestrator-skill-delegation/PROGRESS.md phases 1–4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 4 new files — 2 skill specs + 2 adapter meta YAMLs.
**Files touched:** `commit.md`, `commit_skill.yaml`, `archive-artifacts.md`, `archive-artifacts_skill.yaml`

---

## Conversation 2: Shrink orchestrator to pure delegation (Phases 5–6)

**Stories delivered:** S3

**Prompt to paste:**
```
Read plans/orchestrator-skill-delegation/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-skill-delegation Conversation 2 (Phases 5–6) from plans/orchestrator-skill-delegation/IMPLEMENTATION_PLAN.md.

**Before editing anything:** verify Conv 1 is DONE in PROGRESS.md. Then read both orchestrator files.

**Codebase files this conversation touches:**
- `src/pathly_data/core/agents/orchestrator.md` — MODIFY (shrink Execute transition_actions)
- `C:/Users/Yafit/.claude/agents/orchestrator.md` — MODIFY (sync installed copy)

Scope:
- Phase 5: In src/pathly_data/core/agents/orchestrator.md, replace the entire `### Execute transition_actions` block with the new 10-line delegation version from IMPLEMENTATION_PLAN.md Phase 5. Remove all type: git_commit, type: update_progress, type: archive_artifacts handling. Remove the feedback-file guard from the orchestrator (it now lives in the commit skill).
- Phase 6: Apply the exact same replacement to C:/Users/Yafit/.claude/agents/orchestrator.md. Verify the two files' Execute transition_actions sections are identical.

Architectural rules:
- The new section must contain ZERO shell commands and ZERO file edits.
- The dispatch model: read action.skill, spawn that skill with (topic, storage_path, conv, + action fields), wait, continue. That is all.
- Do NOT touch any flow YAML in this conversation.

Verify: diff the Execute transition_actions section in both files — must be identical.
After done, update plans/orchestrator-skill-delegation/PROGRESS.md phases 5–6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Orchestrator's Execute transition_actions section reduced to ≤10 lines in both source and installed copies.
**Files touched:** `orchestrator.md` ×2

---

## Conversation 3: Update flow YAMLs + fix debug bug (Phases 7–10)

**Stories delivered:** S4, S5

**Prompt to paste:**
```
Read plans/orchestrator-skill-delegation/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-skill-delegation Conversation 3 (Phases 7–10) from plans/orchestrator-skill-delegation/IMPLEMENTATION_PLAN.md.

**Before editing anything:** verify Conv 2 is DONE in PROGRESS.md. Then read all six flow YAML files (3 source + 3 installed).

**Codebase files this conversation touches:**
- `src/pathly_data/core/flows/team.flow.yaml` — MODIFY transition_actions type: → skill:
- `src/pathly_data/core/flows/debug.flow.yaml` — MODIFY FIXING bug + replace transition_actions
- `src/pathly_data/core/flows/explore.flow.yaml` — MODIFY replace transition_actions
- `C:/Users/Yafit/.claude/agents/team.flow.yaml` — SYNC
- `C:/Users/Yafit/.claude/agents/debug.flow.yaml` — SYNC
- `C:/Users/Yafit/.claude/agents/explore.flow.yaml` — SYNC

Scope:
- Phase 7: team.flow.yaml — change type: git_commit → skill: commit; type: archive_artifacts → skill: archive-artifacts (exact YAML from IMPLEMENTATION_PLAN.md Phase 7)
- Phase 8: debug.flow.yaml — (a) change agent_map.FIXING from tester to builder; (b) replace transition_actions: {} with the block from IMPLEMENTATION_PLAN.md Phase 8
- Phase 9: explore.flow.yaml — replace transition_actions: {} with the block from IMPLEMENTATION_PLAN.md Phase 9
- Phase 10: Sync all three installed copies in C:/Users/Yafit/.claude/agents/ to match their source counterparts exactly. NOTE: the installed copies are currently missing transition_actions entirely — replace that section completely.

Architectural rules:
- No type: keys should remain in any flow YAML's transition_actions after this conversation.
- The installed copies must be byte-for-byte identical to source on the changed sections.
- Do NOT touch orchestrator.md or any skill file in this conversation.

Verify: for each of the 6 files, diff source vs installed — must be identical on transition_actions and agent_map sections.
After done, update plans/orchestrator-skill-delegation/PROGRESS.md phases 7–10 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 6 flow YAML files updated — type: replaced with skill:, debug FIXING bug fixed, all installed copies in sync.
**Files touched:** `team.flow.yaml`, `debug.flow.yaml`, `explore.flow.yaml` ×2 each
