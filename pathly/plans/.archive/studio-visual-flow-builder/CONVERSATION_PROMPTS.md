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
- `transition_rules` is keyed by source state, matching `src/pathly_data/core/flows/*.flow.yaml` and `src/pathly_orchestrator/fsm.py`. Do not implement the incorrect artifact-keyed shape `{ artifact_name: { source: target } }`.
- Canvas positions are UI state only unless an explicit layout persistence design is added later.
- Do not introduce a new flow schema in this conversation.

Do NOT touch drag/drop library behavior, inspector redesign, YAML export, terminal panes, monitor, setup, installer, or backend MCP code yet.

Verify: cd studio; npm run typecheck
On Windows, use `npm.cmd run typecheck` if the PowerShell `npm.ps1` shim is blocked by execution policy.
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 1-3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Existing flow YAML files render as connected React Flow graphs, and canvas connections update transitions.
**Files touched:** `StateNode.tsx`, `useFlowGraph.ts`, `flowToGraph.ts`, optionally `useFlowFile.ts` if required for sync.

---

## Conversation 2: Reuse-Only Library And Drag/Drop (Phases 4-7)

**Stories delivered:** S3, S8

**Prompt to paste:**

```text
Read pathly/plans/studio-visual-flow-builder/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-visual-flow-builder Conversation 2 (Phases 4-7) from pathly/plans/studio-visual-flow-builder/IMPLEMENTATION_PLAN.md.

Before editing anything: verify Conversation 1 is complete in PROGRESS.md and glob/read the live repo to confirm every Conversation 2 path in FEATURE_INDEX.md exists.

Scope:
- Phase 4: add host-neutral draggable library item types (`PathlyLibraryDragItem`).
- Phase 5: switch the existing Editor's default tab to `preview` for skills/agents/templates and gate edit-mode behind an explicit user action. Suppress auto-save in preview.
- Phase 6: make skill, agent, and template sidebar rows draggable using native HTML5 drag/drop while preserving click-to-open behavior.
- Phase 7: make VisualView accept dropped library items inside a ReactFlowProvider, assigning behavior to an existing node or creating a new state on empty canvas.

Architectural rules to observe:
- Drag/drop payloads should be small and stable: item type, name, path, and behavior kind. Use the MIME key `application/pathly-library-item`.
- Dropping a skill, agent, or template should update canonical flow data and mark the selected file dirty.
- Tree-internal file system drag/drop (reorder, reparent, multi-select, cut/copy/paste) is OUT OF SCOPE for this feature. Do not implement it.
- Drag/drop on workspace plan, debug, or exploration rows is OUT OF SCOPE.
- Editing skills/agents/templates from inside the flow editor is OUT OF SCOPE.

Do NOT touch node inspector redesign, edge inspector redesign, validation UI, export targets, installer, MCP, or plan/monitor features yet.

Verify: cd studio; npm run typecheck
On Windows, use `npm.cmd run typecheck` if the PowerShell `npm.ps1` shim is blocked by execution policy.
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 4-7 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Clicking a skill/agent/template opens preview. Dragging the same row onto the canvas assigns behavior or creates a state.
**Files touched:** `types/index.ts`, `Editor/index.tsx`, `Sidebar.tsx`, `VisualView/index.tsx`.

---

## Conversation 3: Docked Inspector, Behavior Picker, And Validation (Phases 8-11)

**Stories delivered:** S4, S5

**Prompt to paste:**

```text
Read pathly/plans/studio-visual-flow-builder/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-visual-flow-builder Conversation 3 (Phases 8-11) from pathly/plans/studio-visual-flow-builder/IMPLEMENTATION_PLAN.md.

Before editing anything: verify Conversations 1 and 2 are complete in PROGRESS.md and glob/read the live repo to confirm every Conversation 3 path in FEATURE_INDEX.md exists.

Scope:
- Phase 8: convert the inspector from an absolute overlay into a docked third pane inside `VisualView`.
- Phase 9: replace the basic node panel with a docked node inspector; implement the behavior picker as a popover with z-index 40 per DESIGN.md.
- Phase 10: replace the basic edge panel with a transition inspector for conditions, artifact gates, and actions (edit + delete) using the real state-keyed `transition_rules` schema.
- Phase 11: create `utils/validateFlow.ts` and surface issues as inline badges on nodes, edge color changes, and inspector field errors with `role="alert"` and `aria-live="polite"`.

Architectural rules to observe:
- Use the docked layout, z-index scale, behavior picker spec, and validation rules in DESIGN.md.
- Keep YAML structures compatible with existing flow files; do not invent a new schema.
- `transition_rules` must stay state-keyed: `transition_rules[SOURCE].on_artifact[ARTIFACT] = TARGET`, `transition_rules[SOURCE].default = TARGET`, and optional `on_content` / `decide` entries follow `src/pathly_orchestrator/fsm.py`.
- Validation messages should be short, local, and actionable. No banners.
- State rename is OUT OF SCOPE; show state id as read-only with a hint pointing to YAML view.

Do NOT touch export file writes, installer logic, MCP servers, terminal panes, or monitor views yet.

Verify: cd studio; npm run typecheck
On Windows, use `npm.cmd run typecheck` if the PowerShell `npm.ps1` shim is blocked by execution policy.
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 8-11 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Node and edge clicks open useful docked inspectors, behavior picker popover works, and invalid graph states show inline badges and field errors.
**Files touched:** `VisualView/index.tsx`, `VisualView.styles.ts`, `NodePanel.tsx`, `EdgePanel.tsx`, `StateNode.tsx`, `utils/validateFlow.ts` (new).

---

## Conversation 4: YAML Preview And Export Targets (Phases 12-14)

**Stories delivered:** S6, S7

**Prompt to paste:**

```text
Read pathly/plans/studio-visual-flow-builder/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-visual-flow-builder Conversation 4 (Phases 12-14) from pathly/plans/studio-visual-flow-builder/IMPLEMENTATION_PLAN.md.

Before editing anything: verify Conversations 1-3 are complete in PROGRESS.md and glob/read the live repo to confirm every Conversation 4 path in FEATURE_INDEX.md exists.

Scope:
- Phase 12: harden YAML preview/edit sync so invalid YAML does not destroy the last valid graph.
- Phase 13: add explicit export target controls for Pathly package, Claude Code, and Codex per the path resolver in ARCHITECTURE_PROPOSAL.md. Disable export while validation has errors; gate warnings behind a confirmation modal.
- Phase 14: add a minimal `pathlyApi` export helper only if `window.pathly.fs.write` cannot create parent directories. The current IPC write path already creates parent dirs, so this is expected to be a no-op.

Architectural rules to observe:
- One canonical flow model feeds all export targets via `resolveExportPath(target, ctx)`.
- Export target adapters may write host-specific files but must not silently mutate the source graph.
- Export should be disabled or warning-gated when validation fails.

Do NOT touch installer packaging, MCP runtime code, monitor event processing, or unrelated Studio layout polish.

Verify: cd studio; npm run typecheck
On Windows, use `npm.cmd run typecheck` if the PowerShell `npm.ps1` shim is blocked by execution policy.
After done, update pathly/plans/studio-visual-flow-builder/PROGRESS.md phases 12-14 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** YAML preview safely round-trips with the graph, and valid flows can be exported to explicit targets.
**Files touched:** `YamlView/index.tsx`, `useFlowFile.ts`, `VisualView/index.tsx`, `pathlyApi.ts`, `types/index.ts`.
