---
name: Happy Flow
---
# antigravity-adapter — Happy Flow

## Ideal journey: end-to-end install on a machine with `agy` installed

### 1. Developer runs pre-flight
```
agy --version
# → Antigravity CLI 2.0.x
agy models list
# → gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-8b (or current names)
python -m pytest tests/ -q
# → all pass (baseline recorded)
```

### 2. Developer installs pathly-adapters package
```
pip install pathly-adapters
# or: pipx install pathly-adapters
```

### 3. Developer runs setup
```
pathly-setup antigravity --apply
```

### 4. Setup output
```
[antigravity] Wrote 11 file(s) to ~/.gemini/antigravity-cli/agents/
[antigravity] Wrote 5 flow(s) to ~/.gemini/antigravity-cli/agents/
[antigravity] Wrote 19 skill(s) to ~/.gemini/antigravity-cli/skills/
[antigravity] Wrote N template(s) to ~/.gemini/antigravity-cli/plugins/pathly/templates/
```

### 5. Developer opens Antigravity and invokes Pathly
```
agy "pathly go"
```
The `agy` CLI reads the skill from `~/.gemini/antigravity-cli/skills/pathly-go/SKILL.md` and executes the Pathly go workflow.

### 6. Developer repairs or re-installs
```
pathly-setup antigravity --repair
# → Only Pathly-owned files are overwritten; user-customised files are untouched
```

### 7. Developer uninstalls
```
pathly-setup antigravity --uninstall
# → All Pathly-owned files removed from ~/.gemini/antigravity-cli/
```
