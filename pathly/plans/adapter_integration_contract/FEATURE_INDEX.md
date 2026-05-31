---
name: Feature Index
---
# Adapter Integration Contract — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file - single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria - the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design - the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts - one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status - the checkpoint |
| `HAPPY_FLOW.md` | Planner | Builder, Reviewer | Golden path and happy-path expectations |
| `EDGE_CASES.md` | Planner | Builder, Tester | Failure modes, retries, and edge behavior |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Builder, Architect | Contract-shape and layering decisions |
| `FLOW_DIAGRAM.md` | Planner | Builder | ASCII contract / flow diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

> **Note:** The response envelope fields (`schema_version`, `decision`, `agent_hint`, `stage_brief`, etc.) are **already present** in `fsm_ops.py`. The changes below are targeted corrections — not a rewrite.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/fsm_ops.py` | Conv 1 | (1) Rename `agent_hint` inner keys to adapter-neutral (`agent`, `role` instead of `pathly_agent`, `codex_role`); (2) fix `complete_stage` to emit `current_state` instead of `next_state`; (3) add `escalate` decision for human-target and corrupt-state paths; (4) normalize `_blocked_response` shape to match the main envelope. |
| `tests/test_fsm_ops.py` | Conv 1 | Add/update assertions for new `agent_hint` key names, `current_state` on both endpoints, `escalate` vs `block` distinction, and normalized blocked response shape. |
| `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` | Conv 2 | Add `## Decisions` block documenting `continue`, `block`, `escalate`; ensure `codex_subagent` is not taught as the primary dispatch path. |
| `tests/test_setup.py` | Conv 2 | Assert SKILL_EXECUTION.md contains the three decision values and `agent_hint`, and does not reference `codex_subagent` as primary. |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.
> The flow YAML files (`team.flow.yaml`, etc.) are read-only reference for Conv 1 — verify `role_map` is already present but do NOT modify them unless a concrete contract mismatch is discovered.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | FSM contract normalization | S1.1, S1.2 | TODO | `src/pathly_orchestrator/fsm_ops.py`, `tests/test_fsm_ops.py` |
| 2 | Codex surface alignment | S2.1, S2.2 | TODO | `src/pathly_data/adapters/codex/SKILL_EXECUTION.md`, `tests/test_setup.py` |

---

## Feedback files (transient - deleted after resolution)

Live in `pathly/plans/[feature]/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
