---
name: Conversation Guide
---
# Parallel Fleet Part 1 — Conversation Guide

Split into 4 conversations (strict order `1 → 2 → 3 → 4`). Each produces runnable, tested code.
After each conversation, **commit your changes** before starting the next.

**Upstream dependency:** `multi-adapter-runner` must be shipped first — `supervisor.py` and `adapters.py` must exist in `src/pathly_orchestrator/`. Verify this in Phase 0 of every conversation.

---

## Conversation 1: Crash-safe worktree lifecycle (Phases 0-1)

**Stories delivered:** S1

**Prompt to paste:**
```
Read pathly/plans/parallel-fleet-part-1/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Parallel Fleet Part 1 Conversation 1 (Phases 0-1) from pathly/plans/parallel-fleet-part-1/IMPLEMENTATION_PLAN.md.

Before editing anything: glob/read the live repo to confirm every path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding. Read CLAUDE.md, src/pathly_orchestrator/CLAUDE.md, and src/pathly_data/CLAUDE.md.

Phase 0 (pre-flight):
- Run `python -m pytest tests/ -q` and record the baseline pass count. If it fails, STOP and report — do not proceed with a broken baseline.
- Confirm `src/pathly_orchestrator/supervisor.py` exists (grep for `RunnerState`). If absent, STOP — this feature depends on multi-adapter-runner being shipped.
- Confirm `src/pathly_orchestrator/adapters.py` exists (grep for `resolve_command`). If absent, STOP.
- Confirm `.pathly-worktrees` is in `.gitignore`; if missing, add it.

Phase 1: Create `src/pathly_orchestrator/worktree.py` with:
- Exceptions: `WorktreeLaneError`, `WorktreeDirtyBaseError`, `FootprintViolationError`.
- `WorktreeManager(repo_root: Path)` with methods: `create`, `remove`, `reclaim`, `reconcile`, `check_footprint_violation`.
- Worktrees live at `<repo>/.pathly-worktrees/<feature>/<lane>/`; branches named `fleet/<feature>/<lane>`.
- `create` checks `git status --porcelain` before touching the filesystem; raises `WorktreeDirtyBaseError` if dirty.
- `create` raises `WorktreeLaneError` if worktree already exists AND is healthy (listed in `git worktree list`).
- `create` treats an existing directory NOT in `git worktree list` as stale and reclaims it.
- `remove` is idempotent: no-op if the directory is absent.
- `reconcile` calls `git worktree prune` (swallow errors, log them) then removes orphan directories.
- `check_footprint_violation`: gets `git diff --name-only HEAD` inside the lane's worktree; stray = actual - declared; emits `FOOTPRINT_VIOLATION` event to the feature's `EVENTS.jsonl`; raises `FootprintViolationError` only if stray overlaps another active lane's footprint.
- FOOTPRINT_VIOLATION event schema (exact fields): `{"type":"FOOTPRINT_VIOLATION","fleet_id":str,"feature":str,"lane":str,"stray_files":list,"overlapping_lane":str|null,"escalated":bool,"timestamp":str}`.

Create `tests/test_worktree.py` covering: create fresh, create duplicate raises error, remove idempotency, reconcile orphan, crash simulation (orphan dir without git registration), footprint violation with overlap (raises), footprint violation without overlap (returns True), dirty base raises before filesystem change.

Architectural rules:
- `worktree.py` does NOT import from `supervisor.py` or `fleet_coord.py`.
- Git operations use `subprocess.run(..., check=True)` within `repo_root`; never shell=True.
- The footprint-violation event is a soft-detect-with-tripwire — do NOT hard-block on stray files unless they overlap another active lane.

Do NOT touch: `http_server.py`, `supervisor.py`, `adapters.py`, or anything under `studio/` — those are out of scope.
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/parallel-fleet-part-1/PROGRESS.md phases 0-1 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `worktree.py` with full `WorktreeManager`, exceptions, and footprint-tripwire logic; `tests/test_worktree.py` all green; `.gitignore` updated.
**Files touched:** `src/pathly_orchestrator/worktree.py`, `tests/test_worktree.py`, `.gitignore`

---

## Conversation 2: Overlap-gated decomposition (Phases 0, 2)

**Stories delivered:** S2

**Prompt to paste:**
```
Read pathly/plans/parallel-fleet-part-1/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Parallel Fleet Part 1 Conversation 2 (Phases 0, 2) from pathly/plans/parallel-fleet-part-1/IMPLEMENTATION_PLAN.md. Conversation 1 (worktree.py) is complete.

