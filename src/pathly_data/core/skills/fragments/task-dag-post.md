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
    "context_refs": [...]
  }'
```

Note: `executor` is NOT on the task — it lives on the goal message only.
Record the `"message_id"` from each response to use in later tasks' `depends_on` array.

**Skip-if-down (advisory):** If the comms server is unreachable, record in your completion
report that DAG seeding did not complete. Do NOT retry in a loop or fail the run.
