# CONVERSATION_PROMPTS.md — pathly-commands-v2

_Ready-to-paste prompts. Run each to completion before starting the next._

**Before Conv 1:** verify http-fsm-driver is complete:
```bash
python -c "from pathly_orchestrator.http_server import next_action, complete_stage; print('OK')"
```

---

## Conversation 1 — Python CLI: `pathly-status` + `pathly-log`

**Stories:** S1, S2

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 1 of 5
Stories: S1 (status), S2 (log)

## Context

status and log are Python CLI scripts — no LLM reasoning. They are exposed in
conversations via thin skill wrappers that call them via the Bash tool. This
makes them work on all surfaces: Claude Code CLI, Desktop, VS Code extension, Codex.

Read before writing:
  src/pathly_orchestrator/eventlog.py      (for EVENTS.jsonl append pattern)
  src/pathly_orchestrator/state.py         (for flow loading helpers)
  tests/test_orchestrator.py               (for test style)
  src/pathly_data/adapters/claude/_meta/   (list files — understand YAML shape)

## Files to create

  src/pathly_orchestrator/status_cli.py
  src/pathly_orchestrator/log_cli.py
  src/pathly_data/core/skills/status.md
  src/pathly_data/core/skills/log.md
  src/pathly_data/adapters/claude/_meta/status_skill.yaml
  src/pathly_data/adapters/claude/_meta/log_skill.yaml
  src/pathly_data/adapters/codex/_meta/status_skill.yaml
  src/pathly_data/adapters/codex/_meta/log_skill.yaml
  src/pathly_data/adapters/copilot/_meta/status_skill.yaml
  src/pathly_data/adapters/copilot/_meta/log_skill.yaml

## pyproject.toml — add two entry points

In [project.scripts], after pathly-fsm:
  pathly-status = "pathly_orchestrator.status_cli:main"
  pathly-log    = "pathly_orchestrator.log_cli:main"

## status_cli.py — implement exactly this

Entry point: main(). No class. Stdlib only (argparse, json, pathlib).

