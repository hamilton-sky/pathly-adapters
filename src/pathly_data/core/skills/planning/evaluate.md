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

## Step 3 — Write and post the analysis artifact

Write the analysis to `pathly/plans/<feature>/artifacts/BOARD_EVAL.md`:

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

## Step 4 — Post concrete task proposals

Post one or more `type=task` messages to the board. Tasks must be actionable and specific.
The user runs them with the standard board controls — no intermediate "options" layer.

**`CODE`:** One task per logical implementation unit.
**`RESEARCH`:** One exploration task naming the open question.
**`BOTH`:** Research task first (no dependency), then implementation task(s) depending on it.

Post at least one task. If the board content is too vague, post a `type=question` instead,
state your fallback assumption in `text`, and include 2–4 options.

If the FSM server is unreachable for any post, skip it silently and list the proposed tasks
in your text output so the user can post them manually.

---

## Step 5 — Report

After all posts succeed (or are skipped), output:

```
## Evaluation complete

Classification: <CODE | RESEARCH | BOTH>
Analysis artifact: pathly/plans/<feature>/artifacts/BOARD_EVAL.md
Tasks posted: <N>

- <task 1 text>
- <task 2 text> (if any)
```

---

## Constraints

- Never execute the proposed tasks yourself. Propose only.
- Write only to `pathly/plans/<feature>/artifacts/`. Do not touch plan files or state files.
- One analysis artifact per run — overwrite BOARD_EVAL.md, never append.
- One post per finding. Do not batch multiple findings into a single board message.
