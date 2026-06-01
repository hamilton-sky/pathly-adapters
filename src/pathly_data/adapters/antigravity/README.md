# Antigravity Adapter

Antigravity should expose the shared Pathly command surface through the
Gemini CLI install path.

## Install

```bash
irm https://antigravity.google/cli/install.ps1 | iex
pathly-setup antigravity --apply
```

Preview first:

```bash
pathly-setup antigravity --dry-run
```

## Install destinations

- Agents: `~/.gemini/antigravity-cli/agents/`
- Skills: `~/.gemini/antigravity-cli/skills/`
- Templates: `~/.gemini/antigravity-cli/plugins/pathly/templates`

## Model names

- Pro-tier: `gemini-2.5-pro`
- Flash-tier: `gemini-2.5-flash`

TODO: replace these placeholders if `agy models list` reports different
supported model names in the target environment.
