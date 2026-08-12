# Pathly Adapters Architecture

> **Scope:** Install and package layout — the `pathly-adapters` pip package, its stitch
> pipeline, and the `pathly_data` resource layout. For runtime adapter surfaces (how skills
> and agents are exposed per host), see [ARCHITECTURE.md](ARCHITECTURE.md).
> For the full command reference and invocation examples, see [FLOW_DIAGRAM.md](FLOW_DIAGRAM.md).
>
> Canonical reference for the pathly-adapters package.
> Reflects decisions made after the May 2026 architecture review.

---

## What pathly-adapters Is

pathly-adapters installs Pathly agent and skill files into AI host tools. It
provides:
- **`src/pathly_data/core/`** — single source of truth for agent contracts, skill logic, and plan templates
- **`src/pathly_data/adapters/`** — thin per-host wrappers with YAML metadata
- **`src/install_cli/`** — stitch pipeline and `pathly-setup` CLI
- **`src/pathly_data/`** — package resource layout for installed data files
- **`src/pathly_telemetry/`** — cross-host activity telemetry (`pathly-tokens` command), inside `src/`

- **`src/pathly_studio_cli/`** - `pathly-studio` launcher and Studio install helpers
- **`studio/`** - Electron UI for Canvas, Plan, Monitor, Conductor, and Terminal

The user installs Pathly once. After that, they interact with their AI coding
tool normally — the tool reads Pathly's agents and skills transparently.

> **This doc covers the install/package layer only — not Pathly's purpose.** Pathly's primary
> runtime is **board-driven headless orchestration**: a human supervises through the Studio
> board (the Command Center) while the app drives agents headlessly, step by step. The
> install / transparent-augmentation path described here is the **interactive (secondary)**
> affordance. See [WHAT_IS_PATHLY.md](WHAT_IS_PATHLY.md).

---

## Folder Structure

```
pathly-adapters/                 ← pip package: pathly-adapters
│                                   installs via: pip install -e ".[dev]"
│                                   CLI entries: pathly-setup, pathly-tokens, pathly-events, pathly-state
│
├── src/
│   ├── install_cli/             ← Python CLI: detects host tools, stitches + deploys files
│   │   ├── detect.py            ← Discovers installed AI tools
│   │   ├── stitch.py            ← Combines core/ + adapter _meta/ into deployable files
│   │   ├── materialize.py       ← Writes output files to ~/.claude/, ~/.codex/, etc.
│   │   ├── setup_command.py     ← Entry point for pathly-setup command
│   │   ├── codex_plugin_config.py ← Codex local marketplace registration and plugin config
│   │   ├── resources.py
│   │   └── __main__.py
│   ├── pathly_telemetry/        ← Cross-host activity telemetry (pathly-tokens CLI)
│   ├── pathly_orchestrator/     ← FSM event-log package (pathly-events, pathly-state CLIs)
│   ├── pathly_hooks/            ← Hook scripts deployed into host tool settings by installer
│   └── pathly_data/             ← Package resource layout for installed data files
│       ├── core/                ← SINGLE SOURCE OF TRUTH (tool-agnostic)
│       │   ├── agents/          ← Agent behavior contracts (.md — no spawning syntax), grouped by function
│       │   │   ├── building/    ← builder.md, designer.md (designer: UI/UX design spec generation, used by /design skill)
│       │   │   ├── planning/    ← architect.md, planner.md, po.md
│       │   │   ├── quality/     ← reviewer.md, tester.md
│       │   │   ├── research/    ← scout.md, explorer.md (analyze/explore/conclude phases), web-researcher.md, evaluator.md
│       │   │   ├── support/     ← orchestrator.md, quick.md, human.md (blocks pipeline until user responds — HUMAN_QUESTIONS)
│       │   │   ├── director.md  ← top-level router (not grouped)
│       │   │   └── README_routing.md  ← routing guide (not deployed)
│       │   ├── skills/          ← Skill logic in natural language, grouped by category
│       │   │   ├── controls/    ← start, go, ff, back, pause, end, status, pathly
│       │   │   ├── development/ ← build, review, test, design, debug, explore, fix, quick-fix,
│       │   │   │                   execute-task, drain-dag, analyze, split, summarize (+ -gist / -detailed), commit
│       │   │   ├── planning/    ← plan, po, prd-import, storm, retro, evaluate, consolidate,
│       │   │   │                   create-feature, dag-sketch, feature-decompose, project-decompose, goalize
│       │   │   ├── team/        ← team, discover, plan, design, architect, research, build, review, test, retro
│       │   │   ├── utilities/   ← archive, archive-artifacts, log, log-agent-done, log-phase, lessons, meet,
│       │   │   │                   verify-state, fsm-call, scout-path, reflect, dispatch, help
│       │   │   ├── fix/         ← fix (blocked-feedback quick fix)
│       │   │   ├── custom/      ← user-defined custom skills
│       │   │   ├── debug/       ← debug-specific skills (build, verify)
│       │   │   └── fragments/   ← reusable prompt fragments (board CRUD, context retrieval, completion reporting)
│       │   ├── flows/           ← FSM flow definitions: team.flow.yaml, team-build.flow.yaml,
│       │   │                       consultation.flow.yaml, feature-consultation.flow.yaml, project-consultation.flow.yaml,
│       │   │                       debug.flow.yaml, explore.flow.yaml, test.flow.yaml, quick-fix.flow.yaml
│       │   ├── design/          ← UI/UX design subsystem (data/ CSVs, scripts/, cli.py) — powers `pathly-design`
│       │   └── templates/       ← Plan file templates (PROGRESS, USER_STORIES, etc.)
│       │       └── plan/
│       └── adapters/            ← Thin tool-specific wrappers
│           ├── claude/          ← .claude-plugin/ + _meta/*.yaml per agent/skill
│           ├── codex/           ← .codex-plugin/ + _meta/*.yaml per agent/skill
│           ├── copilot/         ← _meta/*.yaml per agent/skill
│           └── antigravity/     ← _meta/*.yaml per agent/skill (Gemini models)
│
└── pyproject.toml               ← entry_points: pathly-setup, pathly-tokens, pathly-events, pathly-state,
                                                  pathly-fsm-http, pathly-fsm-call, pathly-validate-flow,
                                                  pathly-run, pathly-status, pathly-log, pathly-back,
                                                  pathly-ff, pathly-studio, pathly-design, pathly-otel-export
```

