---
name: Feature Index
---
# flow-wizard-redesign — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `HAPPY_FLOW.md` | Planner | Builder, Tester | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Builder, Tester | Failure modes and risk scenarios |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Builder, Architect | Cross-layer design decisions |
| `FLOW_DIAGRAM.md` | Planner | Builder | Multi-component interaction diagram |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Component decomposition and design decisions |
| `EDGE_CASES.md` | yes | Validation edge cases, drag UX, template conflicts |
| `HAPPY_FLOW.md` | yes | User journey through the redesigned wizard |
| `FLOW_DIAGRAM.md` | yes | Step-by-step wizard state transitions |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` | Conv 1, 2, 3, 4 | Step count 0-5, step rendering, reactive YAML, Step 0 wiring, draft load/save/clear |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts` | Conv 1, 4 | New styles for accordion, pipeline chain, drag handle, YamlPreview |
| `studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx` | Conv 1, 3 | Reflect new 5-step count; animated green checkmark on completed dots |
| `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` | Conv 3 | Cancel confirmation, Start over button + confirmation, Save draft button |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts` | Conv 4 | Add Step 3 transition validation + Step 4 agent validation with descriptive messages |
| `studio/src/renderer/src/components/FlowWizard/utils.ts` | Conv 3 | Export generateYaml so FlowWizard.tsx can call it reactively via useMemo |
| `studio/src/renderer/src/components/FlowWizard/Step2States.tsx` | Conv 4 | Add drag-to-reorder (HTML5 drag API) + inline pipeline chain preview |
| `studio/src/renderer/src/components/FlowWizard/Step5Review.tsx` | Conv 1 | Update review step to consume reactive YAML and align with new step 5 position |
| `studio/src/renderer/src/components/FlowWizard/index.ts` | Conv 2 | Export new Step0Entry and YamlPreview components |

**New files to create:**

| New file | Conversation | Purpose |
|---|---|---|
| `studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx` | Conv 2, 4 | Entry screen: template / from-name / blank; resume draft card added in Conv 4 |
| `studio/src/renderer/src/components/FlowWizard/Step4Quality.tsx` | Conv 1 | Merged accordion: Gates + Feedback Routing + Transition Rules |
| `studio/src/renderer/src/components/FlowWizard/YamlPreview.tsx` | Conv 3 | Live reactive YAML preview panel |
| `studio/src/renderer/src/components/FlowWizard/wizardTemplates.ts` | Conv 2 | 4 preset template data objects |
| `studio/src/renderer/src/components/FlowWizard/draftUtils.ts` | Conv 4 | Serialize/deserialize wizard state to/from JSON for draft persistence |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Step Consolidation (0-5) | S1.1, S1.2 | TODO | `FlowWizard.tsx`, `Step4Quality.tsx`, `StepIndicator.tsx`, `Step5Review.tsx` |
| 2 | Template Entry Point | S2.1, S2.2 | TODO | `Step0Entry.tsx`, `wizardTemplates.ts`, `FlowWizard.tsx`, `index.ts` |
| 3 | Live Preview + Positive States + Cancel + Start Over | S3.1, S3.2, S3.3, S5.1 | TODO | `YamlPreview.tsx`, `FlowWizard.tsx`, `StepIndicator.tsx`, `WizardFooter.tsx` |
| 4 | Validation + Step 2 UX Polish + Draft Save | S4.1, S4.2, S4.3, S5.2, S5.3 | TODO | `FlowWizard.validation.ts`, `Step2States.tsx`, `FlowWizard.styles.ts`, `draftUtils.ts`, `FlowWizard.tsx`, `WizardFooter.tsx`, `Step0Entry.tsx` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/flow-wizard-redesign/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
