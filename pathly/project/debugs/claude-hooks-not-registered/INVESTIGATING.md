# Investigation Report

## Summary
The `pathly-setup claude --apply` command deploys hook scripts to disk (`~/.claude/plugins/pathly/hooks/`) but does not register them in `~/.claude/settings.json`.

## Root Cause
`setup_command.py` contains `deploy_codex_hooks()` and `deploy_copilot_hooks()` functions, but there is **no `deploy_claude_hooks()` function**.

### Evidence
1. **Codex hooks:** `src/install_cli/materialize.py` lines 20-70 implement `deploy_codex_hooks()` which:
   - Reads/creates `~/.codex/hooks.json`
   - Merges Pathly entries under `pathly` key
   - Writes back atomically

2. **Copilot hooks:** `src/install_cli/materialize.py` lines 104-143 implement `deploy_copilot_hooks()` which:
   - Writes individual hook JSON files to `.github/hooks/`

3. **Claude hooks:** Missing entirely. `setup_command.py` lines 226-234 handle Codex and Copilot but skip Claude.

## Expected Behavior
After running `pathly-setup claude --apply`, `~/.claude/settings.json` should contain a `hooks` section like:
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

## Files to Modify
1. `src/install_cli/materialize.py` — add `deploy_claude_hooks()` and `remove_claude_hooks()`
2. `src/install_cli/setup_command.py` — import and call `deploy_claude_hooks()` / `remove_claude_hooks()`

## Implementation Plan
1. Study Codex hooks implementation (simpler, similar to Claude needs)
2. Adapt for Claude's `settings.json` format (not `hooks.json`)
3. Add uninstall support
4. Wire into setup_command.py
5. Test with actual installation
