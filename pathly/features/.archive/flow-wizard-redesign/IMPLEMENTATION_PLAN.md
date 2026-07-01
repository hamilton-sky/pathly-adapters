---
name: Implementation Plan
---
# flow-wizard-redesign - Implementation Plan

## Overview

Redesign the FlowWizard UI from an 8-step linear modal to a 6-step wizard with a separate Step 0 entry screen, a live YAML preview, positive completion states, cancel/start-over confirmation, and better validation. The YAML output format and downstream flow-loading system must not change. All implementation work stays inside `studio/src/renderer/src/components/FlowWizard/`.

## Canonical Step Model

- Step 0: Entry screen
- Step 1: Name your flow
- Step 2: Define stages
- Step 3: Assign agents
- Step 4: Quality & routing
- Step 5: Review & save

Internal wizard state runs `0..5`. The progress indicator shows `Step X of 5` for steps 1-5 and is hidden on Step 0.

## Layer Architecture

```
FlowWizard.tsx  (orchestrator - step state, YAML memo, callbacks)
     |
     ├── Step0Entry.tsx         (new - template/name/blank/resume selector)
     ├── Step1Name.tsx          (unchanged)
     ├── Step2States.tsx        (modified - drag + pipeline chain)
     ├── Step3Transitions.tsx   (unchanged)
     ├── Step4Agents.tsx        (unchanged)
     ├── Step4Quality.tsx       (new - accordion: gates+routing+rules)
     ├── Step5Review.tsx        (modified - receives reactive YAML)
     ├── StepIndicator.tsx      (modified - 5 steps, animated checkmark)
     ├── WizardFooter.tsx       (modified - cancel/start-over/save draft)
     ├── YamlPreview.tsx        (new - reactive YAML panel)
     ├── wizardTemplates.ts     (new - 4 preset data objects)
     ├── draftUtils.ts          (new - draft serialization helpers)
     └── FlowWizard.validation.ts (modified - improved errors/warnings)
```

---

## Phases

### Phase 0: Pre-flight
**File:** `studio/src/renderer/src/components/FlowWizard/` (directory)
**Done when:** All FlowWizard files referenced by FEATURE_INDEX.md are present, including `Step5Review.tsx`.
**Depends on:** nothing
**Enables:** Phase 1
**Details:**
- Verify the directory contents before editing anything.
- Record any discrepancies before touching code.
**Verify:** `ls studio/src/renderer/src/components/FlowWizard/`

---

### Phase 1: Create Step4Quality.tsx
**File:** `studio/src/renderer/src/components/FlowWizard/Step4Quality.tsx` - create
**Done when:** The component renders three accordion sections for Gates, Feedback Routing, and Transition Rules, all collapsed by default.
**Depends on:** Phase 0
**Enables:** Phase 2
**Details:**
- Use local accordion expansion state.
- Inline the JSX content from the existing Step 5/6/7 sub-steps rather than nesting the old components.
- Use chevron text or SVG, not emoji.
**Verify:** TypeScript compiles in the FlowWizard directory.

---

### Phase 2: Update FlowWizard.tsx for step consolidation
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` - modify
**Done when:** The wizard renders steps 0-5 with Step 4 as Quality & routing and Step 5 as Review & save.
**Depends on:** Phase 1
**Enables:** Phase 3
**Details:**
- Keep internal step state as `0..5`.
- Render Step0Entry at step 0.
- Render Step1Name, Step2States, Step3Transitions, Step4Agents, Step4Quality, Step5Review at steps 1-5.
- Update the progress text to `Step X of 5` for steps 1-5.
- Hide the indicator on Step 0.
- Remove imports for Step5Gates, Step6FeedbackRouting, and Step7TransitionRules.
- Add import for Step4Quality.
**Verify:** Wizard navigates cleanly from Step 0 through Step 5.

---

### Phase 3: Update StepIndicator.tsx
**File:** `studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx` - modify
**Done when:** The indicator renders 5 dots, accepts `totalSteps` and `displayStep`, and shows checkmarks for completed steps.
**Depends on:** Phase 2
**Enables:** Phase 4
**Details:**
- Parameterize the dot count.
- Accept optional step labels.
- Keep the existing active/done logic, just make it data-driven.
**Verify:** TypeScript compiles and the wizard shows 5 dots.

---

### Phase 4: Create wizardTemplates.ts
**File:** `studio/src/renderer/src/components/FlowWizard/wizardTemplates.ts` - create
**Done when:** The module exports `WizardTemplate` and a `WIZARD_TEMPLATES` array with 4 presets.
**Depends on:** Phase 3
**Enables:** Phase 5
**Details:**
- Include standard-pipeline, review-loop, debug-cycle, and blank.
- Keep the module pure data.
**Verify:** TypeScript compiles.

---

### Phase 5: Create Step0Entry.tsx
**File:** `studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx` - create
**Done when:** The entry screen renders three cards: From template, From name, and Start blank.
**Depends on:** Phase 4
**Enables:** Phase 6
**Details:**
- Clicking a template calls `onSelect(template)`.
- From name and Start blank both advance with the blank template.
- Do not show a step counter on Step 0.
**Verify:** TypeScript compiles.

---

### Phase 6: Wire Step0Entry into FlowWizard.tsx
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` - modify
**Done when:** Opening the wizard shows Step0Entry first, and Back from Step 1 returns to Step 0.
**Depends on:** Phase 5
**Enables:** Phase 7
**Details:**
- Initialize `step` to `0`.
- Add `handleTemplateSelect(template)` to seed states and transitions.
- Keep Step 0 outside the progress count.
**Verify:** Step 0 renders first and template selection advances correctly.

