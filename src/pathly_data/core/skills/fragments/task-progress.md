## Task progress (board status)

You run **headless** — the human cannot see your terminal, so the comms board is the ONLY place
they watch a task move. Bracket each unit of work with a one-line `status` post so the run never
looks stalled. This is **mandatory**; it is separate from `comms-post` (which mirrors *findings*)
and from phase logging (which marks *pipeline phases* you do not have here).

- **When you START a task/unit of work**, post immediately:
  ```bash
  curl -s -X POST http://127.0.0.1:8765/comms/post -H "Content-Type: application/json" -d '{
    "feature": "<feature>", "from": "<your-role>", "board": "feature",
    "type": "status", "text": "Started: <what you are about to do>" }'
  ```
- **When you FINISH it** (right before you complete / hand off the task), post the outcome:
  ```bash
  curl -s -X POST http://127.0.0.1:8765/comms/post -H "Content-Type: application/json" -d '{
    "feature": "<feature>", "from": "<your-role>", "board": "feature",
    "type": "status", "text": "Done: <what changed / the result>" }'
  ```

Rules:
- **Every** unit of work, not just the first — if you drain several tasks in a loop, bracket each one.
- One line each. `<feature>` = the feature slug; `<your-role>` = your agent role (`builder`, …).
- Best-effort transport: on connection-refused / non-200, skip silently and keep working — never
  block the task or retry in a loop just to post a status.
