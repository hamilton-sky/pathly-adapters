# orchestrator-skill-delegation — Implementation Plan

## Overview

Extract `git_commit` and `archive_artifacts` from the orchestrator's inline `Execute transition_actions` logic into two dedicated skills (`commit`, `archive-artifacts`). Update the flow YAML schema to use `skill:` instead of `type:`. Shrink the orchestrator's transition_actions section to pure delegation. Fix the `debug.flow.yaml` agent_map bug (FIXING: tester → builder). Add transition_actions to debug and explore flows.

## Layer Architecture

```
Flow YAML  (transition_actions: skill: commit)
     │  skill name + args
     ▼
Orchestrator  (Execute transition_actions — pure delegation)
     │  spawn skill by name
     ▼
commit skill / archive-artifacts skill
     │  git add -A && git commit  /  copy files
     ▼
Filesystem + Git
```

## Prerequisites

- Pre-flight: run `pytest` in `C:\Users\Yafit\pathly-adapters` and record any pre-existing failures as known baseline before Conv 1 begins. Do not fix them — just note them.

---

## Phases

### Phase 1: Create commit skill   ← Conversation: 1
**File:** `src/pathly_data/core/skills/commit.md` — CREATE
**Done when:** File exists with input contract, feedback-file guard, `git add -A && git commit`, and ACTION_DONE event append.
**Delivers stories:** S1
**Depends on:** nothing
**Enables:** Phase 5 (orchestrator can reference this skill by name)
**Details:**
- Input: `message` (commit message string), `storage_path` (for feedback file check), `topic`
- Guard: check `<storage_path>/feedback/` for any `.md` file. If found: print "commit suppressed — active feedback file: <name>" and exit without committing.
- Run: `git add -A`
- Run: `git commit -m "<message>"` — if clean tree (exit code 1, "nothing to commit"), exit cleanly.
- Append: `{"type": "ACTION_DONE", "action": "commit", "topic": "<topic>"}` to `<storage_path>/EVENTS.jsonl`
**Verify:** `pytest src/` (baseline only — skill is a markdown spec, not Python)

### Phase 2: Create commit skill adapter meta   ← Conversation: 1
**File:** `src/pathly_data/adapters/claude/_meta/commit_skill.yaml` — CREATE
**Done when:** Meta YAML exists with correct `filename: pathly-commit/SKILL.md` and points to the core skill.
**Delivers stories:** S1
**Depends on:** Phase 1
**Enables:** skill is installable to `~/.claude/skills/pathly-commit/SKILL.md`
**Details:**
- Follow the existing pattern from `src/pathly_data/adapters/claude/_meta/archive_skill.yaml`
- `filename`: `pathly-commit/SKILL.md`
- `source`: `core/skills/commit.md`

### Phase 3: Create archive-artifacts skill   ← Conversation: 1
**File:** `src/pathly_data/core/skills/archive-artifacts.md` — CREATE
**Done when:** File exists with input contract, copy logic, and ACTION_DONE event append.
**Delivers stories:** S2
**Depends on:** nothing
**Enables:** Phase 9 (flow YAMLs can reference this skill)
**Details:**
- Input: `storage_path`, `topic`, `conv` (current conversation number)
- Read all `.md` files from `<storage_path>/feedback/`
- For each: copy to `pathly/pipeline-walkthrough/<topic>/artifacts/<FILENAME>_conv<N>_attempt<M>.md` where M is derived from existing files with the same name prefix (increment from highest existing M, default 1)
- If no feedback files: exit cleanly (no-op)
- Append: `{"type": "ACTION_DONE", "action": "archive-artifacts", "topic": "<topic>"}` to `<storage_path>/EVENTS.jsonl`

### Phase 4: Create archive-artifacts skill adapter meta   ← Conversation: 1
**File:** `src/pathly_data/adapters/claude/_meta/archive-artifacts_skill.yaml` — CREATE
**Done when:** Meta YAML exists with correct `filename: pathly-archive-artifacts/SKILL.md`.
**Delivers stories:** S2
**Depends on:** Phase 3
**Enables:** skill installable to `~/.claude/skills/pathly-archive-artifacts/SKILL.md`
**Details:**
- Follow same pattern as Phase 2
- `filename`: `pathly-archive-artifacts/SKILL.md`
- `source`: `core/skills/archive-artifacts.md`

---

### Phase 5: Shrink orchestrator Execute transition_actions   ← Conversation: 2
**File:** `src/pathly_data/core/agents/orchestrator.md` — MODIFY
**Done when:** The `Execute transition_actions` section is ≤10 lines, contains no shell commands or file-editing logic, and reads as pure delegation.
**Delivers stories:** S3
**Depends on:** Phase 1–4 (skills must exist before orchestrator references them)
**Enables:** Phase 6
**Details:**
Replace the entire `### Execute transition_actions` block (currently ~30 lines, lines 86–114) with:

