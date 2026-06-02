# Conversation Prompts — pathly-observability

Each prompt below is self-contained. Paste the full block as the opening message for that conversation.

---

## Conv 1 — Python infrastructure

**Stories delivered:** S-01, S-02, S-03
**Verify command:** `python -m pytest tests/ -q`

```
phase: implement

FEATURE: pathly-observability
CONVERSATION: 1 of 4 — Python infrastructure
STORIES: S-01 (record phase start), S-02 (record phase done), S-03 (exempt-prefix via YAML)

## Phase 0 — Pre-flight (L-001)

Before writing any code:
1. Run `python -m pytest tests/ -q` and confirm the baseline is green. If tests fail, stop and
   report — do not proceed with edits until the baseline is clean.
2. Run `grep -n "_is_exempt\|record_activity\|EVENTS" src/pathly_orchestrator/http_server.py`
   to confirm the file structure matches what is documented below.
3. Glob `src/pathly_data/core/flows/` to find all flow YAML files and identify which one to edit
   for S-03. Report the file path before editing.

## Context

Current state (from scout findings):
- `/record_activity` endpoint exists in http_server.py. Fields: agent, feature, summary (required),
  plus optional: input_tokens, output_tokens, wall_seconds, tool_uses, total_tokens, duration_ms,
  cost_usd, model, result, conversation, project_root. No `phase` field.
- EVENTS.jsonl today records only AGENT_DONE events. Schema: schema_version, type, ts, agent,
  model, result, total_tokens, tokens_in, tokens_out, tool_uses, wall_seconds, cost_usd, conversation.
- `_is_exempt()` in fsm.py lines 468-469 is hardcoded: p.startswith("pathly/plans/") or
  p.endswith(".tsbuildinfo"). No YAML support.
- `recover_state()` on JSONDecodeError silently sets state_doc = {}.

## Task 1 — /record_phase endpoint (S-01, S-02)

Add a new POST /record_phase endpoint to http_server.py.

Endpoint contract:
  POST /record_phase
  Required body fields: feature (str), agent (str), phase (str), event_type (str)
  Optional body fields: conv (int), total_tokens (int), tool_uses (int), scouts_count (int), summary (str)
  Returns: {"status": "recorded"} on success (HTTP 200)
  Returns: {"error": "<description>"} on validation failure (HTTP 400)

Validation rules:
  - All four required fields must be present and non-empty strings
  - event_type must be exactly "PHASE_START" or "PHASE_DONE"
  - phase must be one of: analyze, scout, implement, review, test, plan, design, storm

Side effect:
  Append one JSON line to pathly/plans/<feature>/EVENTS.jsonl
  Create the file if it does not exist (but do NOT create missing parent directories)

Event schema to write for PHASE_START:
  {"schema_version":1,"type":"PHASE_START","phase":"<phase>","agent":"<agent>","feature":"<feature>","conv":<N>,"ts":"<ISO-8601 UTC>"}
  - Omit optional fields that were not supplied in the request body (do not write null)

Event schema to write for PHASE_DONE:
  {"schema_version":1,"type":"PHASE_DONE","phase":"<phase>","agent":"<agent>","feature":"<feature>","conv":<N>,"total_tokens":<N>,"tool_uses":<N>,"scouts_count":<N>,"ts":"<ISO-8601 UTC>"}
  - Omit optional fields that were not supplied

## Task 2 — Exempt-prefix via flow YAML (S-03)

Edit _is_exempt() in fsm.py to read scope_gate.exempt_prefixes from the active flow YAML.

Behavior:
  - If scope_gate.exempt_prefixes exists in the YAML, use those prefixes IN ADDITION to the
    existing hardcoded defaults (pathly/plans/ and .tsbuildinfo). Do not remove the hardcoded
    defaults — this must be backwards-compatible.
  - If scope_gate.exempt_prefixes is absent, behavior is identical to today.
  - The YAML is already loaded when _is_exempt() runs — do not add a new file read.
  - Identify the correct flow YAML file path by globbing src/pathly_data/core/flows/ in Phase 0.
  - Add scope_gate.exempt_prefixes: [] as an empty list to the YAML (no new prefixes yet —
    just wire up the plumbing so the field is recognized).

## Task 3 — Tests

Add or update tests in tests/ to cover:
  - POST /record_phase with valid PHASE_START body → 200, line appended to EVENTS.jsonl
  - POST /record_phase with valid PHASE_DONE body + all optional fields → 200, all fields present
  - POST /record_phase with missing required field → 400
  - POST /record_phase with invalid event_type → 400
  - POST /record_phase with invalid phase value → 400
  - _is_exempt() with scope_gate.exempt_prefixes in YAML — new prefix is recognized
  - _is_exempt() with scope_gate.exempt_prefixes absent — existing behavior unchanged

## Done when

`python -m pytest tests/ -q` passes with all new tests included. Report the test count before
and after to confirm new tests were added.

File: src/pathly_orchestrator/http_server.py
File: src/pathly_orchestrator/fsm.py
File: src/pathly_data/core/flows/<glob-to-confirm>.yaml
File: tests/ (new or updated test file)
Done when: `python -m pytest tests/ -q` exits 0 with ≥7 new test cases
```

