# studio-visual-flow-builder - Implementation Plan

## Overview

This feature makes Pathly Studio's visual flow editor the primary authoring surface. It repairs connected graph rendering from YAML, adds drag/drop for skills and agents, replaces basic panels with an inspector, validates the canonical flow model, and adds YAML preview/export flows for Pathly, Claude Code, and Codex.

## Layer Architecture

```
Sidebar library       ->  Flow graph model       ->  YAML/export outputs
skills/agents/files       states/transitions         pathly package
templates/flows           node/edge config           Claude Code/Codex

React components      ->  hooks/types/utils      ->  pathlyApi/fs writes
```

## Phases

### Phase 1: Restore connected graph rendering <- Conversation: 1

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` - MODIFY: add React Flow source and target handles, compact connection affordances, and invalid-state badges.
**Done when:** Existing YAML transitions can attach visually to state nodes.
**Delivers stories:** S1
**Depends on:** Existing React Flow setup.
**Enables:** Canvas edge creation and edge inspector behavior.
**Details:**
Add `Handle` components from `reactflow`. Keep the node compact and consistent with current Studio styling. Handles should be visible enough for discovery but not dominate the node.
**Verify:** `cd studio; npm run typecheck`

### Phase 2: Resync graph state when selected flow changes <- Conversation: 1

**File:** `studio/src/renderer/src/components/FlowEditor/hooks/useFlowGraph.ts` - MODIFY: rebuild nodes and edges when `data` or selected flow changes, without wiping in-progress edits from the current file.
**Done when:** Switching from `debug.flow.yaml` to another flow shows that flow's own nodes and edges.
**Delivers stories:** S1
**Depends on:** Phase 1.
**Enables:** Stable visual editing across flow files.
**Details:**
Use React Flow setters to rehydrate nodes and edges from `flowToGraph(data, t)` when the flow identity changes. Avoid stale closures by keeping `dataRef` current. Preserve semantic edits through `onChange`.
**Verify:** `cd studio; npm run typecheck`

### Phase 3: Keep visual graph edits canonical <- Conversation: 1

**File:** `studio/src/renderer/src/components/FlowEditor/utils/flowToGraph.ts` - MODIFY: make YAML-to-graph conversion deterministic, label edges from actual transition metadata, and tolerate malformed references.
**File:** `studio/src/renderer/src/types/index.ts` - MODIFY: extend `FlowYaml` to include `storage_path?: string` and `feedback_routing?: Record<string, string>` so existing YAML keys round-trip without loss.
**Done when:** Visual connect actions add transitions and YAML preview/save reflects those transitions. `debug.flow.yaml` round-trips through visual edit and YAML serialize without losing `storage_path` or `feedback_routing`.
**Delivers stories:** S2
**Depends on:** Phase 2.
**Enables:** Drag/drop and inspector edits to write through the same model.
**Details:**
Keep node position layout deterministic (column layout `i * 220` is fine for now). Use stable edge ids of form `${source}__${target}` so the same edge across re-renders has the same id. Label edges from the runtime schema:
- `transition_rules[source].default === target` -> `default`
- `transition_rules[source].on_artifact[artifactName] === target` -> `artifactName`
- `transition_rules[source].on_content[]` entries whose `next` is `target` -> their file/contains/regex summary
- `transition_rules[source].decide.options[option] === target` -> the option label
Tolerate transitions whose source or target is missing from `states` by skipping the edge and emitting a validation issue (Phase 11 surfaces it). Do not drop unknown YAML keys.
**Verify:** `cd studio; npm run typecheck`

### Phase 4: Add draggable library metadata <- Conversation: 2

**File:** `studio/src/renderer/src/types/index.ts` - MODIFY: add library item metadata types for draggable skills, agents, templates, and flows.
**Done when:** UI code can distinguish item type, name, path, and behavior kind during a drag/drop event.
**Delivers stories:** S3
**Depends on:** Conversation 1 completed.
**Enables:** Sidebar drag/drop wiring.
**Details:**
Keep types host-neutral. Do not encode export target behavior here.
**Verify:** `cd studio; npm run typecheck`

### Phase 5: Switch library default to read-only preview <- Conversation: 2

**File:** `studio/src/renderer/src/components/Editor/index.tsx` - MODIFY: when `selectedItem.type` is `skill`, `agent`, or `template`, initialize `tab` to `'preview'` and add a gated "Edit" affordance so a flow author does not accidentally land in edit mode.
**File:** `studio/src/renderer/src/components/Sidebar.tsx` - MODIFY: keep `handleItemClick` behavior, but rely on the Editor's new default to surface a preview rather than an editor for skills, agents, and templates. Flows and workspace artifacts (debugs, explorations) continue to open their authoring surface on click.
**Done when:** Clicking a skill, agent, or template from the sidebar opens the existing Editor in preview mode. Editing the source requires an explicit user action.
**Delivers stories:** S8
**Depends on:** Phase 4.
**Enables:** Library items act as reuse primitives by default, satisfying the progressive disclosure design decision.
**Details:**
Do not introduce a new preview panel. The existing `Editor` component already supports a `preview` tab via [Editor/index.tsx:134](../../studio/src/renderer/src/components/Editor/index.tsx#L134); the change is the default tab choice plus a small "Edit source" entry point (a button in the toolbar or a context menu item). Do not auto-save while previewing. Frontmatter (`ConfigForm`) is shown read-only in preview.
**Verify:** `cd studio; npm run typecheck`

### Phase 6: Wire sidebar drag/drop into the canvas <- Conversation: 2

**File:** `studio/src/renderer/src/components/Sidebar.tsx` - MODIFY: add drag start data for skill and agent rows while preserving click-to-open behavior.
**Done when:** Skills and agents can be dragged without breaking normal sidebar navigation.
**Delivers stories:** S3
**Depends on:** Phase 4.
**Enables:** Canvas drop behavior.
**Details:**
Use native HTML5 drag/drop. Add `draggable` and `onDragStart` to the existing `button.itemRow` elements for skill and agent rows only (not workspace plan rows or template rows in this conversation). Use a stable MIME key `application/pathly-library-item` and stringify a `PathlyLibraryDragItem` payload. Click-to-open behavior must remain on plain click; drag must require a movement threshold (browser default is acceptable). Set `dataTransfer.effectAllowed = 'copy'` and add a `cursor: grab` hover affordance via `Sidebar.module.css`.
**Verify:** `cd studio; npm run typecheck`

### Phase 7: Handle canvas drops <- Conversation: 2

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: accept dropped library items, assign them to an existing node when dropped over one, or create a new state when dropped on empty canvas.
**Done when:** Dropping a skill or agent changes the flow data and marks the selected flow dirty.
**Delivers stories:** S3
**Depends on:** Phase 6.
**Enables:** Inspector-driven refinement.
**Details:**
Wrap React Flow in a `<ReactFlowProvider>` so the drop handler can call `useReactFlow().screenToFlowPosition` for canvas-space coords. On `onDrop`, parse the `application/pathly-library-item` payload, then:
- If the drop event target resolves to an existing `stateNode`, update `agent_map[stateId]` with the item name (without extension).
- Otherwise, generate a unique uppercase state id from the item name (e.g. `commit.md` -> `COMMIT`, with `_2` suffix on collision), append to `states`, set `agent_map[newId]`, and place the new node at the converted drop coordinates.
- Always call `onChange(updated)` so the selected file is marked dirty.
Keep canvas position as UI state only; do not write positions to YAML in this feature.
**Verify:** `cd studio; npm run typecheck`

### Phase 8: Convert inspector overlay into a docked third pane <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: replace the absolutely-positioned overlay with a flex-row layout that makes the inspector a sibling pane of the canvas.
**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/VisualView.styles.ts` - MODIFY: replace `detailPanel: { position: 'absolute', ... }` with a docked layout: canvas flex 1, inspector fixed 300px (from `DESIGN.md`).
**Done when:** Opening the inspector reduces canvas width without remounting React Flow; closing returns it to full width.
**Delivers stories:** S4, S5
**Depends on:** Conversation 2 completed.
**Enables:** Phases 9 and 10 to assume a stable docked inspector surface.
**Details:**
React Flow handles container resize automatically when inside a flex parent. Apply `transition: width 200ms` only when `prefers-reduced-motion` is not set. Set the inspector container's `z-index` to 10 per the `DESIGN.md` scale.
**Verify:** `cd studio; npm run typecheck`

