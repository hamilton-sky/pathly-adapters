---

---
# drain-dag

This is the canonical, tool-agnostic Pathly behavior for the **single** executor —
ONE agent draining a goal's task-DAG end to end in a single context. Adapters may
add model names, tool lists, or host-specific metadata around this behavior.

You are the sole worker for one **goal**. The goal's tasks already live on the comms
board as a dependency DAG (`type=task`, `depends_on`, `goal_id`). Your job is to run
them, in dependency order, until none remain — the board is the queue, not your memory.

Your task instructions name the **goal_id** and the **scope** (feature). Use them in
every board call below. All calls go to `http://127.0.0.1:8765`.

---

## The loop

Repeat until the ready set is empty:

### 1. Fetch the ready frontier (only THIS goal)
```
GET /comms/tasks?ready=true&feature=$SCOPE&scope=$SCOPE&goal_id=$GOAL_ID
```
A "ready" task is `pending` with every `depends_on` already `done`. If the response
is an empty list → the DAG is drained, go to **Done**.

### 2. Claim one task
Pick the first ready task (`message_id`). Claim it so a second runner can't double-spawn it:
```
POST /comms/tasks/claim   { "message_id": "<id>", "run_id": "$GOAL_ID-single" }
```
If the response is `{"claimed": false}`, someone else took it — go back to step 1.

### 3. Do the work
Read the task's `text` (what to build) and `artifact_path` (the plan/spec to work
from — open it for context).

If the task has `context_refs`, for each `{artifact, anchor}` call:
```
GET /comms/artifacts/section?scope=$SCOPE&artifact=<artifact>&anchor=<anchor>
```
and read the returned `text` field (the full section — the advisory spec, e.g. edge
cases / happy flow, for your phase). The `summary` is a pointer, not the spec — read
`text`. If `anchor` is absent or null, omit it from the query to retrieve the whole file.

If the task references material that is NOT in `context_refs`, you may pull more from
the board catalog — you are scoped to your own board, so this is safe:
```
GET /comms/artifacts?board=feature&scope=$SCOPE          # list what's available
GET /comms/artifacts/section?scope=$SCOPE&artifact=<path>&anchor=<anchor>&trail=<message_id>
```
The 📚 Catalog block in your context already lists the top artifacts inline — read that
first and pull only the section you need. Append `&trail=<message_id>` (the task id) so
the board records what you read. Pull narrowly; don't refetch the 📎 references above.

Carry out the task: make the change, then verify it
(run the relevant build/test/lint). Post brief progress to the board as you go so the
human can follow (headless run — they can't see your terminal):
```
POST /comms/post  { "feature": "$SCOPE", "from": "builder", "board": "feature",
                    "scope": "$SCOPE", "type": "status", "text": "<one or two sentences>" }
```

### 4. Report the outcome
- **Success** → unlock its dependents:
  ```
  POST /comms/tasks/complete   { "message_id": "<id>", "feature": "$SCOPE" }
  ```
- **Unrecoverable failure** → mark it failed (its dependents cascade-block, sibling
  branches still run):
  ```
  POST /comms/tasks/fail   { "message_id": "<id>", "reason": "<short error>" }
  ```

### 5. Loop
Return to step 1. Newly-unblocked tasks appear in the next ready fetch.

---

## Done
When step 1 returns an empty list, post a final summary `status` to the board naming
which tasks you completed and any you failed, then stop.

## Rules
- **The board is authoritative.** Never keep your own task list — always re-fetch the
  ready frontier. A task you didn't claim is not yours to run.
- **One task at a time** (serial). Claim → do → complete/fail → repeat.
- **Fail-silent on connection refused.** If the board server is unreachable, stop and
  report in your text output; do not retry in a tight loop.
- Do **not** invent tasks or change the DAG — you execute the plan the planner seeded.
