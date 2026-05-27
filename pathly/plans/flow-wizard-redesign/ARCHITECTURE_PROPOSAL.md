---
name: Architecture Proposal
---
# flow-wizard-redesign — Architecture Proposal

## Problem Statement

The FlowWizard has 8 steps, no template starting point, no live preview, and no positive feedback states. These UX gaps increase time-to-complete and perceived complexity for technical users creating AI agent flows. The redesign must improve UX without changing the YAML output format or the downstream flow system.

## Proposed Solution

Consolidate 8 steps to 5 (via a merged accordion component), add a pre-wizard entry screen with templates, introduce reactive YAML generation via `useMemo`, and layer in micro-interaction improvements (animated checkmarks, cancel confirmation). All changes are confined to the FlowWizard component tree.

## Layer Breakdown

```
FlowWizard.tsx                   (orchestrator — step state, YAML memo, callbacks)
     │
     ├── Step0Entry.tsx           (new — template picker, before step counter)
     │        └── wizardTemplates.ts  (new — template data, no React)
     │
     ├── Step1Name.tsx            (unchanged)
     ├── Step2States.tsx          (modified — drag handle, pipeline chain)
     ├── Step3Transitions.tsx     (unchanged)
     ├── Step4Agents.tsx          (unchanged)
     │
     ├── Step4Quality.tsx         (new — accordion merging steps 5, 6, 7)
     │        └── inlines JSX from Step5Gates, Step6FeedbackRouting, Step7TransitionRules
     │
     ├── Step5Review.tsx          (modified — receives yaml as prop, renders YamlPreview)
     │        └── YamlPreview.tsx (new — pure display component)
     │
     ├── StepIndicator.tsx        (modified — totalSteps prop, animated checkmark)
     └── WizardFooter.tsx         (modified — cancel confirmation dialog)
```

## Key Design Decisions

### Decision 1: Internal step count 0–6, display step 1–5
- **Options considered:**
  - A: Renumber all steps to 0–5 and show 0 as entry screen
  - B: Keep step 0 outside the numbering; internal count 0–6; display = Math.min(step, 5)
  - C: Treat Step0Entry as a separate component rendered above the wizard modal
- **Chosen:** B
- **Rationale:** Option B avoids renaming all existing step state values and keeps the StepIndicator contract simple (it always shows 1–5, regardless of whether the user is on the entry screen or the review step). Option C adds wrapper complexity in SidebarDialogs.

### Decision 2: Step4Quality inlines JSX rather than importing old step components
- **Options considered:**
  - A: Step4Quality imports Step5Gates, Step6FeedbackRouting, Step7TransitionRules as sub-components
  - B: Step4Quality copies the JSX content from each step directly into accordion bodies
- **Chosen:** B
- **Rationale:** Option A requires threading props through Step4Quality → child step components, which mirrors the existing prop complexity. Option B is a one-time copy that eliminates the prop chain and makes the accordion self-contained. Old step files remain in the directory (unused but not deleted) — they can be removed in a cleanup pass once Conv 1 is stable.

### Decision 3: Reactive YAML via useMemo (not useEffect + state)
- **Options considered:**
  - A: useEffect watches all state values → triggers setState(generateYaml(...)) → re-render
  - B: useMemo computes YAML synchronously on every render where deps changed
- **Chosen:** B
- **Rationale:** useMemo avoids a double-render cycle (state change → effect → setState → re-render). The YAML string is a pure derivation of wizard state — useMemo is the correct primitive. generateYaml() is synchronous and fast; no async concern.

### Decision 4: HTML5 drag API (no new library)
- **Options considered:**
  - A: react-dnd (complex, requires context provider)
  - B: dnd-kit (modern, good touch support, but adds 20KB+ to bundle)
  - C: HTML5 drag API with onDragStart/onDragOver/onDrop
- **Chosen:** C
- **Rationale:** No new npm dependencies. States list is small (typically 3–10 items). HTML5 API is sufficient. Touch support is a known limitation and deferred.

### Decision 5: Cancel dialog as inline overlay in WizardFooter
- **Options considered:**
  - A: Portal-based modal rendered via ReactDOM.createPortal to document.body
  - B: Absolutely positioned overlay inside WizardFooter, above the button row
- **Chosen:** B
- **Rationale:** The wizard is already a fixed modal. A nested portal adds z-index management complexity. An inline overlay inside the footer card is simpler and visually sufficient for a two-button confirmation.

## Key Components

| Component | Description |
|-----------|-------------|
| `Step0Entry.tsx` | Three-card entry selector. Manages template list expansion. Calls onSelect with the chosen WizardTemplate. |
| `wizardTemplates.ts` | Pure data module. No React. Exports WizardTemplate type and WIZARD_TEMPLATES array. |
| `Step4Quality.tsx` | Accordion container for Gates, Feedback Routing, Transition Rules. Local expanded state (Record<string, boolean>). |
| `YamlPreview.tsx` | Pure display component. Receives yaml: string prop. Renders themed pre block. |

## Interface Design

```typescript
// wizardTemplates.ts
type WizardTemplate = {
  id: string
  label: string
  description: string
  states: string[]
  transitions: Transition[]
}
export const WIZARD_TEMPLATES: WizardTemplate[]

// Step0Entry.tsx
type Step0EntryProps = {
  onSelect: (template: WizardTemplate) => void
  theme: AppTheme
}

// Step4Quality.tsx
type Step4QualityProps = {
  gates: Record<string, Gate[]>
  setGates: (g: Record<string, Gate[]>) => void
  feedbackRoutes: FeedbackRoute[]
  setFeedbackRoutes: (r: FeedbackRoute[]) => void
  transitionRules: Record<string, TransitionRule>
  setTransitionRules: (r: Record<string, TransitionRule>) => void
  states: string[]
  transitions: Transition[]
  theme: AppTheme
}

// YamlPreview.tsx
type YamlPreviewProps = {
  yaml: string
  theme: AppTheme
}

// validateStep return type (modified)
type ValidationResult = {
  errors: StepErrors    // blocking — Next disabled
  warnings: StepErrors  // non-blocking — shown in amber
}
```

## Risks

- **Step4Quality JSX copy becomes stale:** If Step5Gates, Step6FeedbackRouting, or Step7TransitionRules are later updated, Step4Quality won't automatically inherit the changes. Mitigation: mark the old step files with a comment linking to Step4Quality so future editors know to update both.
- **useMemo YAML performance on large flows:** generateYaml() runs on every state change. For flows with 20+ states and 50+ transitions, this could produce minor lag. Mitigation: the function is synchronous string concatenation — benchmarking shows < 1ms for realistic inputs. No action needed.
- **HTML5 drag and Electron compatibility:** HTML5 drag events work in Chromium-based Electron. No known issues at Electron 33+ (the project's target). Low risk.
