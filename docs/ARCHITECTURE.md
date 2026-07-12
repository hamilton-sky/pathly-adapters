# Pathly Adapters Architecture

> **New here? Read [WHAT_IS_PATHLY.md](WHAT_IS_PATHLY.md) first** — it states Pathly's primary goal (board-driven *headless* multi-agent orchestration) and the board concept, with diagrams. This document covers only the **install/adapter surface**, which is one layer of the product, not its purpose.
>
> Scope: runtime adapter surfaces and install pipeline. For package layout and install/publish details see `PATHLY_ARCHITECTURE.md`. Version: **2.20.0**.

pathly-adapters installs Pathly agent and skill files into AI host tools (Claude
Code, Codex, Copilot, Antigravity). It owns the stitch pipeline, host detection,
resource loading, the `pathly-setup` CLI, and the local Pathly Studio desktop UI.

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
│       │   ├── agents/          ← Agent behavior contracts (.md — no spawning syntax), grouped by function
│       │   │   ├── building/    ← builder.md, designer.md
│       │   │   ├── planning/    ← architect.md, planner.md, po.md
│       │   │   ├── quality/     ← reviewer.md, tester.md
│       │   │   ├── research/    ← scout.md, explorer.md, web-researcher.md, evaluator.md
│       │   │   ├── support/     ← orchestrator.md, quick.md, human.md
│       │   │   ├── director.md  ← top-level router (not grouped)
│       │   │   └── README_routing.md  ← routing guide (not deployed)
│       │   ├── skills/          ← Skill logic in natural language, grouped by category
│       │   │   ├── controls/    ← start, go, ff, back, pause, end, status, pathly
│       │   │   ├── development/ ← build, review, test, design, debug, explore, fix, quick-fix, …
│       │   │   ├── planning/    ← plan, po, prd-import, storm, retro, evaluate, consolidate,
│       │   │   │                   feature-decompose, project-decompose, goalize, …
│       │   │   ├── team/        ← team, discover, plan, design, architect, research, build, review, test, retro
│       │   │   ├── utilities/   ← archive, log, log-agent-done, fsm-call, scout-path, reflect, commit, …
│       │   │   ├── fix/         ← fix variants
│       │   │   ├── custom/      ← user-defined skills
│       │   │   ├── debug/       ← debug-specific skills
│       │   │   └── fragments/   ← reusable prompt fragments (board CRUD, context retrieval, completion)
│       │   ├── flows/           ← Flow YAML definitions (team.flow.yaml, team-build.flow.yaml,
│       │   │                       consultation/feature-consultation/project-consultation.flow.yaml,
│       │   │                       debug.flow.yaml, explore.flow.yaml, test.flow.yaml, quick-fix.flow.yaml)
│       │   ├── design/          ← UI/UX design subsystem (data/ CSVs, scripts/, cli.py) — powers `pathly-design`
│       │   └── templates/       ← Plan file templates (PROGRESS, USER_STORIES, etc.)
│       │       └── plan/
│       └── adapters/            ← Thin tool-specific wrappers
│           ├── claude/          ← .claude-plugin/ + _meta/*.yaml per agent/skill
│           ├── codex/           ← .codex-plugin/ + _meta/*.yaml per agent/skill
│           ├── copilot/         ← _meta/*.yaml per agent/skill
│           └── antigravity/     ← _meta/*.yaml per agent/skill (Gemini models)
│
└── src/pathly_orchestrator/     ← FSM event-log module (internal, src-layout package)
```

## Adapter Surfaces Per Host

| Host | User surface | Source files | Installed destination |
|---|---|---|---|
| Claude Code | `/pathly ...`, `/go ...` | `src/pathly_data/adapters/claude/_meta/` | `~/.claude/agents/`, `~/.claude/skills/` |
| Codex | `Use Pathly ...` natural-language plugin skills | `src/pathly_data/adapters/codex/_meta/` | `~/.codex/agents/`, `~/.agents/skills/`, plugin bundle/cache |
| Copilot | Copilot-native skill invocation | `src/pathly_data/adapters/copilot/_meta/` | VS Code agents folder |
| Antigravity | `/pathly ...` slash commands (Gemini CLI layout) | `src/pathly_data/adapters/antigravity/_meta/` | `~/.gemini/antigravity-cli/agents/`, `~/.gemini/antigravity-cli/skills/` |

Current Codex builds do not expose Pathly as `/pathly`. Use natural-language
skill prompts in Codex. Antigravity model names (`gemini-2.5-pro`, `gemini-2.5-flash`)
are placeholders until live model availability is verified against the installed binary.

## Skills vs Agents

| | Agent | Skill |
|---|---|---|
| **What it is** | Role/persona with behavior contract | User-invocable workflow command |
| **Who triggers it** | Orchestrator or other agents | User directly (`/skill-name`) |
| **Lives in** | `core/agents/` | `core/skills/` |
| **Format** | Markdown behavior contract | SKILL.md (YAML frontmatter + instructions) |
| **Example** | builder, reviewer, scout | /team, /explore, /review |

## Skill Delivery — Two Modes

How a skill's prompt reaches the CLI depends on which runtime drives it:

| Mode | Trigger | How the prompt reaches the CLI | Skill files on disk? |
|---|---|---|---|
| **Runner (primary)** | Studio **Start** / a goal run | the supervisor assembles the full composed prompt (skill body + fragments) and injects it via `-p` argv | No — assembled in Python at runtime |
| **Interactive (secondary)** | user types `/pathly build` | the host reads the installed `~/.claude/skills/pathly-*.md` | Yes — `pathly-setup claude --apply` |

In runner mode Pathly is the single source of truth for skill content; the CLI receives the complete prompt as an argument and exits when done.

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
        │   ├── src/pathly_data/adapters/claude/_meta/**       ──► ~/.claude/agents/ + ~/.claude/skills/
        │   ├── src/pathly_data/adapters/codex/_meta/**        ──► ~/.codex/agents/ + ~/.agents/skills/
        │   ├── src/pathly_data/adapters/copilot/_meta/**      ──► Copilot workspace config
        │   └── src/pathly_data/adapters/antigravity/_meta/**  ──► ~/.gemini/antigravity-cli/agents/ + skills/
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
| `src/pathly_studio_cli/` | `pathly-studio` launcher and local Studio install helpers |
| `src/pathly_data/core/` | Source-of-truth agent contracts, skill logic, plan templates — never edited by install |
| `src/pathly_data/adapters/` | Per-tool YAML metadata (`_meta/`) and plugin manifests |
| `src/pathly_orchestrator/` | FSM engine package. `http_server/` (blueprint package) exposes `/next_action`, `/complete_stage`, `/record_activity`, `/events/stream` over HTTP (port 8765). Also implements `pathly-events`, `pathly-state`, and `pathly-validate-flow` CLI entry points. |
| `src/pathly_hooks/` | Hook scripts (`classify_feedback.py`, `inject_feedback_ttl.py`) deployed by install into host tool settings. |

## Host Detection

`detect.py` discovers installed AI tools by checking for their config directories:

| Host | Detected by |
|---|---|
| `claude` | `~/.claude/` directory exists |
| `codex` | Codex config directory exists |
| `copilot` | VS Code + Copilot detected |
| `antigravity` | `~/.gemini/antigravity-cli/` directory exists |

## Cross-Tool Compatibility

| Feature | Claude Code | Codex | Copilot | Antigravity |
|---|---|---|---|---|
| Agent behavior contracts | ✓ via ~/.claude/agents/ | ✓ via ~/.codex/agents/ | ✓ via AGENTS.md standard | ✓ via ~/.gemini/antigravity-cli/agents/ |
| Skills (SKILL.md) | ✓ native | ✓ native | ✓ native (Aug 2025) | ✓ via slash commands |
| Subagent spawning | Agent() tool | Named role when exposed; otherwise current-agent execution | /fleet, /delegate | role delegation (Gemini layout) |
| Natural language activation | /go skill + director | natural language | natural language | /pathly + director |

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
- Claude marketplace metadata: `src/pathly_data/adapters/claude/.claude-plugin/marketplace.json`
- Codex plugin manifest: `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`

There is no repository-root `.codex-plugin/` directory. Repository-root
`.agents/` is empty (reserved); installed Codex skills are written to
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

## Pathly Studio Runtime Surface

`studio/` is the local desktop UI for the same project-local Pathly artifacts
that the host skills use. It does not replace the adapters; it reads and writes
the same plan files, flow YAMLs, and FSM event streams.

Current major panes:

| Pane | Runtime source |
|---|---|
| Flow Editor | visual canvas + raw YAML tab; save via `PUT /flows/<name>`; export to `pathly-package`, `claude-code`, or `codex` targets |
| Canvas | bundled `src/pathly_data/core/flows/*.flow.yaml` plus editable user flow files |
| Plan | project-local `pathly/features/**` artifacts (legacy `pathly/plans/**` still resolved) |
| Monitor | `pathly-fsm-http` SSE stream from `/events/stream` |
| Conductor | chat target routing for Claude, Codex, and shell terminals |
| Terminal | Electron PTY IPC exposed through `window.pathly.terminal` |
| Runner / HQ | FlowControlBar **Start** → `POST /runner/start` → the supervisor drives the FSM headlessly, spawning each stage as a **visible PTY tab** (the primary runtime surface) |
| Command Center / Board | the supervisory board — goals → per-goal task-DAG → pluggable executors (`single`/`loop`/`team`); a human sets goals and adjudicates while the app drives agents headlessly |

Terminal ownership is shared by `studio/src/renderer/src/components/Terminal/xtermRegistry.ts`.
The full bottom terminal and Conductor mini terminal card reparent one xterm
instance per `tabId`; they do not spawn duplicate PTYs. Hiding a card or tab view
keeps the process alive. Bin actions kill the PTY, dispose the shared xterm, and
remove the terminal tab. The full terminal exposes a hamburger-controlled
instance rail for focusing, hiding, and killing terminal instances.

## User-Level Data Locations

| Platform | User-level Pathly data |
|---|---|
| Windows | `%LOCALAPPDATA%\Pathly\` or `%APPDATA%\Pathly\` |
| macOS/Linux | XDG-compatible data directory |
| Project state | Always under the active project `pathly/` directory (feature files under `pathly/features/<name>/`; legacy `pathly/plans/<name>/` still resolved) |

## Flow YAMLs

Flows are fully user-definable. `src/pathly_data/core/flows/` ships nine reference flows, but users can create any number of custom flows with any stages in any order.

| Flow | File | States | Used for |
|---|---|---|---|
| `team` | `team.flow.yaml` | STORMING → PLANNING → DESIGNING → BUILDING → REVIEWING → TESTING → RETRO → DONE | Full feature pipeline |
| `team-build` | `team-build.flow.yaml` | BUILDING → REVIEWING → TESTING → RETRO → DONE | Trimmed team flow used by the goal `team` executor |
| `debug` | `debug.flow.yaml` | INVESTIGATING → REPRODUCING → ROOT_CAUSE_FOUND → FIXING → VERIFYING → DONE | Bug investigation |
| `explore` | `explore.flow.yaml` | FRAMING → ANALYZING → TRACING → CONCLUDING → DONE | Codebase exploration |
| `test` | `test.flow.yaml` | STORMING → PLANNING → BUILDING → REVIEWING → TESTING → DONE | Lightweight build+test pipeline (no retro/archive) |
| `quick-fix` | `quick-fix.flow.yaml` | SCOPING → FIXING → VERIFYING → DONE | nano/lite fast path |
| `consultation` | `consultation.flow.yaml` | PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → NO_DAG_SEEDED → DONE | Goal decompose (PO→architect→researcher→designer→planner) |
| `feature-consultation` | `feature-consultation.flow.yaml` | PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → NO_GOALS_SEEDED → DONE | Feature→goals decomposer |
| `project-consultation` | `project-consultation.flow.yaml` | PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → NO_FEATURES_SEEDED → DONE | Project spec→features decomposer |

Each flow YAML specifies: `states`, `transitions`, `agent_map`, `role_map`, `feedback_routing`, `transition_rules`, `transition_actions`, and an optional `adapter_map` for routing stages to different CLI adapters.

`transition_actions` are skills the orchestrator spawns automatically at specific state transitions (e.g., `commit` on `BUILDING->REVIEWING`, `archive-artifacts` on `RETRO->DONE`). These are transparent to the user.

**Creating custom flows:** write a `.flow.yaml` file and place it in `src/pathly_data/core/flows/` (bundled) or export it from Studio to `.claude/pathly-flows/` / `.codex/pathly-flows/` (project-local). The FSM server loads flows from the DB on startup and falls back to disk files if not found.

## Database

The FSM server persists state in SQLite at `~/.pathly/pathly.db`.

| Table | Purpose |
|---|---|
| `flow_definitions` | Full flow YAML content indexed by name. Refreshed from disk on every server start. `PUT /flows/<name>` writes both DB and disk (write-through). |
| `flow_nodes` | Per-node config (reserved — unused, for future visual flow builder) |
| `flow_edges` | Per-edge config (reserved — unused, for future visual flow builder) |

**Connection model:** each Flask thread gets its own `sqlite3.Connection` via `threading.local()`. WAL mode means readers never block writers. A background daemon thread checkpoints the WAL file every 30 seconds.

## Board→Goals→Task-DAG Executor Model

The runtime orchestration layer now extends beyond `transition_actions` auto-spawning. The comms board (`comms_messages` + `comms_artifacts` tables, `/comms/*` routes) acts as the live orchestration substrate:

- **Goals** are top-level intent records; each goal owns a Task-DAG (`goal_id` column on tasks). `GET /comms/goals` is the read-model — goals plus their per-goal task-DAG rollup.
- **Executors** (`single` / `loop` / `team`) are pluggable per goal and drive how tasks are dispatched (`supervisor/goal_executor.py`; `supervisor/goal_run.py` is a thin re-export shim over `goal_executor.py` + `goal_decomposer.py`).
- **Decomposers** turn intent into a Task-DAG or sub-goals: `planning/feature-decompose` (feature → goals) and `planning/project-decompose` (project spec → sibling features), dispatched via the `feature-consultation` / `project-consultation` FSM flows.
- **Per-goal adapter selection** routes each goal's execution to a specific CLI adapter (Claude, Codex, Antigravity, etc.).
- **Context-retrieval** (`context_refs` + `/comms/artifacts/<id>/section` hydration, Board Catalog, opt-in summarizer) injects relevant board context into every agent prompt.
- **Code intelligence** (`POST /code/query`) proxies codebase-structure questions to `codebase-memory-mcp` (the sole code-intel backend; the earlier `gitnexus` tool has been removed).
- **Memory consolidation** (`/comms/consolidate`) deduplicates and merges near-duplicate notes.
- **Goal-stop** (`POST /comms/goals/stop`) terminates an in-progress goal run.

`transition_actions` auto-spawning remains the baseline for flow-driven pipelines; the Board executor model is the layer above it for board-driven (headless-supervised) and multi-goal orchestration.

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

Note: `antigravity/` is already shipped — it is not a future item.
