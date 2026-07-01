---
name: Happy Flow
---
# Multi-Adapter Routing — Happy Flow

## Overview

A user wants BUILD on codex (fast sandboxed code) and REVIEW on claude (nuanced review). They author the routing in the Studio wizard, run the pipeline, and the dispatch skill relays each stage to the chosen adapter — with the FSM never spawning anything itself.

## Step-by-Step Happy Flow

### Step 1: Author routing in the wizard
- **User does**: opens the flow wizard, reaches the new Adapter Routing step, leaves the default as `claude`, sets BUILDING → `codex`.
- **System does**: `generateYaml()` emits `adapter_map: { default: claude, BUILDING: codex }`.
- **State after**: the saved `{name}.flow.yaml` contains the `adapter_map` block; YAML preview showed it live.

### Step 2: Flow validates
- **User does**: saves the flow.
- **System does**: `validate_flow_cli` confirms `default` is present, `codex` is in the known set, and `BUILDING` is a declared state.
- **State after**: flow is valid and usable.

### Step 3: FSM signals the adapter
- **User does**: runs the pipeline; reaches the BUILDING stage.
- **System does**: `/next_action` resolves `preferred_adapter = "codex"` via `adapter_map[BUILDING]`.
- **State after**: the response carries `preferred_adapter: "codex"` plus the usual `agent_hint.instructions`.

### Step 4: Dispatch relays the stage
- **User does**: invokes `pathly-dispatch` (or the host calls it).
- **System does**: current adapter is `claude` ≠ `codex`, so the skill emits a handoff packet — target `codex`, the feature `storage_path`, and the verbatim builder instructions.
- **State after**: the user pastes the packet into codex; the builder runs there.

### Step 5: Next stage routes back
- **User does**: completes BUILDING; pipeline advances to REVIEWING.
- **System does**: `/next_action` resolves `preferred_adapter = "claude"` (the default, since REVIEWING is unmapped); dispatch sees `claude == claude` and runs the reviewer in place.
- **State after**: review runs on claude; no handoff needed.

## End State
A single feature was built on codex and reviewed on claude, driven by the flow's `adapter_map`. The FSM only ever copied a string into its response.

## Success Indicators
- [ ] `/next_action` returns the correct `preferred_adapter` for each stage.
- [ ] A wizard-authored routed flow passes the validator (round-trip).
- [ ] Dispatch runs in place when adapters match and emits a verbatim handoff packet when they differ.
- [ ] A flow with no `adapter_map` produces no `preferred_adapter` routing (empty string) and behaves exactly as before.
