# Exploration — pathly-fsm-mcp-connection

## Question
Why is the `pathly-fsm` MCP server registered in `~/.claude/settings.json` but not connecting at session start — its tools (`mcp__pathly-fsm__next_action`, `mcp__pathly-fsm__complete_stage`) are absent from the available tool list?

## Scope
- `~/.claude/settings.json` mcpServers entry for `pathly-fsm`
- The `pathly-fsm.exe` executable (`C:\Users\Yafit\AppData\Local\Programs\Python\Python313\Scripts\pathly-fsm.exe`)
- `src/pathly_orchestrator/mcp_server.py` — the MCP server module
- `src/install_cli/mcp_config.py` — registration logic
- FSM routing logic (`src/pathly_orchestrator/fsm.py`, flow YAMLs)
- Any startup errors / stderr from the server process

## Out of scope
- The LLM-driven orchestrator fallback path
- Other MCP servers (pathly-telemetry, playwright, etc.)

## Success criterion
We can answer: "What is the specific failure mode preventing pathly-fsm from connecting, and what is the fix?"
