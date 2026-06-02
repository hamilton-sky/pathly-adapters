---
name: Conversation Guide
---
# flow-wizard-redesign - Conversation Guide

Split into 4 conversations. After each conversation, commit your changes before starting the next.

## Conversation 1: Step consolidation

Stories delivered: S1.1, S1.2

Prompt to paste:
```text
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 1 (Phases 0-3) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

Before editing anything, verify the FlowWizard directory contents and confirm Step5Review.tsx exists.

Files in scope:
- studio/src/renderer/src/components/FlowWizard/Step4Quality.tsx - create
- studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx - modify
- studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx - modify

Rules:
- Keep internal step state as 0-5.
- Step 0 is the entry screen and does not show the progress indicator.
- Step 4 is Quality & routing.
- Step 5 is Review & save.
- Parameterize StepIndicator to show 5 dots and accept displayStep / totalSteps.
- Do not add Step0Entry yet.
- Do not add animations, Cancel dialogs, or draft logic yet.

Verify TypeScript compiles and the wizard navigates cleanly from Step 0 through Step 5.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md phases 0-3 to DONE.
```

## Conversation 2: Template entry point

Stories delivered: S2.1, S2.2

Prompt to paste:
```text
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 2 (Phases 4-6) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

Conversation 1 must be complete before starting.

Files in scope:
- studio/src/renderer/src/components/FlowWizard/wizardTemplates.ts - create
- studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx - create
- studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx - modify
- studio/src/renderer/src/components/FlowWizard/index.ts - modify

Rules:
- Step 0 is the entry screen and appears before Step 1.
- Step 0 shows From template, From name, and Start blank.
- From name and Start blank both advance using the blank template.
- Wire template selection into FlowWizard so states and transitions populate.
- Do not add YamlPreview, animations, Cancel dialog, or draft logic yet.

Verify TypeScript compiles and Step0Entry works on open.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md phases 4-6 to DONE.
```

## Conversation 3: Live preview and positive states

Stories delivered: S3.1, S3.2, S3.3, S5.1

Prompt to paste:
```text
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 3 (Phases 7-11) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

Conversation 2 must be complete before starting.

Files in scope:
- studio/src/renderer/src/components/FlowWizard/YamlPreview.tsx - create
- studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx - modify
- studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx - modify
- studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx - modify

Rules:
- Compute one live YAML string with useMemo and reuse it for preview and save.
- Review step should render YamlPreview.
- Add checkmark animation to completed dots with reduced-motion support.
- Add Cancel confirmation for step >= 1.
- Add Start over button and confirmation for step >= 1.
- Leave draft cleanup for the next conversation.

Verify TypeScript compiles and the review step, animations, and dialogs work.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md phases 7-11 to DONE.
```

## Conversation 4: Validation, drafts, and Step 2 polish

Stories delivered: S4.1, S4.2, S4.3, S5.2, S5.3

Prompt to paste:
```text
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 4 (Phases 12-15) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

Conversation 3 must be complete before starting.

Files in scope:
- studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts - modify
- studio/src/renderer/src/components/FlowWizard/draftUtils.ts - create
- studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx - modify
- studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx - modify
- studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx - modify
- studio/src/renderer/src/components/FlowWizard/Step2States.tsx - modify
- studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts - modify

Rules:
- Validation should return blocking errors and advisory warnings separately.
- Add draft save / resume flow using a JSON draft file.
- Add HTML5 drag-to-reorder and pipeline chain preview in Step 2.
- Update styles for drag handle and pipeline chain.
- Write VERIFY.md with RESULT: PASS after verification.

Verify TypeScript compiles and the draft, validation, and drag features work.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md phases 12-15 to DONE.
```
