---
name: Architecture Proposal
---
# flow-wizard-redesign - Architecture Proposal

## Problem Statement

The FlowWizard is too long, hides useful feedback until the end, and gives users too little confidence while editing flows.

## Proposed Solution

Keep the YAML format stable, add a Step 0 entry screen, compress the quality-related steps into one accordion-based section, add a live YAML preview, and add confirmable cancel/start-over actions.

## Canonical Step Model

- Step 0: Entry
- Step 1: Name your flow
- Step 2: Define stages
- Step 3: Assign agents
- Step 4: Quality & routing
- Step 5: Review & save

Internal state runs 0-5. The progress indicator shows 5 dots and is hidden on Step 0.

## Key Decisions

- Keep the wizard local to `studio/src/renderer/src/components/FlowWizard/`.
- Use `useMemo` for reactive YAML generation.
- Inline the merged Quality accordion content instead of nesting the old step components.
- Use HTML5 drag events for Step 2 reordering.
- Keep confirmation dialogs inline inside the footer.

## Risks

- Copying the old quality-step JSX into one accordion component can drift if the source steps change later.
- Draft serialization adds a persistence path that must be kept in sync with the main flow state.
- HTML5 drag remains a Chromium-native compromise, not a mobile-first solution.
