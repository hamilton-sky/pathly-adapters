---
name: Architecture Proposal
---
# Parallel Fleet Part 1 — Architecture Proposal

## Problem Statement

Pathly's FSM runs feature flows sequentially — one stage at a time, one feature at a time. When a large feature contains multiple sub-units with disjoint file footprints, this serialization wastes wall time. The gap is a Python-layer coordinator that can partition work, run disjoint units in parallel git worktrees, and merge the results conservatively — while preserving all the safety properties (crash recovery, lane isolation, clean-or-escalate merging) that make autonomous runs trustworthy.

## Proposed Solution

A fleet of four Python modules that layer cleanly on top of the existing supervisor without modifying it:

1. `worktree.py` — git worktree lifecycle with crash recovery and footprint-violation tripwire.
2. `overlap.py` — pure set-math decomposition producing a `FleetPlan` (foundation lane + parallel lanes).
3. `integrate.flow.yaml` + `integrator.md` — a new flow and agent that merge lane branches conservatively.
4. `fleet_coord.py` — `FleetCoordinator` that drives the full cycle by calling the supervisor via injected topic keys.

## Layer Breakdown

```
Developer call
     │  FleetCoordinator.run(units, base_commit, config)
     ▼
fleet_coord.py       (peer of supervisor — does NOT modify it)
     │  decompose → worktree.create × N → supervisor_start_fn × N → integrate flow
     ├──────────────────────────────────────────────────────────────────────────
     │                              │                              │
overlap.py                   worktree.py                  supervisor.py (upstream)
(pure set-math)          (git worktree ops)             (RunnerState registry)
     │                              │                              │
FleetPlan                    git worktrees               FSM + agent subprocesses
fleet.yaml                .pathly-worktrees/              (unchanged)
                                    │
                         integrate.flow.yaml
                          + integrator agent
                         (merge state machine)
```

## Key Design Decisions

### Decision 1: Fleet coordinator is a peer, not a wrapper
- **Options considered**: (A) wrap the supervisor, overriding its run loop to support parallelism; (B) treat the coordinator as a peer that calls the supervisor via its public interface (topic keys + `project_root` param).
- **Chosen**: B
- **Rationale**: Zero supervisor changes. The supervisor's public surface is already a topic key + `project_root`; multiple concurrent supervisors for different topics is the existing design. Wrapping would require forking the supervisor's run loop and would couple part-1 and part-2 to internal supervisor details.

### Decision 2: FSM stays sequential; parallelism is at coordinator level
- **Options considered**: (A) add fork/join states to the FSM; (B) keep the FSM sequential and achieve parallelism by running N supervisors concurrently in the coordinator.
- **Chosen**: B
- **Rationale**: Fork/join in the FSM would require schema changes, new transition semantics, and would invalidate the existing flow YAML files. The coordinator approach achieves the same parallelism externally, with no FSM changes.

### Decision 3: Soft footprint tripwire (not hard block on stray files)
- **Options considered**: (A) hard-block on any stray file (any write outside declared footprint halts the lane); (B) soft-detect with escalation only on cross-lane overlap.
- **Chosen**: B
- **Rationale**: Agents legitimately write files adjacent to their declared scope (e.g. test fixtures, generated outputs). Hard-blocking on any stray write would cause frequent false-positive halts. The meaningful safety property is cross-lane overlap — two lanes writing the same file concurrently. Soft-detect preserves that property without over-blocking.

### Decision 4: Merge never force/guess
- **Options considered**: (A) attempt multiple resolution strategies including force; (B) one resolution attempt, then escalate.
- **Chosen**: B
- **Rationale**: A committed bad merge is worse than a halted run. The integrator agent has context from both branches' plan files; it attempts one resolution. If that fails, the correct action is to surface the conflict to a human with full context — not to guess or force.

### Decision 5: Degrade to sequential rather than fail
- **Options considered**: (A) raise an error when all footprints intersect (no parallelism possible); (B) degrade gracefully to a single-lane sequential run.
- **Chosen**: B
- **Rationale**: A fully intersecting decomposition is a valid outcome for some features — all work must be serialized. Raising an error would require the caller to handle this case explicitly. Degrading to sequential lets the feature complete normally without special-casing at the coordinator level.

## Key Components

| Module | New/Existing | Description |
|--------|-------------|-------------|
| `src/pathly_orchestrator/worktree.py` | NEW | `WorktreeManager`: create/remove/reclaim/reconcile + footprint-violation tripwire |
| `src/pathly_orchestrator/overlap.py` | NEW | `decompose()` + `FleetPlan` + `write_fleet_plan()`: pure set-math decomposition |
| `src/pathly_data/core/flows/integrate.flow.yaml` | NEW | MERGING→INTEGRATION_TESTING→DONE|ESCALATED flow definition |
| `src/pathly_data/core/agents/quality/integrator.md` | NEW | Integrator agent role contract |
| `src/pathly_data/adapters/{claude,codex,copilot}/_meta/integrator.yaml` | NEW | Adapter meta for integrator (3 files) |
| `src/pathly_orchestrator/fleet_coord.py` | NEW | `FleetState` + `FleetCoordinator` phase loop |
| `src/pathly_data/core/templates/plan/FLEET_PLAN.template.md` | NEW | Fleet plan template added to core template library |
| `src/pathly_orchestrator/supervisor.py` | UPSTREAM — DO NOT MODIFY | Provides `RunnerState` registry and per-topic run loop |
| `src/pathly_orchestrator/adapters.py` | UPSTREAM — DO NOT MODIFY | Provides `resolve_command()` |

## Interface Design

```python
# worktree.py
class WorktreeManager:
    def create(feature: str, lane: str, base_commit: str) -> Path
    def remove(feature: str, lane: str) -> None
    def reclaim(feature: str, lane: str, base_commit: str) -> Path
    def reconcile() -> list[Path]
    def check_footprint_violation(lane: str, declared: set[str], active_lanes: dict[str, set[str]]) -> bool

# overlap.py
def decompose(units: list[dict]) -> FleetPlan
def write_fleet_plan(plan: FleetPlan, output_path: Path) -> None

# fleet_coord.py
class FleetCoordinator:
    def run(units: list[dict], base_commit: str, config: dict) -> FleetState
```

## Risks

| Risk | Mitigation |
|------|-----------|
| Crash-safe idempotent teardown | `reconcile()` called on every startup and teardown; `create` detects stale/orphan worktrees; EC-1 |
| Merge never force/guess | Integrator role contract explicitly prohibits force commands; test guard asserts log contains none; EC-2 |
| Degrade-to-sequential | `decompose` returns `single_lane_mode=True`; coordinator branches on it; EC-3 |
| Real lane isolation | Fan-out assertion before supervisor calls; runtime footprint tripwire; EC-4 |
| CI gate before part 2 | `test_fleet_e2e.py` both scenarios must be green before part-2 begins; EC-5 |