---

## Python Package Layout

The repository uses a `src/` layout. The source packages are:

| Package | Path | Purpose |
|---|---|---|
| `install_cli` | `src/install_cli/` | Install CLI — `pathly-setup` entry point and stitch pipeline |
| `pathly_telemetry` | `src/pathly_telemetry/` | Telemetry — `pathly-tokens` entry point |
| `pathly_data` | `src/pathly_data/` | Installed package data — agent contracts, skill logic, adapter metadata |
| `pathly_orchestrator` | `src/pathly_orchestrator/` | FSM event-log — `pathly-events`, `pathly-state`, and `pathly-validate-flow` entry points; loads and validates `*.flow.yaml` files |
| `pathly_hooks` | `src/pathly_hooks/` | Hook scripts deployed into host tool settings by installer |

Entry points are declared in `pyproject.toml`. `src/install_cli/` contains the
CLI implementation modules (`detect.py`, `stitch.py`, `materialize.py`, `orchestrate.py`, `setup_command.py`, `codex_plugin_config.py`, `resources.py`, `__main__.py`).

---

## install_cli Modules

| Module | Purpose |
|---|---|
| `src/install_cli/detect.py` | Discovers which AI tools (Claude Code, Codex, Copilot, Antigravity) are installed by checking for their config directories |
| `src/install_cli/stitch.py` | Merges `core/` content with adapter `_meta/*.yaml` into deployable agent and skill files |
| `src/install_cli/materialize.py` | Writes stitched output to `~/.claude/`, `~/.codex/`, etc. Maintains a manifest of Pathly-owned files. Install is atomic — already-written files are rolled back if anything fails. |
| `src/install_cli/setup_command.py` | CLI entry point logic. Handles `--dry-run`, `--apply`, `--repair`, `--force`, `--uninstall`, and per-host subcommands. |
| `src/install_cli/codex_plugin_config.py` | Registers the Codex local marketplace and plugin configuration. |
| `src/install_cli/resources.py` | Package resource loading helpers |
| `src/install_cli/__main__.py` | Entry point registered as `pathly-setup` |
| `src/pathly_studio_cli/` | `pathly-studio` launcher and local Studio install helpers |

---

## pathly_data Layout

