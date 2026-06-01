# 03 — Artifact Map: multi-adapter-routing

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Builder agents | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| FEATURE_INDEX.md | Planner | All agents | Entry point listing all plan files |
| ARCHITECTURE_PROPOSAL.md | Planner/Architect | Builder, Reviewer | Layer architecture + decisions |
| HAPPY_FLOW.md | Planner | Tester | End-to-end success path |
| EDGE_CASES.md | Planner | Tester, Reviewer | Out-of-scope + edge conditions |
| FLOW_DIAGRAM.md | Planner | Builder | Orchestration flow diagram |
| REVIEW.md | Reviewer | Orchestrator | Review pass record |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| HUMAN_QUESTIONS.md | Gate/Orchestrator | User (human) | Artifact missing after Conv 2 review — required human unblock to proceed REVIEWING→TESTING |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_orchestrator/fsm_ops.py` | S1 | Added `_resolve_adapter()` helper; `preferred_adapter` field emitted in `_response_envelope()` and `_blocked_response()` |
| `src/pathly_orchestrator/state.py` | S2 | Added `_KNOWN_ADAPTERS` frozenset; registered `adapter_map` in `_KNOWN_OPTIONAL_FLOW_KEYS`; added adapter_map shape validation in `validate_flow_cli` |
| `src/pathly_data/CLAUDE.md` | S2 | Documented canonical `adapter_map` shape, `default` key requirement, known adapter set, resolution precedence |
| `src/pathly_data/core/flows/team.flow.yaml` | S2 | Added commented example `adapter_map` block beside `agent_map`/`role_map` |
| `tests/test_fsm_ops.py` | S1 | 4 new unit tests for `_resolve_adapter` (present/absent/default-only/unmatched-state + blocked path) |
| `tests/test_transition_actions.py` | S2 | Round-trip tests — fixture with valid adapter_map passes validator; bad adapter value fails with message |
| `studio/src/renderer/src/components/FlowWizard/utils.ts` | S3 | `generateYaml()` accepts `adapterMap`; emits `adapter_map:` block only when non-trivial |
| `studio/src/renderer/src/components/FlowWizard/Step5AdapterRouting/Step5AdapterRouting.tsx` | S3 | New component: default selector + per-stage override selectors, theme tokens only |
| `studio/src/renderer/src/components/FlowWizard/Step5AdapterRouting/Step5AdapterRouting.module.css` | S3 | New CSS module for Step5 |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` | S3 | Step5 wired in; `TOTAL_STEPS` 5→6; `adapterMap` state; `updateAdapter()`; `generateYaml` call updated |
| `studio/src/renderer/src/components/FlowWizard/draftUtils.ts` | S3 | `adapterMap` added to `WizardDraft` type and `applyDraft`/`startBlank` functions |
| `studio/src/renderer/src/components/FlowWizard/types.ts` | S3 | `adapterMap: Record<string, string>` added to wizard types |
| `src/pathly_data/core/skills/utilities/dispatch.md` | S4 | New core skill: deterministic relay — run-in-place or emit handoff packet; verbatim-relay rule |
| `src/pathly_data/adapters/claude/_meta/dispatch_skill.yaml` | S4 | Install meta for claude adapter |
| `src/pathly_data/adapters/codex/_meta/dispatch_skill.yaml` | S4 | Install meta for codex adapter |
| `src/pathly_data/adapters/copilot/_meta/dispatch_skill.yaml` | S4 | Install meta for copilot adapter |

---

## Artifact flow diagram

```
USER_STORIES.md          <-- what to build
       |
       v
IMPLEMENTATION_PLAN.md   <-- how to build it (11 phases, 4 conversations)
       |
       v
CONVERSATION_PROMPTS.md  <-- exact builder prompts
       |
       v
PROGRESS.md              <-- which conversations done
       |
       v
RETRO.md                 <-- what we learned
       |
       v
lessons/LESSONS.md       <-- promoted patterns -> next planner
pipeline-walkthrough/multi-adapter-routing/  <-- metrics record -> this folder
```