### Phase 9: Replace node panel with node inspector <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/NodePanel.tsx` - MODIFY: implement identity, assigned behavior, transition summary, and validation sections.
**Done when:** Clicking a node opens a useful inspector that can edit node behavior and show validation issues.
**Delivers stories:** S4
**Depends on:** Phase 8.
**Enables:** Full no-YAML node authoring.
**Details:**
Use the docked inspector layout introduced in Phase 8. Implement the "Assigned behavior" picker as a popover from `DESIGN.md` (chip-style trigger -> searchable list with type filter; z-index 40). Source the list from `useProjectFiles().sections.Skills.items` and `sections.Agents.items`. Missing-on-disk references stay selected with a warning badge. State rename is **out of scope for this feature** to avoid touching `transitions`/`agent_map`/`transition_rules`/`transition_actions` cascade; show state id as read-only with a hint "Rename in YAML view for now."
**Verify:** `cd studio; npm run typecheck`

### Phase 10: Replace edge panel with edge inspector <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/EdgePanel.tsx` - MODIFY: implement transition condition, artifact gate, and action editing.
**Done when:** Clicking an edge opens a useful inspector that can add or edit transition actions.
**Delivers stories:** S5
**Depends on:** Phase 9.
**Enables:** Visual routing configuration.
**Details:**
Keep YAML structures compatible with existing `transition_actions` (`"SOURCE->TARGET": [{ skill, message }]`) and the real runtime `transition_rules` schema:

