# mcp-fsm-driver — Architecture Proposal

## Current state

The LLM orchestrator agent reads `team.flow.yaml` (or debug/explore) as a
prompt, then decides at each step what the next state is, which agent to spawn,
and whether to run transition_actions. All routing decisions are made by the LLM.

```
/pathly team checkout-feature
        │
        ▼
  Skill spawns: Agent(subagent_type="orchestrator", flow_config="team.flow.yaml", topic="checkout-feature")
        │
        ▼
  LLM orchestrator:
    reads flow YAML as prompt text
    reads STATE.json
    decides: current state = PLANNING
    decides: spawn planner
    planner returns
    LLM decides: evaluate transition_rules
    LLM decides: next state = BUILDING
    LLM writes STATE.json
    LLM decides: run transition_actions (commit)
    LLM spawns builder
    ...continues until DONE
```

**Problem:** Every routing decision passes through an LLM. The LLM can misread
STATE.json, skip a feedback file, hallucinate a state name, or forget to run a
transition action. The flow YAML is a hint, not an executable spec.

---

## Target state

A Python MCP server reads the flow YAML and drives the FSM. The LLM only
executes domain work (implement, review, test, plan). All routing is Python.

```
/pathly team checkout-feature
        │
        ▼
  Skill calls: mcp__pathly-fsm__next_action(flow="team", topic="checkout-feature")
        │
        ▼
  Python MCP server (pathly_orchestrator.mcp_server):
    load_flow("team.flow.yaml")           ← importlib.resources, not path
    recover_state(storage_path, flow)     ← reads STATE.json + EVENTS.jsonl
    route_feedback(flow, storage_path)    ← reads feedback/ dir
    → returns: {agent: "planner", instructions: "..."}
        │
        ▼
  LLM acts as planner, writes IMPLEMENTATION_PLAN.md
        │
        ▼
  LLM calls: mcp__pathly-fsm__complete_stage(flow="team", topic="checkout-feature")
        │
        ▼
  Python MCP server:
    route_feedback() → None (no open files)
    evaluate_transition_rules("PLANNING", storage_path) → "BUILDING"
    write_state(storage_path, "BUILDING")
    append_event(storage_path, STATE_TRANSITION)
    run_transition_actions("PLANNING", "BUILDING", ...)  ← no actions for this transition
    → returns: {agent: "builder", instructions: "..."}
        │
        ▼
  LLM acts as builder, writes code
        │
        ▼
  LLM calls: complete_stage(...)
  Python: next = REVIEWING; run commit; → {agent: "reviewer", ...}
        │
        ▼
  ...continues until done=true
```

---

## Module design

### `src/pathly_orchestrator/fsm.py` — FSM core (pure Python, no LLM)

Four functions, no side effects beyond filesystem writes:

```python
def recover_state(storage_path: Path, flow: dict) -> dict:
    """Read STATE.json + EVENTS.jsonl. Return {current_state, conv, open_feedback_files}."""

def evaluate_transition_rules(flow: dict, current_state: str, storage_path: Path) -> str:
    """Check on_artifact entries for current_state. Return next state name."""

def route_feedback(flow: dict, storage_path: Path) -> dict | None:
    """Read feedback/ dir. Return {file, target_agent} or None."""

def run_transition_actions(flow: dict, prev: str, next_: str,
                           storage_path: Path, topic: str, conv: int) -> None:
    """Execute transition_actions[prev->next] in YAML order."""
```

Priority for `route_feedback` follows `protocol_contract.yaml`:
`HUMAN_QUESTIONS` > `ARCH_FEEDBACK` > `DESIGN_QUESTIONS` >
`IMPL_QUESTIONS` > `REVIEW_FAILURES` > `TEST_FAILURES`

### `src/pathly_orchestrator/mcp_server.py` — MCP server

Two tools exposed to LLM clients:

