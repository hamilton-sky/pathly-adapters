---
name: User Stories
---
# Parallel Fleet Part 1 — User Stories

## Context

Running large features through Pathly's sequential FSM is safe but slow — each sub-unit waits for the previous one to finish. When a feature's sub-units have disjoint file footprints they can run in parallel without interfering. This feature adds the Python mechanics to do that: crash-safe git worktrees per lane, a decomposition algorithm that partitions work into lanes, a conservative merge agent that never force-merges, and a coordinator that drives the whole cycle. Part 2 will add the HTTP/SSE control surface so a UI can observe and manage fleets in real time.

The primary beneficiary is the developer who wants to parallelize independent sub-units of a large feature build without losing the safety guarantees (crash recovery, lane isolation, clean-or-escalate merging) that make autonomous runs trustworthy.

---

## Stories

### Story S1: Crash-safe worktree lifecycle

**As a** developer running a parallel fleet, **I want** git worktrees created and cleaned up reliably, **so that** a crash or abort never leaves the repo in a wedged state with orphaned branches or locked worktrees.

**Acceptance Criteria:**
- [ ] `WorktreeManager.create(feature, lane, base_commit)` creates `<repo>/.pathly-worktrees/<feature>/<lane>/` and branch `fleet/<feature>/<lane>` checked out at `base_commit`, or raises `WorktreeLaneError` if the worktree already exists and is not stale.
- [ ] `WorktreeManager.remove(feature, lane)` removes the worktree directory and deletes the branch; if the worktree directory is already absent the call is a no-op (idempotent).
- [ ] `WorktreeManager.reclaim(feature, lane)` removes a stale worktree (directory exists but branch HEAD is unreachable or worktree is not listed by `git worktree list`) and recreates it cleanly.
- [ ] `WorktreeManager.reconcile()` calls `git worktree prune` and then removes any worktree directory under `.pathly-worktrees/` whose entry is no longer in `git worktree list`; after the call, `git worktree list` contains no entries under `.pathly-worktrees/`.
- [ ] After a simulated crash (worktree directory exists, no `FLEET_STATE.json` fleet registration, no active supervisor topic), `reconcile()` removes the orphan and leaves `git worktree list` clean.
- [ ] When a lane's changed files at a stage boundary exceed its declared footprint AND overlap with another active lane's footprint, a `FOOTPRINT_VIOLATION` event is emitted with `escalated: true` and the lane is halted; when there is no overlap with another active lane, the event is emitted with `escalated: false` and execution continues.
- [ ] When `git worktree add` fails due to a disk error, the lane's status is set to `"error"` and the failure does not affect other lanes (no exception propagates to the coordinator loop uncaught).
- [ ] `.pathly-worktrees/` is confirmed absent from tracked git files (gitignored); the test asserts that `git status --short` does not list any `.pathly-worktrees/` path as tracked.

**Edge Cases:**
- Worktree already exists and is healthy: `create` raises `WorktreeLaneError` with a clear message (not silently reclaims).
- Dirty base commit (uncommitted changes in the base working tree): `create` raises `WorktreeDirtyBaseError` before touching the filesystem.
- Worktree directory exists but is not registered in `git worktree list` (partial failure): treated as stale, eligible for `reclaim`.
- `git worktree prune` fails (e.g. locked worktree): log the error and continue; do not raise.

**Delivered by:** Conv 1 → Phase 1

---

### Story S2: Overlap-gated decomposition

**As a** fleet coordinator, **I want** a feature's sub-units automatically partitioned into a foundation lane and parallel lanes, **so that** only truly disjoint work runs in parallel and shared-file work is safely serialized in the foundation lane first.