Scan roots (skip any path containing ".archive"):
  pathly/plans/*/STATE.json     → flow = "team"
  pathly/debugs/*/STATE.json    → flow = "debug"
  pathly/explorations/*/STATE.json → flow = "explore"

For each STATE.json found:
  - Read JSON. Extract "current" (state), "current_conversation" (conv, default 0).
  - Check feedback/: if any *.md files exist, find highest priority by this order:
    HUMAN_QUESTIONS > BLOCKED_ON_HUMAN > ARCH_FEEDBACK > DESIGN_QUESTIONS >
    IMPL_QUESTIONS > REVIEW_FAILURES > TEST_FAILURES
    Show highest + "(+N more)" if multiple.
  - If state == "DONE": add to done list.
  - Otherwise: add to active list.

Sort active by STATE.json mtime descending (most recent first).

Print:
  ─────────────────────────────────────────────────────────
    Pathly · Active features
  ─────────────────────────────────────────────────────────
    <topic>          ·  <flow>   ·  <state>         (conv N)
    <topic>          ·  <flow>   ·  <state>         [BLOCKED: <file>]
  ─────────────────────────────────────────────────────────

--all flag: also show DONE topics with ✓ at the end.
No active topics: print "Nothing in progress."

## log_cli.py — implement exactly this

Entry point: main(). Stdlib only (argparse, json, datetime, pathlib).

Args: optional positional TOPIC, --all flag (default: last 20 events).

If TOPIC not given: find most recently modified STATE.json across all three
scan roots (skip .archive). Use that topic's parent directory as storage_path.

Locate EVENTS.jsonl in storage_path. If absent: print "No events recorded." exit.

Read lines. Apply last-20 limit unless --all.

Render each JSON line as:
  HH:MM:SS  STATE_TRANSITION      <from> → <to>
  HH:MM:SS  STATE_ROLLBACK        <from> → <to>
  HH:MM:SS  DECIDE_ROUTING        chosen: <chosen>  (input: "<decision_input>")
  HH:MM:SS  NEEDS_CONTEXT         count: <count>
  HH:MM:SS  FEEDBACK_RESOLVED     <file>  agent: <agent>
  HH:MM:SS  <other>               <remaining key: value pairs>

Print:
  ─────────────────────────────────────────────────────────
    Pathly log · <topic> · <flow>
  ─────────────────────────────────────────────────────────
    [rendered lines]
  ─────────────────────────────────────────────────────────
    Showing last N of M events. Use --all for full history.

## Skill wrappers — identical shape for both

status.md:
  # status
  Cross-feature dashboard showing all active Pathly flows and their state.
  ## Runtime
  Run: pathly-status $ARGUMENTS
  Print the output exactly as returned.
  If command not found: print "Run pathly-setup first to install Pathly CLI tools."

log.md:
  # log
  Readable timeline of FSM events for the active or named feature.
  ## Runtime
  Run: pathly-log $ARGUMENTS
  Print the output exactly as returned.
  If command not found: print "Run pathly-setup first to install Pathly CLI tools."

## Adapter YAML files (claude, codex, copilot — all three)

Before writing any YAML: read one existing skill YAML from each adapter directory.
They differ: Claude uses `tools:` list, Codex uses `model: gpt-*`, Copilot is a
subset with fewer fields. Match each adapter's own conventions exactly.
natural_language / description: one sentence matching the story AC summary.
No HTTP syntax — these skills call Python CLI via Bash, not HTTP tools.

## Constraints

- Do not touch any existing skill files.
- Do not touch http_server.py or fsm.py.
- status_cli.py and log_cli.py must use stdlib only (no http package, no yaml needed
  for status — just read STATE.json as JSON).

## Verify

python -c "from pathly_orchestrator.status_cli import main; print('OK')"
python -c "from pathly_orchestrator.log_cli import main; print('OK')"
grep "pathly-status\|pathly-log" pyproject.toml
grep "pathly-status" src/pathly_data/core/skills/status.md
pytest -q
```

---

## Conversation 2 — Python CLI: `pathly-back` + `pathly-ff`

**Stories:** S5, S4

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 2 of 5
Stories: S5 (back), S4 (ff)

## Prerequisite

Conversation 1 must be complete. Verify:
  python -c "from pathly_orchestrator.status_cli import main; print('OK')"

## Context

back and ff are Python CLI scripts with input() confirmation. ff calls
complete_stage from http_server.py directly as a Python function — not via
the HTTP protocol. If complete_stage returns {decide: True}, ff prompts the
user for a typed answer via input().

Read before writing:
  src/pathly_orchestrator/http_server.py     (complete_stage + next_action signatures)
  src/pathly_orchestrator/status_cli.py     (auto-detect topic pattern to reuse)
  src/pathly_orchestrator/eventlog.py       (EVENTS.jsonl append pattern)

## Files to create

  src/pathly_orchestrator/back_cli.py
  src/pathly_orchestrator/ff_cli.py
  src/pathly_data/core/skills/back.md
  src/pathly_data/core/skills/ff.md
  src/pathly_data/adapters/claude/_meta/back_skill.yaml
  src/pathly_data/adapters/claude/_meta/ff_skill.yaml
  src/pathly_data/adapters/codex/_meta/back_skill.yaml
  src/pathly_data/adapters/codex/_meta/ff_skill.yaml
  src/pathly_data/adapters/copilot/_meta/back_skill.yaml
  src/pathly_data/adapters/copilot/_meta/ff_skill.yaml

## pyproject.toml — add two entry points

  pathly-back = "pathly_orchestrator.back_cli:main"
  pathly-ff   = "pathly_orchestrator.ff_cli:main"

## back_cli.py — implement exactly this

Entry point: main(). Stdlib + pathlib + json + datetime.

1. Parse optional positional TOPIC from sys.argv. Auto-detect if absent
   (reuse auto-detect logic from status_cli — scan for most recent active STATE.json).
2. Resolve storage_path: same scan as status_cli, match topic to directory.
3. Read EVENTS.jsonl. Scan lines newest→oldest (reversed).
   Find first line where type == "STATE_TRANSITION". Extract "from" = prior_state.
   If none found: print "No previous state to roll back to for <topic>." sys.exit(0).
4. Read STATE.json. current = state["current"].
5. Print:
   "Roll back <topic>:  <current> → <prior_state>
    Note: git commits and transition_actions are NOT undone by this command."
   answer = input("Proceed? (y/n): ").strip().lower()
   If not "y": print "Aborted." sys.exit(0).
6. Write STATE.json atomically:
   a. new_state = {**existing, "current": prior_state,
                   "updated_at": datetime.utcnow().isoformat()}
   b. Write to storage_path / "STATE.json.tmp", then rename to "STATE.json".
7. Append to EVENTS.jsonl:
   {"type": "STATE_ROLLBACK", "from": current, "to": prior_state,
    "ts": datetime.utcnow().isoformat()}
8. Print: "Rolled back <topic>: <current> → <prior_state>"
   Print: "Run /pathly go or pathly-ff to resume."

## ff_cli.py — implement exactly this

Entry point: main(). Import complete_stage and next_action directly:
  from pathly_orchestrator.http_server import complete_stage, next_action

1. Parse optional TOPIC. Auto-detect if absent. Resolve flow, project_root = str(Path.cwd()).
2. Call next_action(flow=flow, topic=topic, project_root=project_root).
   If result.get("blocked"): print blocked state. Print "Use pathly-fix first." sys.exit(0).
3. current_state = result["current_state"]
   Print: "Fast-forward <topic>: <current_state> → (evaluating...)"
   Note: we don't pre-evaluate; just warn about git_commit if the flow YAML has
   transition_actions for any transition from current_state containing git_commit.
   If yes: print "! This transition may include a git commit."
   answer = input("Proceed without running the current agent? (y/n): ").strip().lower()
   If not "y": print "Aborted." sys.exit(0).
4. result = complete_stage(flow=flow, topic=topic, project_root=project_root)
5. Handle result:
   - If result.get("decide"):
       print "FSM needs a routing decision:"
       print f"  Question: {result['question']}"
       if result.get("context"):
           print f"  Context:\n{result['context'][:500]}"
       print f"  Options: {', '.join(result['options'].keys())}"
       decision = input(f"  Your choice [{'/'.join(result['options'])}]: ").strip()
       result = complete_stage(flow=flow, topic=topic,
                               project_root=project_root, decision=decision)
   - If result.get("done"): print "Feature complete." sys.exit(0).
   - If result.get("blocked"): print "Blocked by feedback." print result. sys.exit(0).
   - Otherwise:
       print f"Advanced to: {result['next_state']}  Agent: {result['agent']}"
       print "Run /pathly go to continue with the next agent."

## Skill wrappers

back.md:
  # back
  Roll back the FSM one state with confirmation. Does not undo git commits.
  ## Runtime
  Run: pathly-back $ARGUMENTS
  Print the output exactly as returned.
  If command not found: print "Run pathly-setup first to install Pathly CLI tools."

ff.md:
  # ff
  Fast-forward to the next FSM state without running the current stage agent.
  ## Runtime
  Run: pathly-ff $ARGUMENTS
  Print the output exactly as returned.
  If command not found: print "Run pathly-setup first to install Pathly CLI tools."

## Constraints

- Do not edit http_server.py or fsm.py.
- back_cli.py must write STATE.json atomically (tmp + rename).
- ff_cli.py must import complete_stage as a Python function, NOT via subprocess
  or HTTP protocol.

## Verify

python -c "from pathly_orchestrator.back_cli import main; print('OK')"
python -c "from pathly_orchestrator.ff_cli import main; print('OK')"
grep "pathly-back\|pathly-ff" pyproject.toml
pytest -q
```

---

## Conversation 3 — LLM skill: `fix`

**Stories:** S3

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 3 of 5
Story: S3 (fix)

## Prerequisite

Conversation 2 must be complete. Verify:
  python -c "from pathly_orchestrator.back_cli import main; print('OK')"

## Context

fix is the only new command that must be an LLM skill — it spawns an agent to
resolve feedback content. Python cannot do this. No CLI backing script needed.

Read before writing:
  src/pathly_data/core/skills/team.md                       (topic resolution + HTTP pattern)
  pathly/plans/http-fsm-driver/CONTEXTUAL_MENU_UX.md         (Scenario 2 blocked panel format)

## Files to create

  src/pathly_data/core/skills/fix.md
  src/pathly_data/adapters/claude/_meta/fix_skill.yaml
  src/pathly_data/adapters/codex/_meta/fix_skill.yaml
  src/pathly_data/adapters/copilot/_meta/fix_skill.yaml

## fix.md — implement exactly this

1. Resolve TOPIC from $ARGUMENTS or auto-detect (same logic as team.md).
   Resolve flow from STATE.json "flow" field. Resolve project_root = cwd.

2. Call next_action(flow, topic, project_root).

3. If not blocked: "No open feedback for <topic>. Use /pathly go to continue."  Exit.

4. If blocked, target_agent == "human":
   Print file contents in full.
   Print: "Human decision required — resolve manually, delete feedback/<file>,
           then run /pathly go."  Exit.

5. If blocked, target_agent == <agent>:
   Display Scenario 2 panel from CONTEXTUAL_MENU_UX.md (blocked format).
   Options:
     [1] Resolve  — run <agent> on feedback/<file> now
     [2] View     — print feedback/<file> contents, show menu again
     [3] Escalate — write HUMAN_QUESTIONS.md with escalation note, print contents, halt
     [4] Abort    — exit without changes

6. On [1] Resolve:
   a. Follow instructions returned by next_action for <agent>.
   b. After agent completes: delete feedback/<file>.
      Print: "Deleted: feedback/<filename>"
   c. Call complete_stage(flow, topic, project_root).
      - If blocked again: show Scenario 2 panel, loop from step 5.
      - If {decide: true}: show Scenario 3 Panel A (CONTEXTUAL_MENU_UX.md).
        Wait for user answer. Call complete_stage(..., decision=<answer>).
      - Otherwise: show resulting state panel (Scenario 1 format).
      - If done=true: "Feature complete."

## Constraints

- Do not create any Python files.
- fix.md must resolve feedback one file at a time — never batch multiple files
  before calling complete_stage.

## Verify

grep "complete_stage" src/pathly_data/core/skills/fix.md
grep "HUMAN_QUESTIONS" src/pathly_data/core/skills/fix.md
grep "target_agent" src/pathly_data/core/skills/fix.md
```

---

## Conversation 4 — `meet` enhancement: escalate to pipeline

**Stories:** S6

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 4 of 5
Story: S6

## Prerequisite

Conversation 3 must be complete. Verify:
  grep "complete_stage" src/pathly_data/core/skills/fix.md

## Context

meet.md already has a well-designed consultation flow. We are adding ONE new
option to Step 5 only. Do not touch Steps 1–4 or Step 6 (Promotion behavior).

Read meet.md IN FULL before touching it. Understand the existing Step 5 output
and choice handling. Make the minimum change to add [5] Escalate to pipeline.

## File to edit

  src/pathly_data/core/skills/meet.md   (Step 5 only)

## What to add — Step 5 change

The current Step 5 prints options [1]–[4] and a note about "See all commands".
Replace that block with [1]–[5] plus "See all commands" renumbered:

  [1] Return to <current stage>
  [2] Promote to planner update
  [3] Promote to architecture update
  [4] Ask another meet question
  [5] Escalate to pipeline
  [6] See all commands

Implement option [5] as follows:

1. Print:
   "Which feedback type fits this consultation?
    [1] ARCH_FEEDBACK      → routes to architect
    [2] DESIGN_QUESTIONS   → routes to architect
    [3] IMPL_QUESTIONS     → routes to planner
    Reply with 1–3:"

2. Map choice → filename:
     1 → ARCH_FEEDBACK.md
     2 → DESIGN_QUESTIONS.md
     3 → IMPL_QUESTIONS.md

3. Read the consult note from plans/$FEATURE/consults/<most-recent>-<role>.md.
   (The most recently written file in that directory for this feature.)

4. Target file: plans/$FEATURE/feedback/<chosen>.md
   - If file exists: append with separator:
       \n---\n## Consultation escalated <ISO timestamp>\n<consult note content>
   - If absent: write the consult note content as the file content.

5. Resolve the target agent from the active flow's feedback_routing:
   Read plans/$FEATURE/STATE.json to find the flow name.
   Load the corresponding flow YAML via importlib.resources.
   Look up feedback_routing[<chosen stem>] = target_agent.

6. Print:
   "Pipeline blocked on feedback/<chosen>.md
    Next complete_stage will route to: <target_agent>
    The consults/ file is preserved — escalation is additive.
    Use /pathly fix or /pathly go to continue."

## Constraints

- Do not touch Steps 1–4 or Step 6 of meet.md.
- Do not touch any Python files.
- If the user picks [6] See all commands: existing behavior (print help reference).
  Renumber from [5] to [6] for "See all commands" only.

## Verify

grep "Escalate to pipeline" src/pathly_data/core/skills/meet.md
grep "ARCH_FEEDBACK\|DESIGN_QUESTIONS\|IMPL_QUESTIONS" src/pathly_data/core/skills/meet.md
grep "\[5\]" src/pathly_data/core/skills/meet.md
```

---

## Conversation 5 — Update start / pause / end / go

**Stories:** S7

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: pathly-commands-v2
Conversation: 5 of 5
Story: S7

## Prerequisite

Conversation 4 must be complete. Verify:
  grep "Escalate to pipeline" src/pathly_data/core/skills/meet.md

## Context

This is the deferred work from http-fsm-driver Conv 3. Add the contextual state
panel to four existing entry-point skills. Edits only — no new files.

Read ALL of these before making any change:
  src/pathly_data/core/skills/go.md
  src/pathly_data/core/skills/pause.md
  src/pathly_data/core/skills/end.md
  src/pathly_data/core/skills/start.md
  pathly/plans/http-fsm-driver/CONTEXTUAL_MENU_UX.md   ← authoritative format spec
  src/pathly_data/core/skills/team.md   ← topic resolution + next_action call pattern

## Files to edit

  src/pathly_data/core/skills/go.md
  src/pathly_data/core/skills/pause.md
  src/pathly_data/core/skills/end.md
  src/pathly_data/core/skills/start.md

## go.md — insert after state recovery, before routing

After the step that detects the active feature (reads STATE.json), add:

1. Call next_action(flow, topic, project_root).
2. Display Scenario 1 panel from CONTEXTUAL_MENU_UX.md (all 4 options).
3. On [1] or Enter: route to the flow skill (team/debug/explore) as before.
4. On [2]: call pause skill. Stop.
5. On [3]: print STATE.json + last 10 EVENTS.jsonl lines. Show panel again.
6. On [4]: print "Switch to: (1) team  (2) debug  (3) explore" and route.

## pause.md — insert before writing PAUSED

Before the "write status: PAUSED" step, add this read-only panel:

─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>      Conv : <N>
  Pausing session.
─────────────────────────────────────────────────────────

Read STATE.json directly for current_state and conv. Do NOT call next_action.
After printing: continue with existing PAUSED write and resume instructions.

## end.md — insert before retro prompt

Before the "Write a retro? (y/n)" step, add:

1. Call next_action(flow, topic, project_root).
2. Print read-only summary panel:

─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>      Conv : <N>
  <If any *.md file in feedback/:>
  ! Open feedback — resolve before archiving.
─────────────────────────────────────────────────────────
  Conversations completed: <N>
─────────────────────────────────────────────────────────

Then "Write a retro? (y/n)" as before.

## start.md — insert when user picks option [4]

When the user selects option [4] "Continue in-progress work":
1. Auto-detect active feature (same logic as team.md feature detection).
2. Call next_action(flow, topic, project_root).
3. Display Scenario 1 panel from CONTEXTUAL_MENU_UX.md (all 4 options).
4. Route based on user choice (same as go.md options above).

No changes to options [1], [2], [3], [5].

## Constraints

- Do not change any existing behavior — only insert the panel at the specified point.
- Do not create any new files.
- Do not touch any Python files or adapter YAML files.

## Verify

grep "next_action" src/pathly_data/core/skills/go.md
grep "Pausing session" src/pathly_data/core/skills/pause.md
grep "next_action" src/pathly_data/core/skills/end.md
grep "next_action" src/pathly_data/core/skills/start.md
```
