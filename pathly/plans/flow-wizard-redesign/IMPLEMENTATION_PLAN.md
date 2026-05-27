---
name: Implementation Plan
---
# flow-wizard-redesign — Implementation Plan

## Overview

Redesigns the FlowWizard UI from an 8-step linear modal to a 5-step wizard with a template entry screen (Step 0), live YAML preview, positive completion states, and improved validation. No changes to the YAML output format or the downstream flow loading system. All work is confined to `studio/src/renderer/src/components/FlowWizard/`.

## Layer Architecture

```
FlowWizard.tsx  (orchestrator — step state, YAML generation)
     │
     ├── Step0Entry.tsx         (new — template/name/blank selector)
     ├── Step1Name.tsx          (unchanged)
     ├── Step2States.tsx        (modified — drag + pipeline chain)
     ├── Step3Transitions.tsx   (unchanged)
     ├── Step4Agents.tsx        (unchanged)
     ├── Step4Quality.tsx       (new — accordion: gates+routing+rules)
     ├── Step5Review.tsx        (modified — receives reactive YAML)
     ├── StepIndicator.tsx      (modified — 5 steps, animated checkmark)
     ├── WizardFooter.tsx       (modified — cancel confirmation)
     ├── YamlPreview.tsx        (new — reactive YAML panel)
     ├── wizardTemplates.ts     (new — 4 preset data objects)
     └── FlowWizard.validation.ts (modified — Steps 3+4 + better messages)
```

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1
**File:** `studio/src/renderer/src/components/FlowWizard/` (directory)
**Done when:** All 16 existing FlowWizard files confirmed present; Step5Review.tsx confirmed at that exact name.
**Delivers stories:** (prerequisite — no story)
**Depends on:** nothing
**Enables:** Phase 1
**Details:**
- Glob the FlowWizard directory and confirm each file listed in FEATURE_INDEX.md exists.
- Confirm `Step5Review.tsx` exists (it is the review step despite naming mismatch).
- Record any discrepancies before touching any file.
**Verify:** `ls studio/src/renderer/src/components/FlowWizard/`

---

### Phase 1: Create Step4Quality.tsx   ← Conversation: 1
**File:** `studio/src/renderer/src/components/FlowWizard/Step4Quality.tsx` — CREATE
**Done when:** File exists and renders three accordion sections (Gates, Feedback Routing, Transition Rules) that expand/collapse independently; each section renders the existing step components' content inline.
**Delivers stories:** S1.1
**Depends on:** Phase 0
**Enables:** Phase 2
**Details:**
- Create `Step4Quality.tsx` with props matching the union of Step5Gates, Step6FeedbackRouting, Step7TransitionRules props (gates, setGates, feedbackRoutes, setFeedbackRoutes, transitionRules, setTransitionRules, states, transitions, theme).
- Render three collapsible accordion sections using a local `expanded` state (Record<string, boolean>).
- Section headers: "Quality gates (optional)", "Feedback routing (optional)", "Transition rules (optional)".
- All sections collapsed by default.
- Each section body renders the exact JSX from the corresponding step component (copy the content, do not import the old step as a sub-component — this avoids prop threading complexity).
- Style accordion toggle with a chevron icon (▼/▶) using theme tokens. Do NOT use emoji — use a text or SVG chevron.
**Verify:** TypeScript compiles with no errors in the FlowWizard directory.

---

### Phase 2: Update FlowWizard.tsx — Step Consolidation   ← Conversation: 1
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY
**Done when:** Wizard renders 5 steps (step 1–5); step counter reads "Step X of 5"; step 4 renders Step4Quality; step 5 renders Step5Review; navigation between all steps works correctly.
**Delivers stories:** S1.1, S1.2
**Depends on:** Phase 1
**Enables:** Phase 3
**Details:**
- Change the if-chain from 8 branches to 5 branches:
  - `step === 1` → Step1Name (unchanged)
  - `step === 2` → Step2States (unchanged)
  - `step === 3` → Step3Transitions (unchanged)
  - `step === 4` → Step4Agents (unchanged — agents step stays separate)
  - `step === 5` → Step4Quality (new merged step)
  - `step === 6` → Step5Review (review is now step 6 internally but displayed as "Step 5")
