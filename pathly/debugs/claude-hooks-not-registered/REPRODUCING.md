# Reproduction Report

## Confirmed: Hooks are deployed but not registered

### Hook Files Present
```
~/.claude/plugins/pathly/hooks/classify_feedback.py ✓ (exists)
~/.claude/plugins/pathly/hooks/inject_feedback_ttl.py ✓ (exists)
```

### Settings Registration Missing
```
~/.claude/settings.json → "hooks" key: MISSING ✗
```

Confirmed by grep: `grep -i "hooks" ~/.claude/settings.json` returns no results.

## Why This Breaks
Claude Code CLI reads the `hooks` key from `settings.json` to register event handlers.
Without the registration, the hook scripts are orphaned on disk and never execute.

## Codex Comparison
Codex deployment works correctly because `deploy_codex_hooks()` exists and is called:
- Reads/merges `~/.codex/hooks.json`
- Registers hooks on the `PostToolUse` event
- Called from `setup_command.py` line 227

## Next Steps
Implement Claude hooks deployment equivalent.
