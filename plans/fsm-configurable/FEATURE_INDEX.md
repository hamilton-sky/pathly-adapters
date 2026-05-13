# fsm-configurable — Feature Index

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
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative for the generic FSM engine |
| `EDGE_CASES.md` | Planner | Builder, Tester | Failure modes and risk scenarios |
| `FLOW_DIAGRAM.md` | Planner | All agents | Multi-component interaction diagram |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Flow YAML schema and orchestrator contract |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `PLAN.md` | no | Legacy alias — not used |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_data/core/skills/team.md` | Conv 1 | MODIFY: update feature detection scan path to `pathly/plans/*/` |
| `src/pathly_data/core/agents/orchestrator.md` | Conv 1, Conv 3 | MODIFY: Conv 1 — update artifact archiving to `pathly/pipeline-walkthrough/`; Conv 3 — replace hardcoded team FSM with generic flow_config-driven engine |
| `src/pathly_data/core/flows/team.flow.yaml` | Conv 2 | CREATE: FSM config for team pipeline (storage_path: pathly/plans/{topic}/) |
| `src/pathly_data/core/flows/debug.flow.yaml` | Conv 2 | CREATE: FSM config for debug flow (storage_path: pathly/debugs/{topic}/) |
| `src/pathly_data/core/flows/explore.flow.yaml` | Conv 2 | CREATE: FSM config for explore flow (storage_path: pathly/explorations/{topic}/) |
| `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` | Conv 3 | MODIFY: add flow_config + topic input fields |
| `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` | Conv 3 | MODIFY: add flow_config + topic input fields (if exists) |
| `schemas/state.schema.json` | Conv 3 | MODIFY: replace hardcoded team state enum with `type: string`; remove hardcoded transitions block |
| `src/pathly_data/core/skills/team.md` | Conv 4 | MODIFY: pass flow_config path to orchestrator spawn |
| `src/pathly_data/core/skills/debug.md` | Conv 4 | MODIFY: stop running inline; spawn orchestrator with debug flow config |
| `src/pathly_data/core/skills/explore.md` | Conv 4 | MODIFY: stop running inline; spawn orchestrator with explore flow config |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | pathly/ root consolidation | S0.1 | TODO | `team.md` (scan path), `orchestrator.md` (archive path) |
| 2 | Create core/flows/ YAML configs | S1.1, S1.2, S1.3 | TODO | `core/flows/team.flow.yaml`, `debug.flow.yaml`, `explore.flow.yaml` |
| 3 | Generalize orchestrator.md | S2.1, S2.2 | TODO | `orchestrator.md`, `orchestrator.yaml` (both adapters) |
| 4 | Update skill launchers | S3.1, S3.2, S3.3 | TODO | `team.md`, `debug.md`, `explore.md` |

---

## Dependency

**Conv 3 and Conv 4 depend on `agent-architecture-refactor` Conv 4 completing first.**
Conv 4 of agent-architecture-refactor converts `team.md` to a thin launcher and moves FSM logic into `orchestrator.md`. This feature then generalizes that orchestrator.

Do not start Conv 3 or Conv 4 of this feature until `agent-architecture-refactor` Conv 4 is DONE.
Conv 1 and Conv 2 (path consolidation + flow YAML creation) are safe to run independently.

---

## Feedback files (transient — deleted after resolution)

Live in `plans/fsm-configurable/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
