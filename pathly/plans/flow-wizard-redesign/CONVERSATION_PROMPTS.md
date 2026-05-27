---
name: Conversation Guide
---
# flow-wizard-redesign — Conversation Guide

Split into 4 conversations. Each produces runnable, TypeScript-valid code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Step Consolidation (Phases 0-3)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 1 (Phases 0-3) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob the FlowWizard directory to confirm every file listed in FEATURE_INDEX.md exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/FlowWizard/Step4Quality.tsx` — CREATE: merged accordion step
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY: reduce if-chain to 6 internal steps (0=entry placeholder, 1-5=wizard, 6=review), step counter shows "Step X of 5"
- `studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx` — MODIFY: accept totalSteps and displayStep props, default totalSteps=5

Scope:
- Phase 0: Pre-flight -- glob the directory, list all files, confirm Step5Review.tsx exists. Stop and report if any listed file is missing.
- Phase 1: Create Step4Quality.tsx with props for gates, setGates, feedbackRoutes, setFeedbackRoutes, transitionRules, setTransitionRules, states, transitions, and theme. Render three collapsible accordion sections (Quality gates, Feedback routing, Transition rules) -- all collapsed by default. Copy JSX content from Step5Gates, Step6FeedbackRouting, Step7TransitionRules directly into the accordion bodies. Use a text or SVG chevron for the toggle -- not an emoji.
- Phase 2: Update FlowWizard.tsx -- reduce the step if-chain to internal steps 1-6 (step 5 = Step4Quality, step 6 = Step5Review). Pass displayStep = Math.min(step, 5) and totalSteps = 5 to StepIndicator. Update step labels array to: ['Name your flow', 'Define stages', 'Assign agents', 'Quality & routing', 'Review & save']. Remove imports of Step5Gates, Step6FeedbackRouting, Step7TransitionRules. Add import of Step4Quality.
- Phase 3: Update StepIndicator.tsx -- accept totalSteps: number (default 5) and displayStep: number as props. Map dots over Array.from({ length: totalSteps }). Keep existing checkmark / step-number rendering logic. Accept optional labels?: string[] prop and render each label below its dot.

Architectural rules:
- Stay within FlowWizard/ directory only. Do not touch Sidebar, SidebarDialogs, or any other component.
- No new npm packages. No emoji as icons.
- TypeScript strict mode -- all new props must be typed.

Do NOT add Step0Entry or template functionality yet (that is Conversation 2).
Do NOT add animations or Cancel dialog yet (that is Conversation 3).

Verify: Run TypeScript compiler on the studio package and confirm zero new type errors.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md Phases 0-3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Wizard opens, navigates 5 steps, step counter reads "Step X of 5", Quality & routing step shows 3 accordion sections.
**Files touched:** `Step4Quality.tsx` (new), `FlowWizard.tsx`, `StepIndicator.tsx`

---

## Conversation 2: Template Entry Point (Phases 4-6)

**Stories delivered:** S2.1, S2.2

**Prompt to paste:**
```
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 2 (Phases 4-6) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

Conversation 1 must be complete before starting this conversation (step count is 5, Step4Quality exists).

