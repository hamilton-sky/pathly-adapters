# Symptom — pathly-fsm-mcp-connection

## What broke
`pathly-fsm` MCP server is registered in `~/.claude/settings.json` but its tools
(`mcp__pathly-fsm__next_action`, `mcp__pathly-fsm__complete_stage`) never appear
in the Claude Code session tool list.

## How it manifests
- ToolSearch for `mcp__pathly-fsm__next_action` returns no results
- The server is not listed in the deferred tools at session start
- Running `/pathly-team <feature> mcp` falls back silently because the tools are absent
- No error is surfaced to the user — Claude Code drops the server silently

## Environment
- Branch: `integrate/pathly-ui-mcp`
- OS: Windows 11 Pro
- Python: 3.13 (`C:\Users\Yafit\AppData\Local\Programs\Python\Python313\`)
- `pathly-fsm.exe` exists at `C:\Users\Yafit\AppData\Local\Programs\Python\Python313\Scripts\pathly-fsm.exe`
- `settings.json` entry: `{"command": "C:\\...\\pathly-fsm.exe"}` (exe form, no args)
- `mcp_config.py` generates: `{"command": "python", "args": ["-m", "pathly_orchestrator.mcp_server"]}`
- All mcp-fsm-driver PROGRESS.md convs marked DONE
- `src/pathly_data/core/agents/human.md` is MISSING (confirmed by exploration)

## Expected behavior
`mcp__pathly-fsm__next_action` and `mcp__pathly-fsm__complete_stage` appear in the
tool list at session start, allowing the MCP engine path in `/pathly-team` to function.
