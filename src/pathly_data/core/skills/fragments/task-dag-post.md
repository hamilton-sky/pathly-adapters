## Posting the task DAG to the Comms Board

This is the single canonical mechanism for posting task children to an existing goal.
`$GOAL_ID` must be set before you invoke this step.

**Idempotency guard — skip if this goal already has tasks:**

```bash
curl -s "http://127.0.0.1:8765/comms/tasks?goal_id=$GOAL_ID"
```

If the response has a non-empty `tasks` array, skip all task POSTs below.

For each task, POST this exact shape:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "task",
    "text": "<self-contained task description>",
    "board": "feature",
    "scope": "$FEATURE",
    "stage": "BUILDING",
    "conv": <int — omit if not known>,
    "depends_on": ["<message_id_of_dependency>"],
    "goal_id": "$GOAL_ID",
    "context_refs": [...],
    "lane": "<lane name>",
    "files": ["<path/this/task/writes.py>", "<another/path.py>"]
  }'
```

### `lane` and `files` — what the scheduler may run at once

These two fields are what let a build run tasks in parallel safely. Get them wrong and two
agents edit the same file at the same time, so declare them honestly:

- **`files`** — every path this task will CREATE or MODIFY. A directory (`src/api`) covers
  everything beneath it, which is the right choice when you cannot name exact files yet.
  Declare what you will WRITE, not what you will merely read.
- **`lane`** — the group this task serialises within. **At most one task per lane runs at a
  time**, so two tasks touching ANY of the same files MUST share a lane. Tasks whose file
  sets are completely disjoint should get DIFFERENT lanes — that is what lets them run
  concurrently. Name a lane after the area it owns (`backend`, `frontend`, `db-schema`,
  `docs`); the name is just an identity, but a meaningful one makes the plan readable.

The rule in one line: **same files ⇒ same lane; disjoint files ⇒ different lanes.**

Omitting both is allowed and safe — a task with no declared footprint is treated as
touching everything, so the drain falls back to one task at a time. That costs wall-clock,
never correctness. What IS unsafe is declaring a footprint you then write outside of, or
splitting file-overlapping tasks across different lanes.

Note: `executor` is NOT on the task — it lives on the goal message only.
Record the `"message_id"` from each response to use in later tasks' `depends_on` array.

**Skip-if-down (advisory):** If the comms server is unreachable, record in your completion
report that DAG seeding did not complete. Do NOT retry in a loop or fail the run.
