# Enforcement Gates — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions — gate engine insertion point |
| `EDGE_CASES.md` | yes | Failure modes: diff baseline, sentinel robustness, silent skips |
| `HAPPY_FLOW.md` | yes | Golden-path narrative through a gated transition |
| `FLOW_DIAGRAM.md` | yes | ASCII diagram of complete_stage with gate checkpoint |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/fsm.py` | Conv 1 | Add `run_gates()` with `require_artifact` + `verify_gate` primitives; `GATE_FAILED` event helper |
| `src/pathly_orchestrator/fsm.py` | Conv 2 | Add `scope_gate` primitive; `GATE_SKIPPED` event; harden `verify_gate` to line-1 sentinel |
| `src/pathly_orchestrator/fsm_ops.py` | Conv 1 | Wire `run_gates()` into `complete_stage` between steps 4 and 5 |
| `src/pathly_data/core/flows/team.flow.yaml` | Conv 1 | Add `gates:` section with `verify_gate` on `BUILDING->REVIEWING` and `require_artifact` on `REVIEWING->TESTING` |
| `src/pathly_data/core/flows/team.flow.yaml` | Conv 2 | Add `scope_gate` to `BUILDING->REVIEWING` |
| `tests/test_gates.py` | Conv 1 | NEW — unit tests for `require_artifact`, `verify_gate`, `complete_stage` gate blocking |
| `tests/test_gates.py` | Conv 2 | Extend — `scope_gate` tests, `GATE_SKIPPED`, end-to-end advance-after-resolve |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Core gate engine | S1, S2, S4, S5 | TODO | `fsm.py`, `fsm_ops.py`, `team.flow.yaml`, `tests/test_gates.py` |
| 2 | scope_gate + hardening | S3, S4 (scope path) | TODO | `fsm.py`, `team.flow.yaml`, `tests/test_gates.py` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/enforcement-gates/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