---

## Conv 2 — Skill phase logging

**Stories delivered:** S-04, S-05, S-06
**Gate:** Conv 1 tests must be green before starting
**Verify command:** `grep -r "log-phase\|PHASE_START" src/pathly_data/core/skills/development/`

```
phase: implement

FEATURE: pathly-observability
CONVERSATION: 2 of 4 — Skill phase logging
STORIES: S-04 (build.md logging), S-05 (review.md + test.md logging), S-06 (plan.md + log-phase utility)

## Phase 0 — Pre-flight (L-001)

Before editing any skill files:
1. Run `python -m pytest tests/ -q` to confirm Conv 1 delivered a green baseline.
   If tests fail, stop — do not proceed.
2. Read each of the four skill files to understand their current structure before editing:
   - src/pathly_data/core/skills/development/build.md
   - src/pathly_data/core/skills/development/review.md
   - src/pathly_data/core/skills/development/test.md
   - src/pathly_data/core/skills/development/plan.md
3. Check whether src/pathly_data/core/skills/utilities/ exists. If not, create the directory.
4. Glob src/pathly_data/core/skills/ to confirm directory structure before writing.

## Context

Current state (from scout findings):
- build.md: 3-phase structure (Analyze→Scout→Implement). BUILD_START at Step 4.5, log-agent-done
  at Step 7. NO phase-boundary calls between phases.
- review.md: 3-phase structure (Analyze→Scout→Review). NO HTTP calls at all.
- test.md: 5-step structure (Analyze→Scout→Test→Fix loop→Report). NO HTTP calls at all.
- plan.md: 6-step structure with 3-phase codebase gathering. NO HTTP calls at all.
- src/pathly_data/core/skills/utilities/ — check if this directory exists (Phase 0 step 3).

## Task 1 — Create log-phase utility skill (S-06)

Create src/pathly_data/core/skills/utilities/log-phase.md.

This file documents how any skill calls /record_phase. It must include:
  - Purpose: log a phase boundary event to EVENTS.jsonl via the HTTP server
  - Usage syntax: log-phase <event_type> <phase> [optional args]
  - The exact curl command to use:
    curl -s -X POST http://127.0.0.1:8765/record_phase \
      -H "Content-Type: application/json" \
      -d '{"feature":"<FEATURE>","agent":"<AGENT>","phase":"<PHASE>","event_type":"<EVENT_TYPE>"}'
  - How to pass optional fields (conv, scouts_count, total_tokens, tool_uses)
  - Note: If the HTTP server is not running, the curl will fail silently — this is acceptable.
    Phase logging is best-effort and must never block skill execution.

## Task 2 — build.md phase logging (S-04)

Edit src/pathly_data/core/skills/development/build.md to add log-phase calls at phase boundaries.

Add these calls at the precise phase entry/exit points already present in the file structure:
  - Before the first analysis step: log-phase PHASE_START analyze
  - After analysis, before scout spawning: log-phase PHASE_DONE analyze
  - Before spawning any scout agents: log-phase PHASE_START scout
  - After all scouts return (include scouts_count in the call): log-phase PHASE_DONE scout
  - Before writing any code or file edits: log-phase PHASE_START implement
  - After all edits and the verify step: log-phase PHASE_DONE implement

Keep existing BUILD_START and log-agent-done calls intact. Add log-phase calls around them,
not instead of them.

## Task 3 — review.md and test.md phase logging (S-05)

Edit src/pathly_data/core/skills/development/review.md to add log-phase calls at its three
phase boundaries (Analyze, Scout, Review). Same pattern as Task 2.

Edit src/pathly_data/core/skills/development/test.md to add log-phase calls at its phase
boundaries (Analyze, Scout, Test). Include scouts_count on PHASE_DONE scout calls.

## Task 4 — plan.md phase logging (S-06)

Edit src/pathly_data/core/skills/development/plan.md to add log-phase calls at its phase
boundaries. The 6-step structure has a 3-phase codebase gathering section — log phase start/done
at the entry and exit of each named phase.

## Done when

`grep -r "log-phase\|PHASE_START" src/pathly_data/core/skills/development/` returns at least
10 matches across the four skill files.

File: src/pathly_data/core/skills/utilities/log-phase.md (new)
File: src/pathly_data/core/skills/development/build.md
File: src/pathly_data/core/skills/development/review.md
File: src/pathly_data/core/skills/development/test.md
File: src/pathly_data/core/skills/development/plan.md
Done when: grep returns ≥10 matches; all phase calls follow the pattern in log-phase.md
```

