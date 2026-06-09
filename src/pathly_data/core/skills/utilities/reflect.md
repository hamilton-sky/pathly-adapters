# reflect

Meta-skill: runs a second-pass critique on the most recently completed stage's output.
Implements the Reflection pattern — a second LLM generation conditioned on the first's output —
so any stage can be quality-gated before the FSM advances.

Call standalone (`/pathly reflect`) or composably from within any stage skill as a post-step.

## Workflow Surface

Host-neutral Pathly route names. Adapters render these in their host-native form.

## Skill Contract

**Consumes:** latest AGENT_DONE event for the active feature + corresponding stage artifacts
**Produces:** `pathly/plans/<FEATURE>/feedback/REFLECT_CRITIQUE.md` (issues found) — absent means PASS
**Side effect:** if verdict is PASS and REFLECT_CRITIQUE.md already exists, deletes it (issue resolved)

## Arguments

`$ARGUMENTS` may contain any combination of:
- A feature slug (non-keyword word) — override auto-detect
- A stage keyword (`build`, `review`, `test`, `plan`, `design`, `storm`) — reflect on that stage
- `--clear` — delete REFLECT_CRITIQUE.md and exit without running a critique

Example: `reflect my-feature build`, `reflect`, `reflect --clear`

## Step 1: Resolve feature and target stage

**Feature detection:** parse `$ARGUMENTS` for a non-keyword word, else auto-detect:
1. Read `pathly/plans/*/STATE.json` sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/plans/*/` folder.
3. If no `pathly/plans/` folder exists: stop →
   `reflect: no active feature found. Start with /pathly go first.`

**`--clear` flag:** if present, delete `pathly/plans/<FEATURE>/feedback/REFLECT_CRITIQUE.md`
if it exists, print `reflect: cleared REFLECT_CRITIQUE.md for <FEATURE>.` and stop.

**Stage detection:**
- If a stage keyword is in `$ARGUMENTS`, map it to its agent name:
  `build` → `builder` · `review` → `reviewer` · `test` → `tester` ·
  `plan` → `planner` · `design` → `designer` · `storm` → `architect`
- Otherwise, read the most recent AGENT_DONE event from the central DB to get
  the last agent that ran:

```bash
python3 -c "
from pathly_orchestrator.db import get_db; import json
conn = get_db()
row = conn.execute(
  \"SELECT payload FROM fsm_events WHERE feature=? AND event_type='AGENT_DONE' ORDER BY seq DESC LIMIT 1\",
  ('<FEATURE>',)
).fetchone()
if row:
    print(json.dumps(json.loads(row[0])))
else:
    print('none')
"
```

Use the `agent` field as the target stage agent.
If result is `none`: print `reflect: no completed stage found for <FEATURE>. Run a pipeline stage first.` and stop.

Also read the AGENT_DONE `summary` and `result` fields — these are the agent's own semantic output.

## Step 2: Load stage artifacts

Read the relevant output files for the target agent:

| Agent | Artifacts to read |
|---|---|
| `planner` | `pathly/plans/<FEATURE>/USER_STORIES.md`, `pathly/plans/<FEATURE>/IMPLEMENTATION_PLAN.md` |
| `architect` | `pathly/plans/<FEATURE>/ARCHITECTURE_PROPOSAL.md` |
| `designer` | `pathly/plans/<FEATURE>/DESIGN_SYSTEM.md` (if exists) |
| `builder` | `git diff HEAD~1 HEAD --stat` + diff of up to 3 most-changed files |
| `reviewer` | `pathly/plans/<FEATURE>/feedback/REVIEW_FAILURES.md` (if exists), else empty |
| `tester` | `pathly/plans/<FEATURE>/feedback/TEST_FAILURES.md` (if exists), else empty |

If the primary artifact file does not exist, note "artifact not found" for that slot and continue.

## Step 3: Spawn reviewer in critique mode

Spawn `reviewer` subagent with this prompt:

```
PATHLY REFLECT — second-pass critique
Stage: <agent>
Feature: <FEATURE>
Agent result: <result from AGENT_DONE>
Agent's own summary: <summary from AGENT_DONE, or "not recorded">

## Stage contract
<one sentence: what this stage must produce — see table below>

## Stage artifacts
<contents of the artifacts loaded in Step 2>

## Critique task
You are running a reflection pass on the output above. Do NOT re-run the work.

Answer exactly these three questions. For each, answer PASS or ISSUE: <one sentence>.
Only flag issues you are confident about — when uncertain, pass.

1. Completeness — Did the output fulfill the stage contract? What is missing or clearly underdeveloped?
2. Downstream risk — What specific issues in this output are likely to cause failures in the next stage?
3. Scope — Did the agent do work that belongs to a different stage (over-reach or under-reach)?

Final verdict on the last line:
VERDICT: PASS   (all three are PASS)
VERDICT: CRITIQUE   (at least one is ISSUE)
```

Stage contract sentences:
- `planner` → "Produce USER_STORIES.md with acceptance criteria and IMPLEMENTATION_PLAN.md with scoped conversations."
- `architect` → "Produce ARCHITECTURE_PROPOSAL.md with layer decisions, dependency direction, and technology choices."
- `designer` → "Produce a design system with palette, typography, and component specifications."
- `builder` → "Implement the current conversation's scope with no regressions and all acceptance criteria addressed."
- `reviewer` → "Identify all architectural and implementation violations and write them to REVIEW_FAILURES.md."
- `tester` → "Verify all acceptance criteria and write unmet ones to TEST_FAILURES.md."

## Step 4: Write or clear REFLECT_CRITIQUE.md

Parse the reviewer's output for the `VERDICT:` line.

**On VERDICT: PASS:**
- If `pathly/plans/<FEATURE>/feedback/REFLECT_CRITIQUE.md` exists, delete it.
- Print:
  ```
  reflect: PASS — <agent> output looks good. No issues found.
  ```
- Stop.

**On VERDICT: CRITIQUE:**
Write `pathly/plans/<FEATURE>/feedback/REFLECT_CRITIQUE.md`:

```markdown
# Reflect Critique — <agent>

> Auto-generated by `/pathly reflect`. Fix the issues below before advancing.
> Delete this file (or run `pathly reflect --clear`) once resolved.

## Completeness
<answer from reviewer>

## Downstream Risk
<answer from reviewer>

## Scope
<answer from reviewer>

---
Stage: <agent> | Feature: <FEATURE> | Timestamp: <iso-timestamp>
```

Print:
```
reflect: CRITIQUE — issues found in <agent> output.
Written: pathly/plans/<FEATURE>/feedback/REFLECT_CRITIQUE.md

The FSM feedback guard will route this before the pipeline advances.
Run `pathly reflect --clear` to dismiss once resolved manually.
```
