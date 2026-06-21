# Pathly Core

This folder is the tool-agnostic source of truth for Pathly workflow content.

Core files describe what Pathly knows and how workflows behave. They should not
depend on Claude Code slash-command syntax, Codex plugin metadata, or any other
host-specific packaging format.

Adapters turn this core into tool-specific experiences — one per supported host tool.

## Repository Boundaries

Keep shared, host-neutral behavior in `core/`. Keep files that package, install,
test, or execute Pathly in their own top-level folders.

```text
src/pathly_data/
  core/
    agents/       agent role contracts (building/, planning/, quality/, research/, support/, director.md)
    skills/       skill markdown (controls/, development/, planning/, team/, utilities/,
                                  fix/, fix-hutk/, custom/, debug/, hello/, planning-hello/, fragments/)
    templates/    plan file templates (plan/, pipeline-walkthrough/)
    flows/        flow YAML files (team, team-build, debug, explore, test, quick-fix, consultation)
    design/       UI/UX design subsystem (data/CSVs, scripts/, cli.py)
  adapters/
    claude/       _meta/ YAMLs + .claude-plugin/
    codex/        _meta/ YAMLs
    copilot/      _meta/ YAMLs
    antigravity/  _meta/ YAMLs
```

Current adapters: `claude` (→ ~/.claude/), `codex` (→ ~/.codex/), `copilot` (→ ~/.vscode/extensions/pathly/), `antigravity` (→ ~/.gemini/antigravity-cli/).