**Before editing anything:** glob the FlowWizard directory to confirm Step4Quality.tsx exists (Conv 1 output). Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/FlowWizard/wizardTemplates.ts` — CREATE: 4 template data objects
- `studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx` — CREATE: 3-way entry screen
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY: add step 0, wire template selection
- `studio/src/renderer/src/components/FlowWizard/index.ts` — MODIFY: export new files

Scope:
- Phase 4: Create wizardTemplates.ts -- export type WizardTemplate and WIZARD_TEMPLATES array with 4 entries: standard-pipeline (STORMING/PLANNING/BUILDING/REVIEWING/TESTING/DONE + linear transitions), review-loop (DRAFTING/REVIEW/DONE + DRAFTING->REVIEW, REVIEW->DONE, REVIEW->DRAFTING), debug-cycle (REPRODUCING/DIAGNOSING/FIXING/VERIFYING/DONE + linear transitions), blank (empty states and transitions).
- Phase 5: Create Step0Entry.tsx -- props: onSelect(template: WizardTemplate), onResumeDraft?: (draft: WizardDraft) => void, draft?: WizardDraft, theme. Render heading "Create a new flow", three option cards (From template / From name / Start blank). "From template" card expands to show the 3 named templates as clickable options. "From name" and "Start blank" both call onSelect with the blank template. Card hover uses accent border. No emoji. Draft card is not shown yet -- that prop is wired in Conv 4.
- Phase 6: Update FlowWizard.tsx -- initial step state changes from 1 to 0. Add {step === 0 && <Step0Entry onSelect={handleTemplateSelect} theme={t} />} before existing step blocks. Add handleTemplateSelect: set states from template.states, set transitions from template.transitions, advance to step 1. When step === 0: StepIndicator is hidden, WizardFooter shows only Cancel. Update index.ts to export Step0Entry and wizardTemplates.

Architectural rules:
- Stay within FlowWizard/ directory only.
- Import Transition type from ./types (already exists).
- No new npm packages. No emoji as icons.
- TypeScript strict mode -- all new props must be typed.

Do NOT add YamlPreview, animations, or Cancel dialog yet (that is Conversation 3).

Verify: Run TypeScript compiler. Then manually verify: opening wizard shows Step0Entry; selecting "Start blank" advances to Step 1; selecting "Standard pipeline" pre-fills states with STORMING/PLANNING/BUILDING/REVIEWING/TESTING/DONE.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md Phases 4-6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Opening wizard shows entry screen; selecting a template pre-populates states and transitions on Step 2.
**Files touched:** `wizardTemplates.ts` (new), `Step0Entry.tsx` (new), `FlowWizard.tsx`, `index.ts`

---

## Conversation 3: Live Preview + Positive States + Cancel + Start Over (Phases 7-11)

**Stories delivered:** S3.1, S3.2, S3.3, S5.1

**Prompt to paste:**
```
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 3 (Phases 7-11) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

Conversation 2 must be complete before starting this conversation (Step0Entry exists, templates work).

