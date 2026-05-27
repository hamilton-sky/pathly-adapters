# AI-Assisted Flow Wizard - Feature Index

> Read this first. This plan folder is retained for continuity, but the former Chat/Automate Playwright scope is superseded.

## Goal

Let a user describe a Pathly workflow in natural language inside the Studio Flow Wizard, receive a structured draft, edit it, validate it, and save a canonical `.flow.yaml` file.

This is option 2: a full flow assistant, implemented through the wizard's data model rather than UI-click automation.

## Live-code findings that shape the plan

| Finding | Consequence |
|---|---|
| `FlowWizard/utils.ts` serializes only part of the shipped YAML schema. | Fix wizard round-trip support before adding AI drafting. |
| Shipped flows use `role_map` and `transition_actions`; `FlowYaml`/FlowEditor already reference them. | The wizard must expose and preserve these fields. |
| Wizard captures `description` but does not write it to YAML. | Remove the misleading saved-field behavior or label it as draft-only intent. |
| FlowEditor uses `js-yaml` plus `validateFlow`; wizard hand-builds YAML. | Consolidate on structured parse/dump and shared validation. |
| `llmBridge.ts` currently calls `ollamaChat` with a fourth `think` argument rejected by its exposed type. | Fix the existing bridge typing before making LLM generation an acceptance gate. |

## Plan files

| File | Purpose |
|---|---|
| `FEATURE_INDEX.md` | Entry point and verified scope |
| `USER_STORIES.md` | Product contract and acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Four-conversation delivery plan |
| `CONVERSATION_PROMPTS.md` | Builder prompts for each conversation |
| `PROGRESS.md` | Implementation checkpoint |
| `HAPPY_FLOW.md` | Primary user journey |
| `EDGE_CASES.md` | Failure and safety cases |
| `ARCHITECTURE_PROPOSAL.md` | Design decisions and Stepper comparison |
| `FLOW_DIAGRAM.md` | Component/data flow |

## Codebase touchpoints

| Codebase file or area | Planned change |
|---|---|
| `studio/src/renderer/src/types/index.ts` | Extend canonical `FlowYaml` coverage, including `gates` if absent |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts` | Reuse structured YAML parse/dump boundary where needed |
| `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts` | Extend full-schema validation used by wizard drafts |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` | Host full-schema editing and AI draft application |
| `studio/src/renderer/src/components/FlowWizard/types.ts` | Align wizard state with canonical flow model |
| `studio/src/renderer/src/components/FlowWizard/utils.ts` | Replace partial hand-built YAML with canonical conversion/serialization |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts` | Validate references and schema consistency |
| `studio/src/renderer/src/components/FlowWizard/Step*.tsx` | Add role/action support and correct step/review UX |
| `studio/src/renderer/src/lib/llmBridge.ts` and exposed IPC typings | Repair Ollama typing required by generation |
| `studio/src/renderer/src/components/FlowWizard/AiDraftPanel.tsx` | Create natural-language draft UI |

## Conversation map

| Conv | Title | Delivers | Status |
|---|---|---|---|
| 1 | Canonical flow model and validation baseline | S1, S2 prerequisite | TODO |
| 2 | Lossless full-schema wizard | S1, S2 | TODO |
| 3 | LLM-generated wizard drafts | S3, S4 | TODO |
| 4 | Safety UX and verification | S5, regression coverage | TODO |

## Explicitly out of scope

- A `[Chat | Automate]` toggle in Conductor.
- Generating Playwright clicks to fill Studio's own wizard.
- Executing Pathly phases by guessed UI labels.
- Stepper-style locator healing inside this feature.

Stepper remains useful as an architecture reference: stable structured intent should be separated from execution. Healing only becomes relevant in a later feature that runs flows against an external UI.
