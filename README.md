# pathly-adapters

Stitches Pathly agent files and installs them into AI host tools (Claude Code, Codex, Copilot).

## Install (end users)

Requires Python 3.11+. Install [pipx](https://pipx.pypa.io) if you don't have it:

```bash
pip install pipx
pipx ensurepath
```

Then install Pathly:

```bash
pipx install pathly-adapters
```

`pipx` keeps the package in its own isolated environment and puts `pathly-setup` on your PATH automatically — no virtual environment to manage, no activation step.

## Quick start

```bash
pathly-setup --dry-run    # preview what will be installed
pathly-setup --apply      # install into all detected hosts
```

That's it. Pathly detects Claude Code, Codex, and Copilot automatically.

## All commands

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

## Supported Hosts

| Host | Detected by | Default destination |
|------|-------------|---------------------|
| `claude` | `~/.claude/` directory exists | `~/.claude/agents/` |
| `codex` | Codex config directory exists | `~/.codex/agents/` |
| `copilot` | VS Code + Copilot detected | VS Code agents folder |

## How It Works

1. **Detect** — scans for installed hosts on the current machine.
2. **Stitch** — combines `core/agents/<name>.md` with adapter-specific `_meta/<name>.yaml` to produce the final agent file (frontmatter + body + spawn section).
3. **Materialize** — writes stitched files to the host config location. A manifest tracks Pathly-owned files; `--repair` overwrites owned files, `--force` overwrites everything. Install is atomic — if anything fails, already-written files are rolled back.

## Development setup

```bash
git clone <repo>
cd pathly-adapters
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
pytest
```

To build and publish a new release:

```bash
python -m build
twine upload dist/*
```

## Docs

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Adapter surfaces per host (Claude, Codex, Copilot), deployment structure, how skills/agents are materialized, host detection, installed manifests |
| [docs/FLOW_DIAGRAM.md](docs/FLOW_DIAGRAM.md) | How a user invokes Pathly from each host, install flow, what files get deployed where, host-specific entry points |
| [docs/PATHLY_ARCHITECTURE.md](docs/PATHLY_ARCHITECTURE.md) | install_cli packages, pathly_data layout, stitch pipeline, resource loading, host adapter structure, pyproject entry points |
| [docs/INSTALLER_DESIGN.md](docs/INSTALLER_DESIGN.md) | Design goals, implementation phases, subagent policy, user stories, main risks |
| [docs/MULTI_TOOL_DESIGN.md](docs/MULTI_TOOL_DESIGN.md) | Current adapter structure, source-of-truth rules, current adapters, installed manifests, future adapter work |
| [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) | Adapter release criteria: install checks for each host, pathly-setup flags, package build/publish, marketplace manifests |
| [docs/SECURITY.md](docs/SECURITY.md) | Hook injection risks, subprocess calls in installer, file write safety, trust boundaries, marketplace manifest integrity |
| [docs/SYSTEM_REVIEW.md](docs/SYSTEM_REVIEW.md) | Adapter strengths, risks, design decisions, hardening recommendations |

For engine-specific docs (FSM, orchestrator, state machine, team-flow driver):
see [github.com/hamilton-sky/pathly](https://github.com/hamilton-sky/pathly) — `pathly-engine/docs/` folder.

## Release Status

Stable (1.0.0). Core install path (`--dry-run`, `--apply`, `--uninstall`) is verified with full rollback on failure. Copilot destination paths follow the VS Code Copilot agent spec and may require `--repair` after a VS Code update.
