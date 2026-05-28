# Pathly Adapters Architecture

pathly-adapters installs Pathly agent and skill files into AI host tools (Claude
Code, Codex, Copilot). It owns the stitch pipeline, host detection, resource
loading, and the `pathly-setup` CLI.

## Package Layout

```text
pathly-adapters/                 ← pip package: pathly-adapters (CLI: pathly-setup)
│
├── src/
│   ├── install_cli/             ← Python CLI: detects host tools, stitches + deploys files
│   │   ├── detect.py            ← Discovers installed AI tools
│   │   ├── stitch.py            ← Combines core/ + adapter _meta/ into deployable files
│   │   ├── materialize.py       ← Writes output files to ~/.claude/, ~/.codex/, etc.
│   │   ├── setup_command.py     ← Entry point for pathly-setup command
│   │   ├── resources.py
│   │   └── __main__.py
│   └── pathly_data/
│       ├── core/                ← SINGLE SOURCE OF TRUTH (tool-agnostic)
│       │   ├── agents/          ← Agent behavior contracts (.md — no spawning syntax)
│       │   │   ├── architect.md
│       │   │   ├── builder.md
│       │   │   ├── designer.md
│       │   │   ├── director.md
│       │   │   ├── explorer.md
│       │   │   ├── human.md
│       │   │   ├── orchestrator.md
│       │   │   ├── planner.md
│       │   │   ├── po.md
│       │   │   ├── quick.md
│       │   │   ├── README_routing.md  ← routing guide (not deployed)
│       │   │   ├── reviewer.md
│       │   │   ├── scout.md
│       │   │   ├── tester.md
│       │   │   └── web-researcher.md
│       │   ├── skills/          ← Skill logic in natural language (tool-agnostic .md)
│       │   │   ├── team.md      ← full pipeline entry point
│       │   │   ├── explore.md
│       │   │   ├── build.md
│       │   │   ├── review.md
│       │   │   ├── storm.md
│       │   │   ├── po.md        ← product owner consultation
│       │   │   ├── scout-path.md
│       │   │   ├── fsm-call.md  ← internal utility: HTTP transport to FSM server (shared)
│       │   │   ├── commit.md    ← transition-action skill (orchestrator only)
│       │   │   ├── archive-artifacts.md  ← transition-action skill (orchestrator only)
│       │   │   └── ...          (29 user-facing + 2 transition-action skills total)
│       │   ├── flows/           ← Flow YAML definitions (team.flow.yaml, debug.flow.yaml, explore.flow.yaml)
│       │   └── templates/       ← Plan file templates (PROGRESS, USER_STORIES, etc.)
│       │       └── plan/
│       └── adapters/            ← Thin tool-specific wrappers
│           ├── claude/          ← .claude-plugin/ + _meta/*.yaml per agent/skill
│           ├── codex/           ← .codex-plugin/ + _meta/*.yaml per agent/skill
│           └── copilot/         ← _meta/*.yaml per agent/skill
│
└── src/pathly_orchestrator/     ← FSM event-log module (internal, src-layout package)
```

## Adapter Surfaces Per Host

| Host | User surface | Source files | Installed destination |
|---|---|---|---|
| Claude Code | `/pathly ...`, `/go ...` | `src/pathly_data/adapters/claude/_meta/` | `~/.claude/agents/`, `~/.claude/skills/` |
| Codex | `Use Pathly ...` natural-language plugin skills | `src/pathly_data/adapters/codex/_meta/` | `~/.codex/agents/`, `~/.agents/skills/`, plugin bundle/cache |
| Copilot | Copilot-native skill invocation | `src/pathly_data/adapters/copilot/_meta/` | VS Code agents folder |

Current Codex builds do not expose Pathly as `/pathly`. Use natural-language
skill prompts in Codex.

## Skills vs Agents

| | Agent | Skill |
|---|---|---|
| **What it is** | Role/persona with behavior contract | User-invocable workflow command |
| **Who triggers it** | Orchestrator or other agents | User directly (`/skill-name`) |
| **Lives in** | `core/agents/` | `core/skills/` |
| **Format** | Markdown behavior contract | SKILL.md (YAML frontmatter + instructions) |
| **Example** | builder, reviewer, scout | /team, /explore, /review |

## Stitch Pipeline

