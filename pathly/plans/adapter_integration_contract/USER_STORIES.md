---
name: User Stories
---
# Adapter Integration Contract — User Stories

## Context
Pathly currently has a useful but incomplete adapter contract. The FSM still returns a `codex_subagent` blob, response shapes differ between `next_action` and `complete_stage`, and the Codex-facing docs still depend on the older shape. This feature tightens the contract so adapters receive a stable, adapter-agnostic payload with explicit decision semantics, structured context, and a clear boundary between automated continuation and human escalation.

## Stories

### Story 1.1: Normalize FSM response shape
**As a** platform integrator, **I want** `next_action` and `complete_stage` to expose the same top-level contract shape, **so that** adapters do not need endpoint-specific parsing rules.

**Acceptance Criteria:**
- [ ] Both endpoints return `schema_version`, `decision`, `current_state`, `conv`, `role`, `agent_hint`, `stage_brief`, `warnings`, and `storage_path` where applicable.
- [ ] `codex_subagent` is still available only as a compatibility field during the transition, but the new contract fields are the primary surface.
- [ ] `complete_stage` no longer forces adapters to special-case `next_state`-only payloads in normal flow.

**Edge Cases:**
- A completion call returns a blocked or escalated decision.
- The feature is resumed after an interrupted session and the FSM reconstructs the same state deterministically.

**Delivered by:** Phase 1 → Conversation 1

### Story 1.2: Separate block from escalate
**As a** builder, **I want** a strict `block` versus `escalate` decision model, **so that** I can stop on structural issues and surface human-resolvable feedback without inventing local policy.

**Acceptance Criteria:**
- [ ] Feedback files and human questions map to `block`.
- [ ] Corrupt state and unknown feedback route to `escalate`.
- [ ] The adapter can safely automate `continue` but must surface `block` and `escalate`.

**Edge Cases:**
- `complete_stage` discovers a gate failure after work has already been performed.
- Retry limits are exceeded and the adapter must halt cleanly.

**Delivered by:** Phase 1 → Conversation 1

### Story 2.1: Expose adapter-agnostic hints
**As a** Codex adapter maintainer, **I want** the runtime hint to be expressed as `agent_hint`, **so that** dispatch logic does not depend on the legacy `codex_subagent` shape.

**Acceptance Criteria:**
- [ ] `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` references `agent_hint.role` and `agent_hint.instructions`.
- [ ] The Codex surface no longer teaches consumers to read `codex_subagent.codex_role`.
- [ ] Setup / packaging assertions reflect the new contract shape.

**Edge Cases:**
- Old transition docs still mention `codex_subagent` while the implementation is being migrated.
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
