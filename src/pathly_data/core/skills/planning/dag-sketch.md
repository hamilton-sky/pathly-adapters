---

---

Decompose the goal in your prompt into 3–7 concrete, independently-runnable tasks.

Each task title must be:
- Actionable and specific (e.g. "Set up DB schema" not "Database work")
- A self-contained unit of work that one agent can complete without context from sibling tasks
- Sized to take roughly one agent session (not too broad, not trivially small)

Write a one-page `DAG_PLAN.md` in the feature working directory with:

## Tasks

| id | title | depends_on |
|----|-------|-----------|
| T1 | <title> | — |
| T2 | <title> | T1 |
...

Include a one-line `Purpose:` description for each task below the table.

Each task needs something to prove it done: end its `text` with a ```check block of read-only
commands that pass once the task is built, or, when no command can prove it, a line
`Check: none - <why>` with the reason. The board refuses a task with neither (HTTP 422, nothing
stored): post it again with its block or its `Check: none - <why>` line.

Then post each task to the board using the board-posting mechanics in the fragment below.
The goal already exists — post task children only, do NOT post a new goal.
