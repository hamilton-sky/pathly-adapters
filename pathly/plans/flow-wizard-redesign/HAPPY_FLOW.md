---
name: Happy Flow
---
# flow-wizard-redesign — Happy Flow

## Overview

A developer wants to create a "Standard CI pipeline" flow for their AI agent team. They open the wizard, select the pre-built template, confirm the stages, assign agents, and save — reaching a valid YAML file in under 2 minutes, without having to understand the full YAML schema.

## Step-by-Step Happy Flow

### Step 1: Open the wizard
- **User does:** Clicks "+" next to the Flows section in the sidebar
- **System does:** Renders Step0Entry with three option cards
- **State after:** Entry screen visible; no step counter shown; Cancel button available

### Step 2: Select a template
- **User does:** Clicks "From template", then selects "Standard pipeline"
- **System does:** Calls handleTemplateSelect with the standard-pipeline template; sets states to STORMING/PLANNING/BUILDING/REVIEWING/TESTING/DONE and transitions to the linear chain; advances to step 1
- **State after:** Step 1 visible; step counter shows "Step 1 of 5"; states and transitions already populated

### Step 3: Name the flow
- **User does:** Types "ci-pipeline" in the flow name field, adds an optional description
- **System does:** Validates on blur — name matches pattern, no error shown
- **State after:** Step 1 dot shows green ✓ after advancing; step counter shows "Step 2 of 5"

### Step 4: Confirm stages
- **User does:** Reviews the pre-filled states list; drags REVIEWING before TESTING to reorder; sees the pipeline chain update live
- **System does:** Reorders the states array; auto-generated transitions remain valid (names preserved)
- **State after:** States list reflects new order; pipeline chain shows updated sequence

### Step 5: Assign agents
- **User does:** Types agent identifiers for each non-terminal state (e.g. `team/build` for BUILDING)
- **System does:** Stores agent map; no warning if all non-terminal states are assigned
- **State after:** Step 3 dot shows green ✓; step counter shows "Step 4 of 5"

### Step 6: Quality & routing (optional)
- **User does:** Leaves all accordion sections collapsed — no gates, routing, or rules needed for this flow
- **System does:** Passes empty values for gates/feedbackRoutes/transitionRules to YAML generation
- **State after:** Step 4 dot shows green ✓; step counter shows "Step 5 of 5"

### Step 7: Review and save
- **User does:** Reviews live YAML preview on the Review step; confirms storage path; clicks "Save Flow"
- **System does:** Writes YAML to `{projectPath}/src/pathly_data/core/flows/ci-pipeline.flow.yaml`; calls onCreated callback; sidebar refreshes
- **State after:** Wizard closes; new flow appears in the Flows section of the sidebar; flow panel opens

## End State

The developer has a valid `ci-pipeline.flow.yaml` with 6 states, linear transitions, and per-state agent assignments, written to disk without manually authoring any YAML.

## Success Indicators

- [ ] Wizard closed without error after Save
- [ ] YAML file exists at the expected path
- [ ] File is valid YAML parseable by the flow loader
- [ ] All 6 states appear in the YAML `states:` block
- [ ] Transitions reflect the reordered state sequence
- [ ] Agent assignments appear under `agent_map:` for all non-terminal states