Before editing anything: glob/read the live repo to confirm that `src/pathly_orchestrator/worktree.py` exists (from Conv 1) and that every new path below is correct.

Phase 0 (pre-flight): Run `python -m pytest tests/ -q`. If tests are not green, STOP and report.

Phase 2:

Create `src/pathly_orchestrator/overlap.py` with:
- Dataclasses: `LaneGroup(name, units, footprint)` and `FleetPlan(foundation_units, parallel_lanes, single_lane_mode, shared_files)`.
- `decompose(units: list[dict]) -> FleetPlan`:
  - `units` shape: `[{"name": str, "footprint": set[str]}]`.
  - Step 1: shared files = files in ≥ 2 units' footprints.
  - Step 2: foundation units = units touching ≥ 1 shared file.
  - Step 3: residual = units not in foundation.
  - Step 4: residual overlap graph (edge when two residual units share a file).
  - Step 5: connected components of residual graph = parallel lane groups.
  - Step 6: if foundation_units == all inputs → `single_lane_mode=True`, `parallel_lanes=[]`.
  - Step 7: unit with empty footprint → its own single-unit parallel lane.
- `write_fleet_plan(plan: FleetPlan, output_path: Path) -> None`:
  - Writes `fleet.yaml` with fields: `mode` (sequential|parallel), `foundation.units`, `lanes[].name`, `lanes[].units`, `lanes[].footprint`, `shared_files`.
  - `mode: sequential` when `single_lane_mode=True`.

Create `src/pathly_data/core/templates/plan/FLEET_PLAN.template.md` with:
- Frontmatter: `name: Fleet Plan`.
- Sections: `## Feature`, `## Mode`, `## Foundation Lane`, `## Parallel Lanes`, `## Shared Files`, `## Merge Order`.
- A fenced block documenting the `fleet.yaml` schema.

Create `tests/test_overlap.py` covering:
- Normal: 3 units, 2 share a file → 1 foundation unit, 2 parallel lanes.
- All-intersecting: all 3 units share files → `single_lane_mode=True`, `parallel_lanes==[]`.
- Single-unit: → 1 parallel lane, 0 foundation.
- Empty-footprint unit: placed in its own parallel lane.
- `write_fleet_plan` produces valid YAML with correct `mode` field.
- Sequential plan round-trips: `mode: sequential`.

Architectural rules:
- `overlap.py` is pure Python — no subprocess calls, no git, no filesystem side effects except `write_fleet_plan`.
- `decompose` must be deterministic: same input always produces the same `FleetPlan`.

Do NOT touch: `worktree.py`, `http_server.py`, `supervisor.py`, `adapters.py`, or anything under `studio/`.
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/parallel-fleet-part-1/PROGRESS.md phase 2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `overlap.py` with pure-Python decomposition; `FLEET_PLAN.template.md` in the core templates; `tests/test_overlap.py` all green.
**Files touched:** `src/pathly_orchestrator/overlap.py`, `src/pathly_data/core/templates/plan/FLEET_PLAN.template.md`, `tests/test_overlap.py`

---

## Conversation 3: Conservative merge agent (Phases 0, 3)

**Stories delivered:** S3

