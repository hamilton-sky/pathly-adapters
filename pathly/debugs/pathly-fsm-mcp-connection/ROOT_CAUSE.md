# Root Cause — pathly-fsm-mcp-connection

## Previous (incorrect) diagnosis

The prior investigation blamed the setuptools `.exe` wrapper for stdout buffering issues on Windows.
This was **wrong**. After updating `settings.json` to `python -m` form and confirming the server
responds correctly to initialize + tools/list, tools still never appeared after restarts.

---

## Actual root cause

**`mcpServers` in `~/.claude/settings.json` is not loaded in Claude Code desktop CCD sessions.**

The desktop app runs in CCD mode (epitaxy sidebar, worktree sessions). In this mode all MCP
servers are provided by the CCD daemon via `replaceRemoteMcpServers`. User-configured local
stdio servers from `settings.json` are handled by `LocalMcpServerManager`, which is **never
populated in CCD mode**.

### Log evidence (`C:\Users\Yafit\AppData\Roaming\Claude\logs\main.log`, every restart since 2026-05-14)

```
[LocalMcpServerManager] Closing all (0 servers)
[CCD] LocalSessions.replaceRemoteMcpServers: serverCount=0
[CCD] [replaceRemoteMcpServers] Calling SDK with 7 total servers {
  serverNames: ['Claude in Chrome', 'mcp-registry', 'Claude Preview', 'ccd_session', ...]
}
```

- `LocalMcpServerManager` is always 0 — never loads from `settings.json`
- `serverCount=0` in every `replaceRemoteMcpServers` call — zero user servers passed to CCD
- The 7 servers are fixed CCD-owned servers: `Claude in Chrome`, `mcp-registry`, `Claude Preview`,
  `ccd_session`, `ccd_directory`, `ccd_session_mgmt`, `scheduled-tasks`

`pathly-fsm` and `pathly-telemetry` have never appeared in any session since registration.

### Why "pathly-telemetry works" was a false premise

The original analysis assumed `pathly-telemetry` was a working example. It is not — it has
the same architectural issue. The assumption was never verified with log evidence.

### Server-side: no bug

The `pathly-fsm` server is fully functional:
- `python -m pathly_orchestrator.mcp_server` responds correctly to initialize + tools/list
- No crash, no buffering issue, no import error
- The problem is entirely on the Claude Code client side

---

## Scope

`mcpServers` in `~/.claude/settings.json` works for the `claude` CLI but is ignored by the
Claude Code desktop app's CCD session interface. Restarting the desktop app cannot fix this —
it is an architectural constraint of CCD mode, not a configuration problem.
