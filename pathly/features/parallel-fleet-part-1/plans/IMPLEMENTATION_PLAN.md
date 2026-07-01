---
name: Implementation Plan
---
# Parallel Fleet Part 1 — Implementation Plan

## Overview

Adds the Python mechanics for running multiple feature-flows in parallel git worktrees. Four sequential conversations deliver: a crash-safe worktree lifecycle module, a pure-set-math decomposition algorithm, a conservative merge flow with escalation, and a coordinator that drives the full fleet lifecycle by reusing the existing supervisor. The HTTP/SSE control surface is out of scope (part 2).

## Layer Architecture

```
Plans (IMPLEMENTATION_PLAN.md)   →   Fleet modules (Python)   →   Supervisor (upstream)
          |                                   |                           |
  pathly/plans/<feature>/          worktree.py                  supervisor.py (DO NOT MODIFY)
  FLEET_STATE.json                 overlap.py                   topic key: <feature>__<lane>
  FLEET_PLAN.md                    fleet_coord.py               project_root = worktree path
                                        |
                             integrate.flow.yaml
                             integrator.md (agent)
```

---

## Phase 0: Pre-flight   ← Conversation: ALL (run first in every conversation)

**File:** `tests/` — read-only baseline
**Done when:** `python -m pytest tests/ -q` exits 0 with no failures.
**Delivers stories:** (gate, not a story)
**Depends on:** `multi-adapter-runner` shipped (`supervisor.py` and `adapters.py` must exist)
**Enables:** All subsequent phases
**Details:**
- Run `python -m pytest tests/ -q` and record the baseline pass count.
- Confirm `src/pathly_orchestrator/supervisor.py` exists (grep for `RunnerState`).
- Confirm `src/pathly_orchestrator/adapters.py` exists (grep for `resolve_command`).
- If either dependency is absent, STOP and report — this feature cannot proceed without `multi-adapter-runner`.
- Confirm `.pathly-worktrees` is in `.gitignore`; if not, add it.
**Verify:** `python -m pytest tests/ -q`

---

## Phase 1: Crash-safe worktree lifecycle   ← Conversation: 1

**File:** `src/pathly_orchestrator/worktree.py` — CREATE
**Done when:** `python -m pytest tests/test_worktree.py -q` exits 0; `git worktree list` contains no `.pathly-worktrees/` entry after `reconcile()` is called on an orphan fixture.
**Delivers stories:** S1
**Depends on:** Phase 0 (pre-flight)
**Enables:** Phase 2 (overlap.py needs worktree paths to write `FLEET_PLAN.md`)
**Details:**

Classes and exceptions:
- `WorktreeLaneError(Exception)` — raised when create is called on a healthy existing worktree.
- `WorktreeDirtyBaseError(Exception)` — raised when the base working tree has uncommitted changes.
- `FootprintViolationError(Exception)` — raised (after event emission) when a stray file overlaps another lane's footprint.

`WorktreeManager(repo_root: Path)`:
- `WORKTREE_BASE = repo_root / ".pathly-worktrees"`
- `create(feature: str, lane: str, base_commit: str) -> Path`
  - Check `git status --porcelain` on `repo_root`; if dirty, raise `WorktreeDirtyBaseError`.
  - Path = `WORKTREE_BASE / feature / lane`.
  - If path exists and is registered in `git worktree list` → raise `WorktreeLaneError`.
  - If path exists but NOT in `git worktree list` → treat as stale, call `remove` first.
  - Run `git worktree add <path> -b fleet/<feature>/<lane> <base_commit>`.
  - On `subprocess.CalledProcessError`: set lane status = `"error"`, re-raise as `WorktreeLaneError`.
  - Return the created path.
- `remove(feature: str, lane: str) -> None`
  - Idempotent: if path does not exist, return immediately.
  - Run `git worktree remove --force <path>`, then `git branch -D fleet/<feature>/<lane>` (ignore error if branch absent).
- `reclaim(feature: str, lane: str, base_commit: str) -> Path`
  - Call `remove` then `create`.
- `reconcile() -> list[Path]`
  - Call `git worktree prune` (swallow errors, log them).
  - Walk `WORKTREE_BASE`; for each subdirectory not in `git worktree list` output, call `remove`.
  - Return list of removed paths.
