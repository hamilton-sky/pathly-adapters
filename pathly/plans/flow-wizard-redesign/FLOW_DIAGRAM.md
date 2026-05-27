---
name: Flow Diagram
---
# flow-wizard-redesign — Flow Diagram

## Happy Path: Template-based flow creation

```
User clicks "+" in Flows sidebar
        │
        ▼
Step0Entry — 3-way selector
        │
        ├─ "From template" ──► template list expands
        │        │
        │        └─ user picks template ──► handleTemplateSelect()
        │                │  sets states[], transitions[]
        │                ▼
        ├─ "From name" ──► handleTemplateSelect(blank)
        │
        └─ "Start blank" ──► handleTemplateSelect(blank)
                │
                ▼
        [step = 1] Step1Name
        Name field (validated on blur)
                │  Next (if valid)
                ▼
        [step = 2] Step2States
        Drag-to-reorder + pipeline chain preview
                │  Next → auto-generate transitions if none
                ▼
        [step = 3] Step3Transitions
        From/To dropdowns
                │  Next
                ▼
        [step = 4] Step4Agents
        State → agent map
        (amber warning if non-terminal state has no agent)
                │  Next
                ▼
        [step = 5] Step4Quality (accordion)
        ├─ Quality gates (collapsed by default)
        ├─ Feedback routing (collapsed by default)
        └─ Transition rules (collapsed by default)
                │  Next
                ▼
        [step = 6] Step5Review
        YamlPreview (reactive, updates from useMemo)
        Storage path input
                │  Save Flow
                ▼
        handleSave() — writeFile(liveYaml)
                │
                ├─ success ──► onCreated(filePath) → wizard closes
                └─ error   ──► saveError shown inline on Review step
```

## Cancel Flow

```
User clicks Cancel
        │
        ├─ step === 0 ──► onClose() immediately (no dialog)
        │
        └─ step >= 1 ──► showCancelConfirm = true
                │
                ├─ "Keep editing" ──► showCancelConfirm = false (resume)
                │
                └─ "Discard" ──► onClose() (wizard closes, state resets)
```

## StepIndicator State Machine

```
Step dot states (per dot):
        future ──► active (user arrives at step)
                       │
                       └─ done (user advances past step)
                              │ (first time only)
                              └─ animate: scale 0.95 → 1.0, 150ms ease-out
                                 (skipped if prefers-reduced-motion)
```

## Template Selection → State Pre-population

```
handleTemplateSelect(template: WizardTemplate)
        │
        ├─ setStates(template.states)
        ├─ setTransitions(template.transitions)
        └─ setStep(1)

Note: agentMap, gates, feedbackRoutes, transitionRules are NOT reset.
      If user had previously entered those, they are preserved.
```

## Save Draft Flow

```
User clicks "Save draft" (step >= 1)
        │
        ▼
handleSaveDraft()
        │  serializeDraft({ all state, step })
        ▼
writeFile(.wizard-draft.json, JSON)
        │
        ├─ success ──► draftSavedAt = Date.now()
        │               "Draft saved" shown 2s in footer
        │
        └─ error   ──► draftError = 'Could not save draft'
                        shown in red in footer

On final Save Flow:
        handleSave() success ──► deleteFile(.wizard-draft.json) [fire-and-forget]

On Start over confirm:
        handleStartOver() ──► deleteFile(.wizard-draft.json) ──► reset state ──► step = 0
```

## Resume Draft Flow

```
Wizard opens (FlowWizard.tsx mount)
        │  useEffect: readFile(.wizard-draft.json)
        │
        ├─ file not found or read error ──► detectedDraft = null
        │                                    Step0Entry: 3 standard cards
        │
        └─ file found ──► deserializeDraft(content)
                │
                ├─ malformed / null ──► detectedDraft = null (silent)
                │
                └─ valid ──► detectedDraft = WizardDraft
                              Step0Entry: 4th card "Resume draft -- [flowName]"
                                        │
                                        └─ user clicks ──► handleResumeDraft(draft)
                                                              set all state from draft
                                                              set step = draft.step
```

## Start Over Flow

```
User clicks "Start over" (step >= 1)
        │
        ▼
showStartOverConfirm = true
        │
        ├─ "Keep editing" ──► showStartOverConfirm = false (resume)
        │
        └─ "Start over" ──► handleStartOver()
                                deleteFile(.wizard-draft.json)
                                reset: flowName='', states=[], transitions=[], agentMap={},
                                       gates={}, feedbackRoutes=[], transitionRules={},
                                       storagePath='pathly/plans/{topic}/'
                                set step = 0
                                ──► Step0Entry shown fresh
```

## Component Legend

| Symbol/Component | Role in this feature |
|-----------------|----------------------|
| `Step0Entry` | Pre-wizard entry; decoupled from step counter; handles its own click logic |
| `wizardTemplates` | Static data; no React; imported by Step0Entry and FlowWizard |
| `Step4Quality` | Replaces 3 separate steps; owns accordion expanded/collapsed state locally |
| `YamlPreview` | Pure display; receives pre-computed yaml string; no generation logic |
| `useMemo (liveYaml)` | Single source of truth for YAML; used by YamlPreview and handleSave |
| `validateStep` | Returns `{ errors, warnings }`; errors block Next, warnings are advisory |
