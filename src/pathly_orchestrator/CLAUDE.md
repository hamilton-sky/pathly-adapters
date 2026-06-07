# pathly_orchestrator - FSM Layer

Python package that implements the Pathly finite-state machine. Runs as both an MCP server (registered in `.claude/settings.json` as `pathly-fsm`) and an HTTP server on port **8765**.

## State machine

Features advance through: `STORM -> PLAN -> DESIGN -> BUILD -> REVIEW -> TEST -> RETRO -> DONE`

Each transition is driven by events written to the central SQLite DB (`~/.pathly/pathly.db`). The orchestrator reads `STATE.json` (filesystem snapshot) and queries the DB to determine the next action.

## HTTP endpoints

Use the packaged `pathly-fsm-call` helper as the canonical transport. It
encodes JSON safely on Windows and Unix shells and auto-starts the server if
needed.

```bash
pathly-fsm-call next-action \
  --flow "team" \
  --topic "<feature>" \
  --project-root "C:/Users/Yafit/pathly-adapters"

pathly-fsm-call complete-stage \
  --flow "team" \
  --topic "<feature>" \
  --project-root "C:/Users/Yafit/pathly-adapters"
```

If you need to debug the raw HTTP server, use a real JSON-capable client rather
than shell-escaped `curl` strings on PowerShell.

### Runner endpoints (Studio ↔ supervisor)

```
POST /runner/start                   ← Studio FlowControlBar: start a new pipeline run
POST /runner/pause                   ← pause running pipeline
POST /runner/resume                  ← resume paused pipeline
POST /runner/advance                 ← skip past current block
POST /runner/retry                   ← retry blocked stage
POST /runner/abort                   ← abort run completely
POST /runner/terminal/result         ← PTY exit callback: { run_id, topic, exit_code, stdout_tail, wall_seconds, user_initiated } — enriched with AGENT_DONE.summary from central DB; stdout used only for session_id + cost_usd
POST /runner/terminal/started        ← PTY started confirmation: { run_id, topic, tab_id }
GET  /events/runner?topic=<topic>    ← SSE stream of runner events for Studio
POST /shutdown                       ← graceful server shutdown (used by Electron on restart)
```

### SSE events (GET /events/runner)

| Event type | Payload fields | Purpose |
|---|---|---|
| `RUN_STARTED` | `topic`, `run_id` | pipeline run began |
| `RUN_COMPLETE` | `topic`, `run_id`, `status` | pipeline finished (done/aborted/error) |
| `TERMINAL_SPAWN` | `tab_id`, `run_id`, `label`, `cwd`, `argv[]`, `adapter` | Studio should open a new terminal tab and spawn the PTY |
| `TERMINAL_STARTED` | `tab_id`, `run_id` | PTY confirmed running |
| `SESSION` | `kind` (new/continue), `session_id` | adapter session continuity signal |
| `RUNNER_WARNING` | `message` | non-fatal warning to surface as a toast |
| `STATUS` | `status`, `stage`, `adapter`, `cost_usd`, `session_kind` | periodic state sync |

## `/next_action` response contract

Every `/next_action` response includes the following top-level fields:

| Field | Values | Notes |
|---|---|---|
| `current_state` | FSM stage string | e.g. `"BUILDING"` |
| `agent` | role name string | e.g. `"builder"` |
| `decision` | `"continue"` / `"block"` / `"escalate"` | automation gate - see below |
| `agent_hint.role` | `"worker"` or `"explorer"` | host-neutral delegation signal |
| `agent_hint.instructions` | string | full prompt for the next agent |
| `codex_subagent` | legacy object | **frozen** - present for backward compat only; new adapters must read `agent_hint` |

**`decision` field:**
- `continue` - adapter may automate the next step without human involvement
- `block` - an agent-resolvable feedback file is open; surface to the next Pathly agent via the standard feedback resolution flow
- `escalate` - human input is required (corrupt state, unknown feedback, or retry limit exceeded); do not automate

## FSM recovery

The `orchestrator` agent (haiku) can reconstruct state from the central DB event log if `STATE.json` is lost or corrupt. It is deterministic — same event log always produces the same state.

## Visible runner (supervisor.py)

`supervisor.py` drives the pipeline by polling `/next_action` and calling `/complete_stage`. Every agent invocation goes through a visible terminal — there is no headless fallback.

**Stage flow:**
1. `supervisor.py` calls `/next_action` → gets `agent_hint.instructions` (full prompt)
2. Builds `argv = ['claude', '-p', '<instructions>', '--model', ..., '--print', '--output-format=json', '--dangerously-skip-permissions']`
3. Emits `TERMINAL_SPAWN` SSE with `{ tab_id, run_id, argv, cwd, label, adapter }`
4. Studio opens a PTY tab (`node-pty`) and spawns the process via the `argv`
5. Studio POSTs `/runner/terminal/started` when PTY is up
6. PTY exits → `terminal.ts` POSTs `/runner/terminal/result` with exit code and stdout tail
7. `supervisor.py` receives the result, calls `/complete_stage`, advances to next stage

Same-adapter consecutive stages share a `session_id`. Cross-adapter transitions start a new session.

On Windows, the argv is passed to PowerShell via `-EncodedCommand` (base64 UTF-16LE) to handle arbitrary prompt content safely.

## CLI shortcuts

```bash
pathly-ff      # fast-forward current feature state one step
pathly-back    # roll back current feature state one step
pathly-status  # show all active features and their current FSM state
```

## Result split — stdout vs EVENTS.jsonl

When a PTY stage exits, the supervisor merges two sources:

| Source | Used for |
|---|---|
| `--output-format=json` stdout | `session_id` (session continuity) + `cost_usd` (API-accurate billing) |
| Central DB `AGENT_DONE.summary` | Semantic result text — what the agent did, outcome, key files |

The `summary` field is written by the agent via the `log-agent-done` skill to the central DB during its run.
It is never subject to the PTY's 500-chunk rolling output buffer.
If `summary` is absent (e.g. legacy agent), stdout `result` is used as a fallback.