**Before editing anything:** glob the FlowWizard directory to confirm Step0Entry.tsx and wizardTemplates.ts exist (Conv 2 outputs). Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/FlowWizard/YamlPreview.tsx` — CREATE: reactive YAML preview panel
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY: useMemo YAML generation, integrate YamlPreview, add handleStartOver()
- `studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx` — MODIFY: animated green checkmark on completion
- `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` — MODIFY: Cancel confirmation + Start over button + confirmation

Scope:
- Phase 7: Create YamlPreview.tsx -- props: yaml: string, theme: AppTheme. Render a "Generated YAML" label and a pre block with overflow-y: auto, max-height: 300px, font-size: 12px, monospace font, bgMantle background, textPrimary text.
- Phase 8: Update FlowWizard.tsx -- add useMemo that calls generateYaml() with all state values (liveYaml). Pass liveYaml to Step5Review (remove YAML generation from Step5Review). Render YamlPreview inside the step 6 block. Use liveYaml in handleSave() instead of re-calling generateYaml().
- Phase 9: Update StepIndicator.tsx -- add CSS keyframe animation (step-pop: scale 0.95->1.0, 150ms ease-out) on the dot span when it first transitions to done. Use a useRef Set to track which steps have animated (animation fires once only). Add @media (prefers-reduced-motion: reduce) { animation: none } guard.
- Phase 10: Update WizardFooter.tsx -- add local state showCancelConfirm and step: number prop. On Cancel click: if step >= 1 show dialog; if step === 0 call onClose() directly. Dialog text: "Discard this flow? Your progress will be lost." with "Keep editing" (primary) and "Discard" (red) buttons. Escape while dialog open closes dialog only.
- Phase 11: Extend WizardFooter.tsx -- add showStartOverConfirm state and onStartOver: () => void prop. Render "Start over" button in footer left (next to Cancel), visible only when step >= 1. Confirmation: "Start over? All your progress will be cleared." with "Keep editing" and "Start over" (red) buttons. Escape closes dialog only. In FlowWizard.tsx: add handleStartOver() -- resets all state to initial empty/default values, sets step to 0. Leave a // TODO: delete draft (Phase 13) comment inside handleStartOver for Conv 4 to fill in.

Architectural rules:
- Stay within FlowWizard/ directory only.
- No new npm packages. Animation via CSS keyframes only.
- Respect prefers-reduced-motion in all animations.
- TypeScript strict mode -- all new props must be typed.

Do NOT touch Step2States.tsx, FlowWizard.validation.ts, or draft logic (that is Conversation 4).

Verify: Run TypeScript compiler. Then manually verify: (a) changing flow name and navigating to Review shows updated YAML; (b) completing Step 1 shows animated checkmark on dot 1; (c) Cancel on Step 1 shows confirmation; Discard closes wizard; (d) "Start over" button visible on Step 1+; confirming resets all fields and returns to Step0Entry.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md Phases 7-11 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Review step shows live YAML; step dots animate on completion; Cancel and Start over both show confirmation dialogs; Start over resets state.
**Files touched:** `YamlPreview.tsx` (new), `FlowWizard.tsx`, `StepIndicator.tsx`, `WizardFooter.tsx`

---

## Conversation 4: Validation + Draft Save + Step 2 UX Polish (Phases 12-15)

**Stories delivered:** S4.1, S4.2, S4.3, S5.2, S5.3

**Prompt to paste:**
```
Read pathly/plans/flow-wizard-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement flow-wizard-redesign Conversation 4 (Phases 12-15) from pathly/plans/flow-wizard-redesign/IMPLEMENTATION_PLAN.md.

Conversation 3 must be complete before starting this conversation (YamlPreview, Cancel dialog, and Start over exist).

**Before editing anything:** glob FlowWizard directory to confirm YamlPreview.tsx exists (Conv 3 output). Read FlowWizard.validation.ts, Step2States.tsx, and WizardFooter.tsx in full before editing any of them.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts` — MODIFY: add Step 2 and Step 4 validation + improve error messages
- `studio/src/renderer/src/components/FlowWizard/draftUtils.ts` — CREATE: serialize/deserialize wizard state for draft persistence
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY: handleSaveDraft, handleResumeDraft, draft detection on mount, delete draft on Save and Start over
- `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` — MODIFY: Save draft button + draftSavedAt/draftError feedback display
- `studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx` — MODIFY: optional 4th Resume draft card
- `studio/src/renderer/src/components/FlowWizard/Step2States.tsx` — MODIFY: drag-to-reorder + inline pipeline chain
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts` — MODIFY: dragHandle, pipelineChain, pipelinePill, pipelineArrow styles

