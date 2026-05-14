# orchestrator-skill-delegation — Happy Flow

## Overview

A flow author adds `skill: commit` to a transition in their flow YAML. When the orchestrator hits that transition, it spawns the `commit` skill, which checks for open feedback files, stages all changes, commits, and appends an ACTION_DONE event. The orchestrator never touches git itself. The whole interaction is logged in EVENTS.jsonl.

## Step-by-Step Happy Flow

### Step 1: Orchestrator evaluates transition
- **Trigger**: A subagent (e.g. `team/build`) returns. Orchestrator reads `transition_rules`, determines next state is REVIEWING.
- **System does**: Appends `STATE_TRANSITION` to EVENTS.jsonl, reads `transition_actions["BUILDING->REVIEWING"]`.
- **State after**: Orchestrator has a list: `[{skill: commit, message: "feat: complete building stage"}]`

### Step 2: Orchestrator spawns commit skill
- **System does**: Reads `action.skill = "commit"`, spawns skill with args `(topic, storage_path, conv=2, message="feat: complete building stage")`.
- **State after**: `commit` skill is running; orchestrator waits.

### Step 3: commit skill checks for feedback files
- **System does**: Reads `<storage_path>/feedback/` — no `.md` files found.
- **State after**: Guard passes. Skill proceeds.

### Step 4: commit skill stages and commits
- **System does**: Runs `git add -A`, runs `git commit -m "feat: complete building stage"`.
- **State after**: Git has a new commit. Working tree is clean.

### Step 5: commit skill appends ACTION_DONE
- **System does**: Appends `{"type": "ACTION_DONE", "action": "commit", "topic": "my-feature"}` to EVENTS.jsonl.
- **State after**: EVENTS.jsonl has the ACTION_DONE entry. Skill returns.

### Step 6: Orchestrator continues FSM loop
- **System does**: Reads next state (REVIEWING from step 1), spawns `team/review`.
- **State after**: Pipeline continues normally.

## End State

The orchestrator has delegated a git commit without running a single shell command itself. EVENTS.jsonl has a complete audit trail. The commit skill can be improved, tested, or replaced independently of the orchestrator.

## Success Indicators
- [ ] `Execute transition_actions` in orchestrator.md contains no shell commands
- [ ] A `git log` after a BUILDING→REVIEWING transition shows the auto-commit
- [ ] EVENTS.jsonl contains an `ACTION_DONE` entry for each skill invocation
