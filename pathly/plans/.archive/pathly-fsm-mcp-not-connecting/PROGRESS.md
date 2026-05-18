# Progress — pathly-fsm-mcp-not-connecting

## Conversations

| Conv | Phase | Status |
|------|-------|--------|
| 1    | Implement HTTP wrapper + team-mcp updates | DONE |

## Current Focus

Building the HTTP wrapper solution for the FSM server connection issue.

## Completed

1. Created `src/pathly_orchestrator/http_server.py`
   - Flask-based HTTP server wrapping MCP functions
   - Endpoints: `/next_action`, `/complete_stage`, `/health`
   - Tested and working on port 8765

2. Updated `src/pathly_data/core/skills/team-mcp.md`
   - Added HTTP fallback detection in MCP server check guard
   - Added instructions for using HTTP endpoints when MCP unavailable
   - Updated FSM engine loop sections to handle both MCP and HTTP modes

3. Verified pyproject.toml
   - Flask dependency already present
   - Entry point `pathly-fsm-http` already defined
   - HTTP server callable as `python -m pathly_orchestrator.http_server`

## Testing

- HTTP server starts without error
- `/health` endpoint returns `{"status": "ok"}`
- `/next_action` endpoint returns proper FSM state information
- Server listens on `127.0.0.1:8765`

## Next Steps

1. Commit changes
2. Test end-to-end with actual /pathly-team-mcp workflow
3. Verify state transitions work correctly via HTTP
