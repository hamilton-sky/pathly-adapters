# AI-Assisted Flow Wizard - Conversation Prompts

Use one implementation conversation at a time. Each prompt requires live-path verification before editing.

## Conversation 1: Canonical flow boundary and baseline repair

```text
Read pathly/plans/chat-automate-toggle/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Conversation 1 from pathly/plans/chat-automate-toggle/IMPLEMENTATION_PLAN.md.

The feature is an AI-assisted Flow Wizard, not ChatPanel automation. Read the shipped flow YAML files, the existing FlowYaml type, FlowEditor YAML handling, validateFlow, FlowWizard/utils.ts, and llmBridge/exposed IPC typings before editing.

Deliver a canonical full flow-document boundary that preserves the supported runtime schema, including role_map, transition_actions, and gates where supported. Reuse structured YAML parse/dump behavior rather than adding another partial string serializer. Extend validation only where required for full wizard safety.

Fix the existing Ollama bridge typing mismatch exercised by future AI generation: the implementation passes the think option, so the exposed type/contract and handler must agree.

Add focused tests for full-schema parse/serialize/validation behavior. Run the relevant tests and the Studio TypeScript check after addressing the known bridge mismatch. Update PROGRESS.md for Conversation 1 only when verification is recorded.

Keep changes within shared flow-model, validation/serialization, LLM contract, tests, and plan progress boundaries. Do not add ChatPanel automation, Playwright execution, or wizard AI UI yet.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

## Conversation 2: Lossless full-schema wizard

```text
Read pathly/plans/chat-automate-toggle/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Conversation 2 from pathly/plans/chat-automate-toggle/IMPLEMENTATION_PLAN.md after Conversation 1 is complete.

Upgrade FlowWizard to edit and save the canonical full FlowYaml model. Read every current FlowWizard step component before changing navigation or adding fields. Add UI support for schema sections the shipped runtime uses but the wizard currently cannot preserve, especially role_map and transition_actions. Keep gates, feedback routing, and state-keyed transition rules aligned with shared validation.

Fix the misleading description/review behavior: no field may appear to persist to runtime YAML while being silently discarded, and the review step numbering/content must reflect the real wizard.

Add tests proving a representative full-schema flow can load into wizard state and save without dropping supported keys, plus tests for invalid reference handling. Do not add AI generation in this conversation.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

## Conversation 3: AI draft generation in Flow Wizard

```text
Read pathly/plans/chat-automate-toggle/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Conversation 3 from pathly/plans/chat-automate-toggle/IMPLEMENTATION_PLAN.md after the full-schema wizard is working.

Add an AI draft panel inside FlowWizard. The user provides natural-language workflow intent; the LLM returns a constrained canonical FlowYaml candidate through the existing repaired LLM bridge. Parse and validate the candidate before applying it to editable wizard state.

A valid generated flow becomes an unsaved draft only. Invalid response, transport error, or abort must preserve all existing user-edited wizard data and show an actionable error. Do not auto-save and do not execute any Pathly action.

Add tests for valid generation, malformed output, semantic validation failure, bridge failure, and abort/preserve-state behavior. Do not introduce ChatPanel automation or Playwright-driven form filling.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

## Conversation 4: Review UX and integrated verification

```text
Read pathly/plans/chat-automate-toggle/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Conversation 4 from pathly/plans/chat-automate-toggle/IMPLEMENTATION_PLAN.md.

Complete the Flow Wizard review experience: identify AI-generated data as an unsaved draft, display validation failures before save, disable invalid saves, and show the canonical YAML that will be written. Verify both AI-assisted creation and manual creation/editing of a full-schema flow.

Run the relevant automated tests and Studio TypeScript check, recording the result in the plan progress/verification artifact. Confirm that the delivered feature does not depend on ChatPanel automation, an AutomationCard execution path, or Playwright clicks to populate Studio.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```
