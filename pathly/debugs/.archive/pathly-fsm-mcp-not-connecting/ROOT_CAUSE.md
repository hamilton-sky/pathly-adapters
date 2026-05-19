# Root Cause Analysis — pathly-fsm MCP server not connecting

## Summary
The `pathly-fsm` MCP server is **correctly configured, correctly executable, and correctly implements the MCP protocol**. However, Claude Code Desktop (CCD) **never attempts to connect to it**. The server is not loaded from `settings.json`.

## Evidence

### What works
1. **The server is installed correctly**: `pathly-fsm.exe` exists and can be invoked
2. **The server implements MCP correctly**: Manual testing via stdin pipes shows proper responses
   - `initialize` request → correct response with protocol version
   - `tools/list` request → returns both `next_action` and `complete_stage` tools with full schema
3. **The configuration file is correct**: `settings.json` has valid entries:
   ```json
   "pathly-fsm": {
     "command": "C:\\Users\\Yafit\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\pathly-fsm.exe"
   }
   ```
4. **The entrypoint is correct**: `pyproject.toml` declares `pathly-fsm = "pathly_orchestrator.mcp_server:main"`
5. **The startup log shows ONE activation**: pid 41820 on 2026-05-18T02:06:17, then nothing

### What doesn't work
1. **Claude Code never requests connection**: The `main.log` shows only these connection requests:
   - `MCP Server connection requested for: mcp-registry` (every session)
   - `MCP Server connection requested for: Claude in Chrome` (every session)
   - **NO connection request for `pathly-fsm` or `pathly-telemetry`**

2. **Tools never surface**: `mcp__pathly-fsm__next_action` and `mcp__pathly-fsm__complete_stage` never appear in the deferred tools list

3. **No subsequent spawns**: After the initial pid 41820 startup, the server is never invoked again

## Root Cause

Claude Code Desktop **intentionally does not load MCP servers from settings.json's `mcpServers` section**. Confirmed by logs:

1. **CCD loads ONLY a hardcoded set of 7 built-in MCP servers**:
   - Claude in Chrome
   - mcp-registry
   - Claude Preview
   - ccd_session
   - ccd_directory
   - ccd_session_mgmt
   - scheduled-tasks

2. **Custom MCP servers in settings.json are completely ignored** — no connection attempt is made, no tools are surfaced

3. **The pathly-fsm spawns in the startup log confirm this**:
   - Line 1: Initial spawn at 02:06:17 (no message trace — server running but no messages)
   - Line 8-11: Spawn at 02:25:21 shows `initialize` + `tools/list` → server responds correctly
   - But the tools NEVER appear in CCD's deferred tools list because CCD only requests connections for its 7 hardcoded servers

4. **CCD's `replaceRemoteMcpServers` always reports `serverCount=0`** — it loads 0 remote servers from anywhere, including settings.json

## Supporting Details

- CCD version: 2.1.138 (Claude Code Desktop)
- Settings location: `C:\Users\Yafit\.claude\settings.json`
- Log location: `C:\Users\Yafit\AppData\Roaming\Claude\logs\main.log`
- No error messages appear in logs — CCD simply does not attempt to connect to local MCP servers defined in `mcpServers`

This is distinct from:
- **Plugin MCP servers** (handled specially, shadowed with no-ops to prevent double-load)
- **Remote MCP servers** (loaded from plugin manifests)
- **mcp-registry** (always loaded as a built-in)

## Expected vs. Actual

**Expected**: CCD reads `mcpServers` from settings.json on startup, spawns each server, calls `initialize` + `tools/list`, and surfaces tools as `mcp__<server-name>__<tool-name>`

**Actual**: CCD reads `mcpServers` from settings.json, but **does not spawn or connect to any of them**. Only built-in servers (mcp-registry) and installed extensions (Claude in Chrome) are loaded.
