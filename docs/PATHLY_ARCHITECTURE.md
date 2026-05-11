# Pathly Adapters Architecture

> Canonical reference for the pathly-adapters package.
> Reflects decisions made after the May 2026 architecture review.

---

## What pathly-adapters Is

pathly-adapters installs Pathly agent and skill files into AI host tools. It
provides:
- **`core/`** — single source of truth for agent contracts, skill logic, and plan templates
- **`adapters/`** — thin per-host wrappers with YAML metadata
- **`install_cli/`** — stitch pipeline and `pathly-setup` CLI
- **`pathly_data/`** — package resource layout for installed data files
- **`pathly_telemetry/`** — cross-host activity telemetry (`pathly-tokens` command)

The user installs Pathly once. After that, they interact with their AI coding
tool normally — the tool reads Pathly's agents and skills transparently.

---

## Folder Structure

```
pathly-adapters/                 ← pip package: pathly-adapters
│                                   installs via: pip install -e pathly-adapters/
│                                   CLI entries: pathly-setup, pathly-tokens
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
├── install_cli/                 ← Python CLI: detects host tools, stitches + deploys files
│   ├── detect.py                ← Discovers installed AI tools
│   ├── stitch.py                ← Combines core/ + adapter _meta/ into deployable files
│   ├── materialize.py           ← Writes output files to ~/.claude/, ~/.codex/, etc.
│   └── setup_command.py         ← Entry point for pathly-setup command
│
├── pathly_telemetry/            ← Cross-host activity telemetry
│
└── pyproject.toml               ← entry_points: pathly-setup, pathly-tokens
```

---

## install_cli Modules

| Module | Purpose |
|---|---|
| `detect.py` | Discovers which AI tools (Claude Code, Codex, Copilot) are installed by checking for their config directories |
| `stitch.py` | Merges `core/` content with adapter `_meta/*.yaml` into deployable agent and skill files |
| `materialize.py` | Writes stitched output to `~/.claude/`, `~/.codex/`, etc. Maintains a manifest of Pathly-owned files. Install is atomic — already-written files are rolled back if anything fails. |
| `setup_command.py` | CLI entry point registered as `pathly-setup`. Handles `--dry-run`, `--apply`, `--repair`, `--force`, `--uninstall`, and per-host subcommands. |

---

## pathly_data Layout

`pathly_data/` is the installed package data. Resources are loaded through the
package's internal resource API rather than repo-relative path assumptions.

```
pathly_data/
├── core/
│   ├── agents/          ← .md files (tool-agnostic contracts)
│   ├── skills/          ← .md files (tool-agnostic skill logic)
│   └── templates/plan/  ← .template.md files
└── adapters/
    ├── claude/
    │   ├── .claude-plugin/plugin.json
    │   └── _meta/       ← per-agent and per-skill .yaml files
    ├── codex/
    │   ├── .codex-plugin/plugin.json
    │   └── _meta/
    └── copilot/
        └── _meta/
```

---

## Stitch Pipeline

`core/` is content, not runtime code. `stitch.py` merges `core/` content with
adapter `_meta/*.yaml` files and produces deployable files:

```
stitch.py:
  input:  core/agents/builder.md          (role contract — no spawning syntax)
          adapters/claude/_meta/builder.yaml  (adds Agent() spawn calls + frontmatter)
  output: deployable builder.md for Claude Code
            = frontmatter from yaml
            + body from core/
            + spawn section from yaml
```

`core/skills/` contains skill *logic* in natural language. Each adapter's
`_meta/*.yaml` adds only the tool-specific invocation:

```
# core/skills/team-flow.md
Delegate implementation to the builder agent.
Then delegate review to the reviewer agent.

# adapters/claude/_meta/go_skill.yaml  (adds Agent() spawn calls for Claude Code)
Spawn Agent(subagent_type="builder") for implementation.
Spawn Agent(subagent_type="reviewer") for review.
```

This keeps `core/` host-neutral. A new host adapter only needs new `_meta/` files.

---

## Host Adapter Structure

### Claude

```
adapters/claude/
├── .claude-plugin/
│   └── plugin.json         ← Claude Code plugin manifest
└── _meta/
    ├── builder.yaml        ← frontmatter + spawn section for builder
    ├── reviewer.yaml
    └── ...                 ← one yaml per agent and skill
```

Stitched output → `~/.claude/agents/` + `~/.claude/skills/`
Subagent spawning syntax: `Agent(subagent_type="builder")`

### Codex

```
adapters/codex/
├── .codex-plugin/
│   └── plugin.json         ← Codex plugin manifest
└── _meta/
    ├── builder.yaml        ← natural-language format (no slash commands)
    └── ...
```

Stitched output → `~/.codex/agents/` + `~/.codex/skills/`
Subagent spawning syntax: Agents SDK (MCP)

### Copilot

```
adapters/copilot/
└── _meta/
    └── ...                 ← Copilot-compatible format
```

Stitched output → VS Code agents folder
Subagent spawning syntax: `/fleet`, `/delegate`

---

## Installed Manifests

- Claude plugin manifest: `adapters/claude/.claude-plugin/plugin.json`
- Codex plugin manifest: `adapters/codex/.codex-plugin/plugin.json`
- Public Codex marketplace metadata: `.agents/plugins/marketplace.json`

There is no root `.codex-plugin/` directory. Root `.agents/` is marketplace
metadata only.

---

## pyproject Entry Points

```toml
[project.scripts]
pathly-setup = "pathly_adapters.install_cli.setup_command:main"
pathly-tokens = "pathly_adapters.pathly_telemetry.cli:main"
```

---

## Resource Loading

Assets (agent .md files, skill .md files, adapter yaml, plugin manifests) are
loaded through the package's internal resource API. This ensures commands work
from an installed wheel, not just from the source checkout:

```python
# correct — works from installed wheel
from importlib.resources import files
data = files("pathly_data").joinpath("core/agents/builder.md").read_text()

# wrong — breaks outside source checkout
path = Path(__file__).parent.parent / "core" / "agents" / "builder.md"
```

---

## Source of Truth Rules

- Shared workflow behavior: `core/skills/`
- Shared role behavior: `core/agents/`
- Plan file structure: `core/templates/plan/`
- Host metadata: `adapters/<tool>/_meta/`
- Python runtime code: `install_cli/` (never in `core/`)

`core/` content is never edited by install. `materialize.py` only writes to
host config locations. Source files in `core/` and `adapters/` are read-only
from the installer's perspective.
