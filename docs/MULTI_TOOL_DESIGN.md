# Multi-Tool Architecture Design

Pathly is no longer a Claude-only file layout. The current repository already
uses a core-plus-adapters structure so the same workflow contracts can be
packaged for Claude Code, Codex, the Python CLI, and future hosts.

## Current Structure

```text
pathly/                              ← monorepo root
|-- pathly-adapters/                 ← pip package: pathly-adapters (CLI: pathly-setup)
|   |-- core/                        ← single source of truth (tool-agnostic)
|   |   |-- agents/                  ← 11 agent behavior contracts
|   |   |-- skills/                  ← 19 skill definitions
|   |   `-- templates/plan/          ← plan file templates
|   |-- adapters/                    ← thin tool-specific wrappers
|   |   |-- claude/                  ← .claude-plugin/ + _meta/*.yaml
|   |   |-- codex/                   ← .codex-plugin/ + _meta/*.yaml
|   |   `-- copilot/                 ← _meta/*.yaml
|   |-- install_cli/                 ← Python installer CLI
|   `-- pathly_telemetry/            ← cross-host activity telemetry
|-- pathly-engine/                   ← pip package: pathly-engine (CLI: pathly)
|   |-- orchestrator/                ← pure FSM library
|   |-- runners/                     ← subprocess runners (claude, codex)
|   |-- team_flow/                   ← Python driver
|   `-- engine_cli/                  ← CLI entry point
|-- .agents/                         ← Codex marketplace metadata only
|   `-- plugins/marketplace.json
|-- docs/                            ← architecture, readiness, and review notes
|-- tests/                           ← integration tests
`-- README.md
```

## Source Of Truth

- Shared workflow behavior belongs in `pathly-adapters/core/skills/`.
- Shared role behavior belongs in `pathly-adapters/core/agents/`.
- Plan file structure belongs in `pathly-adapters/core/templates/plan/`.
- Host metadata belongs under the matching adapter in `pathly-adapters/adapters/<tool>/_meta/`.
- Python runtime code belongs in `pathly-engine/` or `pathly-adapters/install_cli/`, not in `core/`.

Adapters should stay thin. They load or wrap core content, add host-specific
metadata, and expose the host-native invocation style.

## Current Adapters

| Adapter | User invocation | Files |
|---|---|---|
| Claude Code | `/pathly <request>` or `/path <request>` (slash commands) | `pathly-adapters/adapters/claude/` |
| Codex | `Use Pathly <request>` or `Pathly <request>` (natural language) | `pathly-adapters/adapters/codex/` |
| Copilot | Version-dependent; agent files as custom instructions | `pathly-adapters/adapters/copilot/` |
| CLI | `pathly <command>` terminal commands | `pathly-engine/engine_cli/` |

## Installed Manifests

- Claude plugin manifest: `pathly-adapters/adapters/claude/.claude-plugin/plugin.json`
- Codex plugin manifest: `pathly-adapters/adapters/codex/.codex-plugin/plugin.json`
- Public Codex marketplace metadata: `.agents/plugins/marketplace.json`

There is no root `.codex-plugin/` directory in the current repository. Root
`.agents/` is marketplace metadata only; there is no `.agents/skills/` directory.

## Future Adapter Work

Cursor, Windsurf, BMAD chat modes, and generic copy-paste prompt packs remain
planned work. Add them only when there is real demand, and keep the same rule:
core owns reusable behavior, adapters own packaging.

Suggested future layout:

```text
adapters/
|-- cursor/
|-- windsurf/
|-- bmad/
`-- generic/
```

## Release Guidance

Do not describe future adapters as shipped. Current public positioning should
remain: Pathly is a public beta candidate with Claude Code, Codex, direct skill,
and CLI surfaces available, while additional adapters are roadmap items.