---

### Phase 7: Create YamlPreview.tsx
**File:** `studio/src/renderer/src/components/FlowWizard/YamlPreview.tsx` - create
**Done when:** A scrollable YAML preview pane renders with the expected theme tokens.
**Depends on:** Phase 6
**Enables:** Phase 8
**Details:**
- Render a labeled pre block.
- Keep it display-only.
**Verify:** TypeScript compiles.

---

### Phase 8: Reactive YAML in FlowWizard.tsx
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` - modify
**Done when:** `useMemo` computes the YAML string on each relevant state change and the Review step renders `YamlPreview`.
**Depends on:** Phase 7
**Enables:** Phase 9
**Details:**
- Compute one `liveYaml` string from current wizard state.
- Pass `liveYaml` into Step5Review.
- Use the same value for Save.
**Verify:** Changing a field updates the review preview.

---

### Phase 9: Animated checkmarks
**File:** `studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx` - modify
**Done when:** Newly completed dots animate once, with reduced-motion respected.
**Depends on:** Phase 8
**Enables:** Phase 10
**Details:**
- Use a simple scale animation.
- Track first completion per step.
**Verify:** Advancing a step animates its dot once.

---

### Phase 10: Cancel confirmation
**File:** `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` - modify
**Done when:** Cancel on Step 1+ shows a confirm prompt; Step 0 still closes immediately.
**Depends on:** Phase 9
**Enables:** Phase 11
**Details:**
- Add local confirmation state.
- Keep the dialog inline to the footer.
**Verify:** Cancel behaves differently on Step 0 versus later steps.

---

### Phase 11: Start over confirmation
**File:** `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` - modify
**Done when:** A Start over button appears on Step 1+ and confirmation resets the wizard to Step 0.
**Depends on:** Phase 10
**Enables:** Phase 12
**Details:**
- Add `onStartOver`.
- In `FlowWizard.tsx`, reset wizard state to initial values.
- Leave draft cleanup for Phase 13.
**Verify:** Confirming Start over returns to Step 0 with cleared state.

---

### Phase 12: Extended validation
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts` - modify
**Done when:** Validation returns blocking errors and advisory warnings with improved message text.
**Depends on:** Phase 11
**Enables:** Phase 13
**Details:**
- Keep Step 1 and Step 2 errors descriptive.
- Add a Step 2 warning when 2+ states exist but no transitions are defined.
- Add a Step 3/4 advisory warning when non-terminal states have no agent assigned.
**Verify:** TypeScript compiles and warnings surface without blocking Next.

---

### Phase 13: Save draft
**Files:** `studio/src/renderer/src/components/FlowWizard/draftUtils.ts` and `FlowWizard.tsx` and `WizardFooter.tsx`
**Done when:** The wizard can serialize a draft, persist it, and delete it on final save or Start over.
**Depends on:** Phase 12
**Enables:** Phase 14
**Details:**
- Add draft serialization helpers.
- Add Save draft UI and feedback.
- Delete the draft file after a successful final save.
**Verify:** Saving a draft writes the JSON file and shows success feedback.

---

### Phase 14: Resume draft
**Files:** `FlowWizard.tsx` and `Step0Entry.tsx`
**Done when:** A saved draft is detected on open and can be resumed from Step 0.
**Depends on:** Phase 13
**Enables:** Phase 15
**Details:**
- Read the draft on mount.
- Show a Resume draft card when valid draft data exists.
- Restore wizard state and step on resume.
**Verify:** Reopening the wizard shows a resume option when a draft exists.

---

### Phase 15: Step 2 UX polish
**Files:** `Step2States.tsx` and `FlowWizard.styles.ts`
**Done when:** State rows can be reordered via HTML5 drag and the pipeline chain updates live.
**Depends on:** Phase 14
**Details:**
- Add drag handle styling and pipeline chain visuals.
- Keep the implementation dependency-free.
**Verify:** Reordering updates the chain and preserves state names.
