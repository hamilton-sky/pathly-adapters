---
name: Happy Flow
---
# adapter-parity — Happy Flow

## Copilot user archives a feature
1. User runs `/pathly archive` in Copilot
2. Copilot finds `archive_skill.yaml` in the installed adapter → skill is available
3. Archive flow runs; feature folder moved to `.archive/`
4. User runs `/pathly archive-artifacts` → artifacts cleaned up

## Pathly-setup installs Copilot adapter (after hooks removal)
1. `pathly-setup --host copilot --apply` runs
2. Installer reads `install.yaml` — no `hooks:` key present
3. All declared skills and agents are materialized to the Copilot extension directory
4. No warning about unimplemented hooks

## Developer adds a new feature using explorer agent
1. User invokes `explorer` agent
2. Agent finds `core/agents/explorer.md` — reads role, tool set, output contract
3. Explorer runs in analyze phase → outputs NEEDS_CONTEXT
4. Explorer runs in explore phase → writes TRACE.md
5. Explorer concludes → writes CONCLUSIONS.md

## Studio user switches themes
1. User opens Settings → switches to Paper theme
2. `data-theme="paper"` set on document root
3. `--focus-ring` token becomes `2px solid #c75c2a` (warm orange)
4. User tabs through sidebar items → focus rings are orange, not blue
5. `filterInput` receives keyboard focus → orange focus ring visible
