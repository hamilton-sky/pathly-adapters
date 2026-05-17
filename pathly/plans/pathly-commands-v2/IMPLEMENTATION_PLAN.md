# IMPLEMENTATION_PLAN.md — pathly-commands-v2

_Rigor: standard — 4 conversations._

**Prerequisite:** `mcp-fsm-driver` plan must be complete. Verify:
```bash
python -c "from pathly_orchestrator.mcp_server import next_action, complete_stage; print('OK')"
grep "pathly-fsm" src/install_cli/mcp_config.py
grep "next_action\|complete_stage" src/pathly_data/core/skills/team.md
```
All three must succeed before starting Conv 1.

**Menu spec:** Every skill in this plan that displays state must read
`pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md` for the exact panel
format before writing any output strings.

---

## Conversation 1 — `status` + `log`

**Stories:** S1, S2

**Scope:** Two new read-only skills. No state mutation. No MCP tool calls.
Pure file reads rendered as formatted output.

**Natural seam:** After this conversation users can orient and audit without
opening any file. Zero risk — no writes anywhere.

### Files to create

| File | Change |
|------|--------|
| `src/pathly_data/core/skills/status.md` | Cross-feature dashboard |
| `src/pathly_data/core/skills/log.md` | Readable event timeline |
| `src/pathly_data/adapters/claude/_meta/status_skill.yaml` | Claude adapter |
| `src/pathly_data/adapters/claude/_meta/log_skill.yaml` | Claude adapter |
| `src/pathly_data/adapters/codex/_meta/status_skill.yaml` | Codex adapter |
| `src/pathly_data/adapters/codex/_meta/log_skill.yaml` | Codex adapter |

### `status.md` — what to implement

```
Scan for STATE.json files in:
  pathly/plans/*/STATE.json
  pathly/debugs/*/STATE.json
  pathly/explorations/*/STATE.json
(skip any path containing .archive/)

For each found file, read it and also read feedback/ dir if it exists.

Print:

─────────────────────────────────────────────────────────
  Pathly · Active features
─────────────────────────────────────────────────────────
  <topic>   ·  <flow>  ·  <state>  (conv <N>)
  <topic>   ·  <flow>  ·  <state>  [BLOCKED: <file>]
  <topic>   ·  <flow>  ·  DONE ✓
─────────────────────────────────────────────────────────

Rules:
- DONE features are shown with ✓ and listed last
- BLOCKED appears when any *.md file exists in feedback/ — show the filename
- If multiple feedback files: show the highest-priority one (same order as
  flow feedback_routing) + "(+N more)" if there are others
- If nothing found: print "Nothing in progress."
- If $ARGUMENTS contains "--all": include DONE and archived topics
```

### `log.md` — what to implement

```
Parse $ARGUMENTS:
  First non-keyword word = TOPIC (optional)
  "--all" flag = show full history (default: last 20 events)

If TOPIC not given: scan pathly/plans/ pathly/debugs/ pathly/explorations/
  for the most recently modified STATE.json (skip .archive/).
  Use that topic and its storage_path.

Locate EVENTS.jsonl in storage_path. If absent: "No events recorded for <topic>."

Read lines. Apply --all or tail-20 limit. For each event, render:

  HH:MM:SS  STATE_TRANSITION     PLANNING → BUILDING
  HH:MM:SS  DECIDE_ROUTING       chosen: ARCH_REVIEW  (input: "architecture")
  HH:MM:SS  STATE_ROLLBACK       BUILDING → PLANNING
  HH:MM:SS  FEEDBACK_RESOLVED    REVIEW_FAILURES.md  agent: builder
  HH:MM:SS  NEEDS_CONTEXT        count: 2 / 3
  HH:MM:SS  <other>              raw JSON fields

Print header:
  ─────────────────────────────────────
  Pathly log · <topic> · <flow>
  ─────────────────────────────────────
  [events]
  ─────────────────────────────────────
  Showing last N events. Use --all for full history.
```

### Adapter YAML shape (apply to all four YAML files)

Follow the exact pattern of existing `_meta/*.yaml` files in each adapter dir.
Set `natural_language` / description to match the story acceptance criteria summary.
Do not add MCP syntax — these skills read files directly.

### Verify after Conv 1

```bash
grep "feedback/" src/pathly_data/core/skills/status.md
grep "EVENTS.jsonl" src/pathly_data/core/skills/log.md
grep "status_skill\|log_skill" src/pathly_data/adapters/claude/_meta/status_skill.yaml
```

---

## Conversation 2 — `fix` + `ff`

**Stories:** S3, S4

**Scope:** Two action shortcuts that call MCP tools (`complete_stage`). Both
require the mcp-fsm-driver MCP server to be installed.

