# Symptom — pathly-fsm-mcp-not-connecting

## What broke
`mcp__pathly-fsm__next_action` and `mcp__pathly-fsm__complete_stage` do not appear
in Claude Code's available or deferred tools list. The `/pathly-team-mcp` skill guard
fails with "MCP server not connected."

## How it manifests
- `ToolSearch` for `mcp__pathly-fsm__next_action` returns "No matching deferred tools found"
- `ToolSearch` for `mcp__pathly_fsm__next_action` (underscore variant) also returns nothing
- The skill `/pathly-team-mcp studio-ui-fixes build` exits immediately with the not-connected error

## Diagnostic findings so far

### Server DOES start
- `pathly-fsm.exe` process IS spawned by Claude Code (confirmed via startup log)
- One log entry: `2026-05-18T02:06:17 startup pid=41820 cwd=...\focused-leavitt-3cdd9b stdin_isatty=False`
- Module imports without error: `python -c "import pathly_orchestrator.mcp_server"` → OK
- Manual MCP handshake test (stdin pipe) succeeds — server responds correctly to
  `initialize` and `tools/list`

### But tools don't register
- `mcp__pathly-fsm__*` never appears in the deferred tools system-reminder
- No "MCP Server connection requested for: pathly-fsm" in `AppData\Roaming\Claude\logs\main.log`
  (only `mcp-registry` and `Claude in Chrome` show connection-requested entries)
- After the single confirmed spawn (pid 41820), subsequent sessions don't show new spawns
- Tracing code added to `main()` was never triggered in a subsequent session

### Config history
Original config used `python.exe -m pathly_orchestrator.mcp_server` with `"args": ["-m", "pathly_orchestrator.mcp_server"]`.
Tried:
1. Removed `args: []` empty array → server started once (pid 41820) but tools still not surfacing
2. Switched command to `pathly-fsm.exe` → server stops spawning entirely
3. Removed `args` field entirely → same, no new spawns
4. Added protocol-version echo (`protocolVersion` now reflects client's requested version) → not yet tested with fresh restart
5. Added message-level tracing in `main()` → tracing never triggered in subsequent sessions

### Current settings.json (pathly-fsm entry)
```json
"pathly-fsm": {
  "command": "C:\\Users\\Yafit\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\pathly-fsm.exe"
}
```

### Related observation
The Pathly Studio (Electron, worktree `hardcore-ride-d3a057`) shows:
`[mcp] mcp_server.py not available — using file-watch fallback`
This is an intentional stub in `studio/src/main/ipc/mcp.ts` — unrelated to Claude Code MCP.

## Environment
- OS: Windows 11
- Claude Code Desktop app (CCD), version unknown
- Python: `C:\Users\Yafit\AppData\Local\Programs\Python\Python313\python.exe`
- Package: editable install, source at `C:\Users\Yafit\pathly-adapters\src\pathly_orchestrator\mcp_server.py`
- Settings file: `C:\Users\Yafit\.claude\settings.json`
- Session context: worktree `C:\Users\Yafit\pathly-adapters\.claude\worktrees\focused-leavitt-3cdd9b`

## Expected behavior
`mcp__pathly-fsm__next_action` and `mcp__pathly-fsm__complete_stage` should be available
as callable tools in every Claude Code session, enabling `/pathly-team-mcp` to drive
the Pathly FSM pipeline without the LLM fallback.
