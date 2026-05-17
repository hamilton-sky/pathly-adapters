# Symptom — pathly-fsm-mcp-connection

## What broke
`pathly-fsm` MCP server tools (`mcp__pathly-fsm__next_action`, `mcp__pathly-fsm__complete_stage`)
never appear in Claude Code sessions, even though the server is registered in `~/.claude/settings.json`
and the Python module works correctly.

## How it manifests
- ToolSearch for `mcp__pathly-fsm__next_action` returns no results
- The server is not listed in the deferred tools at session start
- Running `/pathly-team <feature> mcp` falls back because the tools are absent
- No error is surfaced to the user — Claude Code drops the server silently
- `LocalMcpServerManager Closing all (0 servers)` in every shutdown log since May 14

## Environment
- OS: Windows 11 Pro
- Claude Code: desktop app (CCD/epitaxy mode with worktree sessions)
- Python: 3.13 (`C:\Users\Yafit\AppData\Local\Programs\Python\Python313\`)
- `~/.claude/settings.json` has correct `mcpServers` entry (python -m form, not .exe)
- MCP server handshake confirmed working: initialize + tools/list respond correctly in subprocess test
- Log file: `C:\Users\Yafit\AppData\Roaming\Claude\logs\main.log`

## Key log evidence
```
[LocalMcpServerManager] Closing all (0 servers)   ← every shutdown since May 14
[CCD] LocalSessions.replaceRemoteMcpServers: serverCount=0  ← user MCP count always 0
[CCD] [replaceRemoteMcpServers] Calling SDK with 7 total servers  ← always same 7 CCD servers
```
`pathly-fsm` and `pathly-telemetry` are never in the 7-server list.

## Expected behavior
`mcp__pathly-fsm__next_action` and `mcp__pathly-fsm__complete_stage` appear in the
tool list at session start, allowing the MCP engine path in `/pathly-team` to function.

## Previous (incorrect) diagnosis
The prior ROOT_CAUSE.md blamed the `.exe` wrapper causing stdout flush issues on Windows.
This was wrong — the `settings.json` was updated to `python -m` form but the tools still
never appeared. The actual issue is architectural, not a wrapper problem.
