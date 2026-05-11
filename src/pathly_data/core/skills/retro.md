# retro

This is the canonical, tool-agnostic Pathly behavior for the retro workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Skill Contract

**Consumes:** `plans/$ARGUMENTS/PROGRESS.md` + `plans/$ARGUMENTS/CONVERSATION_PROMPTS.md`
**Produces:** `plans/$ARGUMENTS/RETRO.md`
**Consumed by:** `storm` skill (user pastes RETRO.md as context for next storm session)

Run a retrospective on the **$ARGUMENTS** feature plan.

## Step 1: Read the plan

Read both files:
1. `plans/$ARGUMENTS/PROGRESS.md` — overall status, what was completed
2. `plans/$ARGUMENTS/CONVERSATION_PROMPTS.md` — the prompts that were used

If the plan folder doesn't exist, list all `plans/*/` folders and ask which one the user meant.
If PROGRESS.md status is not COMPLETE, warn: "This plan is not marked COMPLETE — retro may be incomplete."

## Step 2: Ask 3 questions

Ask these three questions, one at a time. Wait for an answer before asking the next:

**Q1:** "Looking at the conversation prompts — were any conversations too big (needed mid-conversation scope cuts) or too small (finished too fast with leftover context)?"

**Q2:** "Did anything break unexpectedly during implementation that the plan didn't anticipate? Any unexpected architectural violations, integration failures, or test failures that surprised you?"

**Q3:** "What would you tell yourself before starting this feature — the one thing the plan should have said but didn't?"

## Step 3: Write RETRO.md

**Before writing — compute cost summary (if EVENTS.jsonl exists):**

Read `plans/$ARGUMENTS/EVENTS.jsonl`. For every line where `type == "AGENT_DONE"`,
collect `agent`, `model`, `tokens_in`, `tokens_out`, `cost_usd`.

Aggregate per agent:
- Total `cost_usd` across all events (skip events where `cost_usd == 0.0`)
- Total `tokens_in + tokens_out` per agent

If any events have `cost_usd > 0`, build a cost table. Otherwise omit the Cost section.

Write `plans/$ARGUMENTS/RETRO.md`:

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

If `EVENTS.jsonl` doesn't exist or has no `cost_usd` data, omit the Cost Summary section entirely — do not show a table of zeros.

## Step 4: Extract lessons

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

## Step 5: Report

```
Retro written: plans/$ARGUMENTS/RETRO.md
Lessons appended: LESSONS_CANDIDATE.md

To use in your next storm session:
1. Run route `storm`
2. Paste the "Seed for Next Storm" block from RETRO.md as opening context

To promote lessons to active memory:
  lessons
```
