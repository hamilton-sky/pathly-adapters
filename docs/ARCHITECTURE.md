# Pathly Adapters Architecture

pathly-adapters installs Pathly agent and skill files into AI host tools (Claude
Code, Codex, Copilot). It owns the stitch pipeline, host detection, resource
loading, and the `pathly-setup` CLI.

## Package Layout

```text
pathly-adapters/                 ← pip package: pathly-adapters (CLI: pathly-setup)
│
├── core/                        ← SINGLE SOURCE OF TRUTH (tool-agnostic)
│   ├── agents/                  ← Agent behavior contracts (.md — no spawning syntax)
│   │   ├── architect.md
│   │   ├── builder.md
│   │   ├── director.md
│   │   ├── orchestrator.md
│   │   ├── planner.md
│   │   ├── po.md
│   │   ├── quick.md
│   │   ├── reviewer.md
│   │   ├── scout.md
│   │   ├── tester.md
│   │   └── web-researcher.md
│   ├── skills/                  ← Skill logic in natural language (tool-agnostic .md)
│   │   ├── team-flow.md
│   │   ├── explore.md
│   │   ├── build.md
│   │   ├── review.md
│   │   ├── storm.md
│   │   └── ...
│   └── templates/               ← Plan file templates (PROGRESS, USER_STORIES, etc.)
│       └── plan/
│
├── adapters/                    ← Thin tool-specific wrappers
│   ├── claude/                  ← .claude-plugin/ + _meta/*.yaml per agent/skill
│   ├── codex/                   ← .codex-plugin/ + _meta/*.yaml per agent/skill
│   └── copilot/                 ← _meta/*.yaml per agent/skill
│
└── install_cli/                 ← Python CLI: detects host tools, stitches + deploys files
    ├── detect.py                ← Discovers installed AI tools
    ├── stitch.py                ← Combines core/ + adapter _meta/ into deployable files
    ├── materialize.py           ← Writes output files to ~/.claude/, ~/.codex/, etc.
    └── setup_command.py         ← Entry point for pathly-setup command
```

## Adapter Surfaces Per Host

| Host | User surface | Source files | Installed destination |
|---|---|---|---|
| Claude Code | `/pathly ...`, `/go ...` | `adapters/claude/_meta/` | `~/.claude/agents/`, `~/.claude/skills/` |
| Codex | `Use Pathly ...` natural-language plugin skills | `adapters/codex/_meta/` | `~/.codex/agents/`, `~/.codex/skills/` |
| Copilot | Copilot-native skill invocation | `adapters/copilot/_meta/` | VS Code agents folder |

Current Codex builds do not expose Pathly as `/pathly`. Use natural-language
skill prompts in Codex.

## Skills vs Agents

| | Agent | Skill |
|---|---|---|
| **What it is** | Role/persona with behavior contract | User-invocable workflow command |
| **Who triggers it** | Orchestrator or other agents | User directly (`/skill-name`) |
| **Lives in** | `core/agents/` | `core/skills/` |
| **Format** | Markdown behavior contract | SKILL.md (YAML frontmatter + instructions) |
| **Example** | builder, reviewer, scout | /team-flow, /explore, /review |

## Stitch Pipeline

`core/` is content, not runtime code. `install_cli/` stitches `core/` content
with adapter `_meta/*.yaml` files at install time and deploys the result to the
host tool's config directory.

```
pathly-setup
        │
        ├── detect.py detects which tools are installed
        │
        ├── stitch.py merges core/ + adapters/<tool>/_meta/*.yaml
        │       into deployable agent and skill files
        │
        ├── materialize.py writes stitched files:
        │   ├── adapters/claude/_meta/**  ──────► ~/.claude/agents/ + ~/.claude/skills/
        │   ├── adapters/codex/_meta/**   ──────► ~/.codex/agents/ + ~/.codex/skills/
        │   └── adapters/copilot/_meta/** ──────► Copilot workspace config
        │
        └── setup_command.py is the CLI entry point (registered as `pathly-setup`)
```

For Claude Code: stitched files include Agent() spawn calls, deployed to `~/.claude/`.
For Codex: stitched files use natural language skill prompts, deployed to `~/.codex/`.
For Copilot: stitched files use Copilot-compatible format, deployed to workspace config.

## install_cli Module Summary