**Natural seam:** After this conversation the two most common single-step
operations have dedicated entry points. The FSM and feedback protocols are
unchanged — these are thin wrappers over existing tools.

### Files to create

| File | Change |
|------|--------|
| `src/pathly_data/core/skills/fix.md` | Feedback resolver shortcut |
| `src/pathly_data/core/skills/ff.md` | Fast-forward shortcut |
| `src/pathly_data/adapters/claude/_meta/fix_skill.yaml` | Claude adapter |
| `src/pathly_data/adapters/claude/_meta/ff_skill.yaml` | Claude adapter |
| `src/pathly_data/adapters/codex/_meta/fix_skill.yaml` | Codex adapter |
| `src/pathly_data/adapters/codex/_meta/ff_skill.yaml` | Codex adapter |

### `fix.md` — what to implement

```
1. Resolve TOPIC from $ARGUMENTS or auto-detect (same logic as team.md).
2. Call next_action(flow, topic, project_root).
   - If not blocked: print "No open feedback. Use /pathly go to continue." Exit.
   - If blocked, target_agent == "human": print file contents. Print:
       "This is a human decision — resolve manually then delete the file."
     Exit (do not run any agent).
   - If blocked, target_agent == <agent>:
       Show the blocked panel from CONTEXTUAL_MENU_UX.md (Scenario 2 format).
       Options:
         [1] Resolve  — run <agent> on the feedback file now
         [2] View     — print feedback file contents
         [3] Escalate — write HUMAN_QUESTIONS.md and halt
         [4] Abort    — exit without changes

3. On [1] Resolve:
   a. Follow instructions returned in next_action for <agent>.
   b. After agent completes: delete the feedback file from feedback/.
      Print: "Deleted: feedback/<filename>"
   c. Call complete_stage(flow, topic, project_root).
      Show the resulting state panel (CONTEXTUAL_MENU_UX.md format).
      If complete_stage returns blocked again: show blocked panel again (loop).
      If complete_stage returns {decide: true}: surface question, wait for answer,
        call complete_stage again with decision=<answer>.
      If done=true: print "Feature complete."
```

### `ff.md` — what to implement

```
1. Resolve TOPIC from $ARGUMENTS or auto-detect.
2. Call next_action(flow, topic, project_root).
   - If blocked: show blocked panel. Print:
       "Cannot fast-forward — open feedback must be resolved first. Use /pathly fix."
     Exit.
3. Show the transition that would happen:
   "Fast-forward: <current_state> → <next evaluated state>
    Note: transition_actions for this transition will run (may include git commit).
    Proceed? (y/n)"
   Wait for reply. On n: exit.

4. On y: call complete_stage(flow, topic, project_root).
   - If {decide: true}: surface question, wait for answer,
     call complete_stage again with decision=<answer>.
   - Show the resulting state panel.
   - If done=true: print "Feature complete."

The current stage's agent does NOT run. ff advances state only.
```

### Verify after Conv 2

```bash
grep "complete_stage" src/pathly_data/core/skills/fix.md
grep "complete_stage" src/pathly_data/core/skills/ff.md
grep "HUMAN_QUESTIONS" src/pathly_data/core/skills/fix.md
```

---

## Conversation 3 — `back` + `ask`

**Stories:** S5, S6

**Scope:** `back` mutates STATE.json directly (no MCP tool for rollback — it
reads EVENTS.jsonl and writes STATE.json). `ask` spawns an agent without
touching any FSM state. Both are safe: `back` requires confirmation, `ask`
is read-only from the FSM's perspective.

**Natural seam:** After this conversation the full command set is implemented.
No Python changes — both are skill files only.

### Files to create

| File | Change |
|------|--------|
| `src/pathly_data/core/skills/back.md` | One-state rollback |
| `src/pathly_data/core/skills/ask.md` | Mid-flow role consultation |
| `src/pathly_data/adapters/claude/_meta/back_skill.yaml` | Claude adapter |
| `src/pathly_data/adapters/claude/_meta/ask_skill.yaml` | Claude adapter |
| `src/pathly_data/adapters/codex/_meta/back_skill.yaml` | Codex adapter |
| `src/pathly_data/adapters/codex/_meta/ask_skill.yaml` | Codex adapter |

### `back.md` — what to implement

