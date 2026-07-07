# goalize

Turn an idea into a board-ready **goal + its task DAG — interactively**. You talk the idea through
with the human, propose a goal and a small task DAG, get their sign-off, then post BOTH to the board
in one shot: a `type=goal` message (the goal) and its `type=task` children (the DAG).

This is the human-in-the-loop front door to the Board → Goals → Tasks model. The headless
decomposers (`planning/plan`, `dag-sketch`, `feature-decompose`) assume the goal already exists;
goalize is the path that CREATES the goal and seeds its DAG together, only after you approve it.

## Step 1 — Understand the idea

Read the user's idea from your prompt / the conversation. If something essential is unclear — the
outcome, the scope boundary, or which board it belongs on — ask **1–3 short clarifying questions and
wait** for the answer. One good round is usually enough; don't over-interrogate.

Settle the **target scope** `$FEATURE` — the feature board this goal belongs on. Use the active
board if there is one; otherwise ask. (For a project-level goal, the scope is the normalized project
root path and `board` is `project`.)

## Step 2 — Draft the goal + task DAG

Propose exactly **one goal**:
- **title** — one sentence describing what "done" looks like.
- **scope** — one short paragraph: what is in scope, what is explicitly out.
- **executor** — recommend one, with a reason:
  - `single` — one agent drains the whole DAG (small, tightly-coupled work);
  - `loop` — the supervisor runs the ready-frontier task-by-task (independent tasks);
  - `team` — full plan→build→review→test per task (high-rigor work).

Then propose a **3–7 task DAG**. Each task:
- Actionable and specific, sized to ~one agent session ("Add the `/comms/goals` route", not "Backend").
- Self-contained — runnable without context from sibling tasks.
- `depends_on` wired **only** where a task genuinely cannot start without another's output.

## Step 3 — Show it and get sign-off (this is the gate)

Present the draft as a compact plan and ask the human to **confirm, edit, or cancel**:

```
GOAL: <title>   [executor: <single|loop|team>]
Scope: <one-line scope>
Tasks:
  T1  <title>
  T2  <title>   (depends: T1)
  …
```

**Post nothing until they approve.** If they want changes, revise and re-show. This confirmation IS
the gate — goalize never writes to the board on its own initiative.

## Step 4 — Create the goal

On approval, create the goal **first** so `$GOAL_ID` exists for the tasks. Post a `type=goal` message
(`board` is `project` for a project-level goal, else `feature`):

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "goal",
    "board": "feature",
    "scope": "$FEATURE",
    "slug": "<short-kebab-slug>",
    "executor": "<single|loop|team>",
    "text": "<title>\n\nScope: <scope paragraph>"
  }'
```

Record the returned `"message_id"` as `$GOAL_ID`.

**Idempotency:** first list existing goals
(`curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE&type=goal"`); if one with the
same slug already exists, reuse its id as `$GOAL_ID` instead of posting a duplicate.

**Fallback when the server is unreachable:** write the approved plan to
`pathly/features/$FEATURE/GOAL_PLAN.md`, tell the human it was saved locally (not posted), and stop.

## Step 5 — Post the task DAG

With `$GOAL_ID` set, post the task children using the board-posting mechanics in the fragment below.
Post in dependency order and wire each task's `depends_on` to the `message_id`s of its upstream tasks.

## Step 6 — Confirm to the human

Report back: the goal slug + `$GOAL_ID`, the number of tasks posted, and that it is live on the
board — plus a nudge that they can run it now (dispatch the goal to its executor) or refine the tasks
from the Goals & Tasks view. Then read it back with `GET /comms/goals?feature=$FEATURE` and show the
`{total, ready, …}` rollup so they can see the DAG landed.
