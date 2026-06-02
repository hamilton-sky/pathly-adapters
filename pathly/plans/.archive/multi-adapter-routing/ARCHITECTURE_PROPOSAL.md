---
name: Architecture Proposal
---
# Multi-Adapter Routing — Architecture Proposal

## Problem Statement

Every stage of a Pathly pipeline runs on whichever single CLI the user launched. We want a flow to route stages to different adapters (claude/codex/copilot) to exploit per-model strengths (codex for sandboxed execution, claude for nuanced review) and control cost — without making the FSM responsible for launching processes.

## Proposed Solution

Add an optional `adapter_map` block to flow YAML. The FSM reads it and emits a `preferred_adapter` string in `/next_action` (signal only). A thin `pathly-dispatch` skill reads that field and either runs the stage in place or relays the verbatim prompt to the target adapter. The Studio wizard authors the routing.

## Layer Breakdown

```
Studio Wizard (TS)         build-time: emits adapter_map block into flow YAML
     │  writes {name}.flow.yaml
     ▼
Flow YAML (config home)    adapter_map: { default, <STATE>: <adapter> }
     │  read by
     ├──────────────► validate_flow_cli (state.py) — single arbiter of shape
     ▼
FSM (fsm_ops.py)           _resolve_adapter() → preferred_adapter in /next_action
     │  PASSIVE — copies an opaque string; never imports adapter code
     ▼
pathly-dispatch (skill)    pref == current ? run in place : emit handoff packet
     │  depends on the FSM response contract; FSM never depends on it
     ▼
Target CLI                 human/host relays the verbatim prompt (passive)
```

## Key Design Decisions

### Decision 1: FSM stays passive (signal, not launcher)
- **Options considered**: (A) FSM spawns the target CLI; (B) FSM emits `preferred_adapter`, a coordinator dispatches.
- **Chosen**: B
- **Rationale**: A turns the FSM into a process manager (install paths, failure handling, waiting) — large scope creep for a state machine. B adds one optional response field and keeps every concern where it already lives.

### Decision 2: `adapter_map` lives in flow YAML, sibling to `agent_map`
- **Options considered**: a separate routing file; per-feature only; flow YAML.
- **Chosen**: flow YAML.
- **Rationale**: routing IS pipeline structure, which the flow YAML already owns. It is per-flow, user-editable, self-documenting, and the FSM already parses this file.

### Decision 3: Closed adapter set, validated at author time
- **Options considered**: open strings; closed set `{claude, codex, copilot}`.
- **Chosen**: closed set, defined once in `state.py`.
- **Rationale**: the adapter universe is small, fixed, and in-repo. An open string lets a typo route to nothing and fail downstream where it is hard to trace. Catch it at flow-authoring time — the cheapest place.

### Decision 4: Validator is the single arbiter; a round-trip test forces Studio to conform
- **Rationale**: `generateYaml()` (TS) and `validate_flow_cli()` (Python) could drift across languages. Making the validator authoritative and asserting "Studio output passes the validator" in a test means any divergence goes red in CI.

### Decision 5: Passive relay now; auto-launch is future work
- **Rationale**: the relay is a deterministic string compare + verbatim copy — no reasoning, no spawning, maximally safe. Auto-launch reintroduces process management and is a separate feature (see Future Work).

### Decision 6: Per-feature override deferred, precedence slot reserved
- **Rationale**: a per-feature `STATE.json` override crosses a read/write boundary the rest of the feature avoids, and the flow-level map satisfies 100% of the stated use case. Reserving precedence slot 1 now makes the later addition purely additive.

## Key Components
- `_resolve_adapter(flow_config, state_name)` — new pure helper in `fsm_ops.py`; resolves `preferred_adapter`.
- `_KNOWN_ADAPTERS` — name allowlist in `state.py` (not a capability registry).
- `Step5AdapterRouting` — new Studio wizard component (state→adapter selectors).
- `pathly-dispatch` — new core skill; deterministic relay/handoff.

## Interface Design
- **FSM → coordinator contract:** `/next_action` gains `preferred_adapter: string` (`""` when unset). All existing keys unchanged.
- **Coordinator output:** either in-place execution, or a handoff packet `{ target_adapter, storage_path, instructions (verbatim) }`.
- **Canonical YAML shape:** documented in `src/pathly_data/CLAUDE.md` (see FEATURE_INDEX.md).

## Risks
- **Cross-adapter artifact drift**: a stage handed to codex writes `REVIEW_FAILURES.md` in a structure the next claude stage mis-parses. *Mitigation*: FSM gates/transitions key on documented markers (e.g. `pass_marker: "RESULT: PASS"`), not adapter prose; artifacts conform to `core/templates/`. See EDGE_CASES.md EC-2.1.
- **TS/Python shape drift**: *Mitigation*: Decision 4 round-trip test.
- **Silent mis-route from a typo**: *Mitigation*: Decision 3 closed-set validation.

## Future Work (out of scope for this plan)
- **Per-feature `STATE.json` override** — precedence slot 1 reserved now.
- **Auto-launch supervisor** — an opt-in loop that spawns the target CLI, detects stage completion, and calls `complete_stage`. Because its decisions are narrow (done / retry / escalate) and schema-bounded, a small **local LLM (Ollama / node-llama-cpp) or a Brightsky endpoint with constrained output** is a sound, low-hallucination host for this always-on loop — keeping frontier-model tokens out of routine supervision. The dispatch *decision* itself stays deterministic code; only the supervisory loop would use a model.
