---

---
# evaluate

This is the canonical, tool-agnostic Pathly behavior for the evaluate workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## When to use

The evaluator skill is triggered automatically when a board run is started with no active
task and no flow selected. It can also be invoked directly:

```
/pathly evaluate <feature>
```

Use it when you have information on the board but are not yet sure whether it calls for a
code implementation, a research exploration, or both.

---

## Step 1 — Read board context

The board context is injected into your prompt. It contains all messages currently on the
feature board: discoveries, decisions, constraints, warnings, artifacts, and free-form text.

If no context is injected, post a `warning` noting the board appears empty and ask the user
to add content before re-running.

---

## Step 2 — Classify

Classify the board content as one of:

| Class | When to use |
|---|---|
| `CODE` | Content describes a software change, bug, implementation task, or codebase question |
| `RESEARCH` | Content describes an open question, exploration topic, or a decision without clear implementation scope |
| `BOTH` | Content has both a concrete engineering component and an open research question that must be answered first |

When in doubt between `RESEARCH` and `BOTH`, choose `BOTH`.

---

## Step 3 — Write and post the analysis artifact (MANDATORY — your primary deliverable)

**Every evaluate run MUST post this artifact — it is the ONE output that always has to exist.**
NEVER skip it, and do it BEFORE any other posting. It is required even when the board already has a
goal/task DAG (that only lets you skip Step 4 below — never this step). Do NOT substitute a
free-form `discovery`/`question` post or a text-only reply for it: if the board raises a question,
your classification + recommendation goes INSIDE `BOARD_EVAL.md` and is posted as an `artifact`.

Write the analysis to `pathly/features/<feature>/artifacts/BOARD_EVAL.md`:

```markdown
# Board Evaluation

## Classification
<CODE | RESEARCH | BOTH>

## Summary
<3–5 sentences: what the board says, why this classification applies, what the key unknown is>

## Key unknown / risk
<one sentence, or "none">

## Recommended next steps
<bulleted list of the tasks you will post in Step 4>
```

Create the `artifacts/` directory if it does not exist.

Then post an `artifact` message to the board using the comms-post recipe below. Keep `text`
self-contained — other agents read it without opening the file.

---

## Step 4 — Post goal + concrete task proposals

Post a `type=goal` message first, then one or more `type=task` messages stamped with its
`goal_id`. Tasks must be actionable and specific. The user runs them with the standard board
controls — no intermediate "options" layer.

> These posts target the board this run is evaluating: the runner fills in the board tier
> (feature, project, or global) and its scope for you. Do not force a feature-tier post — on a
> project or global board that spawns a stray feature board named after the scope instead of
> posting to the board you opened.

**Idempotency guard — skip THIS STEP ONLY (never Step 3) if a DAG already exists for this scope.** Before posting, check:

```bash
curl -s "http://127.0.0.1:8765/comms?feature=<feature>&board=<board>&scope=<feature>&type=goal"
curl -s "http://127.0.0.1:8765/comms/tasks?feature=<feature>"
```

If either response contains any messages, skip this entire step — the board has already been
seeded. Do not double-post.

**Post the goal first.** Compose a one-line synthesis of what the board calls for and POST:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "evaluator",
    "type": "goal",
    "text": "Goal: <one-line synthesis of what the board calls for>",
    "board": "<board>",
    "scope": "<feature>",
    "executor": "single"
  }'
```

Record the response `"message_id"` as `$GOAL_ID`.

**Post tasks stamped with `$GOAL_ID`:**

**`CODE`:** One task per logical implementation unit.
**`RESEARCH`:** One exploration task naming the open question.
**`BOTH`:** Research task first (no `depends_on`), then implementation task(s) with
`depends_on` set to the research task's returned `message_id`.

Each task must include `"goal_id": "$GOAL_ID"`. Example shape:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "evaluator",
    "type": "task",
    "text": "<actionable task description>",
    "board": "<board>",
    "scope": "<feature>",
    "stage": "BUILDING",
    "goal_id": "$GOAL_ID",
    "depends_on": []
  }'
```

Post at least one task. If the board content is too vague, post a `type=question` instead,
state your fallback assumption in `text`, and include 2–4 options (omit the goal in that case).

If the FSM server is unreachable for any post, skip it silently and list the proposed goal
and tasks in your text output so the user can post them manually.

---

## Step 5 — Report

After all posts succeed (or are skipped), output:

```
## Evaluation complete

Classification: <CODE | RESEARCH | BOTH>
Analysis artifact: pathly/features/<feature>/artifacts/BOARD_EVAL.md
Goal posted: <goal text> (id: <$GOAL_ID>)
Tasks posted: <N>

- <task 1 text>
- <task 2 text> (if any)
```

---

## Constraints

- Never execute the proposed tasks yourself. Propose only.
- Write only to `pathly/features/<feature>/artifacts/`. Do not touch plan files or state files.
- One analysis artifact per run — overwrite BOARD_EVAL.md, never append.
- One post per finding. Do not batch multiple findings into a single board message.
