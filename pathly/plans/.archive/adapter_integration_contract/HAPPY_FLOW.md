---
name: Happy Flow
---
# Adapter Integration Contract — Happy Flow

1. An adapter calls `POST /next_action` for `adapter_integration_contract`.
2. The FSM returns `{ decision:"continue", current_state, schema_version, role, agent_hint, stage_brief, warnings }` in a stable, consistent shape.
3. The adapter reads `agent_hint.role` to dispatch its native agent (`"worker"` or `"explorer"`) and uses `agent_hint.instructions` as the full prompt body.
4. The agent completes the work and the adapter calls `POST /complete_stage`.
5. The FSM confirms the stage and returns the same envelope shape with `current_state` updated to the new state — the adapter does not need to special-case which endpoint it called.
6. The adapter loops (steps 1–5) until `done: true` is returned.
7. If `decision = "block"` at any point, the adapter routes to the named `target_agent` with the open feedback file as context, then retries `complete_stage` with `resolved_files`.
8. If `decision = "escalate"` at any point, the adapter halts and surfaces the issue to the user — no automated retry.