- `check_footprint_violation(lane: str, declared_footprint: set[str], active_lanes: dict[str, set[str]]) -> bool`
  - Get actual changed files in the lane's worktree: `git diff --name-only HEAD` relative to the lane's worktree.
  - Stray files = actual - declared.
  - If stray is empty: return False.
  - Overlapping lane = first lane in `active_lanes` whose footprint intersects stray; `None` if none.
  - Emit `FOOTPRINT_VIOLATION` event (write to feature's `EVENTS.jsonl`).
  - If overlapping lane is not None: raise `FootprintViolationError`.
  - Return True (stray detected but no cross-lane overlap — soft tripwire, execution continues).

Tests (`tests/test_worktree.py`) must cover:
- `create` on a fresh repo → worktree path exists, branch exists.
- `create` on an existing healthy worktree → raises `WorktreeLaneError`.
- `remove` idempotency: calling `remove` twice does not raise.
- `reconcile` on an orphan directory → directory removed, `git worktree list` clean.
- Crash simulation: manually create a `.pathly-worktrees/<feature>/orphan/` dir without registering it; `reconcile()` removes it.
- Footprint violation with overlap → `FootprintViolationError` raised, event written.
- Footprint violation without overlap → returns True, no exception.
- Dirty base commit → `WorktreeDirtyBaseError` before any filesystem change.

**Verify:** `python -m pytest tests/ -q`

---

## Phase 2: Overlap-gated decomposition   ← Conversation: 2

**File:** `src/pathly_orchestrator/overlap.py` — CREATE
**File:** `src/pathly_data/core/templates/plan/FLEET_PLAN.template.md` — CREATE
**Done when:** `python -m pytest tests/test_overlap.py -q` exits 0; `decompose` of an all-intersecting input returns `single_lane_mode: True`; `write_fleet_plan` produces a valid YAML file.
**Delivers stories:** S2
**Depends on:** Phase 1 (worktree.py for path constants)
**Enables:** Phase 3 (fleet coordinator uses FleetPlan to create lanes)
**Details:**

Data types:
```python
@dataclass
class LaneGroup:
    name: str               # e.g. "lane-0"
    units: list[str]        # unit names in this group
    footprint: set[str]     # union of all units' footprints

@dataclass
class FleetPlan:
    foundation_units: list[str]
    parallel_lanes: list[LaneGroup]
    single_lane_mode: bool
    shared_files: set[str]
```

`decompose(units: list[dict]) -> FleetPlan`:
- `units` shape: `[{"name": str, "footprint": set[str]}]`.
- Step 1: find shared files = files appearing in ≥ 2 units' footprints.
- Step 2: foundation units = all units that touch ≥ 1 shared file.
- Step 3: residual units = units not in foundation.
- Step 4: build residual overlap graph (edge between units sharing a file in the residual).
- Step 5: connected components of residual graph = parallel lane groups.
- Step 6: if foundation_units == all input units → `single_lane_mode = True`, `parallel_lanes = []`.
- Step 7: a unit with empty footprint → placed in its own single-unit lane group.

`write_fleet_plan(plan: FleetPlan, output_path: Path) -> None`:
- Writes a `fleet.yaml` file. Schema:
  ```yaml
  mode: sequential | parallel
  foundation:
    units: [...]
  lanes:
    - name: lane-0
      units: [...]
      footprint: [...]
  shared_files: [...]
  ```
- `mode: sequential` when `single_lane_mode` is True, `mode: parallel` otherwise.

`FLEET_PLAN.template.md` — added to `src/pathly_data/core/templates/plan/`:
- Header with frontmatter `name: Fleet Plan`.
- Sections: `## Feature`, `## Mode`, `## Foundation Lane`, `## Parallel Lanes`, `## Shared Files`, `## Merge Order`.
- Documents the `fleet.yaml` schema in a fenced block.

Tests (`tests/test_overlap.py`) must cover:
- Normal decomposition: 3 units, 2 share a file → 1 foundation unit, 2 parallel units.
- All-intersecting: all 3 units share files → `single_lane_mode: True`, `parallel_lanes == []`.
- Single-unit input: → `single_lane_mode: False`, 1 parallel lane, 0 foundation units.
- Empty-footprint unit: placed in its own parallel lane.
- `write_fleet_plan` output is valid YAML with correct `mode` field.
- Sequential plan (`single_lane_mode: True`) round-trips: `mode: sequential`.

**Verify:** `python -m pytest tests/ -q`

---

## Phase 3: Conservative merge agent   ← Conversation: 3

**File:** `src/pathly_data/core/flows/integrate.flow.yaml` — CREATE
**File:** `src/pathly_data/core/agents/quality/integrator.md` — CREATE
**File:** `src/pathly_data/adapters/claude/_meta/integrator.yaml` — CREATE
**File:** `src/pathly_data/adapters/codex/_meta/integrator.yaml` — CREATE
**File:** `src/pathly_data/adapters/copilot/_meta/integrator.yaml` — CREATE
**Done when:** `python -m pytest tests/test_integrate_flow.py -q` exits 0; both a clean-merge fixture and a forced-conflict fixture pass; the forced-conflict fixture leaves `feedback/HUMAN_QUESTIONS.md` present and the integration branch in a clean `git status`.
**Delivers stories:** S3
**Depends on:** Phase 2 (FleetPlan provides `merge_order`)
**Enables:** Phase 4 (fleet coordinator triggers integrate flow when all lanes are DONE)
**Details:**

`integrate.flow.yaml`:
```yaml
id: integrate
states:
  - MERGING
  - INTEGRATION_TESTING
  - DONE
  - ESCALATED
initial: MERGING
transitions:
  - from: MERGING
    to: INTEGRATION_TESTING
    on: merge_clean
  - from: MERGING
    to: ESCALATED
    on: conflict_unresolvable
  - from: INTEGRATION_TESTING
    to: MERGING
    on: more_branches
  - from: INTEGRATION_TESTING
    to: DONE
    on: all_merged_tests_pass
  - from: INTEGRATION_TESTING
    to: ESCALATED
    on: tests_failed
agent: integrator
```

`integrator.md` role contract (in `core/agents/quality/`):
- Description: conservative merge agent; never force-merges; escalates both textual and semantic conflicts.
- Tools allowed: Read, Write, Bash (restricted to `git merge --no-ff`, `git status`, `git diff`, `git log`, test runner — never `git push --force`, never `git merge --strategy=ours`).
- Decision logic: per-branch loop → clean merge → tests → next branch; conflict → one resolution attempt → re-test → still failing → write `feedback/HUMAN_QUESTIONS.md` → emit `conflict_unresolvable`.
- Cap rule: same branch conflicting twice → immediate escalation.
- Escalation contract: `HUMAN_QUESTIONS.md` must include the conflicting diff, both branches' intent (from their plan context), and the test output.

Three adapter `_meta/integrator.yaml` files (same structure as `reviewer.yaml`):
```yaml
name: integrator
description: Conservative merge agent — merges lane branches sequentially, never force-merges, escalates unresolvable conflicts.
model: sonnet
tools: [Read, Write, Glob, Grep, Bash]
can_spawn: [quick]
```

Tests (`tests/test_integrate_flow.py`) via fake-conflict fixture:
- Clean merge path: two branches with no overlapping changes → flow reaches `DONE`, no `HUMAN_QUESTIONS.md`.
- Semantic conflict: branches merge cleanly but combined tests fail → `ESCALATED`, `HUMAN_QUESTIONS.md` present, integration branch `git status` clean.
- Textual conflict: branches produce conflict markers → one resolution attempt; if that also fails → `ESCALATED`, `HUMAN_QUESTIONS.md` present, no committed conflict markers.
- Force-merge guard: assert the fixture's bash log contains no `--force` or `--strategy=ours` invocation.

**Verify:** `python -m pytest tests/ -q`

---

## Phase 4: Fleet coordinator   ← Conversation: 4

**File:** `src/pathly_orchestrator/fleet_coord.py` — CREATE
**Done when:** `python -m pytest tests/test_fleet_coord.py -q` exits 0; the happy-path test runs decompose → foundation lane → 2 parallel lanes → integrate → DONE; the forced-conflict test escalates and leaves `FLEET_STATE.json` with `phase: "escalated"` and no orphan worktrees.
**Delivers stories:** S4
**Depends on:** Phases 1–3 (worktree.py, overlap.py, integrate.flow.yaml, supervisor.py from upstream)
**Enables:** End-to-end CI gate (see below); `parallel-fleet-part-2` (HTTP control surface)
**Details:**

`FleetState` dataclass (exact shape from FEATURE_INDEX.md):
```python
@dataclass
class FleetState:
    fleet_id: str
    feature: str
    phase: str            # planning|foundation|fleet|merging|done|escalated
    lanes: list[dict]     # {name, topic_key, worktree_path, status, footprint}
    merge_order: list[str]
    integration_branch: str
    escalations: list[dict]  # {lane, reason, file, timestamp}
```

`FleetCoordinator(feature: str, repo_root: Path, supervisor_start_fn: Callable)`:
- `supervisor_start_fn` is injected (not imported directly) so tests can stub it.
- `run(units, base_commit, config)`:
  1. Load or initialize `FleetState`; write `FLEET_STATE.json`.
  2. `planning` → `decompose(units)` → produce `FleetPlan` → `write_fleet_plan`.
  3. `foundation` → start foundation lane via `supervisor_start_fn(topic_key="<feature>__foundation", project_root=<foundation_worktree>)` → wait for status `"done"` or `"error"`.
  4. `fleet` → assert lane isolation (raise `LaneIsolationError` on footprint overlap) → fan out: for each parallel lane, `supervisor_start_fn(topic_key=..., project_root=...)`.
  5. Poll lane statuses; on all `"done"` → advance to `merging`.
  6. `merging` → trigger `integrate.flow.yaml` (via fsm_http_client or direct call) with `merge_order`.
  7. `done` or `escalated` based on integrate flow outcome.
- Atomic write: `FLEET_STATE.json` written to temp file then `os.replace` (same pattern as `supervisor.py`).
- Resume: on startup, if `FLEET_STATE.json` exists with `phase` not in `{"done", "escalated"}`, resume from that phase.
- `FleetAlreadyRunningError`: raised if `FLEET_STATE.json` exists with an active `fleet_id` different from the caller's.

Tests (`tests/test_fleet_coord.py`) must cover:
- Happy path: 2 units with disjoint footprints → foundation lane + 2 parallel lanes → all DONE → integrate → `phase == "done"`.
- Foundation-failure path: foundation lane returns `"error"` → `phase == "escalated"`, parallel lanes never started.
- Lane isolation assertion: two units sharing a file → `LaneIsolationError` before any supervisor call.
- `FLEET_STATE.json` atomic write: simulate crash mid-write → file not corrupted.
- `FleetAlreadyRunningError` on double-start.
- `reconcile()` called on teardown → no orphan worktrees remain.

**Verify:** `python -m pytest tests/ -q`

---

## End-to-end CI gate (after Conv 4 — before parallel-fleet-part-2)

A toy-repo end-to-end must be green:

**Happy path:** decompose → foundation lane → 2 lanes with disjoint footprints → clean merge → teardown — `FLEET_STATE.json` phase = `"done"`, `git worktree list` shows no `.pathly-worktrees/` entries.

**Forced-conflict path:** decompose → foundation lane → 2 lanes where the second produces a merge conflict → integrate escalates → `FLEET_STATE.json` phase = `"escalated"`, `feedback/HUMAN_QUESTIONS.md` present, integration branch `git status` clean, `git worktree list` shows no orphan worktrees.

Both tests must be in `tests/test_fleet_e2e.py` and pass under `python -m pytest tests/test_fleet_e2e.py -q`. This gate is the green light for `parallel-fleet-part-2`.

---

## Prerequisites
- `multi-adapter-runner` fully shipped: `supervisor.py` (with `RunnerState` and supervisor start function), `adapters.py` (with `resolve_command`) both present in `src/pathly_orchestrator/`.
- `python -m pytest tests/ -q` passes at baseline before Conv 1 begins.
- `.pathly-worktrees/` is in `.gitignore`.

## Key Decisions
- **Fleet coordinator is a peer of supervisor, not a wrapper.** Lanes are namespaced topics `<feature>__<lane>`; the coordinator calls the supervisor's public interface. Zero supervisor changes.
- **FSM stays sequential.** Parallelism lives only in the coordinator running N supervisors concurrently. No fork/join in the FSM, no nested FSM states.
- **Soft footprint tripwire, not hard block.** Stray files that don't overlap another lane's footprint emit a warning event and execution continues. Only cross-lane overlaps halt the lane.
- **Merge never force/guess.** The integrator agent is explicitly prohibited from `git push --force`, `git merge --strategy=ours`, and `git checkout --ours`. Any such invocation is a test failure.
- **Degrade-to-sequential.** When all footprints intersect, the fleet runs as a single supervised flow rather than deadlocking on an empty parallel set.