Scope:
- Phase 12: Update FlowWizard.validation.ts -- change validateStep return type to { errors: StepErrors, warnings: StepErrors }. Existing errors go in errors. Step 1 flowName error = "Flow name can only contain letters, numbers, hyphens, and underscores -- no spaces". Step 2 warning: if states.length >= 2 && transitions.length === 0, warn "No transitions defined. Auto-generation runs on Next, or add them manually." Step 4: for each non-terminal state (not the last), if agentMap[state] empty/undefined, warn "State [X] has no agent assigned. Non-terminal states without an agent will stall the flow." Update FlowWizard.tsx callers to destructure { errors, warnings } and render warnings in amber (t.yellow or t.orange token, else '#d97706').
- Phase 13: Create draftUtils.ts -- export type WizardDraft (all wizard fields + step: number), serializeDraft(state): WizardDraft, deserializeDraft(json: unknown): WizardDraft | null (null if missing fields or unparseable), DRAFT_FILENAME = '.wizard-draft.json'. In FlowWizard.tsx: compute draftPath = projectPath + '/src/pathly_data/core/flows/' + DRAFT_FILENAME. Add handleSaveDraft(): serialize, call writeFile(draftPath, JSON.stringify(draft, null, 2)), on success set draftSavedAt = Date.now(), on error set draftError. In handleSave(): after successful writeFile, call deleteFile(draftPath) fire-and-forget. In handleStartOver(): replace the TODO comment with deleteFile(draftPath) before resetting state. In WizardFooter.tsx: add onSaveDraft prop, draftSavedAt (number | null), draftError (string | null). Render "Save draft" button in footer left area, visible when step >= 1. Show "Draft saved" in green if draftSavedAt within last 2s; show draftError in red if set.
- Phase 14: In FlowWizard.tsx: add useEffect on mount -- call readFile(draftPath). On success: deserializeDraft(); if non-null set detectedDraft state. On error: silently leave detectedDraft as null. Pass detectedDraft to Step0Entry. In Step0Entry.tsx: accept optional draft?: WizardDraft and onResumeDraft?: (draft: WizardDraft) => void props. If draft defined and draft.flowName non-empty: render 4th card "Resume draft -- [draft.flowName]" with accent left border. Card click calls onResumeDraft(draft). In FlowWizard.tsx: add handleResumeDraft(draft: WizardDraft) -- sets all state fields from draft and sets step to draft.step.
- Phase 15: Update Step2States.tsx -- HTML5 drag-to-reorder: dragIndex ref, draggable on each row, onDragStart sets dragIndex, onDragOver prevents default, onDrop reorders the states array by swapping dragIndex and dropIndex. Add text character U+2807 drag handle as leftmost element of each row with cursor: grab (this is a Unicode braille character, not an emoji). Below states list: pipeline chain div with one pill per state and arrow separators, truncate names at 12 chars. Update FlowWizard.styles.ts: dragHandle (cursor: grab, color: muted), pipelineChain (display: flex, flexWrap: wrap, gap: 4px, marginTop: 12px), pipelinePill (padding: 2px 8px, borderRadius: 12px, background: bgSurface1, fontSize: 12px, fontFamily: monospace), pipelineArrow (color: textMuted, alignSelf: center).

Architectural rules:
- Stay within FlowWizard/ directory only.
- No new npm packages. HTML5 drag API only -- no react-dnd, no dnd-kit.
- Draft persistence uses the same writeFile/readFile/deleteFile IPC as existing Save Flow. Check how FlowWizard.tsx currently calls writeFile and use the same pattern.
- TypeScript strict mode -- all new props must be typed.
- Drag reorder preserves initial/terminal logic (first = initial, last = terminal -- computed from position, not metadata).

Verify: Run TypeScript compiler. Then manually verify: (a) empty flow name shows new descriptive error; (b) agents step with empty field shows amber warning; (c) "Save draft" writes .wizard-draft.json and shows "Draft saved"; (d) close and reopen wizard -- Step0Entry shows 4th "Resume draft" card; clicking restores all fields and step; (e) drag a state row -- pipeline chain updates; (f) Start over after saving draft -- draft file is deleted.
After done, update pathly/plans/flow-wizard-redesign/PROGRESS.md Phases 12-15 to DONE.

Write pathly/plans/flow-wizard-redesign/VERIFY.md with first line RESULT: PASS and a one-line summary of what was verified.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Validation warnings shown; Save draft persists to disk; reopening shows Resume draft card; Start over and final Save delete the draft; dragging reorders states with live pipeline chain.
**Files touched:** `FlowWizard.validation.ts`, `draftUtils.ts` (new), `FlowWizard.tsx`, `WizardFooter.tsx`, `Step0Entry.tsx`, `Step2States.tsx`, `FlowWizard.styles.ts`