`src/pathly_data/` is the installed package data. Resources are loaded through the
package's internal resource API rather than repo-relative path assumptions.

- `src/pathly_data/core/agents/` — `.md` files (tool-agnostic agent contracts), grouped into `building/`, `planning/`, `quality/`, `research/`, `support/` subdirectories plus top-level `director.md`
- `src/pathly_data/core/skills/` — `.md` files (tool-agnostic skill logic), grouped by category subdirectory
- `src/pathly_data/core/templates/plan/` — `.template.md` files
- `src/pathly_data/adapters/claude/` — `.claude-plugin/plugin.json` + `_meta/` per-agent and per-skill `.yaml` files
- `src/pathly_data/adapters/codex/` — `.codex-plugin/plugin.json` + `_meta/`
- `src/pathly_data/adapters/copilot/` — `_meta/`
- `src/pathly_data/adapters/antigravity/` — `_meta/` (Gemini models: `gemini-2.5-pro` / `gemini-2.5-flash`)

---

## Flow YAMLs

`src/pathly_data/core/flows/` contains the FSM definitions consumed by the orchestrator at runtime. There are nine flows:

| Flow | File | Storage path | States |
|---|---|---|---|
| `team` | `team.flow.yaml` | `pathly/features/{topic}/` | PLANNING → DESIGNING → BUILDING → REVIEWING → TESTING → RETRO → DONE |
| `team-build` | `team-build.flow.yaml` | `pathly/{topic}/` | BUILDING → REVIEWING → TESTING → RETRO → DONE |
| `debug` | `debug.flow.yaml` | `pathly/debugs/{topic}/` | INVESTIGATING → REPRODUCING → ROOT_CAUSE_FOUND → FIXING → VERIFYING → DONE |
| `explore` | `explore.flow.yaml` | `pathly/explorations/{topic}/` | FRAMING → ANALYZING → TRACING → CONCLUDING → DONE |
| `test` | `test.flow.yaml` | `pathly/features/{topic}/` | STORMING → PLANNING → BUILDING → REVIEWING → TESTING → DONE |
| `quick-fix` | `quick-fix.flow.yaml` | `pathly/fixes/{topic}/` | SCOPING → FIXING → VERIFYING → DONE |
| `consultation` | `consultation.flow.yaml` | `pathly/{topic}/` | PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → NO_DAG_SEEDED → DONE |
| `feature-consultation` | `feature-consultation.flow.yaml` | `pathly/{topic}/` | PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → NO_GOALS_SEEDED → DONE |
| `project-consultation` | `project-consultation.flow.yaml` | `pathly/project/` | PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → NO_FEATURES_SEEDED → DONE |

Each YAML specifies: `version`, `flow`, `storage_path`, `states`, `transitions`, `agent_map`, `feedback_routing`, `transition_rules`, and `transition_actions`.

**transition_actions** are skills the orchestrator automatically spawns at specific state transitions:

```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - skill: commit
      message: "feat: complete building stage"
  "RETRO->DONE":
    - skill: archive-artifacts
```

Flow YAMLs are tool-agnostic — they live in `core/` and are not adapter-specific. The orchestrator agent reads them at spawn time via the `flow_config` input.

---

## Stitch Pipeline

`src/pathly_data/core/` is content, not runtime code. `stitch.py` merges `core/` content with
adapter `_meta/*.yaml` files and produces deployable files:

```
stitch.py:
  input:  src/pathly_data/core/agents/builder.md          (role contract — no spawning syntax)
          src/pathly_data/adapters/claude/_meta/builder.yaml  (adds Agent() spawn calls + frontmatter)
  output: deployable builder.md for Claude Code
            = frontmatter from yaml
            + body from core/
            + spawn section from yaml
```

`src/pathly_data/core/skills/` contains skill *logic* in natural language. Each adapter's
`_meta/*.yaml` adds only the tool-specific invocation:

```
# src/pathly_data/core/skills/team-flow.md
Delegate implementation to the builder agent.
Then delegate review to the reviewer agent.

# src/pathly_data/adapters/claude/_meta/go_skill.yaml  (adds Agent() spawn calls for Claude Code)
Spawn Agent(subagent_type="builder") for implementation.
Spawn Agent(subagent_type="reviewer") for review.
```

This keeps `core/` host-neutral. A new host adapter only needs new `_meta/` files.

