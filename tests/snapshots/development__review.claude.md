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
1. The `ARCHITECTURE_PROPOSAL.md` in the `pathly/plans/*/` folder that most closely matches the changed files — defines the intended architecture for in-progress work
2. Project rule files — project-wide architectural contracts

If neither exists, review against general software engineering good practices and note the absence.

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

1. Update `pathly/plans/<feature>/PROGRESS.md` — in the Conversation Breakdown table, find the row for conversation `<N>` and change its Status cell from `TODO` to `DONE`.
2. Check PROGRESS.md: if all conversation rows are now `DONE`, next state = `"TESTING"`; otherwise next state = `"BUILDING"`.
3. Write `pathly/plans/<feature>/STATE.json`:
   ```json
   {"current": "<next_state>", "feature": "<feature>", "rigor": "<rigor>", "updated_at": "<iso-timestamp>"}
   ```
4. Append to `pathly/plans/<feature>/EVENTS.jsonl`:
   ```
   {"type":"STATE_TRANSITION","to":"<next_state>","ts":"<iso-timestamp>"}
   ```
5. Invoke the `log-agent-done` skill with:
   ```json
   {"agent":"reviewer","feature":"<feature>","conversation":<N>,"result":"PASS"}
   ```

**On FAIL:**

1. Write violations to `pathly/plans/<feature>/feedback/REVIEW_FAILURES.md`.
2. Write `pathly/plans/<feature>/STATE.json` with `"current": "REVIEW_FAILED"`.
3. Append `{"type":"STATE_TRANSITION","to":"REVIEW_FAILED","ts":"<iso-timestamp>"}` to EVENTS.jsonl.
4. Do NOT update PROGRESS.md — the conversation is not DONE until violations are resolved.

## Live progress logging

Each `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>` marker is a mandatory
pipeline event. When you encounter one (or an inline `Run:` bash block replacing it), execute it immediately:

Run:
```bash
# On PHASE_START:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_START \
  --project-root "<project_root>"

# On PHASE_DONE:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_DONE \
  --project-root "<project_root>"
```

- `<feature>` — the feature slug (folder name under `pathly/plans/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

**Server availability — start-if-needed (same contract as log-agent-done):**

If `pathly-fsm-call` fails or the server is not reachable:
1. Start the server in the background: `pathly-fsm-http`
2. Wait 2 seconds, then retry the `record-phase` call once.
3. If the retry also fails: skip silently and continue — phase logging must never block execution.

This makes phase logging reliable on any adapter (Codex, Copilot, CLI) where the
FSM server is not automatically managed by the host environment.

## Scout choreography (analyze → scout → compress)

The stage agent (builder / reviewer / tester) declares what context it needs *before* doing the
work, scouts gather that context in parallel, and the findings are compressed into the work prompt.

### Phase 1 — Analyze

Spawn the stage agent with `phase: analyze`. It outputs a `## NEEDS_CONTEXT` block **only** —
the list of things it must know before implementing / reviewing / testing.

NEEDS_CONTEXT format (one entry per line):
```
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
```

Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2 (or use only the stage's
default scout entry, where one is defined).

### Phase 2 — Scout (parallel, max 4)

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: <stage agent>` + the question
- `type: scout` → spawn `scout` with `ROLE: <stage agent>` + scope + question

Compress all returned findings into a short summary and inject it into the Phase 3 work prompt
as the stage's findings section.

## Sub-agent spawning rules

This stage runs on a host that can spawn sub-agents (Task / subagent capability).

- **Never execute work yourself** — spawn the right subagent for each step.
- Treat the FSM as a deterministic filesystem machine: read disk, process one event, emit one action.
- After every agent completes, check for feedback files before advancing.
- Spawn scouts and parallel workers up to a maximum of 4 at once.

Map each action to its subagent (the stage skill lists the exact roles for that stage):

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Review changes | `reviewer` |
| Verify acceptance criteria | `tester` |
| Clarify requirement | `planner` |
| Clarify / redesign architecture | `architect` |
| Scout context | `scout` or `quick` (with `ROLE:` set to the stage agent) |