- Wait — reconsider: to keep step numbering simple, use `step === 5` for Step4Quality and `step === 6` for Review, but pass `displayStep = step > 5 ? 5 : step` to StepIndicator. OR renumber: use steps 1–5 with step 5 = Quality and step 6 = Review but StepIndicator only shows 1–5.
- Cleaner approach: Keep internal `step` as 1–6, pass `totalDisplaySteps = 5` and `displayStep = Math.min(step, 5)` to StepIndicator. WizardFooter receives `isLastStep = step === 6`.
- Update step labels array: `['Name your flow', 'Define stages', 'Assign agents', 'Quality & routing', 'Review & save']`
- Remove imports for Step5Gates, Step6FeedbackRouting, Step7TransitionRules (their content is now in Step4Quality).
- Add import for Step4Quality.
- Pass all required props (gates, setGates, feedbackRoutes, setFeedbackRoutes, transitionRules, setTransitionRules, states, transitions) to Step4Quality at `step === 5`.
**Verify:** TypeScript compiles; wizard opens, can be navigated step 1 through 6, step counter shows "Step X of 5".

---

### Phase 3: Update StepIndicator.tsx — New Step Count   ← Conversation: 1
**File:** `studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx` — MODIFY
**Done when:** StepIndicator renders 5 dots (not 8); receives `totalSteps` and `displayStep` as props; completed dots show ✓.
**Delivers stories:** S1.2
**Depends on:** Phase 2
**Enables:** Phase 9 (animated checkmark, Conv 3)
**Details:**
- Accept new props: `totalSteps: number` (default 5), `displayStep: number`.
- Map dots over `Array.from({ length: totalSteps })` using `displayStep` for active/done logic.
- Keep existing ✓ / step-number rendering logic — just parameterized on totalSteps.
- Pass step labels as an optional `labels?: string[]` prop; render label below each dot if provided.
**Verify:** TypeScript compiles; StepIndicator shows 5 dots in the wizard.

---

### Phase 4: Create wizardTemplates.ts   ← Conversation: 2
**File:** `studio/src/renderer/src/components/FlowWizard/wizardTemplates.ts` — CREATE
**Done when:** File exports a `WIZARD_TEMPLATES` array of 4 template objects, each with id, label, description, states[], and transitions[].
**Delivers stories:** S2.2
**Depends on:** Phase 3
**Enables:** Phase 5
**Details:**
- Export type `WizardTemplate = { id: string; label: string; description: string; states: string[]; transitions: Transition[] }`.
- Define 4 templates:
  - `standard-pipeline`: states = ['STORMING','PLANNING','BUILDING','REVIEWING','TESTING','DONE'], linear transitions
  - `review-loop`: states = ['DRAFTING','REVIEW','DONE'], transitions: DRAFTING→REVIEW, REVIEW→DONE, REVIEW→DRAFTING
  - `debug-cycle`: states = ['REPRODUCING','DIAGNOSING','FIXING','VERIFYING','DONE'], linear transitions
  - `blank`: states = [], transitions = [] (user starts empty)
- Import `Transition` type from `./types`.
**Verify:** TypeScript compiles with no errors.

---

### Phase 5: Create Step0Entry.tsx   ← Conversation: 2
**File:** `studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx` — CREATE
**Done when:** File renders a 3-card selector (From template, From name, Start blank); clicking any card calls `onSelect(template)`.
**Delivers stories:** S2.1
**Depends on:** Phase 4
**Enables:** Phase 6
**Details:**
- Props: `onSelect: (template: WizardTemplate) => void; theme: AppTheme`.
- Render a heading "Create a new flow" and three option cards side-by-side.
- Card 1 "From template": clicking shows a secondary list of the 3 named templates (standard-pipeline, review-loop, debug-cycle) below the card. Clicking a template name calls `onSelect(template)`.
- Card 2 "From name": calls `onSelect(WIZARD_TEMPLATES.find(t => t.id === 'blank'))` but the label implies the user will type the name in Step 1 and could name it anything. Just advances with blank state.
- Card 3 "Start blank": calls `onSelect(WIZARD_TEMPLATES.find(t => t.id === 'blank'))`.
- Style: each card uses `bgSurface1` background, `accent` border on hover, cursor-pointer.
- No step counter is shown on Step 0.
**Verify:** TypeScript compiles; component renders without errors.

---

