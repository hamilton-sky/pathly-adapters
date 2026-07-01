---
name: Edge Cases
---
# Parallel Fleet Part 1 — Edge Cases

The five edge cases below are the architect's identified risks for this feature. Each has a required acceptance criterion that maps to a test. No edge case is left untested.

---

## EC-1: Crash-safe idempotent teardown

**Risk:** A crash mid-run (e.g., process kill, OOM, power loss) leaves orphan worktrees registered with git, leaving `git worktree list` wedged and blocking future runs on the same feature.

- **Trigger**: `FleetCoordinator.run` is killed between `WorktreeManager.create` and `WorktreeManager.remove`.
- **Expected behavior**: On next startup, `WorktreeManager.reconcile()` detects the orphan (directory present, `FLEET_STATE.json` absent or stale), calls `git worktree prune`, removes orphan directories, and leaves `git worktree list` clean.
- **Acceptance criterion (binary)**: A test in `tests/test_worktree.py` manually creates a `.pathly-worktrees/<feature>/orphan/` directory without registering it via `git worktree add`; after `reconcile()`, asserts `git worktree list` contains no entry for that path and the directory is gone.
- **Handled in**: Conv 1 → Phase 1 (`worktree.py` `reconcile` method + `WorktreeLaneError` guard in `create`).
- **Additional guard**: `FleetCoordinator` calls `reconcile()` at the end of every run, whether it succeeds or escalates.

---

## EC-2: Merge never force/guess

**Risk:** The integrator agent, under pressure to "fix" a conflict, issues a force-merge command (`git push --force`, `git merge --strategy=ours`, `git checkout --ours`), committing a broken or incorrect merge without a human review.

- **Trigger**: A textual or semantic conflict where the integrator's one resolution attempt still leaves failing tests.
- **Expected behavior**: The integrator writes `feedback/HUMAN_QUESTIONS.md` with the full conflict context and halts. The integration branch is left in a clean, inspectable state (no staged conflict markers, no committed bad state). No force command is issued.
- **Acceptance criterion (binary)**: In `tests/test_integrate_flow.py`, the bash-invocation log is asserted to contain none of: `--force`, `--strategy=ours`, `checkout --ours`. The test fails if any of those strings appear. `feedback/HUMAN_QUESTIONS.md` must be present after escalation.
- **Handled in**: Conv 3 → Phase 3 (`integrator.md` explicit prohibition + test guard).
- **Additional guard**: `integrator.md` lists prohibited commands explicitly; reviewer is instructed to flag any invocation of them as a REVIEW_FAILURE.

---

## EC-3: Degrade to sequential when all footprints intersect

**Risk:** A decomposition where every unit touches at least one file that another unit also touches produces an empty parallel lane set. Without a degrade path, the coordinator deadlocks waiting for parallel lanes that never start.

- **Trigger**: `decompose(units)` called where all units share at least one file across the full set (complete overlap graph).
- **Expected behavior**: `decompose` returns `FleetPlan` with `single_lane_mode=True`, `parallel_lanes=[]`, and all units in `foundation_units`. `write_fleet_plan` writes `mode: sequential`. `FleetCoordinator` detects `single_lane_mode=True` in the fleet.yaml and routes the entire feature through a single supervised flow (no fan-out), completing normally.
- **Acceptance criterion (binary)**: In `tests/test_overlap.py`, an input of 3 units where every pair shares a file → `plan.single_lane_mode == True`, `plan.parallel_lanes == []`. In `tests/test_fleet_coord.py`, a coordinator run on a single-lane plan completes with `phase=="done"` without calling `supervisor_start_fn` more than once.
- **Handled in**: Conv 2 → Phase 2 (`overlap.py` degrade logic) + Conv 4 → Phase 4 (`fleet_coord.py` single-lane branch).

---

## EC-4: Real lane isolation (no two lanes write the same path)

**Risk:** Two parallel lanes modify the same file concurrently, producing non-deterministic merge conflicts or silent file corruption when both lanes are merged.

- **Trigger**: A decomposition bug or manual `fleet.yaml` edit that places the same file in two parallel lane footprints; or a lane whose implementation drifts and writes a file outside its declared footprint that overlaps another active lane.
- **Expected behavior** (two sub-cases):
  - At coordinator fan-out time: `FleetCoordinator.run` asserts no two parallel lanes share a file before calling any `supervisor_start_fn`; if the assertion fails, raises `LaneIsolationError` and halts without starting any lane.
  - At stage-boundary time (runtime drift): `WorktreeManager.check_footprint_violation` emits `FOOTPRINT_VIOLATION` event; if the stray file overlaps another active lane's footprint, raises `FootprintViolationError` and halts that lane; the other lane is not affected.
- **Acceptance criterion (binary)**: `tests/test_fleet_coord.py` asserts `LaneIsolationError` is raised when two lanes share a footprint file, and `supervisor_start_fn` was NOT called. `tests/test_worktree.py` asserts `FootprintViolationError` is raised when a stray file overlaps an active lane's footprint, and the event written to `EVENTS.jsonl` has `escalated: true`.
- **Handled in**: Conv 1 → Phase 1 (runtime tripwire in `worktree.py`) + Conv 4 → Phase 4 (fan-out assertion in `fleet_coord.py`).

---

## EC-5: CI gate enforced before part 2

**Risk:** `parallel-fleet-part-2` begins before the Python mechanics are proven end-to-end, importing untested assumptions into the HTTP/SSE layer and making bugs much harder to isolate.

- **Trigger**: Part-2 planning or build begins while `tests/test_fleet_e2e.py` has not been written or is not green.
- **Expected behavior**: `parallel-fleet-part-2` MUST NOT begin until both end-to-end scenarios in `tests/test_fleet_e2e.py` pass under `python -m pytest tests/test_fleet_e2e.py -q`.
  - Happy path: `FLEET_STATE.json` `phase=="done"`, `git worktree list` clean.
  - Forced-conflict path: `FLEET_STATE.json` `phase=="escalated"`, `feedback/HUMAN_QUESTIONS.md` present, integration branch `git status` clean, `git worktree list` clean.
- **Acceptance criterion (binary)**: The CI gate test `tests/test_fleet_e2e.py` must exist and pass before any work on `parallel-fleet-part-2` begins. If it does not pass, part-2 is blocked.
- **Handled in**: Conv 4 → Phase 4 (`tests/test_fleet_e2e.py`) + explicit gate note in `IMPLEMENTATION_PLAN.md`.

---

## Known Limitations

- The HTTP control surface (start/stop/observe fleet runs via REST and SSE) is intentionally out of scope — delivered in `parallel-fleet-part-2`.
- The integrator makes one resolution attempt per conflict. Multiple-conflict scenarios beyond the cap escalate immediately; there is no backoff or retry strategy for very large conflict sets.
- Footprint detection relies on `git diff --name-only HEAD` inside the worktree, which requires the stage boundary to be a git-committed state. Uncommitted intermediate writes are not tracked.