| Module | Purpose |
|---|---|
| `install_cli/detect.py` | Discovers which AI tools (Claude Code, Codex, Copilot) are installed |
| `install_cli/stitch.py` | Merges `core/` content with adapter `_meta/*.yaml` into deployable files |
| `install_cli/materialize.py` | Writes stitched output to `~/.claude/`, `~/.codex/`, etc. A manifest tracks Pathly-owned files; `--repair` overwrites owned files, `--force` overwrites everything. Install is atomic — if anything fails, already-written files are rolled back. |
| `install_cli/setup_command.py` | CLI entry point registered as `pathly-setup` |
| `core/` | Source-of-truth agent contracts, skill logic, plan templates — never edited by install |
| `adapters/` | Per-tool YAML metadata (`_meta/`) and plugin manifests |

## Host Detection

`detect.py` discovers installed AI tools by checking for their config directories:

| Host | Detected by |
|---|---|
| `claude` | `~/.claude/` directory exists |
| `codex` | Codex config directory exists |
| `copilot` | VS Code + Copilot detected |

## Cross-Tool Compatibility

| Feature | Claude Code | Codex | Copilot |
|---|---|---|---|
| Agent behavior contracts | ✓ via ~/.claude/agents/ | ✓ via ~/.codex/agents/ | ✓ via AGENTS.md standard |
| Skills (SKILL.md) | ✓ native | ✓ native | ✓ native (Aug 2025) |
| Subagent spawning | Agent() tool | Agents SDK (MCP) | /fleet, /delegate |
| Natural language activation | /go skill + director | natural language | natural language |

**Key constraint:** Subagent spawning syntax is tool-specific. There is no universal standard.

**Solution (thin adapters):** `core/skills/` contains the skill *logic* in natural language.
Each adapter's `_meta/*.yaml` adds only the tool-specific spawn call on top:

```
# core/skills/team-flow.md
Delegate implementation to the builder agent.
Then delegate review to the reviewer agent.

# adapters/claude/_meta/go_skill.yaml  (adds Agent() spawn calls for Claude Code)
Spawn Agent(subagent_type="builder") for implementation.
Spawn Agent(subagent_type="reviewer") for review.
```

## Installed Manifests

- Claude plugin manifest: `adapters/claude/.claude-plugin/plugin.json`
- Codex plugin manifest: `adapters/codex/.codex-plugin/plugin.json`
- Public Codex marketplace metadata: `.agents/plugins/marketplace.json`

There is no root `.codex-plugin/` directory. Root `.agents/` is marketplace
metadata only; there is no `.agents/skills/` directory.

## pathly-setup Commands

```bash
pathly-setup                        # detect hosts; no writes
pathly-setup --dry-run              # preview what would be written
pathly-setup --apply                # install into all detected hosts
pathly-setup claude --apply         # install for Claude Code only
pathly-setup codex --apply          # install for Codex only
pathly-setup copilot --apply        # install for Copilot / VS Code only
pathly-setup --repair               # overwrite Pathly-owned files
pathly-setup --force                # overwrite all files, even non-Pathly-owned
pathly-setup --uninstall            # remove all Pathly-owned files
```

`--dry-run` never writes. `--apply` is required for any writes.

## What Gets Installed

For Claude Code:

```
~/.claude/
├── agents/                    ← 11 behavioral contracts (.md files)
├── skills/                    ← installed Claude Code lifecycle skills
└── plugins/pathly/
    └── templates/pathly plan/
        └── *.template.md
```

## User-Level Data Locations

| Platform | User-level Pathly data |
|---|---|
| Windows | `%LOCALAPPDATA%\Pathly\` or `%APPDATA%\Pathly\` |
| macOS/Linux | XDG-compatible data directory |
| Project state | Always under the active project `plans/` directory |

## Source of Truth

- Shared workflow behavior belongs in `core/skills/`.
- Shared role behavior belongs in `core/agents/`.
- Plan file structure belongs in `core/templates/plan/`.
- Host metadata belongs under the matching adapter in `adapters/<tool>/_meta/`.
- Python runtime code belongs in `install_cli/`, not in `core/`.

Adapters should stay thin. They load or wrap core content, add host-specific
metadata, and expose the host-native invocation style.

## Future Adapter Work

Cursor, Windsurf, BMAD chat modes, and generic copy-paste prompt packs remain
planned work. Add them only when there is real demand, keeping the same rule:
core owns reusable behavior, adapters own packaging.

```text
adapters/
|-- cursor/
|-- windsurf/
|-- bmad/
`-- generic/
```
