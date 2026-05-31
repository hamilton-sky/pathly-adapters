---
name: User Stories
---
# flow-wizard-redesign - User Stories

## Context

The FlowWizard is an 8-step modal that guides technical users through creating an AI agent workflow flow (YAML). Research and UX analysis revealed: 8 steps exceeds the 7-step abandonment threshold; there is no template entry point causing blank-slate friction; no positive confirmation feedback exists; and YAML is hidden until the final review step, reducing user confidence. This redesign keeps the YAML format stable, adds a Step 0 entry screen, consolidates the quality-related steps into one reviewable section, introduces a live YAML preview, and improves micro-interaction feedback.

---

## Stories

### Story 1.1: Step Consolidation
**As a** technical user creating a flow, **I want** the wizard to feel shorter and more focused, **so that** I don't feel overwhelmed before I reach the save button.

**Acceptance Criteria:**
- [ ] The progress indicator shows 5 numbered steps, not 8
- [ ] Steps 5, 6, and 7 (Gates, Feedback Routing, Transition Rules) are consolidated into a single "Quality & Routing" step rendered as collapsible accordion sections
- [ ] Navigating Back from step 5 (Review) goes to step 4 (Quality & Routing), not step 7
- [ ] All data previously collected across steps 5-7 is still saved to the output YAML

**Edge Cases:**
- Accordion sections collapsed by default; user who never expands them produces valid YAML with no gates, routes, or rules
- Expanding then collapsing an accordion section preserves any data entered

**Delivered by:** Phase 1-3 -> Conversation 1

---

### Story 1.2: Action-Oriented Step Labels
**As a** technical user, **I want** step names that describe what I'm doing, **so that** I understand my progress without reading tooltips.

**Acceptance Criteria:**
- [ ] Step 1 label reads "Name your flow"
- [ ] Step 2 label reads "Define stages"
- [ ] Step 3 label reads "Assign agents"
- [ ] Step 4 label reads "Quality & routing"
- [ ] Step 5 label reads "Review & save"
- [ ] Step counter badge reads "Step X of 5", not "Step X of 8"

**Delivered by:** Phase 2-3 -> Conversation 1

---

### Story 2.1: Template Entry Point
**As a** user opening the wizard for the first time, **I want** to choose a starting template, **so that** I don't face a blank form with no guidance.

**Acceptance Criteria:**
- [ ] A Step 0 entry screen appears before Step 1 when the wizard opens
- [ ] Step 0 shows three options: "From template", "From name", "Start blank"
- [ ] Step 0 does not count toward the progress indicator
- [ ] Clicking any option advances to Step 1; Back from Step 1 returns to Step 0
- [ ] "Start blank" produces the same initial state as the current wizard

**Edge Cases:**
- Pressing Escape on Step 0 closes the wizard
- Clicking the overlay on Step 0 closes the wizard

**Delivered by:** Phase 5-6 -> Conversation 2

---

### Story 2.2: Template Pre-population
**As a** user who selects a template, **I want** the wizard fields to be pre-filled with sensible defaults for that template, **so that** I can reach a working flow in fewer edits.

**Acceptance Criteria:**
- [ ] "Standard pipeline" template pre-fills states with STORMING, PLANNING, BUILDING, REVIEWING, TESTING, DONE and linear transitions between them
- [ ] "Review loop" template pre-fills states with DRAFTING, REVIEW, DONE and transitions DRAFTING->REVIEW, REVIEW->DONE, REVIEW->DRAFTING
- [ ] "Debug cycle" template pre-fills states with REPRODUCING, DIAGNOSING, FIXING, VERIFYING, DONE and linear transitions
- [ ] Selecting a template and then changing to a different template overwrites pre-filled data with the new template's defaults
- [ ] All pre-filled data is fully editable after selection

**Delivered by:** Phase 4-6 -> Conversation 2

---

### Story 3.1: Live YAML Preview
**As a** technical user, **I want** to see the generated YAML updating as I fill in each field, **so that** I can verify the output before reaching the Review step.

**Acceptance Criteria:**
- [ ] A YAML preview pane is visible on the Review step and updates reactively as state changes
- [ ] The preview shows valid YAML at all times
- [ ] The YAML content in the preview matches the file written to disk on Save

**Edge Cases:**
- Preview with no states shows `states: []`
- Preview updates immediately when any wizard state changes

**Delivered by:** Phase 7-8 -> Conversation 3

---

### Story 3.2: Positive Completion States
**As a** user who has completed a step, **I want** to see a clear visual signal that the step is done, **so that** I feel confident progressing forward.

**Acceptance Criteria:**
- [ ] Completed step dots in the StepIndicator show a green checkmark with a subtle scale animation when first marked complete
- [ ] The green checkmark persists on the dot when the user navigates to a later step
- [ ] The animation only plays once per step
- [ ] Respects `prefers-reduced-motion`

