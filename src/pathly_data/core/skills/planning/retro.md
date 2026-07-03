# retro

This is the canonical, tool-agnostic Pathly behavior for the retro workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Skill Contract

**Consumes:** `pathly/features/<FEATURE>/PROGRESS.md` + `pathly/features/<FEATURE>/CONVERSATION_PROMPTS.md`
**Produces:** `pathly/features/<FEATURE>/RETRO.md`
**Consumed by:** `storm` skill (user pastes RETRO.md as context for next storm session)

## Feature detection

If `$ARGUMENTS` contains a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `pathly/features/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/features/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/features/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

Run a retrospective on the **FEATURE** plan.

## Step 1: Read the plan

Read both files:
1. `pathly/features/$ARGUMENTS/PROGRESS.md` — overall status, what was completed
2. `pathly/features/$ARGUMENTS/CONVERSATION_PROMPTS.md` — the prompts that were used

If the plan folder doesn't exist, list all `pathly/features/*/` folders and ask which one the user meant.
If PROGRESS.md status is not COMPLETE, warn: "This plan is not marked COMPLETE — retro may be incomplete."

## Step 2: Ask 3 questions

Ask these three questions, one at a time. Wait for an answer before asking the next:

**Q1:** "Looking at the conversation prompts — were any conversations too big (needed mid-conversation scope cuts) or too small (finished too fast with leftover context)?"

**Q2:** "Did anything break unexpectedly during implementation that the plan didn't anticipate? Any unexpected architectural violations, integration failures, or test failures that surprised you?"

**Q3:** "What would you tell yourself before starting this feature — the one thing the plan should have said but didn't?"

## Step 3: Write RETRO.md

**Before writing — compute cost summary from central DB:**

```bash
python3 -c "
from pathly_orchestrator.db import get_db; import json
conn = get_db()
rows = conn.execute(\"SELECT payload FROM fsm_events WHERE feature=? AND event_type='AGENT_DONE' ORDER BY seq\", ('$ARGUMENTS',)).fetchall()
for (p,) in rows:
    print(json.dumps(json.loads(p or '{}')))
"
```
For every AGENT_DONE event, collect `agent`, `model`, `tokens_in`, `tokens_out`, `cost_usd`.

Aggregate per agent:
- Total `cost_usd` across all events (skip events where `cost_usd == 0.0`)
- Total `tokens_in + tokens_out` per agent

If any events have `cost_usd > 0`, build a cost table. Otherwise omit the Cost section.

Write `pathly/features/$ARGUMENTS/RETRO.md`:

```markdown
# [Feature Name] — Retrospective

## Cost Summary
Total: $X.XX

| Agent     | Model          | Tokens in | Tokens out | Cost     | % of total |
|-----------|----------------|-----------|------------|----------|------------|
| architect | advanced | 12,400   | 2,100      | $2.50    | 60%        |
| builder   | normal   | 8,200    | 4,300      | $1.10    | 26%        |
| reviewer  | normal   | 5,100    | 1,200      | $0.40    | 10%        |
| tester    | normal   | 3,000    | 900        | $0.20    | 5%         |

> Use this to decide: was standard rigor worth the cost? Would lite have been enough?

## Plan Quality
**Conversation sizing:** [too big / too small / good — from Q1]
**Surprises:** [from Q2]
**Missing from plan:** [from Q3]

## What Worked
- [extract from user answers]

## What to Improve Next Time
- [extract from user answers — actionable, specific]

## Seed for Next Storm
> Paste this block as context when starting the next related storm session:
[2-3 sentence summary of the key learning from this retro]
```

If the DB has no AGENT_DONE events for this feature or all `cost_usd == 0.0`, omit the Cost Summary section entirely — do not show a table of zeros.

## Step 4: Generate pipeline-walkthrough files

Using the DB event data already read in Step 3, fill and write the three pipeline-walkthrough
documents to `pathly/pipeline-walkthrough/$ARGUMENTS/`. Create the directory if it does not exist.

**Read context:**
- Run `git branch --show-current` for `{{BRANCH}}`.
- Use today's date for `{{DATE}}`.
- From central DB: first `HUMAN_RESPONSE` event `value` field → `{{USER_INTENT}}` (or "not recorded").
- STATE_TRANSITION events from DB → `{{FSM_STATES}}` (ordered `to` values, one per line).
- AGENT_DONE events from DB → per-agent token/cost rows. If all `cost_usd == 0.0`, replace cost
  columns with "not captured".
- Files in `pathly/pipeline-walkthrough/$ARGUMENTS/artifacts/` → `{{FEEDBACK_FILE_ROWS}}`.
- Run `git diff --name-only` against the main branch → `{{SOURCE_FILE_ROWS}}`.

**Write `pathly/pipeline-walkthrough/$ARGUMENTS/01-PIPELINE-FLOW.md`:**
Fill from the template at `{{TEMPLATES_DIR}}/pipeline-walkthrough/01-PIPELINE-FLOW.md`.
- `{{DISCOVERY_TRACE}}` — STATE_TRANSITION events for IDLE/EXPLORING/STORMING states, formatted as
  `│  Orchestrator → [STATE] (auto-advance)` per line.
- `{{ARCHITECT_CONSULT_TRACE}}` — AGENT_DONE events where agent is architect/scout, or empty line.
- `{{CONVERSATION_TRACES}}` — AGENT_DONE events for builder/reviewer grouped by conversation number.
- `{{TEST_TRACES}}` — AGENT_DONE events where agent is tester.
- `{{FEEDBACK_LOOP_TABLE}}` — RETRY events as `| [stage] | [N] | [cause] | [resolution] |` rows,
  or `| — | 0 | — | — |` if none.
- `{{FSM_STATES}}` — all STATE_TRANSITION `to` values, one per line with `→` prefix.

**Write `pathly/pipeline-walkthrough/$ARGUMENTS/02-TOKEN-USAGE.md`:**
Fill from `{{TEMPLATES_DIR}}/pipeline-walkthrough/02-TOKEN-USAGE.md`.
- `{{AGENT_TOKEN_ROWS}}` — one row per AGENT_DONE event: `| N | agent | role | in | out | total | tools | wall | cost |`.
  If `cost_usd == 0.0` for all events, write "not captured" in cost/token columns.
- `{{TOTAL_SPAWNS}}` — count of AGENT_DONE events.
- `{{TOTAL_TOKENS}}` / `{{TOTAL_COST_USD}}` — sum across events, or "not captured".
- `{{TOTAL_TOOL_USES}}` / `{{TOTAL_WALL_TIME}}` — sum, or "not captured".
- Stage breakdown — group AGENT_DONE by FSM state at time of event; or "not captured".
- `{{COST_ANALYSIS}}` / `{{RIGOR_VERDICT}}` — write "Cost data was not captured at spawn time."
  if all zeros; otherwise summarise which agent drove the most cost.

**Write `pathly/pipeline-walkthrough/$ARGUMENTS/03-ARTIFACT-MAP.md`:**
Fill from `{{TEMPLATES_DIR}}/pipeline-walkthrough/03-ARTIFACT-MAP.md`.
- `{{FEEDBACK_FILE_ROWS}}` — one row per file in `pathly/pipeline-walkthrough/$ARGUMENTS/artifacts/`,
  with written-by and resolved-by inferred from filename. If folder is empty: `| — | — | — | — |`.
- `{{SOURCE_FILE_ROWS}}` — one row per changed file from git diff: `| path | [story ref] | [what changed] |`.
  Story ref: match file path against USER_STORIES.md content; if no match write "—".

If no DB events exist for this feature, write all three files with every placeholder replaced by "not recorded".

## Step 5: Extract lessons

From the user's answers and RETRO.md, extract 1–3 lessons — patterns that a planner should know before starting a similar feature. Only write a lesson if something concrete went wrong or was missing. If nothing stands out, skip this step.

For each lesson, append to `LESSONS_CANDIDATE.md` in the project root (create if it doesn't exist):

```markdown
## [$ARGUMENTS] <brief pattern title>

### Pattern
<what repeatedly went wrong or was missing — one sentence>

### Rule
<what must be true in the plan to prevent this — one sentence, starts with MUST or NEVER>

### Injection
- <specific line or section to add to a plan file>
- <add more only if needed>

### Source
Feature: $ARGUMENTS | Stage: <planning/implementation/review/test> | Date: <today>
```

Do NOT invent lessons. Only extract from what the user actually said.

## Step 5b: Trajectory analysis — GEPA instruction patches

Using the full event log already fetched in Step 3, read all event types for this feature:

```bash
python3 -c "
from pathly_orchestrator.db import get_db; import json
conn = get_db()
rows = conn.execute(
  \"SELECT event_type, payload FROM fsm_events WHERE feature=? ORDER BY seq\",
  ('<FEATURE>',)
).fetchall()
for (t, p) in rows:
    d = json.loads(p or '{}')
    d['type'] = t
    print(json.dumps(d))
"
```

**Build a stage performance table** — group by agent (from AGENT_DONE events):

For each agent that appeared, compute:
- `results`: list of `result` field values across all its AGENT_DONE events (e.g. `["PASS"]` or `["FAIL", "FAIL", "PASS"]`)
- `retry_count`: number of RETRY events whose `retry_key` contains that agent's conversation prefix
- `agent_done_count`: total AGENT_DONE events for that agent (> 1 means re-runs)
- `summaries`: list of non-empty `summary` strings from its AGENT_DONE events
- `cost_usd`: sum of `cost_usd` across its AGENT_DONE events

**Identify underperforming stages** — any stage where at least one is true:
- `results` contains `"FAIL"` or `"BLOCKED"`
- `retry_count` > 0
- `agent_done_count` > 1

**For each underperforming stage**, synthesize a diagnosis:

Read its `summaries` carefully. Ask: what does the agent's own description of its work reveal about *why* it needed retries or produced failures? Be specific — cite vocabulary from the summaries. Then formulate a one-sentence instruction patch: a concrete addition to that agent's prompt that would prevent the diagnosed failure. The patch must:
- Name a specific file, directory, check, or artifact
- Start with an action word: Before / After / Always / Never / Check / Verify
- Stay scoped to that stage only

**Write `pathly/features/$ARGUMENTS/INSTRUCTION_PATCHES.md`:**

```markdown
# Instruction Patches — $ARGUMENTS
> Auto-generated by RETRO trajectory analysis (GEPA pattern).
> These are proposed additions to agent_hint.instructions based on this feature's execution history.
> Apply promising patches by editing core/agents/<category>/<agent>.md and running pathly-setup claude --apply.

## Stage: <agent> (conversation <N>)
**Performance:** results=<list>, retries=<N>, reruns=<agent_done_count>
**Summaries digest:**
> "<key phrases from summaries that reveal the failure mode>"

**Diagnosis:** <one sentence — what the agent failed to do or produce correctly>
**Patch:** `<exact sentence to prepend or append to this agent's stage instructions>`

---

## Stage: <agent2> — nominal (no patch)
**Performance:** results=[PASS], retries=0, reruns=1, cost=$<N>
```

If no stages underperformed: write one line — `All stages performed nominally. No patches proposed.`

**Append to `pathly/INSTRUCTION_EVOLUTION.md`** (create if absent):

```markdown
## $ARGUMENTS — <today's date>

| Stage | Retries | Results | Patch |
|---|---|---|---|
| <agent> | <N> | <list> | <one-line patch, or —> |
```

This file accumulates patches across all features. It is the longitudinal signal for a future cross-feature instruction optimizer.

## Step 6: Report

```
Retro written: pathly/features/$ARGUMENTS/RETRO.md
Pipeline walkthrough written:
  pathly/pipeline-walkthrough/$ARGUMENTS/01-PIPELINE-FLOW.md
  pathly/pipeline-walkthrough/$ARGUMENTS/02-TOKEN-USAGE.md
  pathly/pipeline-walkthrough/$ARGUMENTS/03-ARTIFACT-MAP.md
Lessons appended: LESSONS_CANDIDATE.md
Instruction patches written: pathly/features/$ARGUMENTS/INSTRUCTION_PATCHES.md
Evolution log updated: pathly/INSTRUCTION_EVOLUTION.md

To use in your next storm session:
1. Run route `storm`
2. Paste the "Seed for Next Storm" block from RETRO.md as opening context

To apply a patch to the pipeline:
  Edit core/agents/<category>/<agent>.md then run: pathly-setup claude --apply

To promote lessons to active memory:
  lessons
```
