# Root Cause — pathly-fsm-mcp-connection

## What the server does

The `mcp_server.py` implementation is correct. Manual testing confirms:
- `initialize` → responds with `{"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, ...}`
- `notifications/initialized` → silent (correct)
- `tools/list` → returns both `next_action` and `complete_stage` with correct schemas

## Root cause

**`settings.json` registers `pathly-fsm` using the setuptools `.exe` wrapper instead of `python.exe -m`.**

```json
// Current (broken)
"pathly-fsm": {
  "command": "C:\\Users\\Yafit\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\pathly-fsm.exe"
}

// Required (matches pathly-telemetry which works)
"pathly-fsm": {
  "command": "C:\\Users\\Yafit\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
  "args": ["-m", "pathly_orchestrator.mcp_server"]
}
```

When Claude Code (Electron/Node.js) spawns a setuptools `.exe` wrapper as a child process on Windows,
the child's stdout pipe is not flushed before Claude Code's MCP client times out the handshake.
Direct `python.exe -m` invocation uses a different startup path that doesn't have this buffering issue.

Evidence:
1. `pathly-telemetry` uses `python.exe` + `-m pathly_telemetry` — it works.
2. `pathly-fsm` uses `pathly-fsm.exe` — it doesn't appear at session start.
3. `python -m pathly_orchestrator.mcp_server` tested manually responds correctly in all cases.

## Secondary issue

`mcp_config.py` generates:
```python
{"command": "python", "args": ["-m", "pathly_orchestrator.mcp_server"]}
```
This uses a bare `python` (PATH-relative) which may not resolve correctly in Claude Code's environment.
It should use the absolute `python.exe` path, matching `pathly-telemetry`.

## Not a root cause

- `mcp_server.py` logic: fully correct, tested
- `fsm.py` imports: clean
- `pathly-fsm.exe` existence: confirmed present
- `pathly_orchestrator` install: editable install at `jovial-cray-c49a0b` (on `origin/pathly-mcp`), works
- Missing `human.md`: runtime issue when feedback routes to human — separate bug, does not affect startup
