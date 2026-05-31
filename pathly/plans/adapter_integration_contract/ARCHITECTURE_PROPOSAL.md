---
name: Architecture Proposal
---
# Adapter Integration Contract — Architecture Proposal

## Contract boundary
The FSM owns state recovery, decision-making, and the adapter-facing response envelope. Adapters own native execution and only translate the returned hint into their local agent dispatch mechanism.

## Payload model
- `schema_version` gives the contract a forward-compatible version marker.
- `decision` is the operational control signal for adapters.
- `role` is the abstract, adapter-agnostic dispatch label.
- `agent_hint` carries the executable prompt and any adapter-specific dispatch details.
- `stage_brief` carries bounded context for prompt warm-up.
- `warnings` carries displayable risk context, not policy.

## Migration rule
Keep `codex_subagent` only long enough to avoid breaking current consumers. The new contract fields are the canonical surface and should be the only ones referenced in updated adapter documentation.