**Delivered by:** Phase 9 -> Conversation 3

---

### Story 3.3: Cancel Confirmation Dialog
**As a** user who has filled in several steps, **I want** a confirmation prompt before the wizard closes, **so that** I don't lose my progress by accidentally clicking Cancel.

**Acceptance Criteria:**
- [ ] Clicking Cancel when `step >= 1` shows a confirmation dialog
- [ ] The dialog has two buttons: "Keep editing" and "Discard"
- [ ] Clicking "Keep editing" dismisses the dialog and returns focus to the wizard
- [ ] Clicking "Discard" closes both the dialog and the wizard, resetting all state
- [ ] Clicking Cancel on Step 0 closes the wizard immediately with no dialog

**Edge Cases:**
- Pressing Escape while the dialog is open closes the dialog only

**Delivered by:** Phase 10 -> Conversation 3

---

### Story 4.1: Extended Validation
**As a** user creating a flow, **I want** the wizard to warn me about configuration mistakes before I save, **so that** I don't produce a broken flow YAML.

**Acceptance Criteria:**
- [ ] Step 3 (Assign agents) shows a warning if any non-terminal state has no agent assigned
- [ ] Step 2 (Define stages) shows a warning on Next if no transitions exist and there are 2+ states
- [ ] All existing Step 1 and Step 2 validation error messages include a specific fix hint
- [ ] Step 1 flow name error is descriptive and format-specific

**Edge Cases:**
- Step 3 warning is non-blocking
- A flow with only one state is valid

**Delivered by:** Phase 12 -> Conversation 4

---

### Story 4.2: Drag-to-Reorder States
**As a** user defining flow stages, **I want** to reorder states by dragging, **so that** I can insert a stage between existing ones without deleting and re-typing.

**Acceptance Criteria:**
- [ ] Each state row in Step 2 has a visible drag handle
- [ ] Dragging a state row reorders the states array
- [ ] After reorder, the initial and terminal labels follow the first and last state
- [ ] Transitions that reference moved states are not deleted

**Edge Cases:**
- Dragging with only 1 state does nothing
- Reorder works with the HTML5 drag API

**Delivered by:** Phase 15 -> Conversation 4

---

### Story 4.3: Inline Pipeline Chain Preview
**As a** user defining stages, **I want** to see a visual pipeline of my states updating as I add/remove/reorder them, **so that** I can verify the flow structure while still on Step 2.

**Acceptance Criteria:**
- [ ] Below the states list in Step 2, a horizontal pill-chain renders
- [ ] The chain updates immediately when states are added, removed, or reordered
- [ ] Pills truncate long names
- [ ] The chain wraps to a new line if needed

**Delivered by:** Phase 15 -> Conversation 4

---

### Story 5.1: Start Over
**As a** user who picked the wrong template or wants to rename their flow, **I want** a "Start over" button inside the wizard, **so that** I can reset and begin again without closing and reopening the wizard.

**Acceptance Criteria:**
- [ ] A "Start over" button is visible in the wizard footer from step 1 onwards
- [ ] Clicking "Start over" shows a confirmation dialog
- [ ] Confirming resets all wizard state and returns to Step 0
- [ ] Any saved draft on disk is deleted when the user confirms Start over

**Edge Cases:**
- Pressing Escape while the start-over dialog is open closes the dialog only
- "Start over" from Step 0 does nothing

**Delivered by:** Phase 11 -> Conversation 3

---

### Story 5.2: Save Draft
**As a** user mid-way through creating a flow, **I want** to save my progress and come back later, **so that** I don't lose work if I need to close the wizard before finishing.

**Acceptance Criteria:**
- [ ] A "Save draft" button is visible in the wizard footer from step 1 onwards
- [ ] Clicking "Save draft" serializes all current wizard state to a JSON file
- [ ] A brief success message appears near the button after saving
- [ ] On successful final Save, the draft file is automatically deleted
- [ ] On Start over confirmation, the draft file is automatically deleted

**Edge Cases:**
- If writeFile fails during Save draft, show an error message
- Draft save is available from any numbered step

**Delivered by:** Phase 13 -> Conversation 4

---

### Story 5.3: Resume Draft
**As a** user returning to create a flow after saving a draft, **I want** the wizard to detect my saved progress and offer to resume, **so that** I can continue where I left off.

**Acceptance Criteria:**
- [ ] On wizard open, the app checks for a saved draft file
- [ ] If a draft exists, Step0Entry shows a 4th card to resume it
- [ ] Clicking Resume draft restores all serialized wizard state and returns to the saved step
- [ ] If no draft exists, the resume card is not shown
- [ ] Draft detection failure is silently ignored

**Edge Cases:**
- Malformed draft JSON is ignored
- Missing fields fall back to defaults

**Delivered by:** Phase 14 -> Conversation 4