```yaml
transition_rules:
  SOURCE:
    on_artifact:
      ARTIFACT.md: TARGET
    on_content:
      - file: NOTES.md
        contains: "ready"
        next: TARGET
    decide:
      question: "Where next?"
      options:
        approve: TARGET
      default: approve
    default: TARGET
```

Do not use the older incorrect shape `{ artifact_name: { source: target } }`. The edge inspector should edit the rule object for the edge source state and ensure the chosen target is one of that source's declared `transitions[source]`. Use existing `handleAddTransitionAction` and `handleAddTransitionRule` from `useFlowGraph` only after updating them to this state-keyed schema; extend with edit + delete. Avoid inventing a new flow schema.
**Verify:** `cd studio; npm run typecheck`

### Phase 11: Extract validation utility and surface issues <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts` - CREATE: pure function that takes `FlowYaml` plus known skill/agent names and returns `FlowValidationIssue[]`.
**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: run validation each render, pass issues into `StateNode` (badge), edge style (color), and inspector (inline error rows).
**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` - MODIFY: accept an optional `issues` array and render a subtle warning badge (Lucide `AlertTriangle`) when present.
**Done when:** Invalid graph conditions are visible inline before save/export. Inspector inputs validate on blur, with `role="alert"` and `aria-live="polite"`.
**Delivers stories:** S4, S5
**Depends on:** Phase 10.
**Enables:** Safe YAML preview and export.
**Details:**
Run the validation checks listed in `DESIGN.md` (states exist, transitions reference real states, behavior references exist, non-terminal states have outgoing transitions, terminal states do not require outgoing). Also validate runtime routing compatibility:
- every `transition_rules` key is an existing state
- every `default`, `on_artifact`, `on_content.next`, and `decide.options/default` target is listed in `transitions[source]`
- every `transition_actions` key uses `SOURCE->TARGET` or `->TARGET` and points at known transitions/states
Keep messages short ("Target state DEPLOY missing", "Behavior commit not in library"). Do not use banners.
**Verify:** `cd studio; npm run typecheck`

### Phase 12: Harden YAML preview sync <- Conversation: 4

**File:** `studio/src/renderer/src/components/FlowEditor/YamlView/index.tsx` - MODIFY: preserve the last valid parsed model, show parse errors, and prevent unsafe visual switches.
**Done when:** Invalid YAML does not destroy the last valid graph and valid YAML rehydrates Visual view.
**Delivers stories:** S6
**Depends on:** Conversation 3 completed.
**Enables:** User trust in round-trip editing.
**Details:**
Coordinate with `useFlowFile.ts` so raw YAML and parsed flow data stay explicit. Surface YAML parse errors via the existing error banner; on a tab switch back to Visual while YAML is invalid, keep the last valid `flowData` rendered and show a non-blocking warning.
**Verify:** `cd studio; npm run typecheck`

### Phase 13: Add export target UI and service calls <- Conversation: 4

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: add export controls and target selection for Pathly package, Claude Code, and Codex per the toolbar layout in `DESIGN.md`.
**Done when:** A valid flow can be exported through an explicit target action.
**Delivers stories:** S7
**Depends on:** Phase 12.
**Enables:** Packaging workflows.
**Details:**
Use one canonical YAML serialization (`jsYaml.dump(flowData, { lineWidth: 120 })`). Export target adapters write the same content to host-specific paths:

| Target | Destination | Notes |
|---|---|---|
| Pathly package | `${projectPath}/src/pathly_data/core/flows/${flow}.flow.yaml` | Overwrites in place; same path as the source flow. |
| Claude Code | `${projectPath}/.claude/pathly-flows/${flow}.flow.yaml` | Creates folder if missing. Claude Code reads from `.claude/`. |
| Codex | `${projectPath}/.codex/pathly-flows/${flow}.flow.yaml` | Creates folder if missing. Mirrors the Claude Code convention for now. |

Disable the Export button while `validateFlow` returns errors. Warnings require an explicit confirmation modal. Successful export shows a toast with a "Copy path" action.
**Verify:** `cd studio; npm run typecheck`

### Phase 14: Add export helpers if needed <- Conversation: 4

**File:** `studio/src/renderer/src/services/pathlyApi.ts` - MODIFY: add a minimal helper for writing exported flow files when the destination directory does not exist yet. Add only if `writeFile` does not already create missing parent directories on the IPC side.
**Done when:** Export does not duplicate filesystem IPC logic in React components.
**Delivers stories:** S7
**Depends on:** Phase 13.
**Enables:** Cleaner host-specific export behavior.
**Details:**
Keep Electron IPC boundaries unchanged unless a missing capability blocks export. The current main-process `fs:write` handler already calls `fs.mkdirSync(path.dirname(filePath), { recursive: true })`, so this phase is expected to be a no-op unless that behavior changes before implementation. Prefer reusing `writeFile(path, content)` from `pathlyApi.ts` directly for export writes.
**Verify:** `cd studio; npm run typecheck`

## Prerequisites

- Confirm current dirty files before implementation and do not overwrite unrelated user edits.
- Verify React Flow imports and current canvas behavior before editing.
- Treat existing `src/pathly_data/core/flows/*.flow.yaml` as schema examples.

## Key Decisions

- Canvas is the primary authoring model; wizard becomes a template starter.
- YAML remains inspectable and editable, but it serializes from the canonical graph model.
- Skills, agents, and templates are exposed for **reuse by default**. Clicking such an item opens read-only preview; editing the source requires an explicit user action.
- Export targets are adapters over one canonical flow model, not separate editors.

## Scope Exclusions

The following are explicitly **out of scope** for this feature. Do not implement them in any of the four conversations.

| Excluded | Why |
|---|---|
| VS Code-style file tree drag/drop (reorder, reparent, multi-select, cut/copy/paste) | The Pathly sidebar is a domain-aware library, not a generic FS tree. Tree-internal FS operations are a separate future feature (`studio-file-tree-ops`). |
| Drag/drop from OS filesystem onto the canvas | Library is the only source of skills/agents/templates in this feature. |
| State rename from the node inspector | Renaming a state requires cascading edits to `transitions`, `agent_map`, `transition_rules`, and `transition_actions`. Out of scope; YAML view remains the rename path. |
| Persisting canvas node positions to YAML | Positions stay UI state. A future layout-persistence feature can revisit this. |
| Editing skills, agents, or templates from inside the visual flow editor | The visual editor is for assembly. Editing source remains the existing Editor's job and now requires an explicit action. |
| Redesigning Monitor, Terminal, TopBar, PlanBoard, Settings, HomeScreen, SetupScreen, or FlowWizard | These surfaces are stable. The wizard remains as "New Flow from Template" only. |
| MCP runtime, Electron installer, or backend changes | This feature is renderer-side except for the optional `pathlyApi.ts` helper in Phase 14. |
| Drag/drop on workspace plan rows, debug rows, or exploration rows | Workspace artifacts are not library primitives. Their click-to-open behavior stays unchanged. |
