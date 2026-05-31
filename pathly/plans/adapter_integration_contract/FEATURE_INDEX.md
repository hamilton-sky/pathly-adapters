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

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/fsm_ops.py` | Conv 1 | Add `schema_version`, `decision`, `role`, `agent_hint`, `stage_brief`, and `warnings`; align `next_action` and `complete_stage` payloads; deprecate `codex_subagent`. |
| `tests/test_fsm_ops.py` | Conv 1 | Update response-shape assertions for the new contract fields and edge cases. |
| `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` | Conv 2 | Switch Codex fallback references from `codex_subagent` to `agent_hint`. |
| `tests/test_setup.py` | Conv 2 | Update setup / packaging expectations that still assert the old `codex_subagent` surface. |
| `src/pathly_data/core/flows/team.flow.yaml` | Conv 1 | Verify current flow metadata already carries `role_map`; only adjust if a contract mismatch is discovered. |
| `src/pathly_data/core/flows/test.flow.yaml` | Conv 1 | Verify current flow metadata already carries `role_map`; only adjust if a contract mismatch is discovered. |
| `src/pathly_data/core/flows/quick-fix.flow.yaml` | Conv 1 | Verify current flow metadata already carries `role_map`; only adjust if a contract mismatch is discovered. |
| `src/pathly_data/core/flows/debug.flow.yaml` | Conv 1 | Verify current flow metadata already carries `role_map`; only adjust if a contract mismatch is discovered. |
| `src/pathly_data/core/flows/explore.flow.yaml` | Conv 1 | Verify current flow metadata already carries `role_map`; only adjust if a contract mismatch is discovered. |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | FSM contract normalization | S1.1, S1.2, S1.3 | TODO | `src/pathly_orchestrator/fsm_ops.py`, `tests/test_fsm_ops.py` |
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
