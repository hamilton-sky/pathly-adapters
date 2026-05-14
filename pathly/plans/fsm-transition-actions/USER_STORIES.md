# USER_STORIES.md — fsm-transition-actions

_Decomposed from PO_NOTES.md. Do not re-author. Story IDs match FEATURE_INDEX.md conv map._

---

## Story S1.1 — Declarative transition_actions in flow YAML schema

**As a** flow author,
**I want** to declare per-transition side effects in the flow YAML under a `transition_actions` key,
**so that** I can add or change flow behavior without touching orchestrator code.

**Delivered by:** Conversation 1

### Acceptance criteria

- `transition_actions` field is present in `team.flow.yaml` with entries for `BUILDING->REVIEWING` (git_commit) and `RETRO->DONE` (archive_artifacts).
- `debug.flow.yaml` contains a `transition_actions` key (may be empty or minimal — flow has no mandatory side effects for MVP).
- `explore.flow.yaml` contains a `transition_actions` key (may be empty or minimal — flow has no mandatory side effects for MVP).
- Every `FROM->TO` key present in any flow's `transition_actions` references a transition pair that exists in that flow's `transitions` list.
- Action type values are limited to: `git_commit`, `update_progress`, `archive_artifacts`.
- Flows without side effects may omit `transition_actions` entirely without breaking schema loading.

---

## Story S1.2 — team.flow.yaml fully migrates all existing side effects

**As a** flow author,
**I want** `team.flow.yaml` to declare all side effects that were formerly hardcoded in orchestrator.md,
**so that** no team-pipeline behavior is lost when orchestrator is generalized.

**Delivered by:** Conversation 1

### Acceptance criteria

- `BUILDING->REVIEWING` transition in team.flow.yaml declares a `git_commit` action with message `"feat: complete building stage"`.
- `RETRO->DONE` transition (or `->DONE` wildcard) declares an `archive_artifacts` action.
- Each action entry has exactly `type` (and `message` where required by the action type).
- Running `grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml` returns at least one match.

---

## Story S2.1 — Orchestrator executes transition_actions generically

**As a** Pathly maintainer,
**I want** the orchestrator to read and execute `transition_actions` from the active flow YAML,
**so that** orchestrator.md becomes a pure FSM engine with no knowledge of any specific flow's side effects.

**Delivered by:** Conversation 2

### Acceptance criteria

- All hardcoded git commit logic is removed from orchestrator.md (lines 125-135 of current file).
- All hardcoded artifact archiving logic is removed from orchestrator.md (lines 142-156 of current file).
- Orchestrator.md contains a transition_actions executor block inserted after the EVENTS.jsonl append step (after current line 84) in the FSM loop.
- The executor looks up `FROM->TO` in `transition_actions` and executes listed actions in YAML-declared order.
- The executor also checks for a `->DONE` wildcard entry when the destination state is `DONE`.
- A transition with no matching `transition_actions` entry executes cleanly as a no-op.
- Running `grep -i "git commit\|artifact archiv\|PROGRESS.md" src/pathly_data/core/agents/orchestrator.md` returns no flow-specific hardcoded lines (only generic executor references).
- The FSM loop lines (state recovery, single-event rule, subagent routing, transition_rules evaluation, STATE.json write, EVENTS.jsonl append) are preserved verbatim.

---

## Story S3.1 — Schema validation recognizes transition_actions

**As a** flow author,
**I want** `state.py` / `validate_flow` to recognize and validate the `transition_actions` key,
**so that** typos in action names or transition keys are caught early instead of silently failing at runtime.

**Delivered by:** Conversation 3 (BLOCKED — see note below)

**BLOCKED:** Conversation 3 is blocked on `fsm-configurable` Phase 5c landing. The `_REQUIRED_FLOW_KEYS` and `validate_flow_cli` constructs in `state.py` do not yet exist; they are deliverables of the upstream feature. Do not begin Conversation 3 until `fsm-configurable` is DONE.

### Acceptance criteria

- `validate_flow` (from fsm-configurable) recognizes `transition_actions` as a known top-level optional key and does not warn about it being unknown.
- Validator warns (does not error) when `transition_actions` is absent from a flow YAML.
- Validator errors with a clear message when an action name is not in the known vocabulary (`git_commit`, `update_progress`, `archive_artifacts`).
- Validator errors with a clear message when a `FROM->TO` key in `transition_actions` does not exist in the flow's `transitions` list.
- `state.py` loads and exposes `transition_actions` so the orchestrator can consume it at runtime.

---

## Edge cases (applicable to all stories)

- A `FROM->TO` key in `transition_actions` references a pair that does not exist in `transitions` — validator must catch this (S3.1), and orchestrator must not crash if validation is skipped (S2.1 no-op behavior).
- An action listed for a transition fails mid-execution (e.g. git commit fails) — orchestrator behavior on partial failure matches current behavior (halt-and-report).
- Flow YAML omits `transition_actions` entirely — orchestrator treats all transitions as no-op and continues normally.
- Three known flows (team, debug, explore) must all be migrated in lockstep in Conversation 1 to prevent regression when Conversation 2 removes hardcoded logic.
