---
name: Happy Flow
---
# Parallel Fleet Part 1 — Happy Flow

## Overview

A developer has a large feature with 4 sub-units. After inspection, 2 units share a configuration file (they go into the foundation lane) and the other 2 have completely disjoint footprints (they become parallel lanes). The fleet coordinator decomposes the work, runs the foundation lane first to serialize the shared-file changes, then fans out the two parallel lanes simultaneously, and finally merges both lane branches cleanly into an integration branch that passes all tests. The repo is left in a clean state with no orphan worktrees.

---

## Step-by-Step Happy Flow

### Step 1: Decomposition
- **User does**: calls `FleetCoordinator.run(units=[...], base_commit="main", config={...})` with 4 units.
- **System does**: `decompose(units)` identifies `config.py` as a shared file (touched by units A and B); assigns A and B to the foundation lane; assigns C and D to separate parallel lanes (disjoint footprints).
- **State after**: `FleetPlan` produced with `foundation_units=["A","B"]`, `parallel_lanes=[LaneGroup("lane-0",["C"],...), LaneGroup("lane-1",["D"],...)]`, `single_lane_mode=False`. `fleet.yaml` written. `FLEET_STATE.json` written with `phase="planning"`.

### Step 2: Worktree creation
- **User does**: (automatic — coordinator proceeds).
- **System does**: `WorktreeManager.create` creates `.pathly-worktrees/<feature>/foundation/` (branch `fleet/<feature>/foundation`) and `.pathly-worktrees/<feature>/lane-0/` (branch `fleet/<feature>/lane-0`) and `lane-1/`. Base commit is the current `main` HEAD.
- **State after**: 3 worktrees registered in `git worktree list`. No changes to the main working tree. `FLEET_STATE.json` updated with `phase="foundation"`, lanes list populated.

### Step 3: Foundation lane runs
- **User does**: (automatic).
- **System does**: coordinator calls `supervisor_start_fn(topic_key="<feature>__foundation", project_root=<foundation_worktree>)`. The supervisor runs the FSM flow for units A and B inside the foundation worktree.
- **State after**: foundation lane completes with `status="done"`. The integration branch `fleet/<feature>/integration` is created from the foundation branch HEAD. `FLEET_STATE.json` updated with `phase="fleet"`.

### Step 4: Parallel lanes fan out
- **User does**: (automatic).
- **System does**: coordinator asserts lane isolation (C's footprint ∩ D's footprint = ∅ — confirmed). Calls `supervisor_start_fn` for `<feature>__lane-0` and `<feature>__lane-1` concurrently. Each supervisor runs its assigned unit in its own worktree.
- **State after**: both lanes running. `LANE_STARTED` events emitted to `EVENTS.jsonl` for each lane.

### Step 5: Parallel lanes complete
- **User does**: (automatic).
- **System does**: coordinator polls lane statuses; both return `"done"`. `LANE_DONE` events emitted for each lane.
- **State after**: `FLEET_STATE.json` lanes show `status="done"` for lane-0 and lane-1. Phase advances to `"merging"`.

### Step 6: Conservative merge
- **User does**: (automatic).
- **System does**: integrate flow begins with `merge_order=["fleet/<feature>/lane-0", "fleet/<feature>/lane-1"]`. Integrator runs `git merge --no-ff fleet/<feature>/lane-0` → clean merge → runs tests → pass → runs `git merge --no-ff fleet/<feature>/lane-1` → clean merge → runs tests → pass → advances FSM to `DONE`.
- **State after**: integration branch contains all changes from foundation + lane-0 + lane-1. All tests green. `MERGE_CONFLICT` event NOT emitted.

### Step 7: Teardown
- **User does**: (automatic).
- **System does**: coordinator calls `WorktreeManager.remove` for each worktree; `WorktreeManager.reconcile()` confirms no orphans. `FLEET_DONE` event emitted. `FLEET_STATE.json` written with `phase="done"`, `integration_branch="fleet/<feature>/integration"`.
- **State after**: `git worktree list` shows no `.pathly-worktrees/` entries. Main working tree is clean. Integration branch is ready for review/promotion.

---

## End State

The feature's integration branch (`fleet/<feature>/integration`) contains all sub-unit changes merged cleanly. `FLEET_STATE.json` shows `phase="done"`. `git worktree list` is clean. `tests/` pass. The developer can inspect the integration branch, run additional review/test cycles, and promote it to `main` via normal PR flow.

---

## Success Indicators

- [ ] `FLEET_STATE.json` `phase == "done"` after the run.
- [ ] `git worktree list` contains no `.pathly-worktrees/` entries after teardown.
- [ ] Integration branch exists with a clean merge commit history (no conflict markers, no force-merge commits).
- [ ] `python -m pytest tests/ -q` passes on the integration branch.
- [ ] `EVENTS.jsonl` contains `FLEET_PHASE_CHANGE` events for all phases and `LANE_STARTED`/`LANE_DONE` for both parallel lanes.
- [ ] No `feedback/HUMAN_QUESTIONS.md` file exists (happy path has no escalations).
