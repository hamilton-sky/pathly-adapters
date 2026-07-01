---
name: Flow Diagram
---
# Parallel Fleet Part 1 — Flow Diagram

## Primary Flow: Happy Path (decompose → foundation → fleet → merge → done)

```
FleetCoordinator.run(units, base_commit)
        │
        ▼
overlap.decompose(units)
        │  ┌─────────────────────────────────────────┐
        │  │  shared files → foundation_units         │
        │  │  disjoint residual → parallel_lanes      │
        │  │  all intersect → single_lane_mode=True   │
        │  └─────────────────────────────────────────┘
        │
        ├─ single_lane_mode=True ──► run as single supervised flow ──► DONE
        │
        ▼ (parallel mode)
write_fleet_plan → fleet.yaml
        │
        ▼
WorktreeManager.create (foundation + N lanes)
        │  .pathly-worktrees/<feature>/foundation/  branch: fleet/<feature>/foundation
        │  .pathly-worktrees/<feature>/lane-0/      branch: fleet/<feature>/lane-0
        │  .pathly-worktrees/<feature>/lane-N/      branch: fleet/<feature>/lane-N
        │
        ▼
[FOUNDATION PHASE]
supervisor_start_fn(topic="<feature>__foundation", project_root=foundation_worktree)
        │
        ├─ status=error ──► FLEET_STATE phase=escalated, parallel lanes NEVER start
        │
        ▼ status=done
[FLEET PHASE]
assert lane isolation (no two footprints share a file)
        │
        ├─ LaneIsolationError ──► halt, no supervisor calls
        │
        ▼
fan-out: supervisor_start_fn × N  (one per parallel lane, concurrent)
        │
        │  [lane-0 running in worktree]   [lane-1 running in worktree]   ...
        │  WorktreeManager.check_footprint_violation at stage boundaries
        │     │
        │     ├─ stray, no cross-lane overlap → FOOTPRINT_VIOLATION(escalated=false), continue
        │     └─ stray, cross-lane overlap → FOOTPRINT_VIOLATION(escalated=true), lane halted
        │
        ▼ all lanes done
[MERGING PHASE]
trigger integrate.flow.yaml  (merge_order=[fleet/<feature>/lane-0, ..., lane-N])
        │
        └──► see Merge Flow below
```

---

## Merge Flow: integrate.flow.yaml

```
MERGING (initial state)
        │
        │  for each branch in merge_order:
        │    git merge --no-ff <branch>
        │
        ├─ clean merge ──────────────────────► INTEGRATION_TESTING
        │                                              │
        │                                    run project tests
        │                                              │
        │                               ┌─────────────┴──────────────┐
        │                               │                             │
        │                          tests pass                    tests fail
        │                               │                             │
        │                    more branches? ─yes─► MERGING       ESCALATED
        │                          │                              │
        │                    all merged ──────────► DONE         write HUMAN_QUESTIONS.md
        │                                                         integration branch clean
        │
        ├─ textual conflict ───► one resolution attempt
        │                               │
        │                     ┌─────────┴──────────┐
        │                     │                     │
        │               tests pass             still failing / unresolvable
        │                     │                     │
        │             continue merge            ESCALATED
        │                                       │
        │                              write HUMAN_QUESTIONS.md
        │                              integration branch clean
        │                              NEVER force-merge / guess
        │
        └─ same branch fails twice ──► ESCALATED immediately (cap)
```

---

## Teardown / Reconcile Flow

```
FleetCoordinator.run completes (done OR escalated)
        │
        ▼
WorktreeManager.remove(feature, lane) × N
        │  removes each worktree dir + branch
        │
        ▼
WorktreeManager.reconcile()
        │  git worktree prune
        │  walk .pathly-worktrees/ → remove any dir not in git worktree list
        │
        ▼
git worktree list: no .pathly-worktrees/ entries
FLEET_STATE.json: phase = "done" | "escalated"
EVENTS.jsonl: FLEET_DONE | FLEET_ESCALATED event appended
```

---

## Crash Recovery Flow

```
Process killed mid-run
        │
        ▼ (next FleetCoordinator.run for same feature)
load FLEET_STATE.json
        │
        ├─ phase in {done, escalated} ──► return immediately, nothing to recover
        │
        ├─ phase = planning|foundation|fleet|merging ──► resume from that phase
        │
        ▼
WorktreeManager.reconcile()
        │  git worktree prune
        │  remove any .pathly-worktrees/<feature>/* dirs not in git worktree list
        │
        ▼
continue from last known phase
```

---

## Component Legend

| Symbol / Component | Role in this feature |
|---|---|
| `FleetCoordinator` | Drives the phase loop; peers with supervisor via topic keys; writes FLEET_STATE.json |
| `WorktreeManager` | Git worktree CRUD + orphan reconciliation + footprint-violation tripwire |
| `overlap.decompose` | Pure set-math: classifies units into foundation vs parallel lanes |
| `integrate.flow.yaml` | FSM flow definition for the merge state machine (3 states + ESCALATED) |
| `integrator` agent | Runs the merge loop inside integrate.flow.yaml; never force-merges |
| `supervisor` (upstream) | Per-topic daemon run loop; called by coordinator via `supervisor_start_fn` |
| `FLEET_STATE.json` | Durable write-through mirror of FleetState; enables crash recovery |
| `EVENTS.jsonl` | Append-only event log; receives all FLEET_* and FOOTPRINT_VIOLATION events |
| `feedback/HUMAN_QUESTIONS.md` | Written on escalation; contains conflict context for human review |
