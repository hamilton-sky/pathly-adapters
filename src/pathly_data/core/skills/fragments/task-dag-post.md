## Posting the task DAG to the Comms Board

This is the single canonical mechanism for posting task children to an existing goal.
`$GOAL_ID` must be set before you invoke this step.

**Idempotency guard — skip if this goal already has tasks:**

```bash
curl -s -H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN" "http://127.0.0.1:8765/comms/tasks?goal_id=$GOAL_ID"
```

If the response has a non-empty `tasks` array, skip all task POSTs below.

For each task, POST this exact shape:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN" \
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

### `text` carries the phase's check block

Put the phase's ```check block (its `Check:` field in `IMPLEMENTATION_PLAN.md`) at the end of
the task `text`, verbatim. After the task reports success the supervisor runs the block and
fails the task if a command does not give the result the block asks for. It runs the block
from the `text` as it was when the task was claimed, so an edit made after the claim does not
count: the block must be right before you post. A phase marked `Check: none` posts no block.

The block is one `$ <command>` line per command, each with optional `exit <N>` (or
`exit nonzero`) and `prints <text>` lines. Commands are read-only, run from the repo root and
use no shell features (no `&&` or pipes):

```check
$ python -m pytest tests/test_widget.py -q
exit 0
prints passed
```

The curl body holds the text as one JSON string, so its newlines are written `\n` (and a `"`
inside a command is written `\"`):

```json
"text": "Phase 2: add the widget parser.\nFile: src/widget.py\nDone when: parse() returns a list.\n\n```check\n$ python -m pytest tests/test_widget.py -q\nexit 0\nprints passed\n```"
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

`files` also sets the task's scope for `scope_gate`, which sends the builder back when it
changes a path no task declared, so list every path the task writes.

Omitting both is allowed and safe — a task with no declared footprint is treated as
touching everything, so the drain falls back to one task at a time. That costs wall-clock,
never correctness. What IS unsafe is declaring a footprint you then write outside of, or
splitting file-overlapping tasks across different lanes.

Note: `executor` is NOT on the task — it lives on the goal message only.
Record the `"message_id"` from each response to use in later tasks' `depends_on` array.

**Skip-if-down (advisory):** If the comms server is unreachable, record in your completion
report that DAG seeding did not complete. Do NOT retry in a loop or fail the run.
