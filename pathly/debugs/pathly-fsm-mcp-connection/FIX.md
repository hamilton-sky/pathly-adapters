# Fix — pathly-fsm-mcp-connection

## Changes made

### 1. `~/.claude/settings.json` — immediate fix (takes effect on next Claude Code restart)

```diff
- "pathly-fsm": {
-   "command": "C:\\Users\\Yafit\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\pathly-fsm.exe"
- }
+ "pathly-fsm": {
+   "command": "C:\\Users\\Yafit\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
+   "args": ["-m", "pathly_orchestrator.mcp_server"]
+ }
```

Matches the pattern used by the working `pathly-telemetry` server. The `.exe` wrapper has
a Windows/Electron stdout flushing issue when spawned as a child process; direct `python.exe -m`
does not.

### 2. `src/install_cli/mcp_config.py` — prevents regression on future installs

```diff
- _FSM_CLAUDE_ENTRY: dict = {
-     "command": "python",
-     "args": ["-m", "pathly_orchestrator.mcp_server"],
- }
+ _FSM_CLAUDE_ENTRY: dict = {
+     "command": sys.executable,
+     "args": ["-m", "pathly_orchestrator.mcp_server"],
+ }
```

`sys.executable` resolves to the absolute path of the Python running the install script —
the same Python that will have `pathly_orchestrator` in its site-packages.

## How to verify

1. **Restart Claude Code** (MCP servers connect at session start)
2. In a new session, run `/pathly-team <any-feature> mcp fast`
3. If `mcp__pathly-fsm__next_action` appears in available tools → fixed

## Secondary bug (open)

`src/pathly_data/core/agents/human.md` is missing. All three flows (`team`, `debug`, `explore`)
route feedback to `human`, which causes `_load_agent_text("human")` to raise `FileNotFoundError`
at runtime. This does NOT block startup but will crash the server when a human feedback gate
is triggered. Tracked separately.
