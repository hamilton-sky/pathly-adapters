# studio-visual-flow-builder - Edge Cases

## Category 1: Graph And YAML Drift

### EC-1.1: Selected flow changes but graph remains stale

- **Trigger:** User selects a different flow after viewing another YAML file.
- **Current behavior:** React Flow state can remain initialized from older data if hooks do not resync.
- **Expected behavior:** Nodes and edges rebuild from the selected flow.
- **Handled in:** Phase 2 / Conv 1.

### EC-1.2: YAML parse error after valid graph load

- **Trigger:** User edits YAML into invalid syntax.
- **Current behavior:** The parsed flow can become null or visual mode can be blocked without preserving prior context.
- **Expected behavior:** Show parse error and keep last valid graph visible.
- **Handled in:** Phase 10 / Conv 4.

## Category 2: Invalid Flow References

### EC-2.1: Transition references missing state

- **Trigger:** YAML contains a transition target not listed in `states`.
- **Expected behavior:** Render recoverably when possible and show validation issue.
- **Handled in:** Phase 3 and Phase 9.

### EC-2.2: Behavior reference is missing

- **Trigger:** `agent_map` references a skill or agent not found in the loaded library.
- **Expected behavior:** Show a warning and allow explicit external/unknown status.
- **Handled in:** Phase 7 and Phase 9.

## Category 3: Drag/Drop Ambiguity

### EC-3.1: Drop lands between nodes

- **Trigger:** User drops a skill or agent onto empty canvas.
- **Expected behavior:** Create a new state node with a generated unique state id.
- **Handled in:** Phase 6 / Conv 2.

### EC-3.2: Drop lands on an existing node

- **Trigger:** User drops a skill or agent over a node.
- **Expected behavior:** Assign behavior to that state instead of creating a duplicate state.
- **Handled in:** Phase 6 / Conv 2.

## Category 4: Export Safety

### EC-4.1: Target path is missing

- **Trigger:** User exports to a host target that has no configured destination.
- **Expected behavior:** Show an actionable error and do not silently write elsewhere.
- **Handled in:** Phase 11 and Phase 12 / Conv 4.

### EC-4.2: Export with warnings

- **Trigger:** Flow has non-fatal validation warnings.
- **Expected behavior:** Require explicit user approval before export.
- **Handled in:** Phase 11 / Conv 4.

## Category 5: Library Reuse vs Edit Ambiguity

### EC-5.1: Click on a library skill, agent, or template

- **Trigger:** User clicks a skill, agent, or template row in the sidebar.
- **Current behavior:** The Editor opens in `edit` mode and auto-saves on change.
- **Expected behavior:** The Editor opens in `preview` mode by default. Edit mode requires an explicit user action. Auto-save is suppressed in preview.
- **Handled in:** Phase 5 / Conv 2.

### EC-5.2: Drag start vs click conflict

- **Trigger:** User starts dragging a sidebar library row, then releases without moving past the drag threshold.
- **Expected behavior:** Treat as click. Both behaviors coexist; drag wins only after the browser's movement threshold.
- **Handled in:** Phase 6 / Conv 2.

### EC-5.3: Editing a library item that is referenced by an open flow

- **Trigger:** User opens a flow that references `commit` in `agent_map`, then explicitly switches the referenced skill into edit mode.
- **Expected behavior:** Edit mode is allowed. The flow editor's behavior picker continues to show the skill regardless of edit state. Validation does not warn unless the skill file is deleted or renamed.
- **Handled in:** Phase 5 and Phase 11 / Conv 2-3.

## Known Limitations

- This plan does not implement VS Code-style file tree drag/drop (reorder, reparent, multi-select, cut/copy/paste). Tree-internal FS operations are deferred to a separate future feature.
- This plan does not implement drag/drop from the OS filesystem onto the canvas.
- This plan does not implement state rename from the inspector. YAML view remains the rename path.
- This plan does not persist manual graph node positions to YAML.
- This plan does not redesign Terminal, Monitor, TopBar, PlanBoard, Settings, HomeScreen, SetupScreen, or FlowWizard.