**Acceptance Criteria:**
- [ ] `decompose(units)` accepts a list of `{"name": str, "footprint": set[str]}` dicts and returns a `FleetPlan` with `foundation_units` (sub-units touching shared files) and `parallel_lanes` (list of lane groups, each group's footprints disjoint from all others).
- [ ] Files appearing in more than one unit's footprint are classified as shared and their owning units are assigned to the foundation lane; a unit with no shared files is eligible for a parallel lane.
- [ ] Connected components of the residual overlap graph are used to group parallel-lane units: two units sharing any file after foundation extraction land in the same lane.
- [ ] When every unit's footprint intersects with at least one other unit's footprint, `decompose` returns a `FleetPlan` with all units in `foundation_units`, an empty `parallel_lanes` list, and `single_lane_mode: True`.
- [ ] A `FleetPlan` with `single_lane_mode: True` serializes to a `fleet.yaml` whose `mode: sequential` field causes the coordinator to run it as an ordinary supervised single-flow — no parallel fan-out, no deadlock, no empty parallel set.
- [ ] `write_fleet_plan(plan, output_path)` writes a valid `fleet.yaml` matching the `FLEET_PLAN.template.md` schema.
- [ ] A unit with an empty footprint set is treated as universally disjoint and placed in its own parallel lane (not in the foundation).

**Edge Cases:**
- Single-unit input: produces zero foundation units, one parallel lane containing that unit, `single_lane_mode: False`.
- All units have identical footprints: produces single-lane degrade.
- Units with partially overlapping footprints (A∩B ≠ ∅, B∩C ≠ ∅, A∩C = ∅): B goes to foundation or a merged lane depending on the connected-component logic; the result must produce no plan where A and C could write the same file concurrently.

**Delivered by:** Conv 2 → Phase 2

---

### Story S3: Conservative merge agent

**As a** fleet coordinator, **I want** completed lane branches merged conservatively with full conflict escalation, **so that** no bad merge is ever committed and every unresolvable conflict is surfaced to a human with full context.

**Acceptance Criteria:**
- [ ] `integrate.flow.yaml` defines a flow with three states: `MERGING`, `INTEGRATION_TESTING`, and `DONE`; the integrator agent drives the FSM through these states sequentially.
- [ ] For each branch in `merge_order`, the integrator runs `git merge --no-ff <branch>`; a clean merge (exit 0, no conflict markers) proceeds to `INTEGRATION_TESTING`.
- [ ] `INTEGRATION_TESTING` runs the project's configured test command; if tests pass, the next branch in `merge_order` is processed; if all branches are merged and tests pass, the state advances to `DONE`.
- [ ] A textual conflict (merge exit non-zero, conflict markers present): the integrator attempts one resolution pass using the intent from both branches' plan contexts; if tests pass after resolution, continue; if tests still fail or the conflict is unresolvable, write `feedback/HUMAN_QUESTIONS.md` with the conflicting diff and context, advance state to `ESCALATED`, and halt — no further merge attempt.
- [ ] A semantic conflict (clean merge, failing tests): write `feedback/HUMAN_QUESTIONS.md` with test output and the commit history of both conflicting branches, advance state to `ESCALATED`, and halt.
- [ ] The merge loop is capped: if the same branch produces a conflict on a second attempt, it is immediately escalated without a third attempt.
- [ ] In both escalation cases, the integration branch is left in a clean, inspectable state (no staged bad merge, no committed conflict markers); `git status` on the integration branch is clean.
- [ ] A force-merge (`git merge --strategy=ours`, `git checkout --ours`, `git push --force`) is NEVER issued; any such command in the integrator's output is a test failure.
- [ ] Three adapter `_meta/integrator.yaml` files exist (one per adapter: claude, codex, copilot) with the correct `name`, `description`, `model`, `tools`, and `can_spawn` fields.

**Edge Cases:**
- Empty `merge_order`: flow reaches `DONE` immediately with no merge operations.
- All branches merge cleanly but tests fail on the final combined state: treated as a semantic conflict; escalate with full combined test output.
- Integration branch does not exist yet: the integrator creates it from `foundation` branch HEAD before beginning the merge loop.

**Delivered by:** Conv 3 → Phase 3

---

### Story S4: Fleet coordinator

**As a** developer, **I want** a `FleetCoordinator` that drives the full fleet lifecycle (decompose → foundation → parallel lanes → merge) using existing supervisor topic keys, **so that** I can launch a parallel fleet with a single call and trust that lane isolation is enforced and the state is durable across restarts.

**Acceptance Criteria:**
- [ ] `FleetCoordinator.run(feature, units, base_commit, config)` executes the full phase sequence: `planning → foundation → fleet → merging → done` (or `escalated` on unresolvable conflicts), writing `FLEET_STATE.json` on every phase transition.
- [ ] Each lane is started by calling the existing supervisor (via its topic key `<feature>__<lane>`) with `project_root` set to the lane's worktree path; the coordinator does NOT embed `RunnerState` or replicate supervisor internals.
- [ ] Before starting any lane, the coordinator asserts that no two lanes in the current fleet share a file path in their footprints; if the assertion fails, it raises `LaneIsolationError` and halts without starting any lane.
- [ ] Per-lane plan folder lives inside the lane's worktree (`<worktree>/pathly/plans/<feature>__<lane>/`), not in the main repo.
- [ ] When all lanes reach status `"done"`, the coordinator transitions to `merging` phase and triggers the integrate flow.
- [ ] When any lane reaches status `"error"` or `"blocked"`, the coordinator writes the failure to `escalations` in `FleetState` and transitions to `escalated`; it does NOT cancel other running lanes immediately (they run to completion or error on their own).
- [ ] `FLEET_STATE.json` is written atomically (write to temp file then rename) on every state mutation; a simulated crash during a mutation does not corrupt the state file.
- [ ] On `FleetCoordinator` startup, if an existing `FLEET_STATE.json` is found with `phase` not in `{"done", "escalated"}`, the coordinator resumes from the last known phase rather than restarting from scratch.

**Edge Cases:**
- Foundation lane fails: coordinator transitions immediately to `escalated`; parallel lanes never start.
- All lanes complete successfully but the integrate flow escalates: `FleetState.phase` = `"escalated"`, `FLEET_STATE.json` is consistent, integration branch is inspectable.
- Two concurrent coordinator instances for the same `fleet_id`: the second instance detects the active `FLEET_STATE.json` and raises `FleetAlreadyRunningError`.

**Delivered by:** Conv 4 → Phase 4
