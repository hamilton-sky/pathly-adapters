# composition-blocks — Feature Index

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
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions, user-block merge strategy, type-safety contract |
| `EDGE_CASES.md` | yes | Failure modes — missing blocks, capability gaps, merge conflicts |
| `HAPPY_FLOW.md` | yes | Golden-path narrative: author → store → wizard → compose |
| `FLOW_DIAGRAM.md` | yes | Mermaid diagram: stage → block → fragments → composed prompt |

---

## Feature summary

**composition-blocks** adds named, reusable **composition blocks** (presets) selectable in the Studio Flow Wizard. A block is a named ordered list of skill fragments. Flows reference blocks by name per FSM state via a new optional `composition:` top-level key in flow yaml. The runtime resolver expands a block's fragments and threads them into `build_prompt` at execution time. Backward-compatible: flows with no `composition:` key behave exactly as today.

**What is NOT changing:** FSM states, transitions, phase names, adapter routing. A block is config injected into an existing stage — never a new state or control-flow construct.

---

## Codebase touchpoints

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

| Codebase file | Conv | What changes |
|---|---|---|
| `src/pathly_data/core/skills/composition.yaml` | Conv 1 | Add top-level `blocks:` map with 3 default blocks |
| `src/pathly_orchestrator/compose.py` | Conv 1 | Add block resolver, `compose_skill_with_block`, block validator |
| `tests/test_compose.py` | Conv 1 | Add block resolution + validation unit tests |
| `src/pathly_orchestrator/state.py` | Conv 2 | Register `composition:` key in allowed-keys; validate per-state block references |
| `src/pathly_orchestrator/fsm_ops.py` | Conv 2 | Wire `build_prompt` to resolve stage block when active flow has `composition:` |
| `tests/test_state*.py` (locate by glob) | Conv 2 | Add flow-schema validation tests for `composition:` key |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` | Conv 3 | Add wizard step state for per-stage block binding; wire to generateYaml |
| `studio/src/renderer/src/components/FlowWizard/types.ts` | Conv 3 | Extend wizard types with block-selection state |
| `studio/src/renderer/src/components/FlowWizard/utils/` (generateYaml) | Conv 3 | Extend generateYaml signature to emit `composition:` map |
| `studio/src/renderer/src/components/FlowWizard/Step4Agents/` | Conv 3 | Add per-stage block dropdown within the agents step |
| `studio/src/renderer/src/components/FlowWizard/BlockAuthorForm/` | Conv 3 | NEW subfolder: block authoring form component + css module |
| `studio/src/renderer/src/components/FlowWizard/wizardTemplates.ts` | Conv 3 | Register any new wizard template defaults |

**Scouted this session (treat as live):** All Python paths above were confirmed by a scout in this planning session. Studio paths were also confirmed by scout. Builders must still glob-verify before editing — the scout was run at plan time and paths could shift.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 0 | Pre-flight baseline | — | TODO | (read-only checks) |
| 1 | Block resolver + composition.yaml | S1, S2, S3 | TODO | `compose.py`, `composition.yaml`, `tests/test_compose.py` |
| 2 | Flow schema + runtime wiring | S4, S5 | TODO | `state.py`, `fsm_ops.py`, `tests/test_state*.py` |
| 3 | Studio wizard: block authoring + per-stage dropdown | S6, S7 | TODO | FlowWizard/* (TypeScript/React) |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/composition-blocks/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