```
1. Resolve TOPIC from $ARGUMENTS or auto-detect.
2. Resolve storage_path from flow YAML (same logic as MCP server).
3. Read EVENTS.jsonl. Find the most recent STATE_TRANSITION event.
   Extract its "from" field = prior_state.
   If no STATE_TRANSITION found: print "No previous state to roll back to." Exit.
4. Read STATE.json. Extract current state.

5. Print confirmation:
   "Roll back <topic>: <current_state> → <prior_state>
    Note: git commits and other transition_actions are NOT undone.
    Proceed? (y/n)"
   Wait for reply. On n: exit.

6. On y:
   a. Write STATE.json: set "current" = prior_state, preserve all other fields,
      update "updated_at".
   b. Append to EVENTS.jsonl:
      {"type": "STATE_ROLLBACK", "from": current_state, "to": prior_state}
   c. Print the contextual state panel for prior_state
      (CONTEXTUAL_MENU_UX.md format, options [1–4]).

IMPORTANT: back.md writes STATE.json directly — it does NOT call complete_stage.
This is the only skill permitted to write STATE.json without going through the
MCP server. Document this clearly with a comment in the skill file.
```

### `ask.md` — what to implement

```
Parse $ARGUMENTS:
  First word = ROLE
  Remainder = QUESTION

Valid roles: any value in the agent_map of the active flow, plus:
  architect, builder, planner, reviewer, tester, scout, explorer

If ROLE not recognised: print list of valid roles. Exit.
If QUESTION is blank: ask "What is your question for <role>?"

Spawn <role> agent with exactly:
  "Answer this question as <role>. One focused reply only.
   Do not write any files. Do not read STATE.json or feedback/.
   Question: <QUESTION>"

After agent replies: exit. Do not call next_action or complete_stage.
Do not write anything to the storage_path.
```

### Verify after Conv 3

```bash
grep "STATE_ROLLBACK" src/pathly_data/core/skills/back.md
grep "complete_stage\|next_action" src/pathly_data/core/skills/ask.md  # must return nothing
grep "Do not write" src/pathly_data/core/skills/ask.md
```

---

## Conversation 4 — Update start / pause / end / go with contextual menu

**Stories:** S7

**Scope:** Deferred from mcp-fsm-driver Conv 3. Add the contextual state panel
to the four entry-point skills, each in a simplified form appropriate to its
role. No new files — edits only.

**Natural seam:** After this conversation every Pathly command shows consistent
state information. The full command suite is visually coherent.

### Files to edit

| File | Change |
|------|--------|
| `src/pathly_data/core/skills/go.md` | Show panel after state recovery, before routing |
| `src/pathly_data/core/skills/pause.md` | Show read-only panel before writing PAUSED |
| `src/pathly_data/core/skills/end.md` | Show panel with conv count before retro prompt |
| `src/pathly_data/core/skills/start.md` | Show panel when user picks "continue" (option 4) |

**Before editing any file:** read `pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md`
in full. Use Scenario 1 as the reference format for all four skills.

### `go.md` change

After recovering state (reading STATE.json), before routing to the flow skill:
- Call `next_action(flow, topic, project_root)` to get current state + agent.
- Display full contextual panel (all 4 options including Proceed/Pause/Status/Switch).
- On [1] Proceed: route to the appropriate flow skill (team/debug/explore).
- On [2] Pause: call pause skill.
- On [3] Status: print STATE.json + last 10 events, show panel again.
- On [4] Switch: show flow options.

### `pause.md` change

After finding the in-progress feature and before writing PAUSED:
- Display a read-only version of the panel (state + conv count, no options menu).
- Then write `status: PAUSED` and print the resume instructions.

Read-only panel format:
```
─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <state>      Conv : <N>
  Pausing session.
─────────────────────────────────────────────────────────
  Resume with: /pathly go
─────────────────────────────────────────────────────────
```

### `end.md` change

Before the retro prompt:
- Call `next_action` to get current state.
- Display a read-only summary panel (state, conv count, any open feedback).
- Then ask "Write a retro? (y/n)".

If open feedback exists, add a warning line:
```
  ! Open feedback files exist — resolve before archiving.
```

### `start.md` change

When user picks option [4] "Continue in-progress work":
- Auto-detect the active feature (same logic as team.md feature detection).
- Call `next_action(flow, topic, project_root)`.
- Display full contextual panel (4 options).
- Then route based on user choice.

### Verify after Conv 4

```bash
grep "next_action\|contextual\|State :" src/pathly_data/core/skills/go.md
grep "Pausing session" src/pathly_data/core/skills/pause.md
grep "next_action" src/pathly_data/core/skills/end.md
grep "next_action" src/pathly_data/core/skills/start.md
```

---

## Overall verify (after all four conversations)

```bash
grep "feedback/" src/pathly_data/core/skills/status.md
grep "EVENTS.jsonl" src/pathly_data/core/skills/log.md
grep "complete_stage" src/pathly_data/core/skills/fix.md
grep "complete_stage" src/pathly_data/core/skills/ff.md
grep "STATE_ROLLBACK" src/pathly_data/core/skills/back.md
grep "Do not write" src/pathly_data/core/skills/ask.md
grep "next_action" src/pathly_data/core/skills/go.md
grep "Pausing session" src/pathly_data/core/skills/pause.md
```

All must return at least one match.
