# USER_STORIES.md — pathly-commands-v2

_Five new commands (4 Python CLI + 1 LLM skill) + meet enhancement + deferred
contextual menu for start/pause/end/go._

---

## Implementation pattern

**Python CLI + thin skill wrapper** — commands that need no LLM reasoning are
implemented as Python scripts (`pathly-<name>`) and exposed in conversations via
a two-line skill wrapper that calls them via the Bash tool. Works on all surfaces:
Claude Code CLI, Desktop App, VS Code Extension, Codex.

**LLM skill only** — commands that spawn agents or make judgment calls stay as
full `.md` skill files (no Python backing).

---

## S1 — `status`: cross-feature dashboard

**As a** developer with multiple active features and debugs,  
**I want** a single command that shows every active flow, its current state,
conv progress, and any blocking feedback files,  
**so that** I can orient in under 5 seconds without opening any file.

**Implementation:** Python CLI (`pathly-status`) + thin skill wrapper.

**Acceptance criteria:**
- Scans `pathly/plans/`, `pathly/debugs/`, `pathly/explorations/` (skips `.archive/`)
- For each active topic: flow name, state, conv count, blocking feedback file
- BLOCKED label when any file exists in `feedback/` — shows highest-priority filename
- DONE topics omitted unless `--all` flag passed
- Works with zero active topics ("Nothing in progress.")

---

## S2 — `log`: readable event timeline

**As a** developer debugging why the FSM went to an unexpected state,  
**I want** a human-readable timeline of EVENTS.jsonl for a given topic,  
**so that** I can see every state transition, decide routing, and feedback event
without parsing raw JSON.

**Implementation:** Python CLI (`pathly-log`) + thin skill wrapper.

**Acceptance criteria:**
- Optional topic argument; defaults to most recently active topic
- Renders each event: `HH:MM:SS  EVENT_TYPE  detail`
- STATE_TRANSITION: `PLANNING → BUILDING`
- DECIDE_ROUTING: chosen state + decision_input
- Defaults to last 20 events; `--all` shows full history

---

## S3 — `fix`: shortcut for resolving blocking feedback

**As a** developer blocked by REVIEW_FAILURES or TEST_FAILURES,  
**I want** a single command that detects the blocking file, routes to the
correct agent, deletes the file after resolution, and calls `complete_stage`,  
**so that** I skip the full menu navigation.

**Implementation:** LLM skill only (spawns an agent — cannot be Python CLI).

**Acceptance criteria:**
- Detects active topic and open feedback file automatically
- Routes to the agent named in `feedback_routing` for that file
- After agent resolves: deletes the feedback file from `feedback/`
- Calls `complete_stage` and shows updated state panel
- If no feedback blocking: "No open feedback. Use /pathly go to continue."
- If HUMAN_QUESTIONS: prints contents and halts (does not auto-resolve)

---

## S4 — `ff`: fast-forward to next state

**As a** developer who has done the current stage's work manually or wants
to advance the FSM without running the current agent,  
**I want** a command that evaluates transition rules and advances state,  
**so that** I can keep FSM state in sync when I work outside the pipeline.

**Implementation:** Python CLI (`pathly-ff`) + thin skill wrapper.  
Python calls `complete_stage` via the HTTP server's Python API directly.
If `{decide: true}` is returned: Python prompts for input via `input()` — no LLM needed.

**Acceptance criteria:**
- Shows the transition before executing (`PLANNING → BUILDING`)
- If transition has `git_commit` in `transition_actions`: warns before proceeding
- Requires `y/n` confirmation via `input()` before writing STATE.json
- If `{decide: true}` returned: prints question + options, waits for typed key
- If blocked by feedback: prints blocked state, exits ("Use pathly-fix")
- If `done`: prints "Feature complete."

---

## S5 — `back`: roll back one state

**As a** developer who advanced the FSM prematurely,  
**I want** to roll STATE.json back to the previous state with confirmation,  
**so that** I can re-run the stage without the FSM thinking it is done.

**Implementation:** Python CLI (`pathly-back`) + thin skill wrapper.

**Acceptance criteria:**
- Reads EVENTS.jsonl to find prior state (last STATE_TRANSITION `from` field)
- Prints: "Roll back `<topic>`: `<current>` → `<prior>` ? (y/n)"
- On y: writes STATE.json atomically, appends STATE_ROLLBACK to EVENTS.jsonl
- Does NOT undo git commits or transition_actions — states this explicitly
- If no prior STATE_TRANSITION: "No previous state to roll back to."

---

## S6 — `meet` enhancement: escalate consultation to pipeline

**As a** developer who just got consultation advice that is important enough
to block the pipeline,  
**I want** a new option in `meet` Step 5 that writes the consultation result
into `feedback/` as a blocking file,  
**so that** the FSM picks it up on the next `complete_stage` call and routes
it to the right agent automatically.

**Implementation:** Edit `src/pathly_data/core/skills/meet.md` Step 5 only.

**Acceptance criteria:**
- Step 5 gains option `[5] Escalate to pipeline`
- When chosen: asks which feedback type fits the consultation:
  `ARCH_FEEDBACK / DESIGN_QUESTIONS / IMPL_QUESTIONS`
- Writes consult note content into `feedback/<chosen_type>.md`
- Prints: "Pipeline blocked on `<filename>` — next `complete_stage` will route
  to `<agent>`" (agent resolved from flow YAML `feedback_routing`)
- Already-written `consults/` file is preserved — escalation is additive
- If feedback file already exists: appends with a separator, does not overwrite

---

## S7 — Contextual menu for start / pause / end / go

**As a** developer using any Pathly entry command,  
**I want** the contextual state panel shown by team/debug/explore,  
**so that** every command shows me where I am and what happens next.

**Implementation:** Edit four existing LLM skill files.

**Acceptance criteria:**
- `go`: full panel (4 options) after state recovery, before routing
- `pause`: read-only panel (state + conv count) before writing PAUSED
- `end`: read-only summary panel (state, conv count, open feedback warning)
- `start` option [4]: full panel after auto-detecting active feature
- All four match `CONTEXTUAL_MENU_UX.md` border/format spec
