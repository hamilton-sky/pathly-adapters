# REVIEW_FAILURES — fsm-transition-actions (Conv 1 + Conv 2 post-fix)

Reviewed files:
- `src/pathly_data/core/flows/team.flow.yaml`
- `src/pathly_data/core/flows/debug.flow.yaml`
- `src/pathly_data/core/flows/explore.flow.yaml`
- `src/pathly_data/core/agents/orchestrator.md`

---

## Violation 1 — Unknown action type not handled (blocking)

**File:** `src/pathly_data/core/agents/orchestrator.md` — `### Execute transition_actions` section (step 4 / lines 96-108)

**Rule violated:** "halt and report on unknown action type or action failure" (Applicable Rules, executor contract item e)

**Description:** The executor block lists the three known action types (`git_commit`, `update_progress`, `archive_artifacts`) but contains no instruction to halt and surface an error when an action entry has an unrecognized `type` value. An unknown type would be silently ignored rather than triggering halt-and-report.

**Required fix:** After the three `type` branches in step 4, add an explicit clause: if the action's `type` is not one of `git_commit`, `update_progress`, `archive_artifacts`, halt and report the unknown action type (same halt-and-report behavior as action failure).

---

## Violation 2 — Duplicate step number 6 in executor section (blocking)

**File:** `src/pathly_data/core/agents/orchestrator.md:109,113` — `### Execute transition_actions` section

**Rule violated:** Structural correctness / unambiguous executor contract

**Description:** Two consecutive items in the `### Execute transition_actions` numbered list are both labeled `6.`:
- Line 109: `6. On action failure: halt and surface the error ...`
- Line 113: `6. Continue FSM loop with next_state.`

The second item is step 7 and must be renumbered. As written, an agent reading the orchestrator contract could misread the flow-control order.

**Required fix:** Renumber "Continue FSM loop with `next_state`" to step 7.

---

## No violations in Conv 1 (flow YAMLs)

- `team.flow.yaml`: both transition_actions keys (`"BUILDING->REVIEWING"`, `"RETRO->DONE"`) reference valid transitions; shape matches the plan.
- `debug.flow.yaml` and `explore.flow.yaml`: `transition_actions` key present, intentionally empty per MVP scope.
