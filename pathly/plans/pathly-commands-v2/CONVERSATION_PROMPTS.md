# CONVERSATION_PROMPTS.md — pathly-commands-v2

_Ready-to-paste prompts. Run each conversation to completion before starting the next._

**Before any conversation:** verify mcp-fsm-driver is complete:
```bash
python -c "from pathly_orchestrator.mcp_server import next_action, complete_stage; print('OK')"
```

---

## Conversation 1 — `status` + `log`

**Stories:** S1, S2

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 1 of 4
Stories: S1 (status), S2 (log)

## Context

This plan adds six new Pathly commands and updates four existing ones.
Conversation 1 adds two read-only skills: status (cross-feature dashboard)
and log (readable event timeline). No state mutation. No MCP tool calls.

Read these files before writing anything:
  src/pathly_data/core/skills/pause.md          (for style reference)
  src/pathly_data/core/skills/verify-state.md   (for file-scan pattern reference)
  src/pathly_data/adapters/claude/_meta/         (list to understand YAML shape)
  pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md  (for border/panel format)

## Files to create

  src/pathly_data/core/skills/status.md
  src/pathly_data/core/skills/log.md
  src/pathly_data/adapters/claude/_meta/status_skill.yaml
  src/pathly_data/adapters/claude/_meta/log_skill.yaml
  src/pathly_data/adapters/codex/_meta/status_skill.yaml
  src/pathly_data/adapters/codex/_meta/log_skill.yaml

## status.md — implement exactly this

