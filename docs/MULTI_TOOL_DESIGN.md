# Multi-Tool Architecture Design

Pathly is no longer a Claude-only file layout. The current repository already
uses a core-plus-adapters structure so the same workflow contracts can be
packaged for Claude Code, Codex, the Python CLI, and future hosts.

## Current Structure

```text
pathly-adapters/                 ← repo root (single package)
├── src/
│   ├── install_cli/             ← Python CLI: detect, stitch, setup_command
│   ├── pathly_orchestrator/     ← FSM event-log module (internal, src-layout package)
│   ├── pathly_hooks/            ← Hook scripts deployed by installer into host tool settings
│   └── pathly_data/             ← installed package data
│       ├── core/                ← single source of truth (tool-agnostic)
│       │   ├── agents/
│       │   ├── skills/
│       │   └── templates/plan/
│       └── adapters/            ← thin tool-specific wrappers
│           ├── claude/
│           ├── codex/
│           └── copilot/
├── docs/
└── pyproject.toml
```

## Source Of Truth

- Shared workflow behavior belongs in `src/pathly_data/core/skills/`.
- Shared role behavior belongs in `src/pathly_data/core/agents/`.
- Plan file structure belongs in `src/pathly_data/core/templates/plan/`.
- Host metadata belongs under the matching adapter in `src/pathly_data/adapters/<tool>/_meta/`.
- Python runtime code belongs in `src/install_cli/`, not in `core/`.

Adapters should stay thin. They load or wrap core content, add host-specific
metadata, and expose the host-native invocation style.

## Current Adapters

| Adapter | User invocation | Files |
|---|---|---|
| Claude Code | `/pathly <request>` or `/path <request>` (slash commands) | `src/pathly_data/adapters/claude/` |
| Codex | `Use Pathly <request>` or `Pathly <request>` (natural language) | `src/pathly_data/adapters/codex/` |
| Copilot | Version-dependent; agent files as custom instructions | `src/pathly_data/adapters/copilot/` |

## Installed Manifests

- Claude plugin manifest: `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`
- Codex plugin manifest: `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`
- Public Codex marketplace metadata: `.agents/plugins/marketplace.json`

There is no root `.codex-plugin/` directory in the current repository. Root
`.agents/` is marketplace metadata only; there is no `.agents/skills/` directory.

## Future Adapter Work

Cursor, Windsurf, BMAD chat modes, and generic copy-paste prompt packs remain
planned work. Add them only when there is real demand, and keep the same rule:
core owns reusable behavior, adapters own packaging.

Suggested future layout:

```text
src/pathly_data/adapters/
|-- cursor/
|-- windsurf/
|-- bmad/
`-- generic/
```

## Release Guidance

Do not describe future adapters as shipped. Current public positioning should
remain: Pathly is a public beta candidate with Claude Code, Codex, direct skill,
and CLI surfaces available, while additional adapters are roadmap items.
