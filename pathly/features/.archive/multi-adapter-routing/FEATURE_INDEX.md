---
name: Feature Index
---
# Multi-Adapter Routing — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What this feature does

Lets a Pathly flow route different pipeline stages to different CLI adapters (claude / codex / copilot). A new optional `adapter_map` block in the flow YAML declares the routing. The FSM stays **passive** — it reads `adapter_map` and emits a `preferred_adapter` string in `/next_action`; a thin `pathly-dispatch` skill reads that and either runs in-place or relays the verbatim prompt to the target adapter. The Studio flow wizard gets a new step to author the routing visually.

**Locked decisions:** passive prompt relay now (auto-launch is future work); per-feature `STATE.json` override deferred to follow-up (precedence slot reserved now); full interactive wizard step included.

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
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions + future work |
| `EDGE_CASES.md` | yes | Failure modes, handoff risk, known limitations |
| `HAPPY_FLOW.md` | yes | Golden-path narrative |
| `FLOW_DIAGRAM.md` | yes | FSM → dispatch → adapter interaction diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies. **Verify each path exists before editing (glob it).**

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/fsm_ops.py` | Conv 1 | Add `_resolve_adapter()` helper; add `preferred_adapter` to `_response_envelope()` (lines ~186-213) and `_blocked_response()` (lines ~218-245) |
| `tests/` (orchestrator test module) | Conv 1 | Unit tests for `_resolve_adapter` — present / absent / default-only / unmatched-state |
| `src/pathly_orchestrator/state.py` | Conv 2 | Add `_KNOWN_ADAPTERS`; add `adapter_map` to `_KNOWN_OPTIONAL_FLOW_KEYS` (lines ~53-58); add validation in `validate_flow_cli()` (lines ~85-166) |
| `src/pathly_data/core/flows/team.flow.yaml` | Conv 2 | Add example `adapter_map` block (sibling to `agent_map` / `role_map`) |
| `src/pathly_data/CLAUDE.md` | Conv 2 | Document the canonical `adapter_map` shape (single source of truth) |
| `tests/` (flow-validation test) | Conv 2 | Round-trip test: a flow with `adapter_map` passes `validate_flow_cli`; a bad adapter name fails |
| `studio/src/renderer/src/components/FlowWizard/utils.ts` | Conv 3 | `generateYaml()` — add `adapterMap` param, emit `adapter_map:` block after `agent_map` (after line 38) |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` | Conv 3 | Add `adapterMap` state, `updateAdapter` handler, render new step, `TOTAL_STEPS` 5→6, draft wiring |
| `studio/src/renderer/src/components/FlowWizard/Step5AdapterRouting/` (NEW) | Conv 3 | New component + `.module.css` (mirror `Step4Agents`) |
| `studio/src/renderer/src/components/FlowWizard/draftUtils.ts` | Conv 3 | Add `adapterMap` to `WizardDraft` |
| `studio/src/renderer/src/components/FlowWizard/types.ts` | Conv 3 | Add `adapterMap` to wizard prop/draft types as needed |
| `src/pathly_data/core/skills/utilities/dispatch.md` (NEW) | Conv 4 | New `pathly-dispatch` coordinator skill (deterministic relay) |
| `src/pathly_data/adapters/claude/_meta/dispatch_skill.yaml` (NEW) | Conv 4 | Skill meta for claude adapter |
| `src/pathly_data/adapters/codex/_meta/dispatch_skill.yaml` (NEW) | Conv 4 | Skill meta for codex adapter |
| `src/pathly_data/adapters/copilot/_meta/dispatch_skill.yaml` (NEW) | Conv 4 | Skill meta for copilot adapter |

---

## Canonical `adapter_map` shape (single source of truth)

Both the FSM validator (`state.py`) and the Studio serializer (`utils.ts`) MUST implement exactly this shape. The validator defines truth; a round-trip test proves Studio conforms.

```yaml
adapter_map:
  default: claude          # REQUIRED if adapter_map present; must be in {claude, codex, copilot}
  BUILDING: codex          # optional per-state override; key must be a declared state; value in known set
  REVIEWING: claude
```

**Resolution precedence for `preferred_adapter` (highest → lowest):**
1. _(reserved: per-feature `STATE.json` override — follow-up, not implemented now)_
2. `adapter_map[current_state]`
3. `adapter_map["default"]`
4. `""` (empty — no `adapter_map`, fully backward compatible)

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | FSM emits preferred_adapter | S1 | TODO | `fsm_ops.py`, `tests/` |
| 2 | Flow validation + canonical doc | S2 | TODO | `state.py`, `team.flow.yaml`, `CLAUDE.md`, `tests/` |
| 3 | Studio wizard adapter step | S3 | TODO | `FlowWizard.tsx`, `utils.ts`, `Step5AdapterRouting/`, `draftUtils.ts`, `types.ts` |
| 4 | pathly-dispatch coordinator | S4 | TODO | `dispatch.md`, 3× `dispatch_skill.yaml` |

**Dependency:** `1 → 2 → 3` (critical path); `4` needs only `1`. After Conv 1, Conv 2 and Conv 4 can run in parallel.

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/multi-adapter-routing/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
