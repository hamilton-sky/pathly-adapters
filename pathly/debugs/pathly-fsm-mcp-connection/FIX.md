---

---
# Fix — pathly-fsm-mcp-connection

## Status

The root cause is a Claude Code desktop app architectural constraint — CCD sessions do not
load user-configured stdio MCP servers from `~/.claude/settings.json`. This cannot be fixed
by changing `settings.json` or restarting the desktop app.

---

## Working paths (no code change needed)

### Option A — Use the `claude` CLI (recommended)

Open a terminal in the project directory and run `claude`. The CLI reads `settings.json`
via `LocalMcpServerManager` and WILL load `pathly-fsm`. Then `/pathly-team <feature> mcp fast`
works as designed.

```powershell
cd C:\Users\Yafit\pathly-adapters
claude
```

### Option B — Drop the `mcp` flag (desktop app sessions)

The `/pathly-team` skill falls back to the LLM orchestrator when `mcp__pathly-fsm__*` tools
are absent. Remove the `mcp` flag:

```
/pathly-team <feature> fast
```

---

## Code changes needed (future work)

### 1. Auto-detect CCD mode in team.md / go.md

When `engine = mcp` is requested but `mcp__pathly-fsm__next_action` is absent, the skill
should detect this and either warn or fall back automatically instead of silently using
Python subprocess calls.

### 2. Update `mcp_config.py` install documentation

The install docs should note that `mcpServers` in `settings.json` only applies to the
`claude` CLI, not the Claude Code desktop app CCD sessions.

---

## What was already fixed (still valid, not reverted)

- `settings.json` uses `python -m` form (not `.exe`) — correct, keep it for CLI users
- `mcp_config.py` uses `sys.executable` — correct, prevents future path issues
- `src/pathly_data/core/agents/human.md` created — fixes runtime crash when feedback
  routes to human (separate from the startup issue)

---

## How to verify Option A

1. Open terminal: `cd C:\Users\Yafit\pathly-adapters && claude`
2. Run `/pathly-team studio-arch-refactor mcp fast`
3. `mcp__pathly-fsm__next_action` should appear in available tools and be called directly