---

## Conv 3 — design.md + storm.md phases

**Stories delivered:** S-07
**Gate:** none (can run independently of Conv 2)
**Verify command:** `grep -n "phase: analyze" src/pathly_data/core/skills/development/design.md src/pathly_data/core/skills/development/storm.md`

```
phase: implement

FEATURE: pathly-observability
CONVERSATION: 3 of 4 — design.md + storm.md phases
STORIES: S-07 (three-phase structure in design.md and storm.md)

## Phase 0 — Pre-flight (L-001)

Before editing:
1. Read both files in full to understand their current structure:
   - src/pathly_data/core/skills/development/design.md
   - src/pathly_data/core/skills/development/storm.md
2. Check whether src/pathly_data/core/skills/utilities/log-phase.md exists.
   If it does not exist yet (Conv 2 not done), write the log-phase calls as inline curl
   commands in the skill files rather than referencing the utility. Note this in a comment.

## Context

Current state (from scout findings):
- design.md: Single-pass skill — calls pathly-design CLI directly. NO phases. NO logging.
- storm.md: Interactive conversational mode. Optional quick spawn at entry. NO phases. NO logging.

## Task 1 — design.md analyze phase (S-07)

Prepend a ## Phase: analyze section to design.md BEFORE the existing main script.

The analyze phase must:
  - Call log-phase PHASE_START analyze (or inline curl if log-phase.md not yet available)
  - Read the feature's USER_STORIES.md and IMPLEMENTATION_PLAN.md if they exist
  - Identify existing design artifacts (glob pathly/plans/<feature>/ for any DESIGN*.md files)
  - Summarize the design constraints in 3-5 bullet points before proceeding to the main script
  - Call log-phase PHASE_DONE analyze before entering the main design script

The existing pathly-design CLI call and main script must remain intact below the new section.

## Task 2 — storm.md analyze phase (S-07)

Prepend a ## Phase: analyze section to storm.md BEFORE the existing interactive conversation.

The analyze phase must:
  - Call log-phase PHASE_START analyze (or inline curl if log-phase.md not yet available)
  - Read the feature's FEATURE_INDEX.md if it exists (to understand prior framing)
  - Note any existing USER_STORIES.md entries that may bound the scope discussion
  - Call log-phase PHASE_DONE analyze before beginning interactive conversation

The existing interactive storm conversation must remain intact below the new section.

## Done when

`grep -n "phase: analyze" src/pathly_data/core/skills/development/design.md \
  src/pathly_data/core/skills/development/storm.md` returns at least 2 matches (one per file).

File: src/pathly_data/core/skills/development/design.md
File: src/pathly_data/core/skills/development/storm.md
Done when: grep returns ≥2 matches; both files have log-phase calls (or inline curl) in the analyze section
```

