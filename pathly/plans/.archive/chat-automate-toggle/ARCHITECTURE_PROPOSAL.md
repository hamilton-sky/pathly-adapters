# AI-Assisted Flow Wizard - Architecture Proposal

## Recommendation

Implement option 2 as a full-schema AI drafting capability inside `FlowWizard`, after upgrading the wizard so it can round-trip the runtime flow format. Do not build it as ChatPanel automation that clicks Studio controls.

## Why the wizard must come first

The current wizard is not a complete editor for the live Pathly schema:

- It hand-builds YAML and omits `role_map` and `transition_actions`, which exist in shipped flows.
- It collects a description but does not serialize it.
- Its validation is limited compared with `FlowEditor/utils/validateFlow.ts`.
- Its review component still reflects older step numbering.

An LLM generating drafts into this surface today would create flows that appear valid in the UI while losing runtime behavior on save.

## Target architecture

```text
User intent text
      |
      v
AiDraftPanel inside FlowWizard
      |
      v
Existing LLM bridge -> constrained FlowYaml response
      |
      v
parse + canonical validation
      |
      +-- invalid: preserve current wizard data, show issues
      |
      +-- valid: populate editable wizard draft
                       |
                       v
              User reviews/edits full schema
                       |
                       v
              canonical YAML dump + save
```

## Schema boundary

`FlowYaml` is the internal contract. It must cover the fields already consumed by the application and shipped configuration:

```text
version, flow, storage_path, states, transitions,
agent_map, role_map, feedback_routing,
transition_rules, transition_actions, gates
```

The wizard and FlowEditor should share the same typed parsing, serialization, and validation behavior. The AI layer supplies a candidate `FlowYaml`; it does not invent a second automation schema.

## Stepper comparison

`playwright-stepper-framework` is a good reference for boundaries, not the executor for this feature:

| Stepper pattern | Use here |
|---|---|
| Stable action/config contract before execution | Generate and validate a stable `FlowYaml` draft |
| Resolver cascade isolated from actions | Keep AI generation isolated from save/runtime execution |
| Healing only when target UI locators fail | Defer; creating Studio-internal flow data does not require locator recovery |

If Studio later tests a flow against a third-party web application, cascade resolution and healing belong in that external execution layer.

## Key decisions

1. **Wizard integration, not ChatPanel mode toggle.** The user is building a flow; the wizard is the correct editing and approval context.
2. **Draft first, save only after user approval.** The model can assist design but cannot persist or run a flow automatically.
3. **Canonical serializer shared with editor behavior.** `js-yaml` is already used by FlowEditor and avoids partial handcrafted output.
4. **Full-schema support precedes AI.** A partial editor is not a safe destination for model-generated workflow definitions.
5. **Fix current LLM typing prerequisite.** The existing `ollamaChat(..., think)` type mismatch is part of the path exercised by AI drafting and must be repaired or explicitly resolved before acceptance.

## Risks

| Risk | Mitigation |
|---|---|
| Model emits malformed structure | Parse and validate before applying; preserve current wizard state on failure |
| Generated graph references missing states/roles | Shared full-schema validation blocks Save |
| AI drafting overwrites manual edits | Apply only after a confirmed successful draft generation; never auto-save |
| Wizard diverges from FlowEditor again | Centralize model/serialization/validation and add round-trip tests |