### Phase 6: Wire Step0Entry into FlowWizard.tsx   ← Conversation: 2
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY
**Done when:** Opening the wizard shows Step0Entry first; selecting a template pre-populates states and transitions; Back from Step 1 returns to Step 0; Step 0 does not count in the step counter.
**Delivers stories:** S2.1, S2.2
**Depends on:** Phase 5
**Enables:** Phase 7 (Conv 3)
**Details:**
- Add `step === 0` as the new initial state: `useState(0)`.
- Add `{step === 0 && <Step0Entry onSelect={handleTemplateSelect} theme={t} />}` before the existing step 1 block.
- Add `handleTemplateSelect(template: WizardTemplate)`:  set states from template.states, set transitions from template.transitions, advance to step 1.
- WizardFooter: when `step === 0`, hide Back/Next/Save — Step0Entry handles its own navigation via card clicks. Show only Cancel.
- StepIndicator: only render when `step >= 1`.
- Update `index.ts` to export `Step0Entry` and `wizardTemplates`.
**Verify:** Wizard opens to Step0Entry; selecting "Start blank" advances to Step 1 name field; Back from Step 1 returns to Step 0.

---

### Phase 7: Create YamlPreview.tsx   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/YamlPreview.tsx` — CREATE
**Done when:** Component renders a scrollable pre block with YAML string content, themed using bgMantle/textPrimary tokens.
**Delivers stories:** S3.1
**Depends on:** Phase 6
**Enables:** Phase 8
**Details:**
- Props: `yaml: string; theme: AppTheme`.
- Render: a labeled section (`<h4>Generated YAML</h4>`) + `<pre>` block with `overflow-y: auto; max-height: 300px; font-size: 12px; font-family: monospace`.
- Use `bgMantle` as background, `textPrimary` for text, `bgSurface0` for the pre block.
- No copy button needed in this iteration.
**Verify:** TypeScript compiles.

---

### Phase 8: Reactive YAML in FlowWizard.tsx   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY
**Done when:** `useMemo` computes YAML on every state change; Step 5 (Review) receives `yaml` prop and renders `YamlPreview`; the file written on Save uses the same memoized value.
**Delivers stories:** S3.1
**Depends on:** Phase 7
**Enables:** Phase 9
**Details:**
- Add: `const liveYaml = useMemo(() => generateYaml(flowName, storagePath, states, agentMap, transitions, gates, feedbackRoutes, transitionRules), [flowName, storagePath, states, agentMap, transitions, gates, feedbackRoutes, transitionRules])`.
- Pass `liveYaml` to Step5Review as a prop (remove YAML generation from Step5Review itself).
- In `handleSave()`, use `liveYaml` instead of calling `generateYaml()` again.
- Render `<YamlPreview yaml={liveYaml} theme={t} />` inside the step 6 (Review) block.
**Verify:** Changing flow name on Step 1, navigating to Step 6 (Review), shows updated YAML.

---

### Phase 9: Animated Checkmark on StepIndicator   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/StepIndicator.tsx` — MODIFY
**Done when:** Completed step dots animate scale 0.95→1.0 on first completion; animation respects `prefers-reduced-motion`.
**Delivers stories:** S3.2
**Depends on:** Phase 8
**Enables:** Phase 10
**Details:**
- Add a CSS keyframe animation `@keyframes step-pop { from { transform: scale(0.95) } to { transform: scale(1) } }` (via inline style or a style string inserted into the document head once).
- Apply `animation: step-pop 150ms ease-out` to the dot `<span>` when it transitions to `done` state.
- Guard with `@media (prefers-reduced-motion: reduce) { animation: none }`.
- Track which steps have previously been `done` using a `completedSteps` ref (Set) so the animation only fires on first completion, not on re-renders.
**Verify:** Completing Step 1 and advancing shows the dot animate; no animation when `prefers-reduced-motion` is enabled in the OS.

---

### Phase 10: Cancel Confirmation Dialog   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` — MODIFY
**Done when:** Clicking Cancel on step >= 1 shows an inline confirmation dialog with "Keep editing" and "Discard" buttons; Discard calls `onClose`; Keep editing dismisses the dialog.
**Delivers stories:** S3.3
**Depends on:** Phase 9
**Enables:** Phase 11
**Details:**
- Add local state `showCancelConfirm: boolean` to WizardFooter.
- Props addition: `step: number` (already available as a pass-through from FlowWizard).
- On Cancel click: if `step >= 1`, set `showCancelConfirm = true`; if `step === 0`, call `onClose()` directly.
- Render confirmation dialog as an absolutely positioned overlay inside the footer area (not a new modal):
  - Text: "Discard this flow? Your progress will be lost."
  - "Keep editing" button (primary style) → `setShowCancelConfirm(false)`
  - "Discard" button (red / destructive style) → `onClose()`
- On Escape keydown when dialog is open: close dialog only, not the wizard.
**Verify:** Cancel on Step 1 shows confirmation; "Keep editing" returns to wizard; "Discard" closes wizard.

---

