# Review Failures — Studio AI Chat — Conv 8

## Conversation
Conv 8 — git diff HEAD~2 HEAD

## Violations

### V1 — Raw `setState` bypasses named store actions
**File:** `studio/src/renderer/src/components/ChatPanel/StepQueue.tsx:23`
**Rule:** Architecture Rule 4 — "Side effects that mutate store state belong to the component layer" (the corollary: mutations must go through named store actions, not raw `setState`, to keep state transitions auditable and testable)
**Description:** `useAutomationStore.setState({ steps: ... })` is called directly in `handleApprove`'s error path, bypassing all named mutators. The store has no `setStepError(id, message)` action, so the developer reached for raw `setState`. This makes the error transition invisible to any middleware, devtools replay, or persist partializer.

### V2 — `AutomationStep` is a cross-layer type defined in the store, not in `src/types/`
**File:** `studio/src/renderer/src/store/automationStore.ts:6–17`
**Rule:** Architecture Rule 3 — "Types that cross layers live in `src/types/chat.ts`. Both store and lib import from `types/`, never from each other."
**Description:** `AutomationStep` and `AutomationStepStatus` are consumed by both `store/automationStore.ts` and `components/ChatPanel/index.tsx` (via inline `import()`). They should be defined in `src/types/` (e.g. `types/automation.ts`) and imported from there by both the store and the component.

### V3 — Redundant dynamic import of already-statically-imported module
**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx:176`
**Rule:** Correctness — `loadSkills` is already imported statically at line 12; the dynamic `import('../../lib/skillsManifest')` inside the catch block re-imports the same module under an alias `_ls` to avoid a naming collision that doesn't exist (the static `loadSkills` is in scope and usable directly).
**Description:** `const { loadSkills: _ls } = await import('../../lib/skillsManifest')` duplicates the static import and is never necessary; the existing `loadSkills` on line 12 is in scope and should be called directly.

## Warnings (non-blocking)

### W1 — `_extract_labels` does not guard against non-string label values
**File:** `src/pathly_orchestrator/chat_agent.py:30–36`
**Concern:** `el.get("label", "")` returns the raw value from the schema dict. If the schema contains a non-string label (e.g. a number), `if label:` passes but subsequent `.lower()` calls in `_generate_steps` will raise `AttributeError`. A `isinstance(label, str)` guard is missing.

### W2 — `handleStepByStep` calls `getState()` from a synchronous handler
**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx:295–297`
**Concern:** `useAutomationStore.getState().setMode(...)` and `.setStatus(...)` are called in a synchronous click handler where the hook-selected `setMode`/`setStatus` selectors are already available. This is not a layer violation but is inconsistent with the rest of the component's pattern.
