# Retrospective — studio-visual-flow-builder
Date: 2026-05-19 | Branch: master | Rigor: lite

## What Went Well

- **Clear phased architecture**: Breaking the feature into 14 focused phases with explicit "done when" criteria made implementation predictable. Each conversation built on prior conversations without rework.
- **Story-first scoping**: User stories with acceptance criteria and edge cases caught ambiguities early. Reviewer feedback on Conv 4 was focused and addressable because the model was well-defined upfront.
- **Single-pass tester validation**: Despite having no automated test framework, static analysis + typecheck found 4 failures on the first pass. All fixed in one builder pass — tight feedback loop.
- **State-keyed transition_rules pattern**: Using the canonical YAML schema (state-keyed, not edge-keyed) as the source of truth from the start meant visual edits naturally mapped back to serialization — no impedance mismatch.
- **Colocation discipline**: Keeping validateFlow.ts, exportPaths.ts, and zIndex.ts colocated in their use sites made the code graph easier to reason about and reduced import thrashing.

## Harder Than Expected

- **Validation scope modeling**: FlowValidationScope required two reviewer passes. The first missed the distinction between node-level rules (required artifacts, behavior exists) and export-level rules. Naming precision would have helped earlier.
- **No test harness friction**: Verification relied entirely on static analysis + typecheck. The tester had to manually exercise the UI to find the 4 failures. Larger features with more business logic will need automated tests.
- **Export modal genericity**: The initial design made export targets too generic. It took reviewer feedback to clarify that each target (Pathly, Claude Code, Codex) needs distinct paths and validation rules.
- **ConfigForm chip interactivity in preview mode**: The tester caught that chips remained interactive in preview when they should be read-only. A missed edge case in Story S8 — preview mode requirements need explicit typecheck or snapshot tests.

## Do Differently

- **FlowValidationScope should be introduced with a matrix document**: Before coding, create a 2D grid of (validation subject × validation rule) mapping what gets checked where. This prevents review surprises about scope boundaries.
- **Require a target-export mapping document for multi-host features**: Explicitly document each target's required files, naming conventions, and validation gates *before* implementation.
- **Automate preview-mode edge cases**: Use visual regression snapshots or E2E tests for UI modes (preview, read-only, interactive).
- **Dead props should cause typecheck failures**: The `onAddRule` prop that was left dangling should have been flagged by ESLint unused-prop detection. Add a pre-commit hook.
- **Schema-first validation**: Define validateFlow logic *before* UI code. Build the validator as a testable library, then wire UI to it.

## Lessons

1. **State-keyed data models reduce visual-to-canonical mapping bugs.** Build the canonical schema first; the visual layer adapts to it.

2. **Scope boundaries must be explicit in naming and docs.** Future features should name scope levels to be unambiguous before implementation begins.

3. **Multi-host export requires a lookup table, not inference.** Build `{ target: { path, requiredFields, warnings } }` as a config constant and reference it in validation.

4. **Preview mode is a distinct state machine.** Define what's disabled, what's read-only, what intercepts clicks — all declaratively before rendering.

5. **Without tests, verification scales to code review only.** Start with validation unit tests, not end-to-end coverage. Business logic (validation) is the highest-value test target.
