# pathly_orchestrator — FSM Layer

Python package that implements the Pathly finite-state machine. Runs as both an MCP server (registered in `.claude/settings.json` as `pathly-fsm`) and an HTTP server on port **8765**.

## State machine

Features advance through: `STORM → PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE`

Each transition is driven by events written to `pathly/plans/<feature>/EVENTS.jsonl`. The orchestrator reads `STATE.json` and `EVENTS.jsonl` to determine the next action.

## HTTP endpoints

```bash
# Verify the server is alive before starting any pipeline
curl http://127.0.0.1:8765/health

# What should happen next for a feature?
curl -s -X POST http://127.0.0.1:8765/next_action \
  -H "Content-Type: application/json" \
  -d '{"flow":"team","topic":"<feature>","project_root":"C:/Users/Yafit/pathly-adapters"}'

# Mark the current stage complete and advance to the next
curl -s -X POST http://127.0.0.1:8765/complete_stage \
  -H "Content-Type: application/json" \
  -d '{"flow":"team","topic":"<feature>","project_root":"C:/Users/Yafit/pathly-adapters"}'
```

Always verify the FSM is running before starting a pipeline — use `Skill(pathly-fsm-call)` → health, or the curl above.

## `/next_action` response contract

Every `/next_action` response includes the following top-level fields:

| Field | Values | Notes |
|---|---|---|
| `current_state` | FSM stage string | e.g. `"BUILDING"` |
| `agent` | role name string | e.g. `"builder"` |
| `decision` | `"continue"` / `"block"` / `"escalate"` | automation gate — see below |
| `agent_hint.role` | `"worker"` or `"explorer"` | host-neutral delegation signal |
| `agent_hint.instructions` | string | full prompt for the next agent |
| `codex_subagent` | legacy object | **frozen** — present for backward compat only; new adapters must read `agent_hint` |

**`decision` field:**
- `continue` — adapter may automate the next step without human involvement
- `block` — an agent-resolvable feedback file is open; surface to the next Pathly agent via the standard feedback resolution flow
- `escalate` — human input is required (corrupt state, unknown feedback, or retry limit exceeded); do not automate

## FSM recovery

The `orchestrator` agent (haiku) can reconstruct state from `EVENTS.jsonl` if `STATE.json` is lost or corrupt. It is deterministic — same event log always produces the same state.

## CLI shortcuts

```bash
pathly-ff      # fast-forward current feature state one step
pathly-back    # roll back current feature state one step
pathly-status  # show all active features and their current FSM state
```
