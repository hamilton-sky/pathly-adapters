# TEST_FAILURES — studio-visual-flow-builder

Verified: 2026-05-19
Verify command: `cd studio && npm.cmd run typecheck` — PASS (0 errors)
Method: static code analysis of implementation files

---

## Test Plan

### Story S1: Existing YAML renders as a connected graph

  Criterion: `transitions` entries render as visible React Flow edges.
  Test: flowToGraph.ts iterates `data.transitions` and pushes Edge objects (lines 73–94)
  Status: PASS

  Criterion: State nodes expose valid source and target handles.
  Test: StateNode.tsx renders `<Handle type="target">` and `<Handle type="source">` (lines 27–64)
  Status: PASS

  Criterion: Switching between flow files reinitializes graph nodes and edges from the selected YAML.
  Test: useFlowGraph.ts useEffect checks `data.flow !== flowIdRef.current` and calls setNodes/setEdges (lines 42–51)
  Status: PASS

  Criterion: Existing YAML files do not lose data when opened in Visual view.
  Test: FlowYaml type includes `storage_path` and `feedback_routing` (types/index.ts lines 78–79). flowToGraph spreads FlowYaml via useFlowGraph onChange calls. useFlowFile reads raw YAML and parses via js-yaml, preserving all keys.
  Status: PASS

---

### Story S2: Visual graph changes update canonical YAML data

  Criterion: Creating a canvas edge adds a transition to the canonical flow data.
  Test: useFlowGraph.ts handleConnect calls onChange with updated transitions (lines 53–68)
  Status: PASS

  Criterion: Duplicate transitions are ignored.
  Test: useFlowGraph.ts line 62: `if (!existing.includes(target))` guards the onChange call
  Status: PASS

  Criterion: Graph layout changes do not accidentally mutate flow semantics.
  Test: ReactFlow node position changes go through `onNodesChange` which is wired to React Flow internal state only; FlowYaml data is never updated by position changes.
  Status: PASS

  Criterion: Dirty-state tracking works after visual edits.
  Test: handleVisualChange in useFlowFile.ts line 108 calls `markDirty(selectedItem.path)` on every visual change.
  Status: PASS

---

### Story S3: Users can drag skills and agents from the library

  Criterion: Skill and agent rows expose drag data.
  Test: Sidebar.tsx — rows with `section.type === 'skill' || 'agent'` render a grip icon (line 354) and handleItemDragStart sets PATHLY_DRAG_MIME with canvas payload when dragFromGripRef is true (lines 182–202)
  Status: PASS

  Criterion: Dropping onto an existing state assigns that behavior to the state.
  Test: VisualView/index.tsx handleDrop lines 130–137: if dropped element has `data-id` matching a state, updates agent_map
  Status: PASS

  Criterion: Dropping onto empty canvas creates a new state node with a generated unique state id.
  Test: VisualView/index.tsx lines 139–148: generateUniqueStateId produces a unique id; new state appended to states array
  Status: PASS

  Criterion: The library remains usable as a normal click-to-open file explorer.
  Test: Sidebar.tsx handleItemClick (line 101) is the onClick handler and still fires independently of drag
  Status: PASS

---

### Story S4: Clicking a node opens a real node inspector

  Criterion: Node inspector shows identity, assigned behavior, required artifacts, outgoing transitions, and validation state.
  Test: NodePanel.tsx renders State ID (lines 121–128), Assigned behavior (lines 132–232), Outgoing transitions (lines 234–252), Validation issues (lines 254–271). "Required artifacts" section is absent — no section in NodePanel.tsx displays required artifacts for the assigned skill/agent.
  Status: FAIL
  Notes: The acceptance criterion lists "required artifacts" as one of the fields to show. NodePanel does not render a required-artifacts section. The behavior popover only shows skill/agent name. No artifact requirements from the behavior's frontmatter are surfaced.

  Criterion: Assigned behavior can be selected from known skills and agents.
  Test: NodePanel.tsx popover builds a filtered list from sections.Skills and sections.Agents (lines 30–34), with keyboard navigation and click selection
  Status: PASS

  Criterion: Invalid node fields show inline errors.
  Test: NodePanel.tsx lines 114 and 254–271: nodeIssues filtered from validationIssues and rendered with color coding
  Status: PASS

  Criterion: Changes update canonical flow data and dirty-state tracking.
  Test: onAgentChange → handleAgentChange (useFlowGraph.ts line 79) → onChange → handleVisualChange → markDirty
  Status: PASS

