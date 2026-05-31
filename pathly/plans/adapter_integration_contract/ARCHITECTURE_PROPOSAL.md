---
name: Architecture Proposal
---
# Adapter Integration Contract — Architecture Proposal

## Contract boundary
The FSM owns state recovery, decision-making, and the adapter-facing response envelope. Adapters own native execution and only translate the returned hint into their local agent dispatch mechanism.

## Payload model

### Top-level response envelope (same shape for both endpoints)
- `schema_version` — forward-compatible version marker (string, currently `"1"`).
- `decision` — operational control signal: `"continue"` | `"block"` | `"escalate"`.
- `current_state` — the active FSM state (consistent on both `next_action` and `complete_stage`).
- `conv` — conversation counter for the current feature.
- `role` — abstract, adapter-agnostic dispatch label (e.g., `"builder"`, `"reviewer"`).
- `agent` — same as `role`; present for backward compat.
- `agent_hint` — adapter-facing dispatch packet with neutral keys (see below).
- `stage_brief` — bounded context for the current step only.
- `warnings` — displayable risk context (not policy); array of `{ code, file? }` entries.
- `storage_path` — absolute path to the feature's plan directory.
- `instructions` — full delegated prompt for the current agent.
- `limits` — per-stage retry / context limits.
- `codex_subagent` — **frozen legacy compat field** with old key names (`codex_role`, `pathly_agent`). Do NOT use as primary contract; exists only until Codex consumers migrate to `agent_hint`.

### `agent_hint` shape (adapter-neutral)
```json
{
  "agent":        "<pathly role, e.g. builder>",
  "role":         "<dispatch label: worker | explorer>",
  "mode":         "native-pathly-agent-if-callable-else-codex-role",
  "instructions": "<full delegated prompt>"
}
```

## Decision semantics
- `continue` — proceed automatically; no human involvement needed.
- `block` — agent-resolvable feedback file is open; the `target_agent` field names the Pathly agent that should handle it. Automated retry is appropriate.
- `escalate` — human input required: feedback target is human, state is corrupt/unknown, or retry limit exceeded. Do not automate; surface to the user.

## Migration rule
`codex_subagent` is frozen with the old inner keys (`codex_role`, `pathly_agent`). It must NOT be updated as `agent_hint` evolves. Remove `codex_subagent` from consumer guidance after all consumers migrate to `agent_hint`. Keep it in the payload for one full release cycle to avoid breaking existing integrations.

## Response shape consistency
Both `next_action` and `complete_stage` return the same envelope shape. `complete_stage` sets `current_state` to the newly-entered state (not a `next_state` key) so adapters do not need endpoint-specific parsing.