### Phase 11: Start Over Button + Confirmation   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` — MODIFY (same file as Phase 10)
**Done when:** A "Start over" button appears in the footer from step >= 1; clicking it shows a confirmation dialog; confirming calls `onStartOver` prop; the button is absent on Step 0.
**Delivers stories:** S5.1
**Depends on:** Phase 10
**Enables:** Phase 12 (Conv 4)
**Details:**
- Add local state `showStartOverConfirm: boolean` alongside `showCancelConfirm`.
- Add prop `onStartOver: () => void` to WizardFooter.
- Render "Start over" button in the footer left area (next to Cancel), visible only when `step >= 1`.
- On "Start over" click: set `showStartOverConfirm = true`.
- Confirmation dialog (same pattern as cancel dialog):
  - Text: "Start over? All your progress will be cleared."
  - "Keep editing" → `setShowStartOverConfirm(false)`
  - "Start over" (red / destructive) → `onStartOver()`
- Escape while start-over dialog open: close dialog only.
- In FlowWizard.tsx: add `handleStartOver()` — reset all state to initial values (empty strings, empty arrays, default storage path), call `deleteDraftIfExists()` (see Phase 13), set step to 0.
**Verify:** "Start over" button visible on Step 1+; confirmation shows; confirming returns to Step0Entry with all fields cleared.

---

### Phase 12: Extended Validation   ← Conversation: 4
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts` — MODIFY
**Done when:** `validateStep` returns warnings for Step 4 (unassigned agents on non-terminal states) and Step 2 (no transitions with 2+ states); error messages include specific fix text.
**Delivers stories:** S4.1
**Depends on:** Phase 11
**Enables:** Phase 13
**Details:**
- Add `agentMap` and `transitions` to the values param (already accepted but unused for steps 3+).
- Step 1 flowName error: change to "Flow name can only contain letters, numbers, hyphens, and underscores — no spaces".
- Step 2: if `states.length >= 2 && transitions.length === 0`, return warning: "No transitions defined. Click Next on Step 2 to auto-generate them, or add them manually."
- Step 4 (new): for each state that is not the last state (terminal), if `agentMap[state]` is empty or undefined, add warning: `"State [${state}] has no agent assigned. Non-terminal states without an agent will stall the flow."` Warnings are non-blocking (user can advance).
- Return separate `errors` (blocking) and `warnings` (non-blocking) from `validateStep`. Update callers in `FlowWizard.tsx` to use both.
**Verify:** TypeScript compiles; entering an invalid flow name shows new error text; advancing from Step 4 with an unassigned agent shows amber warning.

---

### Phase 13: Save Draft   ← Conversation: 4
**File:** `studio/src/renderer/src/components/FlowWizard/draftUtils.ts` — CREATE
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY
**File:** `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` — MODIFY
**Done when:** "Save draft" button in the footer writes `.wizard-draft.json` to disk; brief "Draft saved" success message appears; final Save deletes the draft; Start over deletes the draft.
**Delivers stories:** S5.2
**Depends on:** Phase 12
**Enables:** Phase 14
**Details:**
- Create `draftUtils.ts`:
  - Export type `WizardDraft` — the full serialized wizard state (flowName, description, states, transitions, agentMap, gates, feedbackRoutes, transitionRules, storagePath, step).
  - Export `serializeDraft(state): WizardDraft` — plain object conversion, no React.
  - Export `deserializeDraft(json: unknown): WizardDraft | null` — parses and validates; returns null if malformed or missing required fields.
  - Export `DRAFT_FILENAME = '.wizard-draft.json'`.
- In FlowWizard.tsx:
  - Compute draft path: `const draftPath = \`\${projectPath}/src/pathly_data/core/flows/${DRAFT_FILENAME}\``.
  - Add `handleSaveDraft()`: call `serializeDraft({...all state, step})`, call `writeFile(draftPath, JSON.stringify(draft, null, 2))`. On success: set `draftSavedAt = Date.now()` (local state, triggers 2s message). On error: set `draftError = 'Could not save draft'`.
  - In `handleSave()`: after successful writeFile, call `deleteFile(draftPath)` (fire-and-forget, ignore errors).
  - In `handleStartOver()` (from Phase 11): call `deleteFile(draftPath)` before resetting state.
- In WizardFooter.tsx:
  - Add `onSaveDraft: () => void` and `draftSavedAt: number | null` and `draftError: string | null` props.
  - Render "Save draft" button in the footer left area (alongside Cancel and Start over), visible when `step >= 1`.
  - If `draftSavedAt` is within 2 seconds of now, render small text "Draft saved" in green next to the button.
  - If `draftError` is set, render it in red next to the button.
