# Pathly Core

This folder is the tool-agnostic source of truth for Pathly workflow content.

Core files describe what Pathly knows and how workflows behave. They should not
depend on Claude Code slash-command syntax, Codex plugin metadata, or any other
host-specific packaging format.

Adapters turn this core into tool-specific experiences:

- Claude Code commands and skills
- Codex plugin skills
- CLI commands
- future Cursor, Windsurf, BMAD, or generic prompt packs

Current status: `core/` contains canonical prompt and agent contract copies.
Adapter folders own host-specific wrappers. For Codex, install-time stitching
generates user-level skills under `~/.agents/skills/` from core content plus
`adapters/codex/` metadata and execution instructions.

## Repository Boundaries

Keep shared, host-neutral behavior in `core/`. Keep files that package, install,
test, or execute Pathly in their own top-level folders.

```text
pathly/
|-- core/          # shared prompts, workflow contracts, agent specs, templates
|-- adapters/      # host-specific packaging for Codex, Claude Code, CLI, etc.
|-- .agents/       # Codex marketplace metadata when a repo marketplace is shipped
|-- pathly/        # Python CLI package
|-- orchestrator/  # filesystem state machine/runtime code
|-- tests/         # automated quality gates
|-- docs/          # design, readiness, and review notes
`-- examples/      # sample Pathly project artifacts
```

The target direction is:

- `core/` owns canonical behavior and reusable content.
- `adapters/` wrap `core/` for each host tool.
- Codex installation generates `~/.agents/skills/` rather than maintaining a
  second source copy of each skill in this repository.

Do not move install scripts, tests, Python package files, or runtime code into
`core/` unless `core/` is deliberately redesigned as a runtime package.
