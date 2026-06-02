# User Stories — pathly-observability

## S-01: Record phase start events via HTTP

**As a** pipeline operator,
**I want** to POST a PHASE_START event to `/record_phase` when an agent begins a named phase,
**so that** I can see which phase was active when a session started or failed.

### Acceptance criteria

- [ ] `POST /record_phase` with `{feature, agent, phase, event_type: "PHASE_START"}` returns `{"status": "recorded"}` and HTTP 200
- [ ] A `PHASE_START` JSON line is appended to `pathly/plans/<feature>/EVENTS.jsonl`
- [ ] The appended line matches the canonical schema: `schema_version`, `type`, `phase`, `agent`, `feature`, `ts` (ISO-8601 UTC) all present
- [ ] `POST /record_phase` with missing required field (`feature`, `agent`, `phase`, or `event_type`) returns HTTP 400 with a JSON error body
- [ ] `event_type` value other than `"PHASE_START"` or `"PHASE_DONE"` returns HTTP 400
- [ ] `phase` value not in the allowed enum (`analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`) returns HTTP 400
- [ ] Calling the endpoint for a feature whose `EVENTS.jsonl` does not exist yet creates the file

### Edge cases (see EDGE_CASES.md: EC-01, EC-02)

---

## S-02: Record phase done events via HTTP

**As a** pipeline operator,
**I want** to POST a PHASE_DONE event to `/record_phase` when an agent finishes a named phase,
**so that** I can compute phase duration and verify scout counts against rigor level.

### Acceptance criteria

- [ ] `POST /record_phase` with `{feature, agent, phase, event_type: "PHASE_DONE", total_tokens, tool_uses, scouts_count}` returns `{"status": "recorded"}` and HTTP 200
- [ ] The appended `PHASE_DONE` line includes all optional numeric fields when supplied: `total_tokens`, `tool_uses`, `scouts_count`, `conv`
- [ ] Optional fields omitted from the request body are omitted from the JSONL line (not written as `null`)
- [ ] A `PHASE_DONE` event can be written for a phase with no preceding `PHASE_START` — the endpoint does not enforce ordering
- [ ] Existing `AGENT_DONE` events in the file are not modified

### Edge cases (see EDGE_CASES.md: EC-03)

---

## S-03: Exempt-prefix support via flow YAML

**As a** framework developer,
**I want** `_is_exempt()` to read exempt path prefixes from the active flow YAML instead of a hardcoded list,
**so that** new adapter output paths can be added without editing Python source.

### Acceptance criteria

- [ ] When the active flow YAML contains a `scope_gate.exempt_prefixes` list, those prefixes are used by `_is_exempt()` in addition to any remaining hardcoded defaults
- [ ] When `scope_gate.exempt_prefixes` is absent from the YAML, `_is_exempt()` behaves exactly as before (backwards-compatible)
- [ ] Adding a new prefix to the YAML and reloading the FSM causes `_is_exempt()` to recognize the new prefix without restarting the Python process
- [ ] All existing `_is_exempt` tests pass

### Edge cases (see EDGE_CASES.md: EC-04)

---

## S-04: Phase-boundary logging in build.md

**As a** builder agent,
**I want** `build.md` to call `log-phase PHASE_START` and `log-phase PHASE_DONE` at the boundary of each named phase (Analyze, Scout, Implement),
**so that** EVENTS.jsonl reflects where build time is actually spent.

### Acceptance criteria

- [ ] `build.md` Step 1 (or equivalent phase entry) includes a `log-phase PHASE_START analyze` call before any analysis work
- [ ] `build.md` logs `PHASE_DONE analyze` before entering the Scout phase
- [ ] `build.md` logs `PHASE_START scout` before spawning any scout agents
- [ ] `build.md` logs `PHASE_DONE scout` (with `scouts_count`) before entering Implement
- [ ] `build.md` logs `PHASE_START implement` at the start of code changes
- [ ] `build.md` logs `PHASE_DONE implement` after all edits and the verify step
- [ ] `grep "log-phase\|PHASE_START\|PHASE_DONE" src/pathly_data/core/skills/development/build.md` returns at least 6 matches

### Edge cases (see EDGE_CASES.md: EC-05)

---

## S-05: Phase-boundary logging in review.md and test.md

**As a** reviewer or tester agent,
**I want** `review.md` and `test.md` to call `log-phase` at phase boundaries,
**so that** review and test phases appear in EVENTS.jsonl alongside build phases.

### Acceptance criteria

- [ ] `review.md` logs `PHASE_START` and `PHASE_DONE` for each of its named phases (Analyze, Scout, Review)
- [ ] `test.md` logs `PHASE_START` and `PHASE_DONE` for each of its named phases (Analyze, Scout, Test)
- [ ] Neither file had HTTP calls before — the only new HTTP surface is via `log-phase`
- [ ] `grep "log-phase" src/pathly_data/core/skills/development/review.md` returns at least 4 matches
- [ ] `grep "log-phase" src/pathly_data/core/skills/development/test.md` returns at least 4 matches

