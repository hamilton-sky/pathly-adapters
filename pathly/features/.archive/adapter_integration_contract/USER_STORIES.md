---
name: User Stories
---
# Adapter Integration Contract — User Stories

## Context
Pathly currently has a useful but incomplete adapter contract. The FSM `_agent_hint` still returns Codex-specific key names (`codex_role`, `pathly_agent`), `complete_stage` responses use a different top-level key than `next_action` (`next_state` vs `current_state`), and there is no `escalate` decision distinct from `block`. This feature fixes those gaps so adapters receive a stable, adapter-agnostic payload with explicit decision semantics (`continue | block | escalate`), consistent key names across both endpoints, and a clear boundary between automated continuation and human escalation.

**Note:** Much of the envelope shape is already implemented (`schema_version`, `decision`, `role`, `agent_hint`, `stage_brief`, `warnings`, `codex_subagent`). The stories below target the specific remaining gaps only.

## Stories

### Story 1.1: Normalize FSM response shape
**As a** platform integrator, **I want** `next_action` and `complete_stage` to expose the same top-level contract shape, **so that** adapters do not need endpoint-specific parsing rules.

**Acceptance Criteria:**
- [ ] Both endpoints return `current_state` (not `next_state`) at the top level.
- [ ] `agent_hint` exposes adapter-neutral keys: `agent`, `role`, `mode`, `instructions`.
- [ ] `codex_subagent` is still available with the OLD keys (`codex_role`, `pathly_agent`) as a frozen compat field — inner keys are NOT changed.
- [ ] Blocked/escalated responses have the same top-level shape as normal responses (`agent_hint`, `storage_path`, `stage_brief`).

**Edge Cases:**
- A completion call returns a blocked or escalated decision.
- The feature is resumed after an interrupted session and the FSM reconstructs the same state deterministically.

**Delivered by:** Phase 1 → Conversation 1

### Story 1.2: Separate block from escalate
**As a** builder, **I want** a strict `block` versus `escalate` decision model, **so that** I can stop on agent-resolvable issues and surface human-resolvable feedback without inventing local policy.

**Acceptance Criteria:**
- [ ] Agent-target feedback files → `decision = "block"` (automated retry with a Pathly agent is appropriate).
- [ ] Human-target feedback, corrupt state, unknown feedback → `decision = "escalate"` (human input required).
- [ ] Gate failure with no routable feedback → `decision = "escalate"`.
- [ ] The adapter can safely automate `continue` and `block`, but must surface `escalate` to the user.

**Edge Cases:**
- `complete_stage` discovers a gate failure after work has already been performed.
- `recover_state` fails due to corrupt `STATE.json` — must return `escalate`, not crash.
- Retry limits are exceeded and the adapter must halt cleanly.

**Delivered by:** Phase 1 → Conversation 1

### Story 2.1: Expose adapter-agnostic hints
**As a** Codex adapter maintainer, **I want** the runtime hint to be expressed as `agent_hint` with neutral keys, **so that** dispatch logic does not depend on the legacy `codex_subagent` shape.

**Acceptance Criteria:**
- [ ] `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` references `agent_hint.role` and `agent_hint.instructions` as the primary dispatch contract.
- [ ] The Codex surface does not teach consumers to read `codex_subagent` as the primary path.
- [ ] `SKILL_EXECUTION.md` includes a `## Decisions` block documenting `continue`, `block`, and `escalate`.

**Edge Cases:**
- Old transition docs still mention `codex_subagent` — the file may reference it as legacy/compat only, not as primary guidance.
- A consumer warns on an older schema version but still proceeds when the contract is backward-compatible.

**Delivered by:** Phase 2 → Conversation 2

### Story 2.2: Keep the contract bounded
**As a** reviewer, **I want** the cold-start context fields to stay bounded and explicit, **so that** the contract does not grow into an unstructured blob.

**Acceptance Criteria:**
- [ ] `stage_brief` carries only the structured context the adapter needs for the current step.
- [ ] `warnings` remain displayable without requiring adapter-specific parsing logic.
- [ ] The docs explicitly call out what belongs in `block` versus `escalate`.

**Edge Cases:**
- Feedback ages out but is still present on disk.
- Multiple feedback files exist and the adapter must not improvise precedence rules.

**Delivered by:** Phase 2 → Conversation 2
