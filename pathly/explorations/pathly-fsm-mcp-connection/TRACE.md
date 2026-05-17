# TRACE — pathly-fsm-mcp-connection

## Files visited

| File | Key finding |
|------|-------------|
| `C:\Users\Yafit\.claude\settings.json` | pathly-fsm registered as `.exe` path, no args array |
| `src/pathly_orchestrator/mcp_server.py` | Exists, imports cleanly, tools registered at lines 28–88, `main()` at 437–438 |
| `src/pathly_orchestrator/fsm.py` | Exists, stdlib-only imports, no import errors |
| `src/install_cli/mcp_config.py` | Generates `{"command": "python", "args": ["-m", "pathly_orchestrator.mcp_server"]}` |
| `pyproject.toml:20` | `pathly-fsm = "pathly_orchestrator.mcp_server:main"` — entry point present |
| `src/pathly_data/core/flows/team.flow.yaml` | 7 states, agent_map correct, feedback_routing references `human` |
| `src/pathly_data/core/flows/debug.flow.yaml` | feedback_routing references `human` |
| `src/pathly_data/core/flows/explore.flow.yaml` | feedback_routing references `human` |
| `src/pathly_data/core/agents/human.md` | **MISSING** — all three flows reference it; FileNotFoundError at runtime |
| `pathly/plans/mcp-fsm-driver/PROGRESS.md` | All 4 conversations marked DONE |

## Scout conflicts

Scout 1 (orientation) reported `mcp_server.py` as missing. Scouts 2 and 3 successfully read it with line citations. Scout 1 finding is **discarded** — likely read a stale glob cache.

## Code path for MCP startup

```
Claude Code starts session
→ reads settings.json mcpServers["pathly-fsm"]
→ spawns: C:\Users\Yafit\AppData\Local\Programs\Python\Python313\Scripts\pathly-fsm.exe
→ exe calls mcp_server:main()
→ main() calls run()
→ run() reads stdin line-by-line (JSON-RPC 2.0 + Content-Length framing)
→ on initialize: sends capabilities
→ on tools/list: returns next_action + complete_stage schemas
→ (tools become available in session)
```

## Registration discrepancy

| Source | Command registered |
|--------|--------------------|
| `mcp_config.py` | `python -m pathly_orchestrator.mcp_server` |
| `settings.json` (actual) | `pathly-fsm.exe` (direct exe, no args) |

Both forms should invoke the same `main()`. The discrepancy means settings.json was not written by the current mcp_config.py (written manually or by an older version).
