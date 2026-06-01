---
name: User Stories
---
# Multi-Adapter Routing — User Stories

## Context

Pathly pipelines currently run every stage on whichever single CLI the user launched. Different models have different strengths and costs (codex for fast sandboxed execution, claude for nuanced review). This feature lets a flow declare, per stage, which adapter should handle it — authored in the flow YAML and visually in the Studio wizard — while keeping the FSM passive and fully backward compatible.

---

## Stories

### Story S1: FSM emits preferred adapter per stage
**As a** Pathly adapter/CLI, **I want** the `/next_action` response to tell me which adapter should handle the current stage, **so that** a coordinator can route the stage without the FSM having to spawn anything.

**Acceptance Criteria:**
- [ ] `/next_action` response includes a `preferred_adapter` string field.
- [ ] When the flow has `adapter_map` and the current state is listed, `preferred_adapter` equals that state's mapped value.
- [ ] When the flow has `adapter_map` and the current state is NOT listed, `preferred_adapter` equals `adapter_map.default`.
- [ ] When the flow has no `adapter_map`, `preferred_adapter` is `""` (empty string).
- [ ] The blocked-response path (`_blocked_response`) also includes `preferred_adapter` with the same resolution.
- [ ] All pre-existing `/next_action` response fields are unchanged (no removals, no renames).

**Edge Cases:**
- State not in `adapter_map` but `default` present → falls back to `default`.
- `adapter_map` present but current state is terminal (`DONE`) → resolves to `default` (harmless; no agent runs).

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Flow validator accepts and checks adapter_map
**As a** flow author, **I want** the flow validator to accept `adapter_map` and reject malformed routing, **so that** typos are caught at authoring time instead of failing silently downstream.

**Acceptance Criteria:**
- [ ] A flow YAML containing a well-formed `adapter_map` passes `validate_flow_cli` with exit 0.
- [ ] A flow YAML with NO `adapter_map` still passes (backward compatible).
- [ ] If `adapter_map` is present but has no `default` key, validation fails with a message naming the missing `default`.
- [ ] If any `adapter_map` value is not in the known set `{claude, codex, copilot}`, validation fails with a message naming the offending value (failure-case criterion).
- [ ] If any `adapter_map` per-state key is not a declared state in `states`, validation fails with a message naming the unknown state.
- [ ] The canonical `adapter_map` shape is documented in `src/pathly_data/CLAUDE.md`, including the `default` key, the known adapter set, and the resolution precedence.

**Edge Cases:**
- `adapter_map: {}` (empty map, no default) → treated as a config error (missing `default`).
- Adapter name with wrong case (`Claude`) → fails closed-set check (set is lowercase).

**Delivered by:** Phase 2 → Conversation 2

---

### Story S3: Studio wizard authors adapter routing
**As a** flow author using Studio, **I want** a wizard step to pick an adapter per stage, **so that** I can create routed flows without hand-editing YAML.

**Acceptance Criteria:**
- [ ] The wizard has a new "Adapter Routing" step after the Agents step and before the Quality/Review step.
- [ ] The step shows a global **default** adapter selector (defaulting to `claude`) and one per-stage override selector for each non-terminal state.
- [ ] Each per-stage selector offers "Use default", `claude`, `codex`, `copilot`; "Use default" means no override is written for that stage.
- [ ] `generateYaml()` emits an `adapter_map:` block (with `default` first, then overrides) when the default is non-`claude` OR at least one per-stage override is set; otherwise it emits no `adapter_map` block.
- [ ] A flow saved from the wizard with adapter routing passes `validate_flow_cli` (round-trip conformance — the anti-drift guarantee).
- [ ] The step is skippable: a user can advance with zero interaction and the saved YAML is byte-identical to today's output (no `adapter_map` block).
- [ ] The wizard step counter and progress reflect the new total step count.
- [ ] Adapter routing persists in the wizard draft (resume restores the routing).

**Edge Cases:**
- Terminal state (`DONE`) shows no adapter selector.
- User sets an override then resets it to "Use default" → that stage key disappears from the emitted YAML.

**Delivered by:** Phase 3 → Conversation 3

---

### Story S4: pathly-dispatch coordinator routes the stage
**As a** Pathly user, **I want** a `pathly-dispatch` skill that reads `preferred_adapter` and either runs the stage here or hands it off, **so that** routed flows actually execute on the chosen adapter.

**Acceptance Criteria:**
- [ ] A core skill `dispatch.md` exists at `src/pathly_data/core/skills/utilities/`.
- [ ] When `preferred_adapter` is `""` or equals the current adapter, the skill runs `agent_hint.instructions` in the current CLI (no handoff).
- [ ] When `preferred_adapter` differs from the current adapter, the skill emits a handoff packet: the target adapter name, the feature `storage_path`, and the **verbatim, unmodified** `agent_hint.instructions`.
- [ ] The skill never spawns a process and never rewrites the instructions (deterministic relay only).
- [ ] A `dispatch_skill.yaml` meta file exists for all three adapters (`claude`, `codex`, `copilot`) so `pathly-setup` installs it everywhere (adapter sync rule).

**Edge Cases:**
- `preferred_adapter` names an adapter the user doesn't have installed → the handoff packet still prints; the skill states the target is unavailable rather than failing silently.
- Response has no `preferred_adapter` field (older FSM) → treat as `""` (run in place).

**Delivered by:** Phase 4 → Conversation 4

---

## Out of scope (explicit — see ARCHITECTURE_PROPOSAL.md "Future Work")
- Per-feature `STATE.json` adapter override (precedence slot reserved, not implemented).
- Auto-launch of the target CLI (passive relay only for now).
- Local-LLM / Brightsky-hosted dispatch supervisor for the future auto-launch loop.
