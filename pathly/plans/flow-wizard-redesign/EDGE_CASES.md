---
name: Edge Cases
---
# flow-wizard-redesign — Edge Cases

## Category 1: Template Selection

### EC-1.1: User switches templates after editing
- **Trigger:** User selects "Standard pipeline", edits states, then goes Back to Step 0 and selects a different template
- **Current behavior:** N/A (Step 0 does not exist yet)
- **Expected behavior:** Selecting a new template overwrites all states and transitions with the new template's defaults. User-entered agent map and gates are NOT cleared (user may have added valid config)
- **Handled in:** Phase 6 — handleTemplateSelect always sets states and transitions from template; leaves agentMap, gates, feedbackRoutes, transitionRules untouched

### EC-1.2: User selects "blank" then edits, then returns to Step 0
- **Trigger:** User navigates Back from Step 1 to Step 0 after editing
- **Current behavior:** N/A
- **Expected behavior:** Step 0 shows the entry screen; selecting "Start blank" again resets states and transitions to empty (since blank template has empty arrays). User is not warned.
- **Handled in:** Phase 6 — same handleTemplateSelect logic applies

---

## Category 2: Step Consolidation

### EC-2.1: User has gates/routes/rules data, navigates backward through Quality step
- **Trigger:** User fills in gates in the Quality accordion, advances to Review, then goes Back
- **Expected behavior:** Quality step re-renders with existing gate data intact; accordion sections remember their expanded/collapsed state via local component state (reset on unmount is acceptable)
- **Handled in:** Phase 1 — Step4Quality uses parent state passed as props; data is in FlowWizard.tsx state, not local to the component. Accordion expanded/collapsed state is local and will reset on unmount — this is acceptable.

### EC-2.2: All accordion sections collapsed, Save produces valid YAML
- **Trigger:** User never expands any accordion in Quality step
- **Expected behavior:** YAML is generated with empty `gates: {}`, `feedback_routing: {}`, `transition_rules: {}` sections — same as current behavior with blank fields
- **Handled in:** Phase 1 and Phase 8 — generateYaml handles empty/missing values

---

## Category 3: Drag-to-Reorder

### EC-3.1: Dragging with a single state
- **Trigger:** Only one state in the list; user attempts to drag it
- **Expected behavior:** Drag has no effect — array of length 1 cannot be reordered
- **Handled in:** Phase 12 — onDrop guard: if dragIndex === dropIndex, do nothing

### EC-3.2: Drag reorder changes initial/terminal tag assignments
- **Trigger:** User drags the first state to a middle position
- **Expected behavior:** The new first state gets the "initial" tag; the new last state gets the "terminal" tag. Transitions that referenced the moved states by name are preserved (state names don't change, only positions)
- **Handled in:** Phase 12 — initial/terminal tags are computed from array position in the render, not stored as metadata

### EC-3.3: Drag on mobile / touch devices
- **Trigger:** User is on a touch device (Electron app on tablet)
- **Expected behavior:** HTML5 drag API does not fire touch events on mobile. Drag handle is visible but non-functional on touch
- **Handled in:** Known limitation — out of scope for this plan. Up/down arrow buttons could be added in a future plan if needed.

---

## Category 4: Validation Warnings

### EC-4.1: Step 4 warning with one-state flow
- **Trigger:** User defines only one state (which is both initial and terminal)
- **Expected behavior:** No unassigned-agent warning shown — a single-state flow is terminal-only and requires no agent
- **Handled in:** Phase 11 — warning logic only applies to non-terminal states (all states except the last)

### EC-4.2: User acknowledges warning and advances anyway
- **Trigger:** Step 4 shows "no agent for state X" warning; user clicks Next
- **Expected behavior:** Wizard advances to step 5 (Quality). Warning was non-blocking. YAML will have an empty agent_map entry for that state.
- **Handled in:** Phase 11 — warnings returned separately from errors; Next is not disabled by warnings

---

## Category 5: Live YAML Preview

### EC-5.1: Preview with empty flow name
- **Trigger:** User reaches Review without filling in a flow name (unlikely — step 1 validates — but possible via back-navigation)
- **Expected behavior:** YAML shows `flow: ''` — valid YAML, not an error in the preview
- **Handled in:** Phase 8 — generateYaml accepts empty string; preview renders whatever is returned

### EC-5.2: Very long YAML
- **Trigger:** User defines 15+ states with transitions, gates, and routing
- **Expected behavior:** YamlPreview scrolls vertically within its max-height (300px); no horizontal overflow
- **Handled in:** Phase 7 — YamlPreview uses `overflow-y: auto; overflow-x: auto; white-space: pre`

---

## Category 6: Draft Save & Resume

### EC-6.1: Draft saved with no flow name
- **Trigger:** User clicks "Save draft" on Step 1 before typing a flow name
- **Expected behavior:** Draft is still written to disk with flowName: ''. Step0Entry shows Resume card with label "Resume draft -- (unnamed)"
- **Handled in:** Phase 14 -- draft card shown if draft exists, regardless of flowName content; label uses draft.flowName || '(unnamed)'

### EC-6.2: Draft file is corrupted / malformed JSON
- **Trigger:** Another process writes garbage to .wizard-draft.json, or the file was truncated
- **Expected behavior:** deserializeDraft() returns null; detectedDraft stays null; wizard opens with 3 standard cards; no error shown
- **Handled in:** Phase 13 -- deserializeDraft wraps JSON.parse in try/catch; validates required fields; returns null on any failure

### EC-6.3: Draft written at Step 4, user resumes and immediately saves
- **Trigger:** User saves draft mid-way; reopens; resumes at Step 4; clicks "Save Flow" without reviewing
- **Expected behavior:** handleSave() uses liveYaml (useMemo), writes flow YAML, then deletes the draft file. Everything works normally.
- **Handled in:** Phase 13 -- handleSave() calls deleteFile(draftPath) after successful flow save

### EC-6.4: Two browser windows / two wizard instances open simultaneously
- **Trigger:** User somehow opens two wizard instances at the same time (unusual in Electron)
- **Expected behavior:** Both can write to .wizard-draft.json; last write wins. No data loss beyond one session overwriting the other.
- **Handled in:** Known limitation -- out of scope. Single-window assumption holds in Electron.

### EC-6.5: Start over deletes a draft the user might have wanted to keep
- **Trigger:** User has saved a draft; clicks "Start over" and confirms
- **Expected behavior:** Draft is deleted as part of Start over. The confirmation dialog text "All your progress will be cleared" covers this implicitly. No additional warning about the draft.
- **Handled in:** Phase 13 -- handleStartOver() calls deleteFile(draftPath) before resetting state. This is intentional.

---

## Known Limitations

- **Drag on touch devices:** HTML5 drag API does not support touch — intentionally out of scope
- **"From name" AI generation:** Step 0's "From name" card currently falls back to blank; AI-based state generation from a description is a future enhancement
- **Accordion state persistence across navigation:** Expanded/collapsed state of accordion sections resets when leaving and returning to the Quality step — acceptable for this plan