```markdown
### Execute transition_actions

After appending the transition event:

1. Read `transition_actions[PREV->NEW]` from the flow YAML (also check `->NEW` wildcard). If absent or empty: no-op, continue.
2. For each action in list order:
   - Read `action.skill` — the skill name to spawn.
   - Spawn that skill with: `topic`, `storage_path`, `conv` (current conversation number from STATE.json), and any additional fields from the action object (e.g. `message`).
   - Wait for the skill to return before spawning the next.
3. Continue FSM loop with `next_state`.
```

Remove: all `type: git_commit`, `type: update_progress`, `type: archive_artifacts` handling. Remove the feedback-file guard from the orchestrator (it belongs in the `commit` skill now).

### Phase 6: Sync installed orchestrator   ← Conversation: 2
**File:** `C:/Users/Yafit/.claude/agents/orchestrator.md` — MODIFY
**Done when:** Installed file matches source file's `Execute transition_actions` section exactly.
**Delivers stories:** S3
**Depends on:** Phase 5
**Enables:** live orchestrator uses the new delegation model
**Details:**
Read `C:/Users/Yafit/.claude/agents/orchestrator.md`, apply the same replacement as Phase 5. Verify the section is identical to the source.
**Verify:** diff the two files — `Execute transition_actions` sections must be identical.

---

### Phase 7: Update team.flow.yaml   ← Conversation: 3
**File:** `src/pathly_data/core/flows/team.flow.yaml` — MODIFY
**Done when:** `transition_actions` block uses `skill:` keys, no `type:` keys remain.
**Delivers stories:** S4
**Depends on:** Phase 5–6 (orchestrator must know how to dispatch `skill:`)
**Enables:** team pipeline uses commit + archive-artifacts skills
**Details:**
Change:
```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - type: git_commit
      message: "feat: complete building stage"
  "RETRO->DONE":
    - type: archive_artifacts
```
To:
```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - skill: commit
      message: "feat: complete building stage"
  "RETRO->DONE":
    - skill: archive-artifacts
```

### Phase 8: Update debug.flow.yaml — fix bug + add transition_actions   ← Conversation: 3
**File:** `src/pathly_data/core/flows/debug.flow.yaml` — MODIFY
**Done when:** `agent_map.FIXING` is `builder`; `transition_actions` block present with skill: syntax.
**Delivers stories:** S4, S5
**Depends on:** Phase 7
**Enables:** debug pipeline auto-commits and has correct agent assignment
**Details:**
1. Change `agent_map.FIXING: tester` → `agent_map.FIXING: builder`
2. Replace `transition_actions: {}` with:
```yaml
transition_actions:
  "FIXING->VERIFYING":
    - skill: commit
      message: "fix: implement fix for {topic}"
  "VERIFYING->DONE":
    - skill: archive-artifacts
```

### Phase 9: Update explore.flow.yaml — add transition_actions   ← Conversation: 3
**File:** `src/pathly_data/core/flows/explore.flow.yaml` — MODIFY
**Done when:** `transition_actions` block present with skill: syntax.
**Delivers stories:** S4
**Depends on:** Phase 7
**Details:**
Replace `transition_actions: {}` with:
```yaml
transition_actions:
  "CONCLUDING->DONE":
    - skill: commit
      message: "docs: exploration complete for {topic}"
    - skill: archive-artifacts
```

### Phase 10: Sync installed flow YAMLs   ← Conversation: 3
**Files:** `C:/Users/Yafit/.claude/agents/team.flow.yaml`, `debug.flow.yaml`, `explore.flow.yaml` — MODIFY
**Done when:** All three installed files match their source counterparts exactly.
**Delivers stories:** S4, S5
**Depends on:** Phase 7–9
**Details:**
For each of the three files: read source, apply same changes, verify installed copy matches. Pay special attention — the installed copies are currently missing `transition_actions` entirely (known baseline gap).
**Verify:** diff source vs installed for all three files — must be identical.

---

## Key Decisions

- **`skill:` dispatch model**: The orchestrator reads `action.skill` and spawns it the same way it spawns FSM agents — by name, with standardized args. No new dispatch mechanism needed; it reuses the existing agent-spawn pattern.
- **Guard stays in the skill, not the orchestrator**: The feedback-file guard before committing moves into `commit.md`. This keeps the orchestrator's delegation loop unconditional and puts guard logic where it can be tested in isolation.
- **`update_progress` deferred**: This action type has no usages in any current flow YAML. It is removed from the orchestrator spec but no `update-progress` skill is created in this plan. Add it only when a flow needs it.
