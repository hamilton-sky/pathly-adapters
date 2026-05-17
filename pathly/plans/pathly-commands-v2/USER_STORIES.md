# USER_STORIES.md — pathly-commands-v2

_Six new commands + deferred contextual menu for start/pause/end/go._

---

## S1 — `status`: cross-feature dashboard

**As a** developer with multiple active features and debugs,  
**I want** a single command that shows every active flow, its current state,
conv progress, and any blocking feedback files,  
**so that** I can orient in under 5 seconds without opening any file.

**Acceptance criteria:**
- Scans `pathly/plans/`, `pathly/debugs/`, `pathly/explorations/` (skips `.archive/`)
- For each active topic: shows flow name, state, conv count, blocking files
- BLOCKED label appears when any file exists in `feedback/`
- DONE topics are omitted unless `--all` flag passed
- Works with zero active topics (prints "Nothing in progress")

---

## S2 — `log`: readable event timeline

**As a** developer debugging why the FSM went to an unexpected state,  
**I want** a human-readable timeline of EVENTS.jsonl for a given topic,  
**so that** I can see every state transition, decide routing, and feedback event
without parsing raw JSON.

**Acceptance criteria:**
- Accepts optional topic argument; defaults to most recently active topic
- Renders each event as: `HH:MM:SS  EVENT_TYPE  detail`
- STATE_TRANSITION shows: `PLANNING → BUILDING`
- DECIDE_ROUTING shows: chosen state + decision_input
- Feedback events show file name and target agent
- Defaults to last 20 events; `--all` flag shows full history

---

## S3 — `fix`: shortcut for resolving blocking feedback

**As a** developer who is blocked by REVIEW_FAILURES or TEST_FAILURES,  
**I want** a single command that detects the blocking file, routes to the
correct agent, deletes the file after resolution, and calls `complete_stage`,  
**so that** I don't have to navigate the full menu or remember the protocol.

**Acceptance criteria:**
- Detects active topic and open feedback file automatically
- Routes to the agent named in `feedback_routing` for that file
- After agent resolves: deletes the feedback file from `feedback/`
- Calls `complete_stage` and shows the updated state panel
- If no feedback blocking: prints "No open feedback. Use /pathly go to continue."
- If HUMAN_QUESTIONS: prints contents and halts (does not auto-resolve human blocks)

---

## S4 — `ff`: fast-forward to next state (skip current agent)

**As a** developer who has done the current stage's work manually or wants
to advance the FSM without running an agent,  
**I want** a command that evaluates transition rules and advances state
without spawning the current stage's agent,  
**so that** I can keep FSM state in sync when I work outside the pipeline.

**Acceptance criteria:**
- Shows the transition that will happen (`PLANNING → BUILDING`) before executing
- Requires explicit confirmation (y/n) before writing STATE.json
- Calls `complete_stage` (which evaluates transition_rules and runs transition_actions)
- If the transition has `git_commit` in `transition_actions`: warn the user before
- If the FSM returns `{decide: true}`: surfaces the question and waits for answer
- If blocked by feedback: shows blocked panel, does not advance

---

## S5 — `back`: roll back one state

**As a** developer who advanced the FSM prematurely (e.g. called `ff` or
`complete_stage` too early),  
**I want** to roll STATE.json back to the previous state with confirmation,  
**so that** I can re-run the stage without the FSM thinking it is done.

**Acceptance criteria:**
- Reads EVENTS.jsonl to determine the prior state (last STATE_TRANSITION `from` field)
- Prints: "Roll back from BUILDING to PLANNING? (y/n)"
- On y: writes STATE.json with prior state, appends STATE_ROLLBACK event
- On n: aborts with no changes
- Does NOT undo git commits or other transition_actions — documents this clearly
- If no prior STATE_TRANSITION found: "No previous state to roll back to."

---

## S6 — `ask <role>`: mid-flow consultation without state change

**As a** developer mid-pipeline who wants a quick second opinion from a
specific role without interrupting the FSM,  
**I want** to spawn any named agent for a single focused question,  
**so that** I get expert input without creating feedback files or touching STATE.json.

**Acceptance criteria:**
- Syntax: `/pathly ask <role> <question>` — role is any key in `agent_map` or
  any of: architect, builder, planner, reviewer, tester, scout
- Spawns the named agent with only the question as context (no flow state injected)
- Does NOT write to STATE.json, feedback/, or any plan file
- Does NOT call `next_action` or `complete_stage`
- Agent responds inline; conversation ends after one reply
- If role name not recognised: lists valid roles and exits

---

## S7 — Contextual menu for start / pause / end / go (deferred from mcp-fsm-driver)

**As a** developer using any Pathly entry command,  
**I want** the same contextual state panel shown by team/debug/explore,  
**so that** every command shows me where I am and what happens next.

**Acceptance criteria:**
- `go`: after recovering state, shows panel before routing (same format as team.md)
- `pause`: shows read-only panel (state + conv count) then writes PAUSED — no options menu
- `end`: shows panel with conv count and asks retro y/n — no options [1–4]
- `start`: when option [4] (continue) chosen, shows full contextual panel for the
  recovered feature before routing
- All four read `CONTEXTUAL_MENU_UX.md` spec for border/format consistency
