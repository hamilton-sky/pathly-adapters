# composition-blocks — Happy Flow

## Overview

A Studio user wants the BUILDING stage of their team flow to always include scout choreography, completion reporting, and spawn-rule injection (when the adapter supports spawning), and the REVIEWING stage to use a stricter preset. They open the Flow Wizard, select blocks from a dropdown for each stage, and click Finish. The wizard generates a flow yaml with a `composition:` map. When the FSM runs that flow, `build_prompt` automatically threads the right fragment set into the composed prompt — without the user touching any skill file.

---

## Step-by-Step Happy Flow

### Step 1: User opens the Flow Wizard in Studio

- **User does:** Clicks "New Flow" in Studio; the Flow Wizard opens at Step 0.
- **System does:** FlowWizard initializes wizard state including `blockMap: {}`.
- **State after:** Wizard is at Step 0; `blockMap` is empty.

### Step 2: User completes flow name, states, transitions, and agent map

- **User does:** Progresses through Steps 1–4 (name, states, transitions, agents), entering state names including `BUILDING` and `REVIEWING`.
- **System does:** Wizard state accumulates `validStates`, `agentMap`, `transitions`.
- **State after:** Flow has named states; `blockMap` is still empty (no blocks selected yet).

### Step 3: User selects composition blocks for BUILDING and REVIEWING

- **User does:** In the Step 4 agents view (or a sibling step), sees a "Composition block" dropdown per state. Selects `full-build` for `BUILDING` and `review-strict` for `REVIEWING`. Leaves other states blank.
- **System does:** Updates `blockMap: { BUILDING: "full-build", REVIEWING: "review-strict" }`. Wizard autosaves the draft.
- **State after:** `blockMap` has two entries; draft is persisted to `pathlyUserHome/flows/<DRAFT_FILE_NAME>`.

### Step 4: User finishes the wizard

- **User does:** Clicks "Finish" through Steps 5–6 (adapter routing, review).
- **System does:** Calls `generateYaml(flowName, storagePath, validStates, agentMap, transitions, gates, feedbackRoutes, transitionRules, adapterMap, blockMap)`. Because `blockMap` has non-empty values, `generateYaml` emits a `composition:` key in the yaml output.
- **State after:** A flow yaml exists at `pathlyUserHome/flows/<name>.flow.yaml` with content including:
  ```yaml
  composition:
    BUILDING: full-build
    REVIEWING: review-strict
  ```

### Step 5: Operator loads the flow into the FSM

- **User does:** Starts the Pathly runner with the new flow yaml.
- **System does:** FSM loads the flow yaml via `state.py`. The validator sees `composition:` key, checks that `BUILDING` and `REVIEWING` are declared states, checks that `full-build` and `review-strict` exist in the merged block library. Validation passes.
- **State after:** Flow is loaded; FSM is ready to run.

### Step 6: FSM enters BUILDING stage

- **User does:** (Automated) FSM transitions to BUILDING.
- **System does:** `build_prompt` is called for the BUILDING stage. It detects `composition: { BUILDING: full-build }` in the active flow. Calls `compose_skill_with_block(agent, "full-build", adapter_caps)`. `resolve_block("full-build", {"can_spawn"})` returns the ordered fragment list: `[completion-report, scout-choreography, feedback-protocol, spawn-rules]`. The prompt is assembled: skill body + `\n\n` + each fragment body rstripped.
- **State after:** The agent receives a composed prompt with all four fragment bodies injected.

### Step 7: FSM enters REVIEWING stage

- **User does:** (Automated) FSM transitions to REVIEWING.
- **System does:** `build_prompt` detects `composition: { REVIEWING: review-strict }`. Calls `compose_skill_with_block(agent, "review-strict", adapter_caps)`. `resolve_block("review-strict", {"can_spawn"})` returns `[scout-choreography, spawn-rules]`.
- **State after:** The reviewing agent receives a prompt with scout-choreography and spawn-rules injected.

### Step 8: FSM enters a state with no block binding

- **User does:** (Automated) FSM transitions to a state not in `composition:` (e.g., `STORMING`).
- **System does:** `build_prompt` checks `composition:` — no binding for `STORMING`. Falls back to `compose_skill(agent, adapter_caps)` (pre-feature behavior).
- **State after:** Agent receives the default composed prompt; no block injection.

---

## End State

The flow runs to completion. BUILDING and REVIEWING stages each used their configured block's fragment set. States without a binding ran with default composition. No skill files were edited. The flow yaml is the single source of the per-stage block selection.

## Success Indicators

- [ ] Flow yaml contains `composition:` map with only the two explicitly-selected states.
- [ ] BUILDING stage prompt contains `completion-report`, `scout-choreography`, `feedback-protocol`, and `spawn-rules` fragment bodies.
- [ ] REVIEWING stage prompt contains `scout-choreography` and `spawn-rules` fragment bodies.
- [ ] A state with no block binding produces a prompt identical to pre-feature behavior.
- [ ] `python -m pytest tests/ -q` and `tsc --noEmit` pass with no new failures.