---

## Conv 4 — Agent contracts + adapter propagation

**Stories delivered:** S-08, S-09
**Gate:** Conv 2 and Conv 3 should both be complete (agents reference the log-phase utility)
**Verify command:** `grep -r "Rigor contract" src/pathly_data/core/agents/`

```
phase: implement

FEATURE: pathly-observability
CONVERSATION: 4 of 4 — Agent contracts + adapter propagation
STORIES: S-08 (rigor_contract tables), S-09 (stage_brief sections)

## Phase 0 — Pre-flight (L-001)

Before editing any agent files:
1. Glob src/pathly_data/core/agents/ to confirm all six target files exist and get their exact paths.
2. Read each of the six agent files in full before making any edits:
   - src/pathly_data/core/agents/building/builder.md
   - src/pathly_data/core/agents/quality/reviewer.md
   - src/pathly_data/core/agents/quality/tester.md
   - src/pathly_data/core/agents/planning/planner.md
   - src/pathly_data/core/agents/planning/architect.md
   - src/pathly_data/core/agents/building/designer.md
3. Check that pathly-setup is available: run `pathly-setup --help` and confirm it exits 0.

## Context

Current state (from scout findings):
- builder.md: sections = Execution discipline, Code quality, Sub-agents, Phase:analyze,
  Phase:implement, Artifact archiving, When blocked, Reporting. NO rigor_contract, NO stage_brief.
- reviewer.md: sections = Review mindset, What to check, Output format, AUTO_FIX, Sub-agents,
  Phase:analyze, Artifact archiving, What NOT to do. NO rigor_contract, NO stage_brief.
- tester.md: sections = Behavior rules, Test plan format, Phase:analyze, Sub-agents, Phase:test,
  Artifact archiving, What NOT to do. NO rigor_contract, NO stage_brief.
- planner.md: sections = Active lessons, Thinking style, User stories, Planning convs, Escalation,
  Traceability, Sub-agents, Phase:analyze, What NOT to do. NO rigor_contract, NO stage_brief.
- architect.md: sections = Thinking style, ASCII diagrams, Phase:analyze, What to explore,
  Sub-agents, What NOT to do. NO rigor_contract, NO stage_brief.
- designer.md: sections = Thinking style, Script, Responsibilities, Output contract, Boundaries,
  Failure behavior. NO rigor_contract, NO stage_brief.

## Task 1 — Add rigor_contract sections (S-08)

Add a ## Rigor contract section to each of the six agent files.

Use the role-specific tables from IMPLEMENTATION_PLAN.md. Do NOT copy a generic table to all
six files — each table must match the agent's specific actions and outputs.

Placement: add the section immediately before the ## What NOT to do section if one exists;
otherwise add it as the second-to-last section in the file.

### Rigor contract tables

**builder.md:**
| Rigor | Scout limit | Verify gate | Scope gate |
|---|---|---|---|
| nano | no scouts | none | none |
| lite | 1 scout allowed | typecheck only | none |
| standard | up to 4 scouts | tests pass | scope_gate active |
| strict | up to 4 scouts + wide required | tests + review pass | scope_gate + audit |

**reviewer.md:**
| Rigor | Input | Scope | Extra |
|---|---|---|---|
| nano | skip review entirely | — | — |
| lite | diff + rules check | — | — |
| standard | diff + rules + scope gate | active | — |
| strict | standard + security check | active | REVIEW_FAILURES.md required |

**tester.md:**
| Rigor | Coverage | Edge cases | Regression |
|---|---|---|---|
| nano | smoke only (1 path) | none | none |
| lite | happy path | none | none |
| standard | happy path + edge cases | per EDGE_CASES.md | none |
| strict | standard + regression suite | full | TEST_FAILURES.md required |

**planner.md:**
| Rigor | Scouts | PO session | Stories |
|---|---|---|---|
| nano | skip consult | not required | 1–2 stories |
| lite | 1 scout | not required | 2–4 stories |
| standard | full consult + up to 4 scouts | optional | full story set |
| strict | full consult + up to 4 scouts | required | full set + PO sign-off |

**architect.md:**
| Rigor | Research | Web | Output |
|---|---|---|---|
| nano | direct answer, no scouts | none | inline answer |
| lite | 1 scout | none | DESIGN_SPEC.md draft |
| standard | up to 4 scouts | optional | DESIGN_SPEC.md full |
| strict | up to 4 scouts | web-researcher required | DESIGN_SPEC.md + ARCH_REVIEW.md |

**designer.md:**
| Rigor | Phase 1 (analyze) | Scouts | Audit |
|---|---|---|---|
| nano | skip | none | none |
| lite | 1 scout | 1 scout | none |
| standard | full 3-phase | up to 4 scouts | — |
| strict | full 3-phase | up to 4 scouts | DESIGN_REVIEW.md required |

## Task 2 — Add stage_brief sections (S-09)

Add a ## Stage brief section to each of the six agent files.

Placement: add immediately after the opening description paragraph (before the first major section).

Each stage_brief must state exactly three things on separate lines:
  Stage: <pipeline stage name>
  Output: <primary artifact produced>
  Done when: <one-line binary condition>

Use these values:

**builder.md:**
  Stage: BUILD
  Output: Working code committed to the feature branch, all verify steps passing
  Done when: `python -m pytest tests/ -q` (or equivalent) exits 0 and scope gate passes

**reviewer.md:**
  Stage: REVIEW
  Output: REVIEW_FAILURES.md (or explicit "no failures" statement in conversation)
  Done when: Reviewer has read every changed file and written or cleared REVIEW_FAILURES.md

**tester.md:**
  Stage: TEST
  Output: TEST_FAILURES.md (or explicit "all tests pass" statement in conversation)
  Done when: All acceptance criteria in USER_STORIES.md checked as pass or fail with evidence

**planner.md:**
  Stage: PLAN
  Output: USER_STORIES.md, IMPLEMENTATION_PLAN.md, CONVERSATION_PROMPTS.md written to plans/
  Done when: All nine plan files exist in pathly/plans/<feature>/ and PROGRESS.md shows TODO rows

**architect.md:**
  Stage: DESIGN
  Output: DESIGN_SPEC.md written to pathly/plans/<feature>/
  Done when: DESIGN_SPEC.md contains a decision for every open architectural question in the plan

**designer.md:**
  Stage: DESIGN (UI/UX)
  Output: Design tokens, component spec, or DESIGN_REVIEW.md in pathly/plans/<feature>/
  Done when: All UI components in scope have a documented design decision or spec reference

## Task 3 — Adapter propagation

After all six agent files are edited and saved:

1. Run `pathly-setup claude --apply`
2. Confirm exit code 0
3. Run `pathly-setup codex --apply`
4. Confirm exit code 0
5. Spot-check that the rigor_contract section appears in the deployed builder agent file.
   For claude: grep "Rigor contract" ~/.claude/agents/builder.md (or equivalent installed path)

## Done when

1. `grep -r "Rigor contract" src/pathly_data/core/agents/` returns 6 matches
2. `grep -r "Stage brief" src/pathly_data/core/agents/` returns 6 matches
3. `pathly-setup claude --apply` exits 0
4. `pathly-setup codex --apply` exits 0

File: src/pathly_data/core/agents/building/builder.md
File: src/pathly_data/core/agents/quality/reviewer.md
File: src/pathly_data/core/agents/quality/tester.md
File: src/pathly_data/core/agents/planning/planner.md
File: src/pathly_data/core/agents/planning/architect.md
File: src/pathly_data/core/agents/building/designer.md
Done when: grep returns ≥6 matches each for "Rigor contract" and "Stage brief"; both pathly-setup calls exit 0
```
