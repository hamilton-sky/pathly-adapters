# Symptom — claude-hooks-not-registered

## What broke
`pathly-setup claude --apply` deploys hook scripts to disk but never registers
them in `~/.claude/settings.json`. Claude has no `hooks` key in settings.json,
so the hooks never fire.

## How it manifests
After running `pathly-setup claude --apply --repair`:
- `~/.claude/plugins/pathly/hooks/classify_feedback.py` — exists ✅
- `~/.claude/plugins/pathly/hooks/inject_feedback_ttl.py` — exists ✅
- `~/.claude/settings.json` → `hooks` key — MISSING ❌

Running `python -c "import json; from pathlib import Path; d=json.loads(Path('~/.claude/settings.json').expanduser().read_text()); print(d.get('hooks', 'NO HOOKS KEY'))"` prints `NO HOOKS KEY`.

## Environment
- pathly-adapters 2.4.1
- Windows 11, Claude Code CLI
- `src/install_cli/setup_command.py` — no `deploy_claude_hooks()` equivalent

## Expected behavior
After `pathly-setup claude --apply`, `~/.claude/settings.json` should contain a
`hooks` section registering both scripts on the `PostToolUse` event, exactly as
Codex's `hooks.json` is written by `deploy_codex_hooks()`.
