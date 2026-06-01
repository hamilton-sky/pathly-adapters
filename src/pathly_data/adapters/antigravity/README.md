# Antigravity Adapter

Antigravity should expose the Pathly entry points through the Gemini CLI layout:

```text
/pathly ...
/path ...
```

`/pathly` is canonical. `/path` remains the short alias for daily use.

## Install

Install the Antigravity CLI on Windows:

```powershell
irm https://antigravity.google/cli/install.ps1 | iex
```

Then apply the adapter:

```bash
pathly-setup antigravity --apply
```

Preview writes first:

```bash
pathly-setup antigravity --dry-run
```

## Paths

- Agents: `~/.gemini/antigravity-cli/agents/`
- Skills: `~/.gemini/antigravity-cli/skills/`
- Templates: `~/.gemini/antigravity-cli/plugins/pathly/templates`

## Models

- Pro-tier: `gemini-2.5-pro`
- Flash-tier: `gemini-2.5-flash`

`agy` was not installed in this environment during pre-flight, so these model
names are placeholders until the binary is available and the live model list
can be verified.
