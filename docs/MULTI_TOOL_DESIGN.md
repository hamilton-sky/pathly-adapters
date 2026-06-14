# Multi-Tool Architecture Design

Pathly is no longer a Claude-only file layout. The current repository already
uses a core-plus-adapters structure so the same workflow contracts can be
packaged for Claude Code, Codex, the Python CLI, and future hosts.
Pathly Studio is the local desktop surface over the same project files and FSM
HTTP runtime; it is not a separate workflow source of truth.

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
│           ├── copilot/
│           └── antigravity/
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
| Codex | `Use Pathly <request>` or `Pathly <request>` (natural language) plus `pathly-fsm-call` for HTTP lifecycle steps | `src/pathly_data/adapters/codex/` |
| Copilot | Version-dependent; agent files as custom instructions | `src/pathly_data/adapters/copilot/` |
| Antigravity | `/pathly <request>` slash commands (Gemini CLI layout); models: `gemini-2.5-pro` / `gemini-2.5-flash` | `src/pathly_data/adapters/antigravity/` |

## Studio Surface

Studio uses the same core runtime rather than defining another adapter:

- Canvas reads bundled `src/pathly_data/core/flows/*.flow.yaml`.
- Plan reads and writes project-local `pathly/plans/**` files.
- Monitor consumes `pathly-fsm-http` events.
- Conductor routes chat work to Claude, Codex, or shell targets.
- Terminal uses `window.pathly.terminal` and a shared `xtermRegistry` so the
  chat mini terminal and full terminal reparent one xterm instance per `tabId`.

The terminal control contract is consistent across surfaces: X hides a view and
keeps the PTY alive; the bin icon kills/disposes/removes the terminal instance.

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

Current public positioning: Pathly ships four adapters — Claude Code, Codex,
Copilot, and Antigravity (Gemini CLI). Do not describe Cursor, Windsurf, BMAD,
or generic adapters as shipped; those remain roadmap items.
