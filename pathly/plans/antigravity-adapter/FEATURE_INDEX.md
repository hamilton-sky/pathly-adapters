---
name: Feature Index
---
# antigravity-adapter — Feature Index

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
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions — model mapping, install paths, plugin deferral rationale |
| `EDGE_CASES.md` | yes | Failure modes: missing agy binary, unknown model names, path conflicts |
| `HAPPY_FLOW.md` | yes | Golden-path: full `pathly-setup antigravity --apply` run |
| `FLOW_DIAGRAM.md` | yes | ASCII diagram: adapter install pipeline for antigravity |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/install_cli/orchestrate.py` | Conv 1 | Add `"antigravity"` to `ALLOWED_HOSTS` |
| `src/install_cli/detect.py` | Conv 1 | Add `"antigravity"` entry to `_HOST_MARKERS` |
| `src/pathly_data/adapters/antigravity/_meta/install.yaml` | Conv 1 | CREATE — install config: dest dirs, skills, templates |
| `src/pathly_data/adapters/antigravity/README.md` | Conv 1 | CREATE — adapter usage docs |
| `src/pathly_data/adapters/antigravity/_meta/architect.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/builder.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/director.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/explorer.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/planner.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/po.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/quick.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/reviewer.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/scout.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/tester.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/web-researcher.yaml` | Conv 2 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/archive_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/build_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/end_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/go_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/help_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/lessons_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/meet_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/pause_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/pathly_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/plan_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/po_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/prd-import_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/retro_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/review_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/scout-path_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/start_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/storm_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/test_skill.yaml` | Conv 3 | CREATE |
| `src/pathly_data/adapters/antigravity/_meta/verify-state_skill.yaml` | Conv 3 | CREATE |
| `tests/test_setup.py` | Conv 4 | Add antigravity host marker assertions |
| `tests/test_e2e_install.py` | Conv 4 | Add antigravity dry-run end-to-end test |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Infrastructure skeleton | S1.1, S1.2 | TODO | `orchestrate.py`, `detect.py`, `install.yaml`, `README.md` |
| 2 | Agent YAML files | S2.1 | TODO | 11 `_meta/<agent>.yaml` files |
| 3 | Skill YAML files | S3.1 | TODO | 19 `_meta/<skill>_skill.yaml` files |
| 4 | Test coverage | S4.1 | TODO | `test_setup.py`, `test_e2e_install.py` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/antigravity-adapter/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
