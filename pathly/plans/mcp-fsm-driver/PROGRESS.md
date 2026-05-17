# PROGRESS.md — mcp-fsm-driver

| Conv | Scope | Stories | Status |
|------|-------|---------|--------|
| 1 | Python FSM core (`fsm.py`) + MCP server (`mcp_server.py` with `next_action`, `complete_stage`) + entry point | S1.1, S1.2, S1.3 | DONE |
| 2 | `mcp_config.py` registers `pathly-fsm` for Claude + Codex | S2.1 | DONE |
| 3 | Skill files updated: engine branch added (`engine = "python-mcp"` calls MCP tools, `engine = "llm"` spawns orchestrator unchanged) | S3.1, S3.2 | DONE |
| 4 | Tests for FSM core and MCP server | S4.1 | NOT STARTED |

## Status key

| Symbol | Meaning |
|--------|---------|
| NOT STARTED | Work has not begun |
| IN PROGRESS | Conversation is active |
| DONE | All acceptance criteria verified |
| BLOCKED | Cannot begin — upstream dependency not met |
