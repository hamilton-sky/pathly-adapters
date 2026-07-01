---
name: Progress
---
# Parallel Fleet Part 1 — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | Crash-safe worktree lifecycle | Conv 1 | TODO |
| S2 | Overlap-gated decomposition | Conv 2 | TODO |
| S3 | Conservative merge agent | Conv 3 | TODO |
| S4 | Fleet coordinator | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | Phase 0 (pre-flight) + Phase 1 (worktree) | S1 | TODO | `python -m pytest tests/ -q` |
| 2 | Phase 0 (pre-flight) + Phase 2 (overlap) | S2 | TODO | `python -m pytest tests/ -q` |
| 3 | Phase 0 (pre-flight) + Phase 3 (integrate) | S3 | TODO | `python -m pytest tests/ -q` |
| 4 | Phase 0 (pre-flight) + Phase 4 (coordinator) | S4 | TODO | `python -m pytest tests/ -q` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| all | Phase 0 | `tests/` (read-only) | Pre-flight: baseline pytest, confirm supervisor.py + adapters.py exist | `pytest` exits 0, both upstream files confirmed | TODO |
| 1 | Phase 1 | `src/pathly_orchestrator/worktree.py` | Create WorktreeManager: create/remove/reclaim/reconcile + footprint tripwire | `test_worktree.py` passes; orphan reconcile test passes | TODO |
| 1 | Phase 1 | `tests/test_worktree.py` | Unit tests for full worktree lifecycle including crash/orphan scenarios | All tests green | TODO |
| 2 | Phase 2 | `src/pathly_orchestrator/overlap.py` | decompose() + FleetPlan + write_fleet_plan() + degrade-to-sequential | `test_overlap.py` passes; all-intersect returns single_lane_mode=True | TODO |
| 2 | Phase 2 | `src/pathly_data/core/templates/plan/FLEET_PLAN.template.md` | Fleet plan template added to core template library | File exists with correct schema sections | TODO |
| 2 | Phase 2 | `tests/test_overlap.py` | Unit tests for decomposition including edge cases | All tests green | TODO |
| 3 | Phase 3 | `src/pathly_data/core/flows/integrate.flow.yaml` | Integrate flow: MERGING→INTEGRATION_TESTING→DONE, escalation path | Flow YAML valid; integrator agent drives states correctly | TODO |
| 3 | Phase 3 | `src/pathly_data/core/agents/quality/integrator.md` | Integrator agent role contract | File exists with correct tools/prohibitions | TODO |
| 3 | Phase 3 | `src/pathly_data/adapters/claude/_meta/integrator.yaml` | Claude adapter meta | File exists with name/model/tools/can_spawn | TODO |
| 3 | Phase 3 | `src/pathly_data/adapters/codex/_meta/integrator.yaml` | Codex adapter meta | File exists with name/model/tools/can_spawn | TODO |
| 3 | Phase 3 | `src/pathly_data/adapters/copilot/_meta/integrator.yaml` | Copilot adapter meta | File exists with name/model/tools/can_spawn | TODO |
| 3 | Phase 3 | `tests/test_integrate_flow.py` | Fake-conflict fixture: clean + semantic + textual conflict paths | All three fixture scenarios pass; no force-merge in bash log | TODO |
| 4 | Phase 4 | `src/pathly_orchestrator/fleet_coord.py` | FleetState + FLEET_STATE.json + phase loop driving supervisors by topic key | Happy-path + forced-conflict tests pass; no orphan worktrees after teardown | TODO |
| 4 | Phase 4 | `tests/test_fleet_coord.py` | Unit tests for FleetCoordinator lifecycle | All tests green including atomic write and double-start guard | TODO |
| CI | E2E gate | `tests/test_fleet_e2e.py` | Toy-repo end-to-end: happy path + forced-conflict path | Both scenarios pass under `pytest tests/test_fleet_e2e.py -q` | TODO |

## Prerequisites
- `multi-adapter-runner` shipped: `supervisor.py` + `adapters.py` in `src/pathly_orchestrator/`
- `python -m pytest tests/ -q` passes at baseline before Conv 1

## Blocked By
- `multi-adapter-runner` — `supervisor.py` must exist before Conv 4; `adapters.py` must exist before Conv 1 pre-flight can confirm it
