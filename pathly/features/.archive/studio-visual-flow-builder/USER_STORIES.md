# studio-visual-flow-builder - User Stories

## Context

Pathly Studio already has a sidebar, React Flow canvas, YAML tab, and flow wizard. After the refactor, the visual canvas appears to show nodes without reliable connections or editing affordances. The next product step is to make the visual canvas the primary flow authoring surface while preserving YAML as the exact serialized source.

The user should be able to drag skills or agents into the canvas, connect states, configure nodes and edges, validate the flow, preview YAML, and export host-specific packages for Pathly, Claude Code, and Codex.

## Stories

### Story S1: Existing YAML renders as a connected graph

**As a** Pathly Studio user, **I want** an existing flow YAML file to render with connected nodes, **so that** I can understand the workflow shape without reading raw YAML.

**Acceptance Criteria:**
- [ ] `transitions` entries render as visible React Flow edges.
- [ ] State nodes expose valid source and target handles.
- [ ] Switching between flow files reinitializes graph nodes and edges from the selected YAML.
- [ ] Existing YAML files do not lose data when opened in Visual view.

**Edge Cases:**
- A transition references a missing state.
- A flow has a terminal state with no outgoing transitions.
- A YAML edit fails to parse after a valid graph was already loaded.

**Delivered by:** Phase 1 and Phase 2 -> Conversation 1

### Story S2: Visual graph changes update canonical YAML data

**As a** flow author, **I want** connecting nodes on the canvas to update the flow model, **so that** Save and YAML preview reflect what I changed visually.

**Acceptance Criteria:**
- [ ] Creating a canvas edge adds a transition to the canonical flow data.
- [ ] Duplicate transitions are ignored.
- [ ] Graph layout changes do not accidentally mutate flow semantics.
- [ ] Dirty-state tracking works after visual edits.

**Edge Cases:**
- User creates an edge with a missing source or target.
- User reconnects an existing edge.
- User switches tabs before saving.

**Delivered by:** Phase 3 -> Conversation 1

### Story S3: Users can drag skills and agents from the library

**As a** workflow designer, **I want** to drag a skill or agent from the sidebar into the canvas, **so that** I can assemble a flow visually.

**Acceptance Criteria:**
- [ ] Skill and agent rows expose drag data.
- [ ] Dropping onto an existing state assigns that behavior to the state.
- [ ] Dropping onto empty canvas creates a new state node with a generated unique state id.
- [ ] The library remains usable as a normal click-to-open file explorer.

**Edge Cases:**
- The item is external or missing from the loaded Pathly installation.
- The generated state id conflicts with an existing state.
- The drop occurs outside the canvas.

**Delivered by:** Phase 4, Phase 6 and Phase 7 -> Conversation 2

### Story S4: Clicking a node opens a real node inspector

**As a** user, **I want** node configuration in a clear inspector, **so that** I can edit state identity, assigned behavior, and transition rules without editing YAML manually.

**Acceptance Criteria:**
- [ ] Node inspector shows identity, assigned behavior, required artifacts, outgoing transitions, and validation state.
- [ ] Assigned behavior can be selected from known skills and agents.
- [ ] Invalid node fields show inline errors.
- [ ] Changes update canonical flow data and dirty-state tracking.

**Edge Cases:**
- Renaming a state requires updating transitions and agent map references.
- A behavior is deleted from the library while the flow references it.
- Required fields are empty.

**Delivered by:** Phase 8, Phase 9 and Phase 11 -> Conversation 3

### Story S5: Clicking an edge opens transition configuration

**As a** user, **I want** edge configuration in the inspector, **so that** I can set artifact gates, feedback routing, and transition actions visually.

**Acceptance Criteria:**
- [ ] Edge inspector shows source, target, label, conditions, and transition actions.
- [ ] Adding a transition action updates `transition_actions`.
- [ ] Artifact gates map back to supported flow YAML structures.
- [ ] Validation catches unsupported or incomplete edge config.

**Edge Cases:**
- Multiple conditions route to the same target.
- A transition action references a missing skill.
- Edge config conflicts with an existing default route.

**Delivered by:** Phase 10 and Phase 11 -> Conversation 3

### Story S6: YAML preview remains synchronized and safe

**As an** advanced user, **I want** a YAML preview/edit tab, **so that** I can inspect and tweak the generated flow definition directly.

**Acceptance Criteria:**
- [ ] YAML preview serializes from the canonical graph model.
- [ ] Direct YAML edits parse back into the graph only when valid.
- [ ] Invalid YAML shows parse errors without discarding the last valid graph.
- [ ] Save writes the selected flow file only after validation passes or warning approval is explicit.

**Edge Cases:**
- YAML contains comments that cannot be preserved through object serialization.
- YAML has unsupported keys.
- User switches back to visual view after a parse error.

**Delivered by:** Phase 12 -> Conversation 4

### Story S7: Users can export approved flows

**As a** Pathly package author, **I want** export actions for Pathly, Claude Code, and Codex, **so that** one approved flow can be packaged for different hosts.

**Acceptance Criteria:**
- [ ] Export is disabled until required validation passes.
- [ ] Export targets are shown as explicit choices.
- [ ] The canonical flow YAML is copied or written to the correct target path for each supported target.
- [ ] Host-specific export warnings are shown before export.

**Edge Cases:**
- Target path is missing or not writable.
- A target needs files the current flow does not define.
- User exports with warnings.

**Delivered by:** Phase 13 and Phase 14 -> Conversation 4

### Story S8: Library items behave as reuse primitives, not editing targets

**As a** flow author, **I want** clicking a skill, agent, or template in the sidebar to open a read-only preview rather than the source editor, **so that** I can browse and reuse library items without accidentally editing the source.

**Acceptance Criteria:**
- [ ] Clicking a skill, agent, or template opens the existing Editor in `preview` tab by default.
- [ ] An explicit user action (button or context menu) is required to switch the previewed item into edit mode.
- [ ] Frontmatter is shown read-only while previewing.
- [ ] Auto-save is suppressed while previewing.
- [ ] Flows and workspace artifacts (debugs, explorations) continue to open in their authoring surface on click.

**Edge Cases:**
- The item has malformed frontmatter — preview still renders body content and shows a non-blocking warning.
- The user hits an Edit shortcut from preview — confirmation is not required since the action is explicit.
- The same item is dragged and clicked at the same time — drag wins; click does not fire on drag start.

**Delivered by:** Phase 5 -> Conversation 2