---

## S-06: Phase-boundary logging in plan.md + new log-phase utility

**As a** planner agent,
**I want** a `log-phase` utility skill and phase calls in `plan.md`,
**so that** plan phases are observable and other skills can reuse the same utility.

### Acceptance criteria

- [ ] `src/pathly_data/core/skills/utilities/log-phase.md` exists and documents the `curl` call to `/record_phase`
- [ ] The utility skill accepts arguments: `feature`, `agent`, `phase`, `event_type`, and optional `scouts_count`
- [ ] `plan.md` calls `log-phase` at the boundary of each of its named phases
- [ ] `grep "log-phase" src/pathly_data/core/skills/planning/plan.md` returns at least 2 matches

---

## S-07: Three-phase structure in design.md and storm.md

**As a** designer or storm agent,
**I want** `design.md` and `storm.md` to have an explicit analyze phase before acting,
**so that** they follow the same observable multi-phase contract as build/review/test.

### Acceptance criteria

- [ ] `design.md` has a `phase: analyze` section that runs before the main design script
- [ ] `storm.md` has a `phase: analyze` section that runs before interactive conversation
- [ ] Both files call `log-phase PHASE_START analyze` at the top of their analyze section
- [ ] `grep -n "Phase: analyze" src/pathly_data/core/skills/development/design.md src/pathly_data/core/skills/planning/storm.md` returns at least 2 matches

---

## S-08: Rigor contract tables in agent files

**As a** builder, reviewer, tester, planner, or architect agent,
**I want** a `rigor_contract` table in my agent contract file,
**so that** I know exactly what actions are required or forbidden at each rigor level without re-reading a separate document.

### Acceptance criteria

- [ ] All six agent files contain a `## Rigor contract` section with the canonical rigor table (nano / lite / standard / strict columns)
- [ ] Each row in the table is role-specific — not a copy of a generic table
- [ ] `grep -r "rigor_contract\|Rigor contract" src/pathly_data/core/agents/` returns at least 6 matches (one per agent file)

---

## S-09: stage_brief sections in agent files

**As a** pipeline director or operator reading a conversation output,
**I want** each agent file to have a `stage_brief` section describing what the agent's stage produces and how to know it is done,
**so that** the FSM can surface a plain-language status without reading full conversation logs.

### Acceptance criteria

- [ ] All six agent files contain a `## Stage brief` section
- [ ] Each `stage_brief` states: the stage name, primary output artifact, and one-line done condition
- [ ] `grep -r "Stage brief\|stage_brief" src/pathly_data/core/agents/` returns at least 6 matches
- [ ] Adapter propagation runs without error: `pathly-setup claude --apply && pathly-setup codex --apply`

---

## S-10: fast/auto mode chains build → review automatically

**As a** developer running `/pathly build <feature> fast`,
**I want** the build skill to automatically invoke the reviewer after a successful build,
**so that** I don't have to manually trigger review after each conversation.

### Acceptance criteria

- [ ] `build.md` recognises both `"auto"` and `"fast"` as auto-flow mode triggers
- [ ] In auto-flow mode, after `log-agent-done` completes and verification passed, `build.md` invokes `review <feature> <N>`
- [ ] In auto-flow mode, if verification failed, `build.md` does NOT chain to review — it stops and reports
- [ ] In non-auto mode (no `fast`/`auto` arg), `build.md` behaviour is unchanged — no auto-chain
- [ ] `grep "fast\|auto.*mode" src/pathly_data/core/skills/development/build.md` shows the updated auto-detection line

---

## S-11: Reviewer marks conversation DONE in PROGRESS.md on pass

**As a** pipeline operator,
**I want** the review skill to update `PROGRESS.md` and `STATE.json` when it passes,
**so that** conversation progress is tracked automatically without manual orchestrator calls.

### Acceptance criteria

- [ ] When called as `review <feature> <N>` and reviewer returns PASS: the Conv `<N>` row in PROGRESS.md changes from `TODO` to `DONE`
- [ ] After marking DONE: if all convs are DONE, STATE.json transitions to `"TESTING"`; otherwise to `"BUILDING"`
- [ ] A `STATE_TRANSITION` event and an `AGENT_DONE` (reviewer) event are appended to EVENTS.jsonl on pass
- [ ] When reviewer returns FAIL: `REVIEW_FAILURES.md` is written, STATE.json → `"REVIEW_FAILED"`, PROGRESS.md is NOT updated
- [ ] `grep "Exit contract\|REVIEW_FAILED\|TESTING" src/pathly_data/core/skills/development/review.md` returns at least 3 matches