> **The fragments layer (the Pathly connection).** Skill bodies in `core/skills/` are the
> **agnostic task** ("what to do"). ALL connection to Pathly — board CRUD, context retrieval,
> progress logging, completion reporting, delegation — lives in the un-editable **fragments**
> (`core/skills/fragments/`), composed onto skill bodies by `composition.yaml` + `compose.py`.
> `_meta/*.yaml` adds host-specific invocation; the fragments add the board connection. See
> `src/pathly_data/CLAUDE.md` › Skill composition.

---

## Host Adapter Structure

### Claude

```
src/pathly_data/adapters/claude/
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
src/pathly_data/adapters/codex/
├── .codex-plugin/
│   └── plugin.json         ← Codex plugin manifest
├── SKILL_EXECUTION.md      ← host contract for role directions in skills
└── _meta/
    ├── builder.yaml        ← natural-language format (no slash commands)
    └── ...
```

Stitched output → `~/.codex/agents/` + `~/.agents/skills/` + plugin bundle/cache
Role execution: use a named Pathly role only when callable in the active
Codex session; otherwise run the lifecycle role in the current agent, with
generic delegation used only when requested and permitted.

### Copilot

```
src/pathly_data/adapters/copilot/
└── _meta/
    └── ...                 ← Copilot-compatible format
```

Stitched output → VS Code agents folder
Subagent spawning syntax: `/fleet`, `/delegate`

### Antigravity

```
src/pathly_data/adapters/antigravity/
└── _meta/
    ├── builder.yaml        ← Gemini CLI slash-command format
    └── ...                 ← one yaml per agent and skill (Gemini models: gemini-2.5-pro / gemini-2.5-flash)
```

Stitched output → `~/.gemini/antigravity-cli/agents/` + `~/.gemini/antigravity-cli/skills/`
Subagent spawning syntax: role delegation (Gemini CLI layout)

---

## Installed Manifests

- Claude plugin manifest: `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`
- Claude marketplace metadata: `src/pathly_data/adapters/claude/.claude-plugin/marketplace.json`
- Codex plugin manifest: `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`

There is no root `.codex-plugin/` directory. Root `.agents/` is empty (reserved).

---

## pyproject Entry Points

```toml
[project.scripts]
pathly-setup         = "install_cli.__main__:main"
pathly-tokens        = "pathly_telemetry.report:main"
pathly-events        = "pathly_orchestrator.eventlog:_cli"
pathly-state         = "pathly_orchestrator.eventlog:_state_cli"
pathly-fsm-http      = "pathly_orchestrator.http_server:main"
pathly-fsm-call      = "pathly_orchestrator.fsm_cli:main"
pathly-validate-flow = "pathly_orchestrator.fsm.state:validate_flow_cli"
pathly-run           = "pathly_orchestrator.runner:main"
pathly-status        = "pathly_orchestrator.cli.status:main"
pathly-log           = "pathly_orchestrator.cli.log:main"
pathly-back          = "pathly_orchestrator.cli.back:main"
pathly-ff            = "pathly_orchestrator.cli.ff:main"
pathly-studio        = "pathly_studio_cli.install:main"
pathly-design        = "pathly_data.core.design.cli:main"
pathly-otel-export   = "pathly_orchestrator.otel_export:cli_main"
```

---

## Resource Loading

Assets (agent .md files, skill .md files, adapter yaml, plugin manifests) are
loaded through the package's internal resource API. This ensures commands work
from an installed wheel, not just from the source checkout:

```python
# correct — works from installed wheel
from importlib.resources import files
data = files("pathly_data").joinpath("core/agents/building/builder.md").read_text()  # package name, not path

# wrong — breaks outside source checkout
path = Path(__file__).parent.parent / "core" / "agents" / "building" / "builder.md"
```

---

## Source of Truth Rules

- Shared workflow behavior: `src/pathly_data/core/skills/`
- Shared role behavior: `src/pathly_data/core/agents/`
- Plan file structure: `src/pathly_data/core/templates/plan/`
- Host metadata: `src/pathly_data/adapters/<tool>/_meta/`
- Python runtime code: `src/install_cli/` (never in `core/`)

`src/pathly_data/core/` content is never edited by install. `materialize.py` only writes to
host config locations. Source files in `src/pathly_data/core/` and `src/pathly_data/adapters/`
are read-only from the installer's perspective.
