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

Then open Claude Code in your project directory and start:

```
/pathly start            ← welcome screen + pick what to do
/pathly go               ← describe what you want; director routes it
/pathly build            ← implement next conversation
/pathly end              ← retro + archive
```

All commands go through `/pathly`. See `/pathly help` for the full command list.

## All commands

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

## Supported Hosts

| Host | Detected by | Installed locations |
|------|-------------|---------------------|
| `claude` | `~/.claude/` directory exists | `~/.claude/agents/` + `~/.claude/skills/` |
| `codex` | Codex config directory exists | `~/.codex/agents/` + `~/.codex/skills/` |
| `copilot` | VS Code + Copilot detected | VS Code agents folder |

## How It Works

1. **Detect** — scans for installed hosts on the current machine.
2. **Stitch** — combines `core/agents/` and `core/skills/` content with adapter-specific `_meta/*.yaml` to produce deployable agent and skill files (frontmatter + body + spawn section).
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

## Known Limitations

- **Windows: broken stub if you previously ran `pip install pathly-adapters` directly** — a bare `pip install` (outside pipx) leaves a `pathly-setup.exe` stub in the global Python Scripts directory that shadows the pipx version and throws `ModuleNotFoundError: No module named 'install_cli'`. Fix: delete the stub at `%LOCALAPPDATA%\Programs\Python\Python3XX\Scripts\pathly-setup.exe` and its matching `~athly_adapters-*.dist-info` folder in `site-packages`, then open a fresh terminal. Always use `pipx install pathly-adapters` as documented.

- **Codex install unverified on a clean machine** — the Codex adapter is committed and `pathly-setup codex --apply` runs without error, but a full clean-machine smoke test has not been completed. Use Codex support at your own risk until this is confirmed.

- **Copilot paths may need `--repair` after a VS Code update** — Pathly installs agent files to the VS Code Copilot agent spec path, which may change between VS Code versions. Run `pathly-setup --repair` after a VS Code update if Copilot agents stop appearing.

- **Hook path validation requires Python 3.9+** — hook scripts use `Path.is_relative_to()`, introduced in Python 3.9. The project already requires Python 3.11+, so this is always satisfied.

- **Hooks require `PATHLY_PROJECT_ROOT`** — hook scripts (`classify_feedback.py`, `inject_feedback_ttl.py`) read the `PATHLY_PROJECT_ROOT` environment variable to locate the active project's `plans/` directory. If this variable is not set, hooks exit immediately without performing any action.