---

### Story S5: Clicking an edge opens transition configuration

  Criterion: Edge inspector shows source, target, label, conditions, and transition actions.
  Test: EdgePanel.tsx renders source→target header, default/on_artifact/on_content/decide condition sections, and transition_actions list
  Status: PASS

  Criterion: Adding a transition action updates `transition_actions`.
  Test: handleAddTransitionAction in useFlowGraph.ts lines 99–109 uses SOURCE->TARGET key format and calls onChange
  Status: PASS

  Criterion: Artifact gates map back to supported flow YAML structures.
  Test: EdgePanel.tsx submitAddCondition handles on_artifact (artifact name keyed), on_content (file+contains array entry), decide (question+options)
  Status: PASS

  Criterion: Validation catches unsupported or incomplete edge config.
  Test: validateFlow.ts validates transition_rules targets, on_artifact targets, on_content targets, decide targets, and transition_actions key format
  Status: PASS

---

### Story S6: YAML preview remains synchronized and safe

  Criterion: YAML preview serializes from the canonical graph model.
  Test: useFlowFile.ts handleTabSwitch lines 79–81: switching to yaml tab serializes flowData via jsYaml.dump and sets syncContent
  Status: PASS

  Criterion: Direct YAML edits parse back into the graph only when valid.
  Test: YamlView/index.tsx EditorView.updateListener (lines 42–55): parses on every change, calls onParsed only on success; on error sets parseError and calls onParseError without updating graph
  Status: PASS

  Criterion: Invalid YAML shows parse errors without discarding the last valid graph.
  Test: useFlowFile.ts lastValidFlowDataRef (line 45) preserves last valid parse; handleTabSwitch (lines 92–100) falls back to lastValidFlowDataRef when switching to visual with invalid YAML; parse error banner in YamlView (lines 89–92)
  Status: PASS

  Criterion: Save writes the selected flow file only after validation passes or warning approval is explicit.
  Test: YamlView Save button is disabled when parseError is truthy (lines 96–100). However, validateFlow is NOT called before YamlView Save — the button only gates on YAML parse validity, not on flow semantic validation (missing states, broken transitions, etc.). The Export button in VisualView correctly gates on validateFlow errors, but the YAML tab's own Save does not.
  Status: FAIL
  Notes: The criterion says "Save writes... only after validation passes or warning approval is explicit." YamlView Save is gated on YAML parse validity but NOT on validateFlow semantic errors. A flow with missing states, orphaned transitions, or unknown behaviors can be saved directly from YAML view without any warning. The Export path in VisualView correctly implements the validation gate (hasExportErrors disabled, hasExportWarnings requires modal confirmation), but the same gate is absent on YamlView's Save button.

---

### Story S7: Users can export approved flows

  Criterion: Export is disabled until required validation passes.
  Test: VisualView/index.tsx line 151: `const hasExportErrors = validationIssues.some((i) => i.level === 'error')`. Export button has `disabled={hasExportErrors}` (line 242).
  Status: PASS

  Criterion: Export targets are shown as explicit choices.
  Test: VisualView/index.tsx lines 215–231: select element with three options: pathly-package, claude-code, codex
  Status: PASS

  Criterion: The canonical flow YAML is copied or written to the correct target path for each supported target.
  Test: exportPaths.ts resolveExportPath returns correct paths for all three targets. doExport calls writeFile with the resolved path.
  Status: PASS

  Criterion: Host-specific export warnings are shown before export.
  Test: VisualView/index.tsx lines 178–180: when hasExportWarnings is true, showConfirmModal is set. Modal message (line 296): "This flow has validation warnings. Export anyway?" — this is a generic warnings modal, not host-specific. No per-target warnings (e.g. "Claude Code requires X", "Codex requires Y") are shown.
  Status: FAIL
  Notes: The criterion specifies "host-specific export warnings." The implementation shows one generic confirmation modal for any validation warning, regardless of target. There is no logic that inspects which export target was selected and generates warnings tailored to that target's requirements. This is a gap — the modal fires for flow-level warnings but does not check target-specific constraints.

---

