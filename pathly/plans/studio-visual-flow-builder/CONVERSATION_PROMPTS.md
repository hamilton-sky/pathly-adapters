# studio-visual-flow-builder - Conversation Guide

Split into 4 conversations. Each produces runnable, testable code. After each conversation, commit your changes before starting the next.

---

## Conversation 1: Repair Graph Rendering And Canonical Sync (Phases 1-3)

**Stories delivered:** S1, S2

**Prompt to paste:**

```text
Read pathly/plans/studio-visual-flow-builder/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-visual-flow-builder Conversation 1 (Phases 1-3) from pathly/plans/studio-visual-flow-builder/IMPLEMENTATION_PLAN.md.

Before editing anything: glob/read the live repo to confirm every file path in FEATURE_INDEX.md for Conversation 1 exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

Scope:
- Phase 1: add React Flow handles and compact connection affordances to StateNode.
- Phase 2: resync useFlowGraph nodes and edges when selected flow data changes.
- Phase 3: make flowToGraph deterministic enough for stable visual rendering and preserve canonical semantics.

Architectural rules to observe:
- The YAML flow object remains the semantic source for states, transitions, agent_map, transition_rules, and transition_actions.
- Canvas positions are UI state only unless an explicit layout persistence design is added later.
- Do not introduce a new flow schema in this conversation.

Do NOT touch drag/drop library behavior, inspector redesign, YAML export, terminal panes, monitor, setup, installer, or backend MCP code yet.

Verify: cd studio; npm run typecheck
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 1-3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Existing flow YAML files render as connected React Flow graphs, and canvas connections update transitions.
**Files touched:** `StateNode.tsx`, `useFlowGraph.ts`, `flowToGraph.ts`, optionally `useFlowFile.ts` if required for sync.

---

## Conversation 2: Add Drag/Drop Library Behavior (Phases 4-6)

**Stories delivered:** S3

**Prompt to paste:**

```text
Read pathly/plans/studio-visual-flow-builder/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-visual-flow-builder Conversation 2 (Phases 4-6) from pathly/plans/studio-visual-flow-builder/IMPLEMENTATION_PLAN.md.

Before editing anything: verify Conversation 1 is complete in PROGRESS.md and glob/read the live repo to confirm every Conversation 2 path in FEATURE_INDEX.md exists.

Scope:
- Phase 4: add host-neutral draggable library item types.
- Phase 5: make skill and agent sidebar rows draggable while preserving click-to-open behavior.
- Phase 6: make VisualView accept dropped library items, assigning behavior to an existing node or creating a new state on empty canvas.

Architectural rules to observe:
- Drag/drop payloads should be small and stable: item type, name, path, and behavior kind.
- Dropping a skill or agent should update canonical flow data and mark the selected file dirty.
- Keep workspace plan rows out of drag/drop scope.

Do NOT touch node inspector redesign, edge inspector redesign, export targets, installer, MCP, or plan/monitor features yet.

Verify: cd studio; npm run typecheck
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 4-6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Skills and agents can be dragged from the sidebar into the flow canvas.
**Files touched:** `types/index.ts`, `Sidebar.tsx`, `VisualView/index.tsx`, optionally `useProjectFiles.ts`.

---

## Conversation 3: Inspector And Validation UX (Phases 7-9)

**Stories delivered:** S4, S5

**Prompt to paste:**

```text
Read pathly/plans/studio-visual-flow-builder/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-visual-flow-builder Conversation 3 (Phases 7-9) from pathly/plans/studio-visual-flow-builder/IMPLEMENTATION_PLAN.md.

Before editing anything: verify Conversations 1 and 2 are complete in PROGRESS.md and glob/read the live repo to confirm every Conversation 3 path in FEATURE_INDEX.md exists.

Scope:
- Phase 7: replace the basic node panel with a docked node inspector for identity, assigned behavior, outgoing transitions, and validation.
- Phase 8: replace the basic edge panel with a transition inspector for conditions, artifact gates, and actions.
- Phase 9: show validation issues in the visual editor before save/export.

Architectural rules to observe:
- Use the docked inspector behavior described in DESIGN.md.
- Keep YAML structures compatible with existing flow files.
- Validation messages should be short, local, and actionable.

Do NOT touch export file writes, installer logic, MCP servers, terminal panes, or monitor views yet.

Verify: cd studio; npm run typecheck
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 7-9 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Node and edge clicks open useful inspectors, and invalid graph states are visible.
**Files touched:** `NodePanel.tsx`, `EdgePanel.tsx`, `VisualView/index.tsx`, `VisualView.styles.ts`.

---

## Conversation 4: YAML Preview And Export Targets (Phases 10-12)

**Stories delivered:** S6, S7

**Prompt to paste:**

```text
Read pathly/plans/studio-visual-flow-builder/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-visual-flow-builder Conversation 4 (Phases 10-12) from pathly/plans/studio-visual-flow-builder/IMPLEMENTATION_PLAN.md.

Before editing anything: verify Conversations 1-3 are complete in PROGRESS.md and glob/read the live repo to confirm every Conversation 4 path in FEATURE_INDEX.md exists.

Scope:
- Phase 10: harden YAML preview/edit sync so invalid YAML does not destroy the last valid graph.
- Phase 11: add explicit export target controls for Pathly package, Claude Code, and Codex.
- Phase 12: add a minimal pathlyApi export helper only if existing filesystem helpers are insufficient.

Architectural rules to observe:
- One canonical flow model feeds all export targets.
- Export target adapters may write host-specific files but must not silently mutate the source graph.
- Export should be disabled or warning-gated when validation fails.

Do NOT touch installer packaging, MCP runtime code, monitor event processing, or unrelated Studio layout polish.

Verify: cd studio; npm run typecheck
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 10-12 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** YAML preview safely round-trips with the graph, and valid flows can be exported to explicit targets.
**Files touched:** `YamlView/index.tsx`, `useFlowFile.ts`, `VisualView/index.tsx`, `pathlyApi.ts`, `types/index.ts`.
