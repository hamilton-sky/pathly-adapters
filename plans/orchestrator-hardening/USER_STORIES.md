# orchestrator-hardening — User Stories

## Context

The `orchestrator/` and `hooks/` directories sit at the repo root but are excluded
from `pyproject.toml`'s `packages.find`, so they are not shipped in the wheel.
Their docstrings advertise CLI commands (`python -m orchestrator.eventlog summary
<feature>`) that end users cannot run after `pipx install pathly-adapters`.

At the same time, the FSM concept is load-bearing: 13 state names live in
`orchestrator/state.py:25`, 8 event types in `events.py:73`, and 90+ skill/agent
markdown files reference `STATE.json` / `EVENTS.jsonl`. The example in
`events.py:71` already shows non-canonical state names (`BUILDING_CONV_1`) that
are not in the `STATES` dict — drift is happening today.

`protocol_contract.yaml` is hand-mirrored between this repo and `pathly-engine`,
enforced only by failing tests in two separate CI runs. The classification hook
uses naive keyword matching including `"how"`, which matches almost any question.

This plan tightens these eight concrete issues without changing user-facing
behavior of the installer.

## Stories

### Story 1: Orchestrator and hooks are first-class shipped code

**As a** Pathly end user, **I want** `pathly-events` and `pathly-state` console
scripts available after `pipx install pathly-adapters`, **so that** I can inspect
my own pipeline runs without cloning the source repo.

**Acceptance Criteria:**
- [ ] `pathly-events summary <feature>` runs after a clean pipx install.
- [ ] `pathly-state <feature>` prints current FSM state from `plans/<feature>/STATE.json`.
- [ ] No code remains at the repo root under `orchestrator/` or `hooks/`.
- [ ] `pyproject.toml` includes `pathly_orchestrator*` and `pathly_hooks*` in `packages.find`.

**Delivered by:** Phase 1.1, 1.2, 1.3 → Conversation 1

### Story 2: STATE.json is schema-validated with a transition table

**As a** developer modifying the FSM, **I want** invalid state names and illegal
transitions to fail loudly when `write_state` is called, **so that** drift like
`BUILDING_CONV_1` cannot silently corrupt the event log.

**Acceptance Criteria:**
- [ ] `schemas/state.schema.json` exists with an enum of the 13 canonical state names.
- [ ] Schema defines allowed `from_state → to_state` pairs.
- [ ] `pathly_orchestrator.eventlog.write_state` raises on an invalid state name.
- [ ] `write_state` raises on a `STATE_TRANSITION` event that violates the table.
- [ ] At least one test asserts the raise on each violation type.

**Delivered by:** Phase 2.1, 2.2 → Conversation 2

### Story 3: EVENTS.jsonl is safe under concurrent writes

**As a** team-flow orchestrator spawning agents in parallel, **I want** appended
event lines never to interleave, **so that** the event log stays parseable when
two `AGENT_DONE` events fire near-simultaneously.

**Acceptance Criteria:**
- [ ] `append_event` holds an OS-level file lock for the duration of the write.
- [ ] A test spawns 10 concurrent writers and confirms every line round-trips through `json.loads`.
- [ ] No regression in single-writer throughput beyond a small margin.

**Delivered by:** Phase 2.3 → Conversation 2

### Story 4: Pipeline observability is documented in the README

**As a** new Pathly user, **I want** the README to mention `pathly-events` and
`pathly-state`, **so that** I know an inspection surface exists alongside `pathly-tokens`.

**Acceptance Criteria:**
- [ ] README "All commands" block lists `pathly-events summary <feature>` and `pathly-state <feature>`.
- [ ] CHANGELOG entry describes the new console scripts.

**Delivered by:** Phase 1.4 → Conversation 1

### Story 5: Feedback classification no longer mis-tags requirements as architecture

**As a** user filing an `IMPL_QUESTION`, **I want** the question to stay tagged
`[REQ]` unless it is actually architectural, **so that** routing to the architect
agent is not triggered by the word "how".

**Acceptance Criteria:**
- [ ] When `ANTHROPIC_API_KEY` is unset, the heuristic path either runs without the `"how"` keyword or is gated off entirely.
- [ ] A test asserts that "How long does this take?" is tagged `[REQ]`, not `[ARCH]`.
- [ ] A test asserts that "What design approach handles retries?" is tagged `[ARCH]`.

**Delivered by:** Phase 3.1 → Conversation 3

### Story 6: protocol_contract.yaml has a version field and runtime cross-check

**As a** maintainer of both `pathly-adapters` and `pathly-engine`, **I want** a
runtime check that fails fast when the two repos disagree, **so that** silent
drift between feedback file sets cannot escape into a release.

**Acceptance Criteria:**
- [ ] `protocol_contract.yaml` carries a `version: <int>` field.
- [ ] `tests/test_feedback_protocol.py` reads the version and asserts it matches a constant in `src/pathly_hooks/__init__.py`.
- [ ] CHANGELOG documents the bump procedure.

**Delivered by:** Phase 3.2 → Conversation 3

### Story 7: Hook parity gap across hosts is documented

**As a** Codex or Copilot user, **I want** the docs to tell me that the hook
surface is Claude-only today, **so that** I do not assume `classify_feedback`
runs in my environment.

**Acceptance Criteria:**
- [ ] `docs/SECURITY.md` includes a "Hook surface coverage" section listing per-host status.
- [ ] README "Known Limitations" mentions the gap.

**Delivered by:** Phase 4.1 → Conversation 4

### Story 8: Per-stage iteration counter replaces build-only `current_conversation`

**As a** planner running multiple decomposition rounds, **I want** a planning-stage
iteration count tracked in STATE.json, **so that** retry logic is not silently
clipped to build-stage iterations only.

**Acceptance Criteria:**
- [ ] `schemas/state.schema.json` defines `iteration_by_stage: {planning: int, building: int, reviewing: int, testing: int}` as an optional object.
- [ ] Existing `current_conversation` field continues to read correctly (back-compat).
- [ ] `src/pathly_data/core/skills/team-flow.md` references the new field where iteration matters.

**Delivered by:** Phase 4.2 → Conversation 4
