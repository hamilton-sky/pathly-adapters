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

## Target state — dual engine, user picks at start

Both engines coexist on master. The user picks at start time; the choice is
stored in `STATE.json` as `"engine": "python-mcp"` or `"engine": "llm"`.
The LLM-driven path (orchestrator.md) is never touched by this plan.

```
/pathly team checkout-feature

  ┌─ Start menu ────────────────────────────────┐
  │  Routing engine:                            │
  │  [1] Python FSM  — deterministic, MCP       │
  │  [2] LLM driven  — orchestrator reads YAML  │
  └─────────────────────────────────────────────┘
  User picks [1] → STATE.json: { engine: "python-mcp" }
  User picks [2] → STATE.json: { engine: "llm" }
            │
            ▼
  go.md / team.md reads engine from STATE.json
            │
     ┌──────┴──────────┐
  engine=llm        engine=python-mcp
     │                  │
     ▼                  ▼
  spawn              call MCP tool
  orchestrator.md    next_action(...)
  (unchanged)        (new Python server)
```

When `engine = "python-mcp"`: a Python MCP server reads the flow YAML and
drives the FSM. The LLM only executes domain work (implement, review, test,
plan). All routing is Python.

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

Six functions, no side effects beyond filesystem writes:

```python
def recover_state(storage_path: Path, flow: dict) -> dict:
    """Read STATE.json + EVENTS.jsonl. Return {current_state, conv, open_feedback_files, limits}.
    limits resolved from: flow["states"][current_state]["limits"]
                       → flow["limits"]
                       → defaults {needs_context_per_stage: 3, feedback_rounds_per_stage: 2}
    Per-state keys override top-level keys individually."""

def evaluate_transition_rules(
    flow: dict, current_state: str, storage_path: Path
) -> str | dict:
    """
    Evaluate transition rules for current_state in three levels, in order:

    Level 1 — on_artifact: check Path.exists() for each mapped file.
              First match wins. Pure Python, no LLM.
    Level 2 — on_content: read file, apply regex/contains check.
              First match wins. Pure Python, no LLM.
    Level 3 — decide: return a dict sentinel so the caller (mcp_server.py)
              can make a constrained LLM classifier call.
              Returns: {"decide": True, "context_file": str,
                        "question": str, "options": dict[str, str],
                        "default": str}
              fsm.py never calls the LLM — mcp_server.py handles it.

    If no rule matches: return flow["transitions"][current_state][0] (default).
    If transitions also absent: raise ValueError.
    """

def route_feedback(flow: dict, storage_path: Path) -> dict | None:
    """Read feedback/ dir. Return {file, target_agent} or None."""

def run_transition_actions(flow: dict, prev: str, next_: str,
                           storage_path: Path, topic: str, conv: int) -> None:
    """Execute transition_actions[prev->next] in YAML order."""

def write_state(storage_path: Path, next_state: str, prior_state: dict) -> None:
    """Write STATE.json with updated current field, preserving conv and other fields."""

def append_event(storage_path: Path, event: dict) -> None:
    """Append a JSON line to EVENTS.jsonl, adding an ISO-8601 timestamp field."""
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
        # HUMAN_QUESTIONS: target_agent == "human", instructions = raw file contents (no build_prompt)
        # All other feedback: build_prompt using agent name directly, not as agent_map key
        instructions = (feedback["instructions"] if feedback["target_agent"] == "human"
                        else build_prompt_for_agent(fsm_data, feedback["target_agent"], storage_path))
        return {"blocked": True, "target_agent": feedback["target_agent"],
                "instructions": instructions}
    return {"current_state": state["current_state"],
            "agent": fsm_data["agent_map"][state["current_state"]],
            "instructions": build_prompt(fsm_data, state["current_state"], storage_path),
            "storage_path": str(storage_path),
            "limits": state["limits"]}

@mcp_tool
def complete_stage(flow: str, topic: str, project_root: str) -> dict:
    fsm_data = load_flow(flow)
    storage_path = Path(project_root) / fsm_data["storage_path"].format(topic=topic)
    state = recover_state(storage_path, fsm_data)
    feedback = route_feedback(fsm_data, storage_path)
    if feedback:
        instructions = (feedback["instructions"] if feedback["target_agent"] == "human"
                        else build_prompt_for_agent(fsm_data, feedback["target_agent"], storage_path))
        return {"blocked": True, "target_agent": feedback["target_agent"],
                "instructions": instructions}
    routing = evaluate_transition_rules(fsm_data, state["current_state"], storage_path)
    if isinstance(routing, dict) and routing.get("decide"):
        # Level 3: constrained LLM classifier call
        next_state = resolve_decide(routing, storage_path)
        append_event(storage_path, {"type": "DECIDE_ROUTING",
                                    "chosen": next_state, "options": routing["options"]})
    else:
        next_state = routing
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

### `resolve_decide` — Level 3 routing via the calling LLM

No external API. No Anthropic SDK. The same LLM that is already running the
skill (Claude Code or Codex) makes the Level 3 decision.

`complete_stage` uses a **two-call protocol**:

**Call 1** — `complete_stage(flow, topic, project_root)`:  
When `evaluate_transition_rules` returns a `{"decide": True, ...}` sentinel,
`mcp_server.py` reads the `context_file` and returns immediately:
```json
{
  "decide": true,
  "question": "What type of fix does this review require?",
  "context": "<contents of REVIEW_FAILURES.md>",
  "options": {"refactor": "REFACTOR_STAGE", "architecture": "ARCH_REVIEW", "minor": "BUILDING"},
  "default": "BUILDING"
}
```
No STATE.json write. No transition actions. Just the question + context.

**Call 2** — `complete_stage(flow, topic, project_root, decision="refactor")`:  
The calling LLM chose "refactor". Python validates it's a key in `options`,
maps it to `next_state = "REFACTOR_STAGE"`, then continues normally:
write STATE.json, append event, run transition_actions, return next agent.

**Why this design:**
- The calling LLM (Claude/Codex) is already context-rich — it has just finished
  the current stage and has full access to the context file.
- No credentials needed in the MCP server at runtime.
- No external network call on the critical path.
- The decision is audited in EVENTS.jsonl as `DECIDE_ROUTING` regardless.
- Invalid or missing decision → silent fallback to `default`.

**`fsm.py` stays LLM-free:** `evaluate_transition_rules` still returns the
`{"decide": True, ...}` sentinel. All two-call coordination is in `mcp_server.py`
only. `fsm.py` has no SDK dependency.

### YAML shape — all three routing levels together

```yaml
transition_rules:
  REVIEWING:

    # Level 1 — artifact existence (pure Python, Path.exists)
    on_artifact:
      - file: REVIEW_FAILURES.md
        next: BUILDING

    # Level 2 — content pattern (pure Python, regex/contains)
    on_content:
      - file: REVIEW_FAILURES.md
        contains: "CRITICAL"
        next: SECURITY_REVIEW

    # Level 3 — semantic classify (constrained LLM, 2–3 options)
    decide:
      context_file: REVIEW_FAILURES.md
      question: "What type of fix does this review require?"
      options:
        refactor:     REFACTOR_STAGE
        architecture: ARCH_REVIEW
        minor:        BUILDING
      default: BUILDING       # used if LLM fails or returns invalid key

    # fallback if nothing matched at any level
    default: TESTING

# Evaluation order — Python tries each level in sequence, stops at first match:
# L1 on_artifact → L2 on_content → L3 decide → default
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
- **Orchestrator agent retained as part of the LLM flow** — `orchestrator.md`
  and `orchestrator.yaml` are kept and updated in Conv 3 alongside the skill
  rewrites. It is NOT wired as a "MCP unavailable" fallback: skills assume the
  MCP server is available and do not probe for it. If the server is down,
  `pathly-setup --apply` is the recovery path. The orchestrator's role is LLM
  flow execution, not MCP fault tolerance.
- **`fsm.py` has no MCP dependency** — pure functions, importable in tests
  without starting an MCP server.
- **`build_prompt` loads the full agent contract** — reads `core/agents/<agent>.md`
  via `importlib.resources` and appends a minimal context block (feature name,
  state, storage path). The LLM receives the complete role spec without the skill
  file having to load or pass agent content separately.
- **`project_root` is explicit, never inferred** — both tools require `project_root`
  as a parameter. The skill file passes it; the server never calls `Path.cwd()`.
  All git subprocess calls pass `cwd=project_root`.
