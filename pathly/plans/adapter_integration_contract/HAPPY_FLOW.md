---
name: Happy Flow
---
# Adapter Integration Contract — Happy Flow

1. An adapter calls `next_action` for `adapter_integration_contract`.
2. The FSM returns `schema_version`, `decision`, `role`, `agent_hint`, `stage_brief`, and `warnings` in a stable shape.
3. The adapter reads `agent_hint.role` to dispatch its native agent and uses `agent_hint.instructions` as the prompt body.
4. The agent completes the work and reports back through `complete_stage`.
5. The FSM confirms the stage and advances without requiring the adapter to infer any hidden state.
