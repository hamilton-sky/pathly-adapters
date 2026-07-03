# review

This is the canonical, tool-agnostic Pathly behavior for the review workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

> Shared protocols — **Scout choreography**, **Sub-agent spawning rules**, and **Live progress
> logging** — are composed in below from fragments. This body covers only the interactive
> review-workflow specifics (including its own pipeline exit contract).

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

Review code at $ARGUMENTS against this project's architectural standards.

- `staged` or empty → review `git diff --staged`
- `last` → review `git diff HEAD~1 HEAD`
- file path → review that specific file
- `<feature> <N>` (e.g. `pathly-observability 2`) → **pipeline review**: review `git diff HEAD~1 HEAD`, load that feature's `ARCHITECTURE_PROPOSAL.md` for scope context, then run the exit contract on pass/fail

## Pre-review context gathering

**Phase 1 — Analyze:**
log-phase PHASE_START analyze

Spawn `reviewer` with `phase: analyze`. Pass the diff target (`$ARGUMENTS`).
Parse the returned `## NEEDS_CONTEXT` block.

log-phase PHASE_DONE analyze

**Phase 2 — Scout:**
log-phase PHASE_START scout

Run the Scout choreography with `ROLE: reviewer`. Use the returned summary as findings
(`none` if `NEEDS_CONTEXT` was `none`).

log-phase PHASE_DONE scout (include scouts_count = number of entries spawned, or 0 if skipped)

**Phase 3 — Review:**
log-phase PHASE_START review

Spawn `reviewer` with the full review prompt. Inject:
```
## Applicable Rules
[compressed summary from Phase 2, or "none" if skipped]
```
Keep Steps 1–3 and the report format inside the reviewer's spawn prompt.

log-phase PHASE_DONE review

## Step 1 — Get the diff

Run the appropriate git diff command based on `$ARGUMENTS`.

## Step 2 — Load project rules

Read (if present):
1. The `ARCHITECTURE_PROPOSAL.md` in the `pathly/features/*/` folder that most closely matches the changed files — defines the intended architecture for in-progress work
2. Project rule files — project-wide architectural contracts

If neither exists, review against general software engineering good practices and note the absence.

If the task you are reviewing has `context_refs`, for each `{artifact, anchor}` call:
```
GET /comms/artifacts/section?scope=$SCOPE&artifact=<artifact>&anchor=<anchor>
```
and read the returned `text` field (the full section — the advisory spec for that phase,
e.g. edge cases / happy flow). The `summary` is a pointer, not the spec — read `text`.
If `anchor` is absent or null, omit it to retrieve the whole file. These are the same
refs the builder hydrated — review against the same advisory spec the builder used.

## Step 3 — Check for violations

For each changed file, check:

### Dependency direction
- Does the file import from a layer it should not depend on?
- Does the dependency direction match what `ARCHITECTURE_PROPOSAL.md` specifies?

### Layer responsibility
- Does the file contain logic that belongs in a different layer?
- Are concerns properly separated (e.g., data access vs. business logic vs. presentation)?

### Conventions
- Does the file follow naming and structural conventions shown in project rules?
- Are interfaces and contracts implemented correctly per the rules files?

### Scope
- Does the change touch files outside the scope described in the active conversation plan?
- Are there unexpected side effects on other modules?

## Report format

List each check as PASS / FAIL / N/A.

For failures use these prefixes:
```
[ARCH] <file>:<line> — <what the violation is> — <what it should be instead>
[IMPL] <file>:<line> — <what the violation is> — <fix required>
```

If all checks pass: `PASS — no violations found.`

If violations found: list each one. Do NOT auto-fix. Report only.

## Exit contract (pipeline review only — when called as `<feature> <N>`)

**On PASS:**

1. Update `pathly/features/<feature>/PROGRESS.md` — in the Conversation Breakdown table, find the row for conversation `<N>` and change its Status cell from `TODO` to `DONE`.
2. Check PROGRESS.md: if all conversation rows are now `DONE`, next state = `"TESTING"`; otherwise next state = `"BUILDING"`.
3. Report completion to the FSM:
   ```bash
   pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>
   ```
   (The FSM computes the next state from transition_rules: if all conversation rows in PROGRESS.md are DONE, next = TESTING; otherwise next = BUILDING. The FSM writes STATE.json as the authoritative mirror.)
4. Invoke the `log-agent-done` skill with:
   ```json
   {"agent":"reviewer","feature":"<feature>","conversation":<N>,"result":"PASS"}
   ```

**On FAIL:**

1. Write violations to `pathly/features/<feature>/feedback/REVIEW_FAILURES.md`.
2. Report completion to the FSM:
   ```bash
   pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>
   ```
   (The FSM reads REVIEW_FAILURES.md and routes via transition_rules to REVIEW_FAILED. The FSM writes STATE.json as the authoritative mirror.)
3. Do NOT update PROGRESS.md — the conversation is not DONE until violations are resolved.
