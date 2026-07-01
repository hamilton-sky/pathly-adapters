# studio-visual-flow-builder - Happy Flow

## Overview

A Pathly Studio user opens an existing project, selects a flow, visually edits the workflow by dragging skills or agents onto the canvas, configures nodes and transitions, reviews generated YAML, and exports the approved flow to a target host.

## Step-by-Step Happy Flow

### Step 1: Open an existing flow

- **User does:** Selects `debug.flow.yaml` or another flow from the Flows section.
- **System does:** Parses YAML and renders states as connected React Flow nodes and edges.
- **State after:** The visual canvas matches the YAML transitions.

### Step 2: Add or assign behavior

- **User does:** Drags a skill or agent from the sidebar onto the canvas.
- **System does:** Assigns it to the target state or creates a new state when dropped on empty canvas.
- **State after:** The node shows its assigned behavior and the flow is marked dirty.

### Step 3: Connect states

- **User does:** Drags from one node handle to another.
- **System does:** Adds the transition to the canonical flow model.
- **State after:** The edge is visible and YAML preview includes the transition.

### Step 4: Configure node and edge details

- **User does:** Clicks a node or edge.
- **System does:** Opens the inspector with editable fields and validation.
- **State after:** The user can refine behavior, conditions, and actions without raw YAML.

### Step 5: Review YAML

- **User does:** Opens the YAML tab.
- **System does:** Serializes the canonical graph model into YAML.
- **State after:** The YAML is inspectable and can be edited safely.

### Step 6: Export

- **User does:** Chooses Pathly package, Claude Code, or Codex export.
- **System does:** Validates the flow and writes/copies the canonical YAML to the target output.
- **State after:** The flow is ready for the selected runtime surface.

## End State

The user has authored and exported a valid Pathly flow from the visual canvas without needing to hand-edit YAML.

## Success Indicators

- [ ] Existing YAML transitions render as visible connected edges.
- [ ] Drag/drop changes the flow model and dirty state.
- [ ] Node and edge inspectors can configure common flow details.
- [ ] YAML preview and visual graph round-trip without data loss.
- [ ] Export targets are explicit and validation-gated.