**Prompt to paste:**
```
Read pathly/plans/parallel-fleet-part-1/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Parallel Fleet Part 1 Conversation 3 (Phases 0, 3) from pathly/plans/parallel-fleet-part-1/IMPLEMENTATION_PLAN.md. Conversations 1-2 are complete.

Before editing anything: glob/read the live repo. Read `src/pathly_data/CLAUDE.md` carefully — the adapter sync rule means any new agent in `core/agents/` MUST get a `_meta/*.yaml` in all three adapters (claude, codex, copilot). Read an existing `_meta/reviewer.yaml` to confirm the schema.

Phase 0 (pre-flight): Run `python -m pytest tests/ -q`. If tests are not green, STOP and report.

Phase 3:

Create `src/pathly_data/core/flows/integrate.flow.yaml` — a flow with states MERGING, INTEGRATION_TESTING, DONE, ESCALATED; initial state MERGING; transitions: merge_clean (MERGING→INTEGRATION_TESTING), conflict_unresolvable (MERGING→ESCALATED), more_branches (INTEGRATION_TESTING→MERGING), all_merged_tests_pass (INTEGRATION_TESTING→DONE), tests_failed (INTEGRATION_TESTING→ESCALATED); agent: integrator.

Create `src/pathly_data/core/agents/quality/integrator.md` — the integrator role contract:
- Description: conservative merge agent; drives integrate.flow.yaml; never force-merges.
- Allowed tools: Read, Write, Bash (restricted to git merge --no-ff, git status, git diff, git log, and the project test runner).
- Explicitly prohibited: `git push --force`, `git merge --strategy=ours`, `git checkout --ours`.
- Decision logic: per-branch loop → clean merge → run tests → next branch; on conflict → one resolution attempt using both branches' plan context → re-test → still failing → write `feedback/HUMAN_QUESTIONS.md` → emit conflict_unresolvable.
- Cap: same branch conflicting twice → immediate escalation, no third attempt.
- Escalation contract: `HUMAN_QUESTIONS.md` must include conflicting diff, both branches' intent, and test output.
- Integration branch is created from foundation HEAD if it does not yet exist.

Create three adapter meta files with this exact content (field-identical, same schema as `reviewer.yaml`):
- `src/pathly_data/adapters/claude/_meta/integrator.yaml`
- `src/pathly_data/adapters/codex/_meta/integrator.yaml`
- `src/pathly_data/adapters/copilot/_meta/integrator.yaml`
Each must have: `name: integrator`, `description: ...`, `model: sonnet`, `tools: [Read, Write, Glob, Grep, Bash]`, `can_spawn: [quick]`.

Create `tests/test_integrate_flow.py` using a fake-conflict fixture (two temporary git branches in a temp repo):
- Clean-merge scenario: two branches with no overlapping changes → flow reaches DONE, no HUMAN_QUESTIONS.md.
- Semantic-conflict scenario: branches merge cleanly but combined test command returns non-zero → ESCALATED, HUMAN_QUESTIONS.md present, integration branch `git status` clean.
- Textual-conflict scenario: branches modify the same line → one resolution attempt; if still failing → ESCALATED, HUMAN_QUESTIONS.md present, no committed conflict markers.
- Force-merge guard: assert the test log contains none of: `--force`, `--strategy=ours`, `checkout --ours`.

Architectural rules:
- The integrator NEVER guesses a merge resolution; it either resolves with both branches' context or escalates.
- `integrate.flow.yaml` follows the same YAML schema as existing flows in `src/pathly_data/core/flows/`.
- Adapter sync rule: all three `_meta/integrator.yaml` files must be created — leaving one out is a test failure.

Do NOT touch: `http_server.py`, `supervisor.py`, `adapters.py`, `worktree.py`, `overlap.py`, or anything under `studio/`.
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/parallel-fleet-part-1/PROGRESS.md phase 3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `integrate.flow.yaml`, `integrator.md`, three `_meta/integrator.yaml` files, `tests/test_integrate_flow.py` all green — including the force-merge guard.
**Files touched:** `src/pathly_data/core/flows/integrate.flow.yaml`, `src/pathly_data/core/agents/quality/integrator.md`, `src/pathly_data/adapters/claude/_meta/integrator.yaml`, `src/pathly_data/adapters/codex/_meta/integrator.yaml`, `src/pathly_data/adapters/copilot/_meta/integrator.yaml`, `tests/test_integrate_flow.py`

---

## Conversation 4: Fleet coordinator (Phases 0, 4)

**Stories delivered:** S4

**Prompt to paste:**
```
Read pathly/plans/parallel-fleet-part-1/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Parallel Fleet Part 1 Conversation 4 (Phases 0, 4) from pathly/plans/parallel-fleet-part-1/IMPLEMENTATION_PLAN.md. Conversations 1-3 are complete (worktree.py, overlap.py, integrate.flow.yaml all exist).

Before editing anything: glob/read the live repo. Confirm all three upstream files exist: `src/pathly_orchestrator/worktree.py`, `src/pathly_orchestrator/overlap.py`, `src/pathly_orchestrator/supervisor.py`. If any are absent, STOP and report.

Phase 0 (pre-flight): Run `python -m pytest tests/ -q`. If tests are not green, STOP and report.

Phase 4: Create `src/pathly_orchestrator/fleet_coord.py` with:

FleetState dataclass (exact fields from FEATURE_INDEX.md):
- `fleet_id: str` (uuid4)
- `feature: str`
- `phase: str`  # planning|foundation|fleet|merging|done|escalated
- `lanes: list[dict]`  # {name, topic_key, worktree_path, status, footprint}
- `merge_order: list[str]`
- `integration_branch: str`
- `escalations: list[dict]`  # {lane, reason, file, timestamp}

Exceptions: `LaneIsolationError`, `FleetAlreadyRunningError`.

`FleetCoordinator(feature: str, repo_root: Path, supervisor_start_fn: Callable)`:
- `supervisor_start_fn` is injected (not imported from supervisor directly), enabling test stubbing.
- `run(units, base_commit, config)` phase loop:
  1. Load or init FleetState; write FLEET_STATE.json.
  2. planning → decompose(units) → write fleet.yaml.
  3. foundation → call supervisor_start_fn(topic_key="<feature>__foundation", project_root=<foundation_worktree>) → wait for status done|error. If error → escalated.
  4. fleet → assert lane isolation (raise LaneIsolationError if any two lanes share a file in footprint) → fan out all lanes via supervisor_start_fn.
  5. Poll until all lanes done or any error.
  6. merging → trigger integrate flow via fsm_http_client (or direct call, builder's choice).
  7. done or escalated based on result.
- Atomic write: FLEET_STATE.json written to a temp file then os.replace.
- Resume: if FLEET_STATE.json exists with phase not in {done, escalated}, resume from last known phase.
- FleetAlreadyRunningError: raised if FLEET_STATE.json exists with a different active fleet_id.
- Per-lane plan folder lives inside the lane's worktree: <worktree>/pathly/plans/<feature>__<lane>/. Assert this before spawning each lane.
- References lanes by topic key; does NOT embed RunnerState internals.

Emit these events to the feature's EVENTS.jsonl on phase transitions (exact schemas from FEATURE_INDEX.md):
- FLEET_PHASE_CHANGE on every phase advance.
- LANE_STARTED when each lane supervisor is called.
- LANE_DONE when each lane's status is polled as done|error|blocked.
- FLEET_DONE or FLEET_ESCALATED at terminal states.

Create `tests/test_fleet_coord.py` covering:
- Happy path: 2 units, disjoint footprints → decompose → foundation done → 2 parallel lanes done → integrate → phase=="done".
- Foundation-failure: foundation lane returns error → phase=="escalated", parallel lanes never started (assert supervisor_start_fn called exactly once).
- Lane isolation: two units share a file → LaneIsolationError before any supervisor call.
- Atomic write: use a mock that raises mid-write; assert FLEET_STATE.json not corrupted afterward.
- FleetAlreadyRunningError on double-start with same feature.
- After teardown (run completes): reconcile() called, git worktree list shows no fleet worktrees.

Also create `tests/test_fleet_e2e.py` with two toy-repo end-to-end tests:
- Happy path: real temp git repo, 2 units with disjoint footprints → full run → FLEET_STATE.json phase=="done", git worktree list clean.
- Forced-conflict path: real temp git repo, branches produce a merge conflict → integrate escalates → FLEET_STATE.json phase=="escalated", feedback/HUMAN_QUESTIONS.md present, integration branch git status clean, git worktree list clean.

Architectural rules:
- fleet_coord.py does NOT modify supervisor.py, adapters.py, or http_server.py.
- The coordinator is a peer, not a wrapper — it uses supervisor_start_fn as an injected dependency.
- HTTP control surface (starting/stopping fleets via REST) is part 2; do not add routes to http_server.py.
- The FSM stays sequential; parallelism is achieved by calling supervisor_start_fn N times in a loop, not by adding FSM fork/join states.

Do NOT touch: `http_server.py`, `supervisor.py`, `adapters.py`, or anything under `studio/` — those are out of scope.
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/parallel-fleet-part-1/PROGRESS.md phase 4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `fleet_coord.py` with `FleetState`, `FleetCoordinator`, and full phase loop; `tests/test_fleet_coord.py` all green; `tests/test_fleet_e2e.py` both end-to-end scenarios passing.
**Files touched:** `src/pathly_orchestrator/fleet_coord.py`, `tests/test_fleet_coord.py`, `tests/test_fleet_e2e.py`

---

## After Conversation 4 — hard CI gate

Before `parallel-fleet-part-2` begins, the following must be green:

```
python -m pytest tests/test_fleet_e2e.py -q
```

**Happy path scenario:** decompose → foundation lane → 2 disjoint lanes → clean merge → teardown — `FLEET_STATE.json` phase = `"done"`, `git worktree list` shows no `.pathly-worktrees/` entries.

**Forced-conflict scenario:** decompose → foundation lane → 2 lanes where the second produces a merge conflict → integrate escalates → `FLEET_STATE.json` phase = `"escalated"`, `feedback/HUMAN_QUESTIONS.md` present, integration branch `git status` clean, `git worktree list` shows no orphan worktrees.

Both scenarios must pass. This gate is the green light for `parallel-fleet-part-2` (the HTTP/SSE control surface for fleet management).
