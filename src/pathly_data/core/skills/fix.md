# fix

Resolve open feedback for an active Pathly feature. Spawns an agent to handle
blocked feedback files one at a time.

Run for `$ARGUMENTS`.

## Step 1 — Resolve TOPIC, flow, project_root

Parse `$ARGUMENTS`:
- First non-keyword word = TOPIC (if present).

If TOPIC was not in `$ARGUMENTS`, auto-detect:
1. Read `pathly/plans/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If auto-detected, confirm with the user before proceeding.

Resolve:
- `flow` = STATE.json field `"flow"` for the resolved TOPIC.
- `project_root` = current working directory (cwd).

## Step 2 — Call next_action

Call next_action with `{flow, topic, project_root}`.

Preferred: use MCP tool `mcp__pathly-fsm__next_action` if available.
Fallback: POST to `http://127.0.0.1:8765/next_action` with JSON body `{flow, topic, project_root}`.

Store the result as `action`.

## Step 3 — If not blocked

If `action.blocked` is false or absent:
Print: "No open feedback for <topic>. Use /pathly go to continue."
Exit.

## Step 4 — If blocked, target_agent == "human"

If `action.blocked` is true and `action.target_agent == "human"`:
- Print the full contents of `pathly/plans/<topic>/feedback/<action.file>`.
- Print:
  ```
  Human decision required — resolve manually, delete feedback/<file>, then run /pathly go.
  ```
- Exit.

## Step 5 — If blocked, target_agent == <agent>

If `action.blocked` is true and `action.target_agent` is a non-human agent name:

Display the blocked panel:
```
─────────────────────────────────────────────────────────────────
  Pathly  ·  fix  ·  <topic>
  Blocked:  feedback/<file>  →  routed to <agent>
─────────────────────────────────────────────────────────────────
  [1] Resolve   — run <agent> on feedback/<file> now
  [2] View      — print feedback/<file> contents, show menu again
  [3] Escalate  — write HUMAN_QUESTIONS.md with escalation note, halt
  [4] Abort     — exit without changes
─────────────────────────────────────────────────────────────────
  Reply [1–4]:
```

Wait for user reply. Route to the matching step below.

## Step 6 — On [1] Resolve

a. Follow the instructions returned by `action` for the target agent.
   Spawn the appropriate agent (`action.target_agent`) with those instructions,
   passing the feedback file path `pathly/plans/<topic>/feedback/<file>` as context.

b. After the agent completes: call complete_stage.

   Preferred: use MCP tool `mcp__pathly-fsm__complete_stage` if available.
   Fallback: POST to `http://127.0.0.1:8765/complete_stage` with JSON body
   `{flow, topic, project_root, resolved_files: ["<file>"]}`.

   Store result as `stage_result`.

c. Handle `stage_result`:

   - If `stage_result.blocked` is true:
     Show the blocked panel from Step 5 with updated file/agent values.
     Loop — return to Step 5.

   - If `stage_result.decide` is true:
     Show decision panel:
     ```
     ─────────────────────────────────────────────────────────────────
       Pathly  ·  fix  ·  <topic>  ·  Routing decision required
     ─────────────────────────────────────────────────────────────────
       Question: <stage_result.question>
       Options:  <comma-separated list of stage_result.options keys>
     ─────────────────────────────────────────────────────────────────
       Your answer:
     ```
     Wait for user answer. Call complete_stage again with `{flow, topic, project_root, decision: <answer>}`.
     Handle that result with the same logic (blocked → loop, done → "Feature complete.", otherwise → show state).

   - If `stage_result.done` is true:
     Print: "Feature complete."
     Exit.

   - Otherwise:
     Print:
     ```
     ─────────────────────────────────────────────────────────────────
       Pathly  ·  fix  ·  <topic>
       Advanced to: <stage_result.next_state>   Agent: <stage_result.agent>
     ─────────────────────────────────────────────────────────────────
     ```
     Print: "Run /pathly go to continue with the next agent."
     Exit.

## Step 7 — On [2] View

Print the full contents of `pathly/plans/<topic>/feedback/<file>`.
Show the blocked panel again (return to Step 5).

## Step 8 — On [3] Escalate

Write `pathly/plans/<topic>/feedback/HUMAN_QUESTIONS.md` with the following content:

```
Escalated by /fix: feedback/<file> could not be auto-resolved. Manual intervention required.
```

If `HUMAN_QUESTIONS.md` already exists, append the line with a separator:
```
\n---\n<escalation line>
```

Print: "Escalated: feedback/HUMAN_QUESTIONS.md written."
Halt.

## Step 9 — On [4] Abort

Print: "Aborted."
Exit.
