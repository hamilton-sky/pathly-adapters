# AI-Assisted Flow Wizard - Implementation Plan

## Overview

Replace the obsolete Chat/Automate UI-execution direction with an AI-assisted Flow Wizard. The wizard becomes a full editor for the runtime YAML schema first; after that, a local LLM may generate a validated, editable draft from user intent.

No part of this feature should make Playwright click Studio controls or run a Pathly phase automatically.

## Confirmed starting point

| Live area | Current behavior | Required correction |
|---|---|---|
| `FlowWizard/FlowWizard.tsx` and `FlowWizard/utils.ts` | Maintains partial wizard state and hand-builds YAML | Use complete canonical flow document conversion and save boundary |
| `FlowWizard/Step1Name.tsx` | Captures `description` not present in written YAML | Mark as AI intent only or remove from runtime form |
| `FlowWizard/Step3Transitions.tsx` | Has labels not preserved by current output | Align UI state with actual runtime schema; do not imply unsaved fields |
| `FlowWizard/Step5Review.tsx` | Stale review step naming/number | Correct after wizard sections are updated |
| `types/index.ts` `FlowYaml` | Includes roles/actions but may not model every wizard field such as gates | Make type cover full supported schema |
| `FlowEditor/utils/validateFlow.ts` | Validates transitions, state-keyed rules, and transition actions | Share or extend for wizard save/draft validation |
| `lib/llmBridge.ts` | Ollama generation path has current type-contract failure | Repair as prerequisite to AI feature |

## Conversation 1: Canonical flow boundary and baseline repair

**Purpose:** Establish a reliable document contract used by both manual and AI-authored flows.

**Files:**
- `studio/src/renderer/src/types/index.ts` - MODIFY
- `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts` - MODIFY as needed
- `studio/src/renderer/src/components/FlowWizard/utils.ts` - MODIFY or replace with shared conversion usage
- Shared flow parse/serialize helper location established from existing project pattern - CREATE only if needed
- `studio/src/renderer/src/lib/llmBridge.ts` and matching preload/global IPC type declaration - MODIFY
- Focused unit test files near shared flow logic - CREATE/MODIFY

**Work:**
1. Confirm the full supported schema from shipped files and runtime/editor consumers.
2. Extend `FlowYaml` to represent all supported wizard/runtime keys, including `gates` where the current type omits it.
3. Establish structured `js-yaml` serialization/parsing for flow documents; remove dependence on partial line-by-line generation for saves.
4. Extend shared validation for all full-schema references required by the wizard.
5. Fix the existing Ollama `think` parameter typing mismatch across bridge and exposed contract.

**Done when:**
- A full-schema fixture can parse, validate, and dump without omitting `role_map`, `transition_actions`, or `gates`.
- The LLM bridge type mismatch used by generation is fixed.
- Verification records the real baseline and introduces no unrelated type errors.

**Depends on:** none

**Enables:** Conversations 2 and 3
**Verify:** Focused unit tests for serialization/validation, then Studio TypeScript check after the existing bridge mismatch is addressed.

## Conversation 2: Lossless full-schema wizard

**Purpose:** Make manual wizard editing safe before any AI output is routed into it.

**Files:**
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` - MODIFY
- `studio/src/renderer/src/components/FlowWizard/types.ts` - MODIFY
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts` - MODIFY
- Existing `Step*.tsx` files - MODIFY
- New step components for missing schema sections - CREATE only where the existing UX cannot represent them cleanly
- Flow wizard tests - CREATE/MODIFY

**Work:**
1. Convert wizard state to and from the canonical full `FlowYaml` model.
2. Add editing surfaces for missing runtime concepts, at minimum `role_map` and `transition_actions`, and ensure `gates` remain covered.
3. Align feedback routing and transition-rule editors to the validated runtime representation.
4. Correct stale step/review naming and preview output.
5. Resolve the dead `description` field: make it explicitly AI-intent input or remove it from runtime creation UX.
6. Support loading a full existing/drafted flow into wizard fields so round-trip tests are meaningful.

**Done when:**
- A representative shipped flow opens in the wizard and saves without dropping supported behavior.
- Invalid references block save with visible issues.
- Manual creation still works without AI.

**Depends on:** Conversation 1

**Enables:** Conversation 3
**Verify:** Wizard tests for field conversion and validation; manual open/edit/save of a representative full-schema flow.

## Conversation 3: AI drafting inside the wizard

**Purpose:** Let the LLM help create a flow while preserving human review and schema safety.

**Files:**
- `studio/src/renderer/src/components/FlowWizard/AiDraftPanel.tsx` - CREATE
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` - MODIFY
- Prompt/parser helper colocated with existing LLM or flow helpers - CREATE/MODIFY
- `studio/src/renderer/src/lib/llmBridge.ts` - consume repaired contract, avoid duplicating transport
- AI draft tests - CREATE/MODIFY

**Work:**
1. Add a natural-language AI draft panel to the wizard.
2. Define a constrained system prompt that requests only the canonical full flow document.
3. Send generation through the existing local-model bridge.
4. Parse and validate the response before it is eligible to replace wizard fields.
5. Populate fields only as an editable draft; never auto-save or run the result.
6. Preserve current user edits on malformed output, transport error, or abort.

**Done when:**
- A valid response fills full-schema wizard fields for user review.
- Invalid or failed generation leaves the prior draft intact and reports the problem.
- Saving still requires successful validation and explicit user action.

**Depends on:** Conversations 1-2

**Enables:** Conversation 4
**Verify:** Tests for valid draft apply, malformed response, semantically invalid response, error, and abort paths.

## Conversation 4: Review UX and integrated verification

**Purpose:** Complete the user-facing contract and verify no manual-flow regression.

**Files:**
- Flow Wizard review and styling components - MODIFY
- Integration/component tests for wizard flow - CREATE/MODIFY
- Plan verification artifact - CREATE after implementation

**Work:**
1. Mark generated content clearly as a draft until save.
2. Display validation failures in the review/save path and disable invalid saves.
3. Show canonical YAML exactly as it will be written.
4. Verify AI-assisted and manual creation flows.
5. Confirm no ChatPanel automation or Playwright registry was introduced as a substitute for flow definition generation.

**Done when:**
- User can generate, edit, review, and save a valid full-schema flow.
- Manual wizard behavior remains available.
- Focused tests pass and TypeScript check is evaluated against the corrected baseline.

**Depends on:** Conversations 1-3

**Enables:** implementation review/testing
**Verify:** Relevant automated test suite, Studio TypeScript check, and a manual Studio happy-flow pass.

## Scope guardrails

- Do not implement a `chatMode`, AutomationCard route, automation step queue, or Studio-click registry for this goal.
- Do not treat generated text as save-ready before canonical parse and validation.
- Do not introduce healing/resolver logic into the Flow Wizard. That is an external UI execution concern.
