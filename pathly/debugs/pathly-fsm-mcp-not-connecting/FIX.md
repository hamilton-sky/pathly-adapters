# Fix — pathly-fsm MCP server not connecting

## Problem Statement
Claude Code Desktop (CCD) version 2.1.138 **intentionally ignores the `mcpServers` section** in `settings.json`. It only loads a hardcoded set of 7 built-in servers:
- Claude in Chrome
- mcp-registry
- Claude Preview
- ccd_session, ccd_directory, ccd_session_mgmt, scheduled-tasks

Any custom MCP server defined in settings.json is not spawned or connected to.

## Solution Approaches

### Option 1: Use Claude Browser instead of Claude Code Desktop (Workaround)
**Feasibility**: High — immediate, no code changes needed

Claude web app may have different MCP loading behavior. Test if custom MCP servers work there.

**Steps**:
1. Go to claude.ai in browser
2. Try the pathly-fsm tools — they may be available if browser Claude loads local servers differently
3. If it works, use browser for Pathly FSM workflows

**Pros**: No code changes, uses existing infrastructure
**Cons**: Less integrated with workspace than CCD

### Option 2: Report to Anthropic + Use HTTP Wrapper (Medium-term fix)
**Feasibility**: Medium — requires implementation but guaranteed to work

CCD's limitation is likely intentional (security, stability). While Anthropic fixes or documents this:

1. **Build an HTTP wrapper** for pathly-fsm
   - Expose the MCP protocol as HTTP endpoints
   - Run pathly-fsm as a persistent service
   - Have Claude Code call it via Bash/Python (not via MCP)

2. **Update `/pathly-team-mcp` skill** to detect the HTTP server and call it directly instead of via MCP tools

**Benefits**: Works immediately, independent of CCD updates
**Cost**: ~100 lines of code for HTTP wrapper

### Option 3: Manually Load MCP Server at CCD Startup (Hacky)
**Feasibility**: Low — fragile, depends on CCD internals

Attempts:
1. Try `CLAUDE_CODE_DEBUG=1` environment variable to see if debug mode loads local servers
2. Look for CCD startup hooks or extension points to inject custom MCP server registration
3. Examine CCD Electron app files for hardcoded server list and patch it

**Pros**: Works if found
**Cons**: Breaks on every CCD update, depends on undocumented APIs

### Option 4: Package as CCD Plugin with Embedded MCP (Best long-term)
**Feasibility**: Medium-High — requires plugin development

CCD DOES load plugins (it loads "Claude in Chrome" as a plugin). Create a plugin that:

1. **Manifests an MCP server definition** in plugin format
2. **CCD loads the plugin** → plugin registers pathly-fsm as an internal MCP server
3. **Tools surface normally** as `mcp__pathly-fsm__*`

**Steps**:
- Research CCD plugin SDK to see if plugins can define MCP servers
- Update `plugin.json` or marketplace.json to include MCP server definition
- Test loading the plugin in CCD

**Pros**: Official, sustainable, loaded by design
**Cons**: Requires understanding of plugin architecture

---

## Recommended Fix Path

### Immediate (this week)
**Implement Option 2 (HTTP wrapper)**:
1. Create `src/pathly_orchestrator/http_server.py` with Flask/FastAPI
2. Wrap MCP `next_action` and `complete_stage` as HTTP endpoints
3. Run as daemon: `python -m pathly_orchestrator.http_server`
4. Update `/pathly-team-mcp` to detect and use HTTP instead of MCP
5. Test end-to-end with Pathly workflows

### Medium-term (this month)
**Report to Anthropic** — ask:
1. Is settings.json `mcpServers` supported in CCD 2.1.138?
2. If not, when will it be supported?
3. Should we use HTTP wrapper as permanent workaround?

### Long-term (if no fix from Anthropic)
**Implement Option 4 (Plugin)**:
1. Research CCD plugin architecture for MCP support
2. Convert pathly-fsm into a CCD plugin
3. Ship as part of Pathly adapter package

---

## Implementation for Option 2 (Recommended — HTTP Wrapper)

### File: `src/pathly_orchestrator/http_server.py`

```python
"""HTTP wrapper for pathly-fsm MCP server.

Provides REST endpoints that mimic the MCP protocol functions,
allowing Claude Code to call pathly-fsm without relying on CCD's
disabled MCP server loader.

Run: python -m pathly_orchestrator.http_server
"""
from flask import Flask, request, jsonify
import json
import sys
from pathlib import Path

from pathly_orchestrator.mcp_server import _next_action, _complete_stage

app = Flask(__name__)

@app.route('/next_action', methods=['POST'])
def next_action_endpoint():
    """Wrapper for mcp_server._next_action"""
    try:
        data = request.get_json()
        result = _next_action(data)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/complete_stage', methods=['POST'])
def complete_stage_endpoint():
    """Wrapper for mcp_server._complete_stage"""
    try:
        data = request.get_json()
        result = _complete_stage(data)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200

def main():
    import os
    port = int(os.environ.get("PATHLY_FSM_HTTP_PORT", 8765))
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    main()
```

### File: `src/pathly_orchestrator/mcp_server.py` (modification)

Expose `_next_action` and `_complete_stage` by removing the underscore prefix
or adding explicit exports, so HTTP wrapper can import them.

### Update: `/pathly-team-mcp` skill

Modify to detect and use HTTP server:

```python
# At the start of the skill
import requests
import subprocess

def get_pathly_fsm_client():
    """Get either MCP or HTTP client for pathly-fsm"""
    # Try MCP first (if CCD ever enables it)
    try:
        return MCPClient()  # existing code
    except ToolNotFound:
        pass
    
    # Fall back to HTTP
    http_port = 8765
    if not is_server_running(http_port):
        # Start HTTP server
        subprocess.Popen(
            ["python", "-m", "pathly_orchestrator.http_server"],
            env={**os.environ, "PATHLY_FSM_HTTP_PORT": str(http_port)}
        )
        time.sleep(1)
    
    return HTTPClient(f"http://127.0.0.1:{http_port}")
```

### Update: `pyproject.toml`

Add Flask or FastAPI dependency:

```toml
dependencies = [
    "pyyaml>=6.0",
    "flask>=2.3",  # or "fastapi>=0.100"
]
```

---

## Testing the Fix

After implementing HTTP wrapper:

```bash
# Terminal 1: Start HTTP server
python -m pathly_orchestrator.http_server

# Terminal 2: Test with curl
curl -X POST http://127.0.0.1:8765/next_action \
  -H "Content-Type: application/json" \
  -d '{"flow": "debug", "topic": "test", "project_root": "C:/path/to/pathly-adapters"}'

# Terminal 3: In Claude Code, run
/pathly-team-mcp debug test
# Should work with or without MCP tools registered
```

---

## Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `src/pathly_orchestrator/http_server.py` | Create | HTTP wrapper (100 LOC) |
| `src/pathly_orchestrator/mcp_server.py` | Modify | Export public functions if needed |
| `adapters/claude/skills/team-mcp.md` | Modify | Add HTTP fallback logic |
| `pyproject.toml` | Modify | Add Flask/FastAPI dependency |
| `src/pathly_orchestrator/__init__.py` | Possibly | Export public API |

**Estimated effort**: 2-3 hours for implementation + testing