### Story S8: Library items behave as reuse primitives, not editing targets

  Criterion: Clicking a skill, agent, or template opens the existing Editor in `preview` tab by default.
  Test: Editor/index.tsx lines 87–89: `const defaultTab = (type === 'skill' || type === 'agent' || type === 'template') ? 'preview' : 'edit'`; setTab(defaultTab)
  Status: PASS

  Criterion: An explicit user action (button or context menu) is required to switch the previewed item into edit mode.
  Test: Editor/index.tsx lines 159–161: "Edit source" button rendered only when `isPreviewDefault && tab === 'preview'`; clicking it sets tab to 'edit'. No implicit transition to edit mode.
  Status: PASS

  Criterion: Frontmatter is shown read-only while previewing.
  Test: Editor/index.tsx passes ConfigForm with `compact={tab !== 'edit'}` (line 178). In compact mode (preview/split), ConfigForm renders name as static text and adapter chips (ConfigForm.tsx lines 70–78). However, the adapter chips in compact mode retain their `onClick` handler (`onClick={() => toggleAdapter(adapter, !active)}`, line 59) — clicking an adapter chip while in preview mode will toggle it and call onChange, which calls markDirty. The compact view does NOT suppress mutations.
  Status: FAIL
  Notes: ConfigForm compact mode shows adapter chips with live onClick handlers. Toggling an adapter chip in preview mode fires handleConfigChange → markDirty, mutating the item. The criterion requires frontmatter to be "shown read-only while previewing." The compact display of name-only text is read-only, but adapter chips remain interactive and can mutate frontmatter without switching to edit mode.

  Criterion: Auto-save is suppressed while previewing.
  Test: Editor/index.tsx handleBodyChange line 130: `if (tab === 'preview') return` — exits before scheduling setTimeout auto-save
  Status: PASS

  Criterion: Flows and workspace artifacts (debugs, explorations) continue to open in their authoring surface on click.
  Test: Sidebar.tsx handleItemClick line 103: `setActivePanel(item.type === 'flow' ? 'flow' : 'editor')`. Flows route to 'flow' panel; debugs/explorations route to 'editor' as before.
  Status: PASS

---

## Summary

| Story | PASS | FAIL | NOT COVERED |
|-------|------|------|-------------|
| S1    | 4    | 0    | 0           |
| S2    | 4    | 0    | 0           |
| S3    | 4    | 0    | 0           |
| S4    | 3    | 1    | 0           |
| S5    | 4    | 0    | 0           |
| S6    | 3    | 1    | 0           |
| S7    | 3    | 1    | 0           |
| S8    | 4    | 1    | 0           |

**Total: 29 PASS, 4 FAIL, 0 NOT COVERED**

---

## FAIL Details

### FAIL-1: S4.C1 — Node inspector missing "required artifacts" section
- **File:** `studio/src/renderer/src/components/FlowEditor/VisualView/NodePanel.tsx`
- **Expected:** Inspector shows required artifacts for the assigned behavior (skill/agent)
- **Actual:** NodePanel shows State ID, Assigned behavior, Outgoing transitions, Validation issues. No section reading or displaying required artifacts from the behavior definition.

### FAIL-2: S6.C4 — YamlView Save not gated on semantic validation
- **File:** `studio/src/renderer/src/components/FlowEditor/YamlView/index.tsx`
- **Expected:** Save writes only after validation passes or warning approval is explicit
- **Actual:** Save button is disabled only when `parseError` is truthy (YAML syntax error). `validateFlow` is never called in the YamlView path. Semantically invalid flows (missing states, broken transitions, missing behaviors) can be saved directly without warning.
- **Comparison:** VisualView correctly implements `hasExportErrors`/`hasExportWarnings` gating for Export. Same pattern is absent for YAML Save.

### FAIL-3: S7.C4 — Export warning modal is generic, not host-specific
- **File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx`
- **Expected:** Host-specific export warnings are shown before export (e.g. target-specific requirements)
- **Actual:** One generic modal: "This flow has validation warnings. Export anyway?" — no per-target logic inspects which export target was chosen or what that target requires.

### FAIL-4: S8.C3 — Frontmatter adapter chips are interactive in preview mode
- **File:** `studio/src/renderer/src/components/Editor/ConfigForm.tsx` (compact mode, line 59)
- **Expected:** Frontmatter is shown read-only while previewing
- **Actual:** ConfigForm compact mode shows adapter chips that retain `onClick={() => toggleAdapter(...)}`. Clicking a chip in preview mode mutates frontmatter and calls markDirty. The `compact` prop controls layout but does not suppress interactivity.
