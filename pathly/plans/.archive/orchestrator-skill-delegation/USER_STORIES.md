# orchestrator-skill-delegation — User Stories

## Context

The Pathly orchestrator currently implements `git_commit`, `update_progress`, and `archive_artifacts` inline inside its own `Execute transition_actions` section — running shell commands and editing files directly. This violates the orchestrator's own contract: "Delegate, never implement" and "Do not write code or edit files."

The fix: extract those three action types into two dedicated skills (`commit` and `archive-artifacts`), update the flow YAML schema to reference `skill:` instead of `type:`, and shrink the orchestrator to a 5-line delegation loop. This makes transition side-effects composable, independently testable, and available to all flows (team, debug, explore) without orchestrator changes.

---

## Stories

### Story S1: commit skill
**As** the orchestrator, **I want** a `commit` skill I can spawn at any transition, **so that** I never run `git` commands myself.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/skills/commit.md` exists with a clear input contract (`message` arg)
- [ ] The skill checks for active feedback files before committing and exits with a suppression notice if any are found
- [ ] The skill runs `git add -A` then `git commit -m <message>`
- [ ] The skill appends `{"type": "ACTION_DONE", "action": "commit"}` to `EVENTS.jsonl`
- [ ] An adapter meta YAML exists that installs the skill to `pathly-commit/SKILL.md`

**Edge Cases:**
- Feedback file present → commit suppressed, skill reports which file blocked it
- Git working tree clean (nothing to commit) → skill exits cleanly without error

**Delivered by:** Phase 1–2 → Conversation 1

---

### Story S2: archive-artifacts skill
**As** the orchestrator, **I want** an `archive-artifacts` skill I can spawn at any transition, **so that** artifact archiving is independently testable and not embedded in the orchestrator.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/skills/archive-artifacts.md` exists with input contract (`storage_path`, `topic`, `conv`)
- [ ] The skill copies all files from `<storage_path>/feedback/` to `pathly/pipeline-walkthrough/<topic>/artifacts/` using naming `<FILENAME>_conv<N>_attempt<M>.md`
- [ ] The skill appends `{"type": "ACTION_DONE", "action": "archive-artifacts"}` to `EVENTS.jsonl`
- [ ] An adapter meta YAML exists that installs the skill

**Edge Cases:**
- No feedback files present → skill exits cleanly (no-op, no error)

**Delivered by:** Phase 3–4 → Conversation 1

---

### Story S3: orchestrator delegates via skill dispatch
**As** a flow author, **I want** to write `skill: commit` in `transition_actions` YAML instead of `type: git_commit`, **so that** the orchestrator is a pure router and each action is a self-contained skill.

**Acceptance Criteria:**
- [ ] `orchestrator.md`'s `Execute transition_actions` section is ≤10 lines and contains no shell commands or file-edit logic
- [ ] The section reads: for each action with `skill:` key, spawn that skill with the action's args, wait for return, continue
- [ ] The old `type: git_commit`, `type: update_progress`, `type: archive_artifacts` handling is removed
- [ ] Installed `C:/Users/Yafit/.claude/agents/orchestrator.md` is synced

**Delivered by:** Phase 5–6 → Conversation 2

---

### Story S4: debug and explore flows auto-commit
**As** a pipeline user, **I want** debug and explore flows to commit at key transitions the same way team does, **so that** all three flows leave consistent git checkpoints.

**Acceptance Criteria:**
- [ ] `debug.flow.yaml` has `transition_actions` with `skill: commit` on `FIXING->VERIFYING` and `skill: archive-artifacts` on `VERIFYING->DONE`
- [ ] `explore.flow.yaml` has `transition_actions` with `skill: commit` and `skill: archive-artifacts` on `CONCLUDING->DONE`
- [ ] `team.flow.yaml` uses `skill: commit` and `skill: archive-artifacts` (updated from `type:`)
- [ ] All installed copies in `C:/Users/Yafit/.claude/agents/` are synced

**Delivered by:** Phase 7–9 → Conversation 3

---

### Story S5: fix debug flow FIXING agent
**As** the debug pipeline, **I want** `FIXING` state to use `builder`, **so that** the agent that implements the fix is correct.

**Acceptance Criteria:**
- [ ] `debug.flow.yaml` `agent_map.FIXING` is `builder` (not `tester`)
- [ ] Installed `C:/Users/Yafit/.claude/agents/debug.flow.yaml` reflects this fix

**Delivered by:** Phase 8 → Conversation 3
