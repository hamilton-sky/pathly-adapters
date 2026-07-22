# Fix Report — claude-hooks-not-registered

## Problem
`pathly-setup claude --apply` deployed hook scripts to `~/.claude/plugins/pathly/hooks/` but never registered them in `~/.claude/settings.json`, causing hooks to be orphaned and never execute.

## Root Cause
Missing `deploy_claude_hooks()` and `remove_claude_hooks()` functions that write/merge hooks configuration into `~/.claude/settings.json`.

## Solution Implemented

### 1. Added `deploy_claude_hooks()` to materialize.py (lines 209-268)
- Reads/creates `~/.claude/settings.json`
- Initializes `hooks` dict if absent
- Merges Pathly hooks on `post_tool_call` event
- Atomic write of JSON
- Returns list of affected files

### 2. Added `remove_claude_hooks()` to materialize.py (lines 271-298)
- Removes Pathly hook entries (`classify_feedback`, `inject_feedback_ttl`)
- Deletes empty `hooks` dict
- Returns list of affected files

### 3. Wired into setup_command.py
- **Import** (lines 14-23): Added `deploy_claude_hooks` and `remove_claude_hooks` to imports
- **Dry-run** (lines 178-181): Shows what would be written to `~/.claude/settings.json`
- **Install** (lines 239-241): Calls `deploy_claude_hooks()` after successful file deployment
- **Error handler** (lines 275-279): Rolls back hooks on install failure
- **Uninstall** (lines 307-310): Removes hooks via `remove_claude_hooks()`

## Files Modified
1. `src/install_cli/materialize.py` — added 90 lines (deploy/remove functions)
2. `src/install_cli/setup_command.py` — added 24 lines (imports, calls, error handling)

## Verification

### Deploy Test
```bash
pathly-setup claude --apply --repair
# Output: "[claude] Wrote Claude hooks to ~/.claude/settings.json"
```

### Hooks Registration Confirmed
```json
{
  "hooks": {
    "classify_feedback": {
      "event": "post_tool_call",
      "script": "/path/to/classify_feedback.py"
    },
    "inject_feedback_ttl": {
      "event": "post_tool_call",
      "script": "/path/to/inject_feedback_ttl.py"
    }
  }
}
```

### Uninstall Test
```bash
pathly-setup claude --uninstall
# Output: "[claude] Removed Claude hooks from ~/.claude/settings.json"
# Verification: 'hooks' key removed from settings.json ✓
```

### Reinstall Test
```bash
pathly-setup claude --apply --repair
# Verification: 'hooks' key re-created with proper entries ✓
```

## Design Pattern
Matches existing Codex implementation:
- `deploy_codex_hooks()` → writes to `~/.codex/hooks.json`
- `deploy_claude_hooks()` → writes to `~/.claude/settings.json`

Both use JSON merge patterns to preserve other configuration.

## Status
COMPLETE — hooks are now registered and will fire on `post_tool_call` events.
