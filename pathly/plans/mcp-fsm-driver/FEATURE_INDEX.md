# mcp-fsm-driver — Feature Index

## What this feature is

Replace the LLM orchestrator agent with a Python MCP server
(`pathly_orchestrator.mcp_server`) that reads flow YAMLs and drives the FSM
deterministically. Skill files call two MCP tools — `next_action` and
`complete_stage` — instead of spawning the orchestrator agent. All routing
decisions move from LLM to Python. Both Claude Code and Codex consume the same
server via their native MCP support.

## Why it matters

The LLM orchestrator is non-deterministic. Even with a flow YAML spec it can
misread STATE.json, skip feedback file checks, or hallucinate a transition.
Moving FSM execution to Python eliminates this class of failures entirely:
the flow YAML becomes an executable spec run by Python, not a hint read by
an LLM.

## Prior work this builds on

- `fsm-transition-actions` — DONE. Flow YAMLs carry `transition_actions`; the
  action vocabulary (`git_commit`, `update_progress`, `archive_artifacts`) is
  defined.
- `fsm-configurable` — DONE. `state.py` has `load_flow`, `validate_flow_cli`,
  `_REQUIRED_FLOW_KEYS`, `get_transition_actions`.

## Conversation map

| Conv | Scope | Stories |
|------|-------|---------|
| 1 | Python FSM core (`fsm.py`) + MCP server (`mcp_server.py`) + entry point | S1.1, S1.2, S1.3 |
| 2 | `mcp_config.py` registers `pathly-fsm` for Claude + Codex | S2.1 |
| 3 | Skill files updated to call MCP tools; orchestrator marked legacy | S3.1, S3.2 |
| 4 | Tests for FSM core and MCP server | S4.1 |

## Key file paths

**New Python modules:**
- `src/pathly_orchestrator/fsm.py` — FSM core logic (pure functions)
- `src/pathly_orchestrator/mcp_server.py` — MCP server (`next_action`, `complete_stage`)

**Edited Python modules:**
- `src/install_cli/mcp_config.py` — add `pathly-fsm` server registration
- `pyproject.toml` — add `pathly-fsm` entry point

**Edited skill files (three flows):**
- `src/pathly_data/core/skills/team.md`
- `src/pathly_data/core/skills/debug.md`
- `src/pathly_data/core/skills/explore.md`
- `src/pathly_data/adapters/claude/_meta/team_skill.yaml` (+ debug, explore)
- `src/pathly_data/adapters/codex/_meta/team_skill.yaml` (+ debug, explore)

**Edited agent:**
- `src/pathly_data/core/agents/orchestrator.md` — add legacy/reference note

**New tests:**
- `tests/test_fsm.py`
- `tests/test_mcp_server.py`

## Verify command (run after all conversations complete)

```bash
# MCP server starts without error
python -m pathly_orchestrator.mcp_server --help

# Entry point registered
grep "pathly-fsm" pyproject.toml

# MCP config wires both hosts
grep "pathly-fsm" src/install_cli/mcp_config.py

# Skill files call MCP tools, not orchestrator agent
grep "next_action\|complete_stage" src/pathly_data/core/skills/team.md
grep "orchestrator" src/pathly_data/core/skills/team.md  # must return nothing

# Tests pass
pytest tests/test_fsm.py tests/test_mcp_server.py -q
```
