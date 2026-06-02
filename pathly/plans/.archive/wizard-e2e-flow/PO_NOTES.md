---
name: PO Notes
generated: auto (no-interactive)
---
# wizard-e2e-flow — Product Owner Notes

## Feature Summary

End-to-end tests for the FlowWizard component as redesigned in `flow-wizard-redesign`.
The wizard has 6 steps (0-5): entry screen, name, define stages, transitions, agents, quality+review.
Tests must cover the complete wizard journey: open → template/blank → fill fields → navigate → save/cancel.

## Problem Statement

The FlowWizard was redesigned with substantial new behavior: Step 0 entry, template pre-population,
draft save/resume, live YAML preview, cancel/start-over confirmation dialogs, and extended validation.
None of these flows have automated tests. A regression in any of them is invisible until manual QA.

## Scope

### In scope
- Happy path: open wizard, select a template, fill name, advance through all steps, save YAML
- Happy path: blank start, single state, skip optional fields, save
- Template pre-population: selecting each of the 3 templates seeds correct states/transitions
- Step 0 navigation: Escape closes wizard; overlay click closes wizard; Back from Step 1 returns to Step 0
- Validation: Step 1 name field shows error on empty/invalid submit; Step 2 warns on 2+ states with no transitions
- Cancel confirmation: Cancel on step >= 1 shows dialog; Discard closes wizard; Keep editing dismisses dialog
- Start over: button visible on step >= 1; confirmation resets to Step 0 with cleared state
- Draft save/resume: wizard saves draft on step advance; Step 0 shows resume card when draft exists; resuming restores state + step
- Live YAML preview: YAML pane renders on steps 1-5 and matches expected output

### Out of scope
- IPC / main-process file I/O (mock `pathlyApi` at the test layer)
- FlowEditor, ChatPanel, or other unrelated components
- Performance benchmarks

## User Stories (abbreviated for planner)

1. As a QA author, I can run a single test command that exercises every wizard step for both happy paths
2. As a QA author, I can verify each template seeds the correct wizard state
3. As a QA author, I can verify the cancel confirmation dialog behavior on each step
4. As a QA author, I can verify start-over resets state fully
5. As a QA author, I can verify draft save detects an existing draft and offers resume
6. As a QA author, I can verify YAML preview content matches the generated output

## Acceptance Criteria

- Tests use the same test framework already in the project (Vitest + React Testing Library, no Playwright)
- `pathlyApi` (readFile, writeFile) is mocked — no real disk I/O in tests
- All tests pass with `npm test` from the repo root
- TypeScript compiles (`npm run typecheck`) with no new errors after adding tests
- No new npm production dependencies; test-only devDeps are acceptable if already present

## Constraints

- Test files live alongside the component: `studio/src/renderer/src/components/FlowWizard/`
- No inline styles in any test helper components
- Electron WebGPU/WebLLM must not be introduced

## Open Questions

- Does `userEvent` from `@testing-library/user-event` need to be installed, or is `fireEvent` sufficient?
  (Check existing test files for current pattern before deciding.)