**Verify:** Clicking "Save draft" on Step 1 writes `.wizard-draft.json`; file contains valid JSON with current wizard state; "Draft saved" message appears briefly.

---

### Phase 14: Resume Draft in Step0Entry   ← Conversation: 4
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY
**File:** `studio/src/renderer/src/components/FlowWizard/Step0Entry.tsx` — MODIFY
**Done when:** Opening the wizard when a draft exists shows a "Resume draft" 4th card in Step0Entry; clicking it restores state and advances to the saved step.
**Delivers stories:** S5.3
**Depends on:** Phase 13
**Enables:** Phase 15
**Details:**
- In FlowWizard.tsx `useEffect` on mount:
  - Call `readFile(draftPath)`. On success: parse JSON, call `deserializeDraft()`. If result is non-null: set `detectedDraft` state (WizardDraft | null).
  - On read error or parse failure: leave `detectedDraft = null` (silent ignore).
- Pass `detectedDraft` to Step0Entry.
- In Step0Entry.tsx:
  - Accept optional `draft?: WizardDraft` prop.
  - If `draft` is defined and `draft.flowName` is non-empty: render a 4th card "Resume draft — [draft.flowName]" with a different visual treatment (e.g., green left border or `bgSurface1` with accent border).
  - Clicking the card calls `onSelect` with a special sentinel or a separate `onResumeDraft` prop: restores all state from draft and advances to `draft.step`.
- In FlowWizard.tsx: add `handleResumeDraft(draft: WizardDraft)` — set all state fields from draft, set step to draft.step.
**Verify:** Save draft on Step 3; close and reopen wizard; Step0Entry shows 4th "Resume draft — [name]" card; clicking it restores all fields and lands on Step 3.

---

### Phase 15: Step 2 UX Polish — Drag + Pipeline Chain   ← Conversation: 4
**File:** `studio/src/renderer/src/components/FlowWizard/Step2States.tsx` — MODIFY
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts` — MODIFY
**Done when:** State rows have a visible drag handle; dragging reorders the array; below the list, a horizontal pill-chain `STATE1 → STATE2 → ...` renders and updates live.
**Delivers stories:** S4.2, S4.3
**Depends on:** Phase 14
**Enables:** (end of plan)
**Details:**
- Drag-to-reorder using HTML5 drag API (no new library):
  - Add `draggable` attribute to each state row.
  - `onDragStart`: record `dragIndex`.
  - `onDragOver`: call `e.preventDefault()` to enable drop.
  - `onDrop`: reorder `states` array by swapping `dragIndex` with `dropIndex`. Call `setStates(newOrder)`.
  - Add a 6-dot drag handle (`⠿` or SVG equivalent) as the leftmost element of each row, styled with `cursor: grab`.
- Pipeline chain:
  - Below the states list, render `<div className="pipeline-chain">` containing a `<span>` per state and `→` separators.
  - Truncate state names at 12 chars with ellipsis: `name.length > 12 ? name.slice(0, 12) + '…' : name`.
  - Wrap using `flexWrap: 'wrap'` on the container.
- Add styles in `FlowWizard.styles.ts`: `dragHandle`, `pipelineChain`, `pipelinePill`, `pipelineArrow`.
**Verify:** TypeScript compiles; dragging a state row reorders the list; pipeline chain updates immediately; initial/terminal tags remain on first/last states after reorder.

---

## Prerequisites
- No external library changes required (HTML5 drag API, CSS animations, useMemo are all built-in).
- TypeScript strict mode is on — all new props must be typed.

## Key Decisions
- **Step numbering:** Internal step state uses 0–6 (0 = entry, 1–5 = wizard steps, 6 = review). `displayStep = Math.min(step, 5)` passed to StepIndicator keeps the "Step X of 5" contract. This avoids renaming all existing step props and callbacks.
- **Step4Quality as content copy (not sub-component import):** Avoids prop-threading complexity. Gates/FeedbackRouting/TransitionRules JSX is inlined inside the accordion sections of Step4Quality.tsx.
- **Warnings vs errors in validation:** Non-blocking warnings (Step 4 unassigned agents) are returned separately from blocking errors. FlowWizard.tsx renders warnings in amber/yellow, errors in red, using existing `t.yellow` or `t.orange` token.
- **No new dependencies:** Drag-to-reorder uses HTML5 API; animations use CSS keyframes; YAML preview uses existing `generateYaml()` via useMemo.
