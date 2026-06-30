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

Then post each task to the board using the board-posting mechanics in the fragment below.
The goal already exists — post task children only, do NOT post a new goal.
