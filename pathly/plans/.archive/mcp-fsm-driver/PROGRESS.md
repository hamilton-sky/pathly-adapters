# PROGRESS.md — mcp-fsm-driver

| Conv | Scope | Stories | Status |
|------|-------|---------|--------|
| 1 | Python FSM core (`fsm.py`) + MCP server (`mcp_server.py` with `next_action`, `complete_stage`) + entry point | S1.1, S1.2, S1.3 | DONE |
| 2 | `mcp_config.py` registers `pathly-fsm` for Claude + Codex | S2.1 | DONE |
| 3 | Skill files updated: `team-mcp.md` created with MCP + HTTP fallback; `orchestrator.md` gets Runtime note | S3.1, S3.2 | DONE |
| 4 | Tests for FSM core and MCP server | S4.1 | DONE |

## Implementation notes

- Conv 3 deviated from plan: MCP calls went into a new `team-mcp.md` skill rather than replacing `team.md`. `team.md` retains the LLM orchestrator engine. Both skills coexist — users invoke `/pathly-team-mcp` for the MCP engine.
- `http_server.py` added (not in original plan) as HTTP fallback for environments where MCP server cannot connect (see `pathly-fsm-mcp-not-connecting` plan).

## Status key

| Symbol | Meaning |
|--------|---------|
| NOT STARTED | Work has not begun |
| IN PROGRESS | Conversation is active |
| DONE | All acceptance criteria verified |
| BLOCKED | Cannot begin — upstream dependency not met |