```python
@mcp_tool
def next_action(flow: str, topic: str, project_root: str) -> dict:
    fsm_data = load_flow(flow)                     # importlib.resources
    storage_path = Path(project_root) / fsm_data["storage_path"].format(topic=topic)
    state = recover_state(storage_path, fsm_data)
    feedback = route_feedback(fsm_data, storage_path)
    if feedback:
        return {"blocked": True, "target_agent": feedback["target_agent"],
                "instructions": build_prompt(fsm_data, feedback["target_agent"], storage_path)}
    return {"current_state": state["current_state"],
            "agent": fsm_data["agent_map"][state["current_state"]],
            "instructions": build_prompt(fsm_data, state["current_state"], storage_path),
            "storage_path": str(storage_path)}

@mcp_tool
def complete_stage(flow: str, topic: str, project_root: str) -> dict:
    fsm_data = load_flow(flow)
    storage_path = Path(project_root) / fsm_data["storage_path"].format(topic=topic)
    state = recover_state(storage_path, fsm_data)
    feedback = route_feedback(fsm_data, storage_path)
    if feedback:
        return {"blocked": True, "target_agent": feedback["target_agent"],
                "instructions": build_prompt(fsm_data, feedback["target_agent"], storage_path)}
    next_state = evaluate_transition_rules(fsm_data, state["current_state"], storage_path)
    write_state(storage_path, next_state, state)
    append_event(storage_path, {"type": "STATE_TRANSITION", "to": next_state})
    run_transition_actions(fsm_data, state["current_state"], next_state,
                           storage_path, topic, state["conv"])
    if next_state == "DONE":
        return {"done": True}
    return {"next_state": next_state,
            "agent": fsm_data["agent_map"][next_state],
            "instructions": build_prompt(fsm_data, next_state, storage_path)}
```

### `src/install_cli/mcp_config.py` — registration

`pathly-fsm` is added alongside the existing `pathly-telemetry` entry using the
identical registration pattern:

```python
_PATHLY_FSM_CLAUDE: dict = {
    "command": "python",
    "args": ["-m", "pathly_orchestrator.mcp_server"],
}

_PATHLY_FSM_CODEX_BLOCK = (
    "\n[mcp_servers.pathly-fsm]\n"
    'command = "python"\n'
    'args = ["-m", "pathly_orchestrator.mcp_server"]\n'
)
```

---

## What disappears

| Before | After |
|--------|-------|
| `Agent(subagent_type="orchestrator", ...)` in skill files | `mcp__pathly-fsm__next_action(...)` + `complete_stage(...)` |
| LLM orchestrator decides transitions | Python `evaluate_transition_rules()` decides |
| LLM orchestrator runs commit + archive | Python `run_transition_actions()` runs |
| LLM reads STATE.json | Python `recover_state()` reads |
| LLM checks feedback/ dir | Python `route_feedback()` checks |

The orchestrator agent (`orchestrator.md`, `orchestrator.yaml`) is retained as
documentation and fallback, not as the active runtime path.

---

## Cross-host compatibility

Both Claude Code and Codex support MCP natively. `mcp_config.py` registers the
same server for both hosts using their native config formats. The MCP tool call
syntax differs per host but the server is identical:

| Host | Tool call syntax | Config location |
|------|-----------------|-----------------|
| Claude Code | `mcp__pathly-fsm__next_action(...)` | `~/.claude/settings.json` mcpServers |
| Codex | `mcp__pathly-fsm__next_action(...)` | `~/.codex/config.toml` mcp_servers |

One Python server. Both hosts. Registered once via `pathly-setup --apply`.

---

## Design decisions

- **`importlib.resources` for flow YAML loading** — same rule as all other
  `pathly_data` assets. Allows the server to work from an installed wheel, not
  just from the source checkout.
- **No file watcher** — the LLM explicitly calls `complete_stage` to signal it
  is done. Pull-based. No async event loop; no race conditions.
- **Orchestrator agent kept as fallback** — if the MCP server is unavailable,
  the orchestrator agent can still be spawned manually. It is not removed.
- **`fsm.py` has no MCP dependency** — pure functions, importable in tests
  without starting an MCP server.
- **`build_prompt` loads the full agent contract** — reads `core/agents/<agent>.md`
  via `importlib.resources` and appends a minimal context block (feature name,
  state, storage path). The LLM receives the complete role spec without the skill
  file having to load or pass agent content separately.
- **`project_root` is explicit, never inferred** — both tools require `project_root`
  as a parameter. The skill file passes it; the server never calls `Path.cwd()`.
  All git subprocess calls pass `cwd=project_root`.
