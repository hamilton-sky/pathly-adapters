---
name: Feature Index
---
# Parallel Fleet Part 1 — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What this feature does

Adds the **Python mechanics for running multiple feature-flows in parallel git worktrees** with a conservative merge agent. Four pieces:

1. **`worktree.py`** — crash-safe, idempotent lifecycle for per-lane git worktrees: create, reclaim, remove, reconcile/prune orphans, and footprint-violation tripwire detection.
2. **`overlap.py`** + `fleet.yaml` / `FLEET_PLAN.md` template — pure set-math decomposition that partitions a feature's sub-units into a foundation lane and disjoint parallel lanes; degrades to a single-lane sequential run when footprints all intersect.
3. **`core/flows/integrate.flow.yaml`** + `core/agents/quality/integrator.md` — a sequential merge state machine (`MERGING → INTEGRATION_TESTING → DONE`) that never force-merges or guesses; escalates both semantic and textual conflicts to `feedback/HUMAN_QUESTIONS.md`.
4. **`fleet_coord.py`** — `FleetState` + `FLEET_STATE.json` write-through mirror; phase loop (`planning → foundation → fleet → merging → done | escalated`) that drives lanes by topic key via the existing supervisor.

This is **part 1 of 2**. The HTTP control and SSE surface for the fleet are planned separately as `parallel-fleet-part-2`.

## Dependency

**Requires `multi-adapter-runner` shipped** — that feature provides:
- `src/pathly_orchestrator/supervisor.py` — `RunnerState` registry keyed by topic, per-topic daemon run loop, `/runner/start` etc.
- `src/pathly_data/core/adapters.yaml` + `src/pathly_orchestrator/adapters.py` — `resolve_command()`.

Do NOT modify `supervisor.py` or `adapters.py` in this feature.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Fleet topology, worktree layout, merge state machine, coordinator shape |
| `EDGE_CASES.md` | yes | Five architect risks with failure modes and mitigations |
| `HAPPY_FLOW.md` | yes | Golden-path narrative: decompose → foundation → 2 lanes → clean merge → done |
| `FLOW_DIAGRAM.md` | yes | ASCII component interaction across all four modules |

---

## Codebase touchpoints

**Verify these paths exist before editing. Glob each one. If a path is wrong, correct it before proceeding.**

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/worktree.py` (NEW) | Conv 1 | Worktree lifecycle: create, remove, reclaim, reconcile/prune, footprint-violation tripwire |
| `tests/test_worktree.py` (NEW) | Conv 1 | Unit tests: create, reclaim, orphan prune, crash-safe teardown, footprint-overlap tripwire |
| `src/pathly_orchestrator/overlap.py` (NEW) | Conv 2 | Footprint set-math: shared-files → foundation, disjoint residual → parallel lanes, degrade-to-sequential |
| `src/pathly_data/core/templates/plan/FLEET_PLAN.template.md` (NEW) | Conv 2 | Fleet plan template added to core template library |
| `tests/test_overlap.py` (NEW) | Conv 2 | Unit tests: normal decomposition, all-intersect single-lane degrade, empty-footprint lanes |
| `src/pathly_data/core/flows/integrate.flow.yaml` (NEW) | Conv 3 | Flow YAML: MERGING → INTEGRATION_TESTING → DONE, loop-on-conflict cap, escalation path |
| `src/pathly_data/core/agents/quality/integrator.md` (NEW) | Conv 3 | Integrator agent role contract |
| `src/pathly_data/adapters/claude/_meta/integrator.yaml` (NEW) | Conv 3 | Claude adapter meta for integrator |
| `src/pathly_data/adapters/codex/_meta/integrator.yaml` (NEW) | Conv 3 | Codex adapter meta for integrator |
| `src/pathly_data/adapters/copilot/_meta/integrator.yaml` (NEW) | Conv 3 | Copilot adapter meta for integrator |
| `tests/test_integrate_flow.py` (NEW) | Conv 3 | Fake-conflict fixture: clean merge, semantic conflict escalation, textual conflict escalation |
| `src/pathly_orchestrator/fleet_coord.py` (NEW) | Conv 4 | FleetState dataclass + FLEET_STATE.json mirror + phase loop (planning→foundation→fleet→merging→done) |
| `tests/test_fleet_coord.py` (NEW) | Conv 4 | Unit tests: FleetState transitions, lane isolation assertion, DONE path, escalation path |

---

## Fleet event schema (new event types — exact fields)

These events are emitted by `fleet_coord.py` to the feature's `EVENTS.jsonl` log.

```jsonl
{"type":"FLEET_PHASE_CHANGE","fleet_id":str,"feature":str,"phase":str,"timestamp":str}
{"type":"LANE_STARTED","fleet_id":str,"feature":str,"lane":str,"topic_key":str,"worktree_path":str,"timestamp":str}
{"type":"LANE_DONE","fleet_id":str,"feature":str,"lane":str,"status":"done"|"error"|"blocked","timestamp":str}
{"type":"FOOTPRINT_VIOLATION","fleet_id":str,"feature":str,"lane":str,"stray_files":list,"overlapping_lane":str|null,"escalated":bool,"timestamp":str}
{"type":"MERGE_CONFLICT","fleet_id":str,"feature":str,"branch":str,"kind":"textual"|"semantic","escalated":bool,"timestamp":str}
{"type":"FLEET_DONE","fleet_id":str,"feature":str,"integration_branch":str,"timestamp":str}
{"type":"FLEET_ESCALATED","fleet_id":str,"feature":str,"reason":str,"question_file":str,"timestamp":str}
```

---

## Worktree layout

```
<repo>/.pathly-worktrees/
  <feature>/
    foundation/          # branch: fleet/<feature>/foundation
    lane-<N>/            # branch: fleet/<feature>/lane-<N>
```

The `.pathly-worktrees/` directory must be in `.gitignore`.
Phase-2 lanes branch off the post-foundation integration commit (not `main`).

---

## FleetState shape

```python
@dataclass
class FleetState:
    fleet_id: str            # uuid4
    feature: str             # e.g. "my-feature"
    phase: str               # planning|foundation|fleet|merging|done|escalated
    lanes: list[dict]        # [{name, topic_key, worktree_path, status, footprint}]
    merge_order: list[str]   # branch names in merge sequence
    integration_branch: str  # e.g. "fleet/<feature>/integration"
    escalations: list[dict]  # [{lane, reason, file, timestamp}]
```

`FLEET_STATE.json` is written through on every state mutation (same pattern as `RUNNER_STATE.json` in `supervisor.py`).

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Crash-safe worktree lifecycle | S1 | TODO | `worktree.py`, `tests/test_worktree.py` |
| 2 | Overlap-gated decomposition | S2 | TODO | `overlap.py`, `FLEET_PLAN.template.md`, `tests/test_overlap.py` |
| 3 | Conservative merge agent | S3 | TODO | `integrate.flow.yaml`, `integrator.md`, `_meta/integrator.yaml` (×3), `tests/test_integrate_flow.py` |
| 4 | Fleet coordinator | S4 | TODO | `fleet_coord.py`, `tests/test_fleet_coord.py` |

**Dependency:** `1 → 2 → 3 → 4` (strict). A hard CI gate follows Conv 4 — see IMPLEMENTATION_PLAN.md.

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/parallel-fleet-part-1/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
