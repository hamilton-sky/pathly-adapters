# Implementation Plan — pathly-fsm-mcp-not-connecting

## Root Cause
Claude Code Desktop (CCD) version 2.1.138 intentionally ignores the `mcpServers` section in `settings.json`. Only a hardcoded set of 7 built-in servers are loaded. Custom MCP servers defined in settings.json are never spawned or connected to.

## Solution
Create an HTTP wrapper for `pathly-fsm` MCP server. This allows `/pathly-team-mcp` to call the FSM engine via HTTP instead of MCP tools.

## Files to Change

### 1. Create `src/pathly_orchestrator/http_server.py` (new)
HTTP server wrapping the FSM functions as REST endpoints:
- `POST /next_action` — calls `_next_action()` from mcp_server
- `POST /complete_stage` — calls `_complete_stage()` from mcp_server  
- `GET /health` — health check

### 2. Modify `src/pathly_orchestrator/mcp_server.py`
Ensure `_next_action` and `_complete_stage` are importable by the HTTP server. Already structured correctly.

### 3. Modify `src/pathly_data/core/skills/team-mcp.md`
Update the guard section to:
1. Try MCP first (if tools available)
2. Fall back to HTTP server on localhost:8765
3. If HTTP server not running, start it automatically

### 4. Update `pyproject.toml`
Add Flask dependency:
```toml
dependencies = [
    "pyyaml>=6.0",
    "flask>=2.3",
]
```

## Implementation Steps

1. Create the HTTP server with Flask
2. Test manually with curl
3. Update team-mcp.md with fallback logic
4. Test end-to-end with `/pathly-team-mcp <feature> build`
5. Verify STATE.json updates and FSM transitions work correctly

## Success Criteria
- HTTP server starts without error
- `/next_action` and `/complete_stage` endpoints respond with valid JSON
- `/pathly-team-mcp` skill detects and uses HTTP server when MCP unavailable
- Full FSM workflow (BUILDING → REVIEWING) completes successfully