Scan for STATE.json files in (skip any path containing .archive/):
  pathly/plans/*/STATE.json
  pathly/debugs/*/STATE.json
  pathly/explorations/*/STATE.json

For each found file, read it and read feedback/ dir if it exists.

Determine BLOCKED status: any *.md file in feedback/ = BLOCKED.
If BLOCKED: find highest-priority file using feedback_routing priority order
  (HUMAN_QUESTIONS > BLOCKED_ON_HUMAN > ARCH_FEEDBACK > DESIGN_QUESTIONS >
   IMPL_QUESTIONS > REVIEW_FAILURES > TEST_FAILURES).
  If multiple: show highest + "(+N more)".

Print:

─────────────────────────────────────────────────────────
  Pathly · Active features
─────────────────────────────────────────────────────────
  <topic>      ·  <flow>  ·  <state>    (conv <N>)
  <topic>      ·  <flow>  ·  <state>    [BLOCKED: <file>]
  <topic>      ·  <flow>  ·  DONE ✓
─────────────────────────────────────────────────────────

Rules:
- DONE topics listed last with ✓
- Non-DONE topics sorted by most recently modified STATE.json first
- If $ARGUMENTS contains "--all": include DONE topics; otherwise omit DONE
- If no topics found: print "Nothing in progress."
- Conv N: read "current_conversation" from STATE.json (default 0 if absent)

## log.md — implement exactly this

Parse $ARGUMENTS:
  First non-keyword word = TOPIC (optional)
  "--all" flag = show full history (default: last 20 events)

If TOPIC not given:
  Scan pathly/plans/ pathly/debugs/ pathly/explorations/ for most recently
  modified STATE.json (skip .archive/). Use that topic.
  Read flow from STATE.json "flow" field or infer from path (plans=team,
  debugs=debug, explorations=explore).

Locate EVENTS.jsonl at the storage_path of that topic. If absent:
  Print: "No events recorded for <topic>."  Exit.

Read lines. Apply --all or tail last-20 limit.
For each event line (JSON), render one of:

  HH:MM:SS  STATE_TRANSITION      <from> → <to>
  HH:MM:SS  STATE_ROLLBACK        <from> → <to>
  HH:MM:SS  DECIDE_ROUTING        chosen: <next_state>  (input: "<decision_input>")
  HH:MM:SS  NEEDS_CONTEXT         count: <N>
  HH:MM:SS  FEEDBACK_RESOLVED     <file>  agent: <agent>
  HH:MM:SS  <other type>          <all remaining JSON fields as key: value>

Print header and footer:
  ─────────────────────────────────────────────────────────
    Pathly log · <topic> · <flow>
  ─────────────────────────────────────────────────────────
    [events]
  ─────────────────────────────────────────────────────────
    Showing last N of M events. Use --all for full history.

## Adapter YAML files

Follow the exact pattern of an existing adapter YAML in the same directory.
For each skill:
  natural_language (or equivalent): one sentence matching the story AC summary.
  No MCP syntax — these skills read files directly, no tool calls needed.

## Constraints

- Do not touch any existing skill files.
- Do not touch any Python files.
- Do not call next_action or complete_stage — these skills are read-only.

## Verify after completion

grep "feedback/" src/pathly_data/core/skills/status.md
grep "EVENTS.jsonl" src/pathly_data/core/skills/log.md
grep "status_skill" src/pathly_data/adapters/claude/_meta/status_skill.yaml
```

---

## Conversation 2 — `fix` + `ff`

**Stories:** S3, S4

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 2 of 4
Stories: S3 (fix), S4 (ff)

## Prerequisite

Conversation 1 must be complete. Verify:
  grep "feedback/" src/pathly_data/core/skills/status.md
Must return at least one match.

## Context

fix and ff are thin wrappers over the pathly-fsm MCP tools (next_action +
complete_stage). Both require mcp-fsm-driver to be installed.

Read before writing:
  src/pathly_data/core/skills/team.md       (for MCP tool call pattern + topic resolution)
  src/pathly_data/core/skills/pause.md      (for style)
  pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md  (panel format — Scenario 2 for blocked)

## Files to create

  src/pathly_data/core/skills/fix.md
  src/pathly_data/core/skills/ff.md
  src/pathly_data/adapters/claude/_meta/fix_skill.yaml
  src/pathly_data/adapters/claude/_meta/ff_skill.yaml
  src/pathly_data/adapters/codex/_meta/fix_skill.yaml
  src/pathly_data/adapters/codex/_meta/ff_skill.yaml

## fix.md — implement exactly this

1. Resolve TOPIC from $ARGUMENTS or auto-detect (same logic as team.md).
   Resolve flow from active STATE.json. Resolve project_root = cwd.

2. Call next_action(flow, topic, project_root).

3. If not blocked:
   Print: "No open feedback for <topic>. Use /pathly go to continue."  Exit.

4. If blocked, target_agent == "human":
   Print the file contents.
   Print: "This is a human decision — resolve it manually, then delete
           feedback/<filename>, then run /pathly go."
   Exit. Do not run any agent.

5. If blocked, target_agent == <agent>:
   Display Scenario 2 panel from CONTEXTUAL_MENU_UX.md (blocked format).
   Options:
     [1] Resolve   — run <agent> on the feedback file now
     [2] View      — print feedback file contents, then show menu again
     [3] Escalate  — write HUMAN_QUESTIONS.md with escalation note, print
                     contents, halt
     [4] Abort     — exit without changes

6. On [1] Resolve:
   a. Follow the instructions returned in next_action for <agent>.
   b. After agent completes: delete the feedback file from feedback/.
      Print: "Deleted: feedback/<filename>"
   c. Call complete_stage(flow, topic, project_root).
      - If blocked again: show blocked panel again (loop from step 5).
      - If {decide: true}: show Scenario 3 Panel A from CONTEXTUAL_MENU_UX.md.
        Wait for answer. Call complete_stage(... decision=<answer>).
      - Otherwise: show the resulting state panel (Scenario 1 format).
      - If done=true: print "Feature complete. All stages done."

## ff.md — implement exactly this

1. Resolve TOPIC from $ARGUMENTS or auto-detect. Resolve flow. Resolve project_root.

2. Call next_action(flow, topic, project_root).
   If blocked: show blocked panel. Print:
     "Cannot fast-forward — open feedback must be resolved first. Use /pathly fix."
   Exit.

3. Read current_state from the next_action response.
   Evaluate what the next state would be — read transition_rules from flow YAML:
     Check if any on_artifact files exist (L1). Check on_content (L2).
     If decide: next_state = "<decide — will ask after confirmation>"
     If default: next_state = <default>

4. Print confirmation:
   "Fast-forward <topic>: <current_state> → <next_state>
    <If transition_actions has git_commit for this transition:>
    ! This transition will run a git commit. Make sure your changes are staged.
    Proceed without running the current agent? (y/n)"
   Wait. On n: exit.

5. On y: call complete_stage(flow, topic, project_root).
   - If {decide: true}: show Scenario 3 Panel A. Wait for answer.
     Call complete_stage(... decision=<answer>).
   - Show resulting state panel.
   - If done=true: print "Feature complete."

## Constraints

- Do not edit any existing skill files.
- Do not touch any Python files.
- The current stage's agent does NOT run in ff — advance state only.

## Verify after completion

grep "complete_stage" src/pathly_data/core/skills/fix.md
grep "complete_stage" src/pathly_data/core/skills/ff.md
grep "HUMAN_QUESTIONS" src/pathly_data/core/skills/fix.md
grep "agent does NOT run\|advance state only" src/pathly_data/core/skills/ff.md
```

---

## Conversation 3 — `back` + `ask`

**Stories:** S5, S6

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 3 of 4
Stories: S5 (back), S6 (ask)

## Prerequisite

Conversation 2 must be complete. Verify:
  grep "complete_stage" src/pathly_data/core/skills/fix.md
Must return at least one match.

## Context

back writes STATE.json directly (not via MCP server — rollback has no MCP tool).
ask spawns an agent without touching any FSM state.

Read before writing:
  src/pathly_data/core/skills/team.md         (topic resolution pattern)
  src/pathly_data/core/skills/pause.md        (style)
  pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md  (Scenario 1 panel format)

## Files to create

  src/pathly_data/core/skills/back.md
  src/pathly_data/core/skills/ask.md
  src/pathly_data/adapters/claude/_meta/back_skill.yaml
  src/pathly_data/adapters/claude/_meta/ask_skill.yaml
  src/pathly_data/adapters/codex/_meta/back_skill.yaml
  src/pathly_data/adapters/codex/_meta/ask_skill.yaml

## back.md — implement exactly this

1. Resolve TOPIC from $ARGUMENTS or auto-detect. Resolve flow and storage_path.

2. Read EVENTS.jsonl from storage_path. Scan from newest to oldest.
   Find the most recent STATE_TRANSITION event.
   Extract its "from" field = prior_state.
   If no STATE_TRANSITION found:
     Print: "No previous state to roll back to for <topic>."  Exit.

3. Read STATE.json. Extract current = "current" field.

4. Print confirmation:
   "Roll back <topic>:  <current> → <prior_state>
    Note: git commits and other transition_actions are NOT undone by this command.
    Proceed? (y/n)"
   Wait for reply. On n: print "Aborted." Exit.

5. On y:
   a. Write STATE.json:
        - Set "current" = prior_state
        - Preserve all other fields (current_conversation, updated_at updated to now,
          any other keys)
        - Write atomically: write to STATE.json.tmp then rename to STATE.json
   b. Append to EVENTS.jsonl:
        {"type": "STATE_ROLLBACK", "from": "<current>", "to": "<prior_state>"}
        (the append_event function in fsm.py injects "ts" — replicate that here:
         add "ts": <ISO-8601 UTC now> to the dict before appending)
   c. Display the contextual state panel for prior_state (Scenario 1 format from
      CONTEXTUAL_MENU_UX.md). Options [1–4] as normal.

NOTE (include as a comment at the top of the skill file):
  back.md writes STATE.json directly without going through the MCP server.
  This is intentional — rollback has no MCP tool. This is the ONLY skill
  permitted to do so. All forward transitions must use complete_stage.

## ask.md — implement exactly this

Parse $ARGUMENTS:
  First word = ROLE
  Remainder = QUESTION (everything after ROLE)

Valid built-in roles (always valid regardless of active flow):
  architect, builder, planner, reviewer, tester, scout, explorer

Also valid: any agent name that appears as a value in agent_map of the active
flow (read from flow YAML if a topic is active).

If ROLE not in valid list:
  Print: "Unknown role: <ROLE>"
  Print: "Valid roles: architect, builder, planner, reviewer, tester, scout,
          explorer  (+ any agent in the active flow's agent_map)"
  Exit.

If QUESTION is blank:
  Ask: "What is your question for <ROLE>?"
  Wait for reply. Store as QUESTION.

Spawn <ROLE> agent with exactly this prompt and nothing else:
  "Answer this question as <ROLE>. Give one focused reply only.
   Do not write any files. Do not read STATE.json, feedback/, or any plan files.
   Do not call next_action or complete_stage.
   Question: <QUESTION>"

After agent replies: exit. Do not call next_action, complete_stage, or any MCP tool.
Do not write anything to storage_path or feedback/.

## Constraints

- Do not touch any existing skill files.
- Do not touch any Python files.
- ask.md must NOT call next_action or complete_stage under any circumstance.
- back.md must write atomically (tmp + rename).

## Verify after completion

grep "STATE_ROLLBACK" src/pathly_data/core/skills/back.md
grep "STATE.json.tmp" src/pathly_data/core/skills/back.md
grep "complete_stage\|next_action" src/pathly_data/core/skills/ask.md  # must return nothing
grep "Do not write\|Do not call" src/pathly_data/core/skills/ask.md
```

---

## Conversation 4 — Update start / pause / end / go

**Stories:** S7

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 4 of 4
Story: S7

## Prerequisite

Conversation 3 must be complete. Verify:
  grep "STATE_ROLLBACK" src/pathly_data/core/skills/back.md
Must return at least one match.

## Context

This conversation adds the contextual state panel to four existing entry-point
skills. This was deferred from mcp-fsm-driver Conv 3.

Read ALL of these before making any changes:
  src/pathly_data/core/skills/go.md
  src/pathly_data/core/skills/pause.md
  src/pathly_data/core/skills/end.md
  src/pathly_data/core/skills/start.md
  pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md  (authoritative format spec)
  src/pathly_data/core/skills/team.md  (for topic resolution + next_action pattern)

## Files to edit (no new files)

  src/pathly_data/core/skills/go.md
  src/pathly_data/core/skills/pause.md
  src/pathly_data/core/skills/end.md
  src/pathly_data/core/skills/start.md

## go.md — what to add

After recovering active state (reading STATE.json), before routing to the
flow skill, insert:

1. Call next_action(flow, topic, project_root) to get {current_state, agent, limits}.
2. Display full Scenario 1 contextual panel (CONTEXTUAL_MENU_UX.md format).
   Show pipeline progress bar derived from flow YAML states list.
   Show all 4 options: [1] Proceed  [2] Pause  [3] Status  [4] Switch
3. On [1] or Enter: route to the appropriate flow skill (team/debug/explore).
4. On [2]: call pause skill. Stop.
5. On [3]: print STATE.json + last 10 lines of EVENTS.jsonl. Show panel again.
6. On [4]: print "Switch to: (1) team  (2) debug  (3) explore" and route.

Do not change any other behavior in go.md.

## pause.md — what to add

Before writing status: PAUSED, insert a read-only panel:

─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>      Conv : <N>
  Pausing session.
─────────────────────────────────────────────────────────

Read current_state and conv from STATE.json. Do not call next_action.
After printing panel: write PAUSED and print resume instructions as before.

## end.md — what to add

Before the "Write a retro? (y/n)" prompt, insert:

1. Call next_action(flow, topic, project_root) to get {current_state, agent}.
2. Print a read-only summary panel:

─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>      Conv : <N>
  <If any *.md in feedback/:>
  ! Open feedback files — resolve before archiving.
─────────────────────────────────────────────────────────
  Conversations completed: <N>
─────────────────────────────────────────────────────────

Then ask "Write a retro? (y/n)" as before.

## start.md — what to add

When user picks option [4] "Continue in-progress work":
1. Auto-detect active feature (same logic as team.md feature detection).
2. Call next_action(flow, topic, project_root).
3. Display full Scenario 1 contextual panel (all 4 options).
4. Route based on user choice (same as go.md options).

No changes to options [1], [2], [3], [5].

## Constraints

- Do not change any existing behavior in these files — only add the panel.
- Do not change the structure or other steps in go/pause/end/start.
- Do not touch any Python files or adapter YAML files.

## Verify after completion

grep "next_action" src/pathly_data/core/skills/go.md
grep "Pausing session" src/pathly_data/core/skills/pause.md
grep "next_action" src/pathly_data/core/skills/end.md
grep "next_action" src/pathly_data/core/skills/start.md
```