`core/` is content, not runtime code. `src/install_cli/` stitches `core/` content
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
        │   ├── src/pathly_data/adapters/claude/_meta/**  ──────► ~/.claude/agents/ + ~/.claude/skills/
        │   ├── src/pathly_data/adapters/codex/_meta/**   ──────► ~/.codex/agents/ + ~/.agents/skills/
        │   └── src/pathly_data/adapters/copilot/_meta/** ──────► Copilot workspace config
        │
        └── setup_command.py is the CLI entry point (registered as `pathly-setup`)
```

For Claude Code: stitched files include Agent() spawn calls, deployed to `~/.claude/`.
For Codex: stitched files use natural language skill prompts, deployed to `~/.codex/`.
For Copilot: stitched files use Copilot-compatible format, deployed to workspace config.

## install_cli Module Summary

| Module | Purpose |
|---|---|
| `src/install_cli/detect.py` | Discovers which AI tools (Claude Code, Codex, Copilot) are installed |
| `src/install_cli/stitch.py` | Merges `core/` content with adapter `_meta/*.yaml` into deployable files |
| `src/install_cli/materialize.py` | Writes stitched output to `~/.claude/`, `~/.codex/`, etc. A manifest tracks Pathly-owned files; `--repair` overwrites owned files, `--force` overwrites everything. Install is atomic — if anything fails, already-written files are rolled back. |
| `src/install_cli/setup_command.py` | CLI entry point registered as `pathly-setup` |
| `src/install_cli/codex_plugin_config.py` | Codex local marketplace registration and plugin config |
| `src/pathly_data/core/` | Source-of-truth agent contracts, skill logic, plan templates — never edited by install |
| `src/pathly_data/adapters/` | Per-tool YAML metadata (`_meta/`) and plugin manifests |
| `src/pathly_orchestrator/` | FSM engine package. `http_server.py` exposes `/next_action`, `/complete_stage`, `/record_activity`, `/events/stream` over HTTP (port 8765). Also implements `pathly-events`, `pathly-state`, and `pathly-validate-flow` CLI entry points. |
| `src/pathly_hooks/` | Hook scripts (`classify_feedback.py`, `inject_feedback_ttl.py`) deployed by install into host tool settings. |

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
| Subagent spawning | Agent() tool | Named role when exposed; otherwise current-agent execution or permitted generic delegation | /fleet, /delegate |
| Natural language activation | /go skill + director | natural language | natural language |

**Key constraint:** Subagent spawning syntax is tool-specific. There is no universal standard.

**Solution (thin adapters):** `src/pathly_data/core/skills/` contains the skill *logic* in natural language.
Each adapter renders that intent into behavior supported by its host. For Codex,
the generated skill prepends `adapters/codex/SKILL_EXECUTION.md`, which treats
named role invocation as optional and falls back to executing the lifecycle
role in the current agent:

```
# src/pathly_data/core/skills/team.md
Delegate implementation to the builder agent.
Then delegate review to the reviewer agent.

# src/pathly_data/adapters/claude/_meta/go_skill.yaml  (adds Agent() spawn calls for Claude Code)
Spawn Agent(subagent_type="builder") for implementation.
Spawn Agent(subagent_type="reviewer") for review.
```

## Installed Manifests

- Claude plugin manifest: `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`
- Codex plugin manifest: `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`
- Public Codex marketplace metadata: `.agents/plugins/marketplace.json`

There is no repository-root `.codex-plugin/` directory. Repository-root
`.agents/` is marketplace metadata only; installed Codex skills are written to
the user-level `~/.agents/skills/` directory.

## pathly-setup Commands

```bash
pathly-setup                        # detect hosts; launch interactive menu
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
├── agents/          ← behavioral contracts (.md files)
├── skills/          ← skill directories (one folder per sub-skill, each with SKILL.md)
└── plugins/pathly/
    └── templates/pathly plan/
```

See [FLOW_DIAGRAM.md](FLOW_DIAGRAM.md) for the full command reference and deployed file details.

## User-Level Data Locations

| Platform | User-level Pathly data |
|---|---|
| Windows | `%LOCALAPPDATA%\Pathly\` or `%APPDATA%\Pathly\` |
| macOS/Linux | XDG-compatible data directory |
| Project state | Always under the active project `plans/` directory |

## Flow YAMLs

`src/pathly_data/core/flows/` contains three FSM definition files consumed by the orchestrator:

| Flow | File | States | Used for |
|---|---|---|---|
| `team` | `team.flow.yaml` | IDLE → STORMING → PLANNING → BUILDING → REVIEWING → TESTING → RETRO → DONE | Full feature pipeline |
| `debug` | `debug.flow.yaml` | INVESTIGATING → REPRODUCING → ROOT_CAUSE_FOUND → FIXING → VERIFYING → DONE | Bug investigation |
| `explore` | `explore.flow.yaml` | FRAMING → ANALYZING → TRACING → CONCLUDING → DONE | Codebase exploration |
| `test` | `test.flow.yaml` | STORMING → PLANNING → BUILDING → REVIEWING → TESTING → DONE | Lightweight build+test pipeline (no retro/archive) |

Each flow YAML specifies: `states`, `transitions`, `agent_map`, `feedback_routing`, `transition_rules`, and `transition_actions`.

`transition_actions` are skills the orchestrator spawns automatically at specific state transitions (e.g., `commit` on `BUILDING->REVIEWING`, `archive-artifacts` on `RETRO->DONE`). These are transparent to the user.

## Source of Truth

- Shared workflow behavior belongs in `src/pathly_data/core/skills/`.
- Shared role behavior belongs in `src/pathly_data/core/agents/`.
- Plan file structure belongs in `src/pathly_data/core/templates/plan/`.
- Host metadata belongs under the matching adapter in `src/pathly_data/adapters/<tool>/_meta/`.
- Python runtime code belongs in `src/install_cli/`, not in `core/`.

Adapters should stay thin. They load or wrap core content, add host-specific
metadata, and expose the host-native invocation style.

## Future Adapter Work

Cursor, Windsurf, BMAD chat modes, and generic copy-paste prompt packs remain
planned work. Add them only when there is real demand, keeping the same rule:
core owns reusable behavior, adapters own packaging.

```text
src/pathly_data/adapters/
|-- cursor/
|-- windsurf/
|-- bmad/
`-- generic/
```
