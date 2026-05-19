# Pipeline Flow — studio-visual-flow-builder
Date: 2026-05-19 | Branch: master

## FSM State Sequence

| # | State | Notes |
|---|-------|-------|
| 1 | STORMING | Skipped (user chose path 2 — skip discovery) |
| 2 | PLANNING | Skipped via ff |
| 3 | DESIGNING | Skipped via ff |
| 4 | BUILDING | Conv 1 → Conv 2 → Conv 3 → Conv 4 |
| 5 | REVIEWING | Conv 4 only (lite rigor; Convs 1-3 auto-skipped) |
| 6 | TESTING | All criteria PASS after 1 fix cycle |
| 7 | RETRO | Complete |
| 8 | DONE | — |

## Conversation Traces

| Conv | Stories | Result | Notes |
|------|---------|--------|-------|
| 1 | S1, S2 | DONE | StateNode handles, useFlowGraph rebuild, flowToGraph stabilize |
| 2 | S3, S8 | DONE | Drag/drop types, Editor preview default, Sidebar drag, VisualView drop |
| 3 | S4, S5 | DONE | Docked inspector, NodePanel, EdgePanel, validateFlow, zIndex |
| 4 | S6, S7 | DONE | YamlView last-valid, export controls, exportPaths utility |

## Feedback Loop Table

| Conv | File | Rounds | Resolution |
|------|------|--------|-----------|
| 4 | REVIEW_FAILURES.md | 2 | Round 1: FlowExportTarget values, FlowValidationIssue fields, resolveExportPath colocation. Round 2: FlowValidationScope values, dead onAddRule prop. Both resolved by builder. |
| — | TEST_FAILURES.md | 1 | 4 failures: required-artifacts section, YAML save bypass, generic export modal, ConfigForm chips in preview. All resolved by builder in one pass. |
