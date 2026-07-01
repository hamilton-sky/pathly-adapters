# Pathly Adapters — Claude Code Context

## What this repo is

`pathly-adapters` is the monorepo for the **Pathly AI development framework**:
- Python package (`pathly-adapters` v2.16.x) — FSM orchestrator, telemetry, install CLI
- Electron app (`studio/`) — the supervisory **board / Command Center** through which a human drives *headless* multi-agent runs (the visual flow builder + AI chat panel are surfaces within it)
- Agent/skill source (`src/pathly_data/`) — canonical role contracts, skill markdown, adapter configs

Features move through: **STORM → PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE**

## Primary goal — read this first

**Pathly is a board-driven control plane for orchestrating *headless* multi-agent software development.** A human supervises through the visual **board** (the Command Center) — setting goals, answering questions, adjudicating decisions — while the **app drives agents headlessly**, one step at a time, with **no human in the per-step loop** (`human` target in headless mode is an error). Interactive `/pathly` slash-commands are a **secondary** affordance, not the design center.

The board is the substrate (goals → task-DAG → artifacts/decisions → context, read back into every prompt). Agents connect to Pathly through **fragments** — the un-editable system-prompt layer (`core/skills/fragments/`) that owns all board CRUD, context retrieval, progress logging, and completion. The standing direction is that **every prompt Pathly sends to a CLI should flow through fragments**.

Full narrative + diagrams: [docs/WHAT_IS_PATHLY.md](docs/WHAT_IS_PATHLY.md). When writing docs/READMEs, lead with this headless-board framing, not the installer/interactive framing.

---

## Layer files — read these for layer-specific detail

| Layer | File | Covers |
|---|---|---|
| Frontend (Electron/React) | [studio/CLAUDE.md](studio/CLAUDE.md) | TypeScript config, typecheck commands, IPC pattern, build artifacts |
| Data & Adapters | [src/pathly_data/CLAUDE.md](src/pathly_data/CLAUDE.md) | Core→adapter sync rule, agents, skills, templates, design subsystem |
| FSM / Orchestrator | [src/pathly_orchestrator/CLAUDE.md](src/pathly_orchestrator/CLAUDE.md) | HTTP server, state machine, curl commands, CLI shortcuts |

---

## Pipeline architecture

```
User → /pathly <cmd>           skills (installed at ~/.claude/skills/pathly-*)
     → pathly-fsm MCP server   HTTP FSM at http://127.0.0.1:8765
     → Agent(subagent_type=…)  Claude Code sub-agents (architect, builder, reviewer, …)
     → pathly/features/<feature>/plans/  filesystem state (legacy: pathly/plans/<feature>/)

Studio → Start button          FlowControlBar → POST /runner/start
       → supervisor/            drives FSM + spawns agents as visible terminals
       → TERMINAL_SPAWN SSE    Studio opens a PTY tab (node-pty) per pipeline stage
       → terminal:spawn IPC    argv injected from adapters.yaml headless template, e.g.
                               claude: ['claude', '-p', '{prompt}', '--model', '{model}', '--output-format', 'json', '--dangerously-skip-permissions']
                               codex:  ['codex', 'exec', '--sandbox', 'workspace-write', '--model', '{model}', '--', '{prompt}']
       → PTY exits             POST /runner/terminal/result → FSM continues
     → EVENTS.jsonl         Claude writes AGENT_DONE with `summary` mid-run; supervisor reads it after PTY exits as the authoritative semantic result (stdout only used for session_id + cost_usd)
```

**Adapter install step:** `pathly-setup <host> --apply` stitches `core/agents/` and `core/skills/` with adapter-specific `_meta/*.yaml` files and writes deployable files to the host's install directory. Four adapters: `claude` → `~/.claude/`, `codex` → `~/.codex/` + `~/.agents/`, `copilot` → `~/.vscode/extensions/pathly/`, `antigravity` → `~/.gemini/antigravity-cli/`.

**Skill delivery — two modes:**

| Mode | Trigger | How prompt reaches CLI | Skill files needed on disk? |
|---|---|---|---|
| **Interactive** | User types `/pathly build` | CLI reads `~/.claude/skills/pathly-build.md` | Yes — run `pathly-setup claude --apply` |
| **Runner** | Studio Start button | `supervisor/` injects full prompt via `-p` argv | No — prompt assembled in Python at runtime |

In runner mode Pathly is the single source of truth for skill content. The CLI receives the complete prompt as a command-line argument and exits when done — it never reads a skill file.

**Dash-safety:** prompts delivered via CLI argv must never start with `---` (claude parses it as an unknown option). Three mirror implementations enforce this: `_dash_safe_prompt` in `src/pathly_orchestrator/adapters.py` (applied in `resolve_command`); `_strip_leading_frontmatter` in `src/pathly_orchestrator/skills/compose.py` (applied during skill composition); and `dashSafePrompt` in `studio/src/renderer/src/services/cliEngine.ts` (applied in `buildHeadlessArgv`).

**Studio CLI spawn scheduler (`studio/src/main/ipc/terminal.ts`):** a dual-cap concurrency gate controls how many CLI engine processes run simultaneously. Default caps: global ≤ 8, headless ≤ 5, interactive ≤ 5 (all configurable at runtime via the SpawnQueuePanel). Headless one-shots are queued (FIFO + priority); interactive sessions are rejected over cap with a toast. On Windows, headless argv is encoded as a PowerShell temp-script; `codex` headless additionally pipes `$null` as stdin to prevent it stalling on terminal input.

**FSM response contract (`agent_hint`):** Every `/next_action` response includes:
- `agent_hint.role` — `"worker"` or `"explorer"` (host-neutral delegation signal)
- `agent_hint.instructions` — full prompt for the next agent (Pathly role, phase, artifacts, limits)
- `AGENT_DONE.summary` in EVENTS.jsonl — authoritative semantic result text (not truncated by PTY buffer); `--output-format=json` stdout is only used for `session_id` and `cost_usd`
- `decision` — `"continue"` / `"block"` / `"escalate"` (automation gate)
- `codex_subagent` — legacy compat field with frozen keys; new adapters should read `agent_hint`

**Agent roles** (full definitions in `src/pathly_data/core/agents/`):

| Role | Model | Job |
|---|---|---|
| director | sonnet | routes intent, chooses rigor |
| architect | opus | technical design |
| planner | sonnet | user stories, conversation breakdown |
| po | opus | interactive requirements / scope discussion |
| builder | sonnet | implementation |
| reviewer | sonnet | adversarial review → REVIEW_FAILURES.md |
| tester | sonnet | acceptance criteria → TEST_FAILURES.md |
| designer | sonnet | UI/UX design systems |
| explorer | sonnet | traces code paths, structural questions |
| web-researcher | sonnet | external knowledge gathering |
| quick / scout | haiku | fast lookups |
| orchestrator | haiku | deterministic FSM recovery |
| human | — | placeholder for human-in-the-loop steps |

**Rigor levels:** `nano` (1 conv, no review/test) · `lite` (plan+build) · `standard` (full pipeline) · `strict` (standard + audit)

---

## Comms board (orchestration substrate)

A DB-backed message board (`comms_messages` + `comms_artifacts` tables, `/comms/*` routes) where agents and humans post decisions, discoveries, artifacts, and DAG tasks. It is the Studio **Command Center** surface and is injected into every agent prompt as governance + semantic context (`retrieve_board_context`). The **Board → Goals → per-goal Task-DAG → pluggable-executors** model is **live** (`goal_id`/`executor` columns; executors = `single`/`loop`/`team`, dispatched by `supervisor/goal_run.py`; goals decompose via planner/consultation, run with a per-goal executor + CLI-engine selector, and stop via `/comms/goals/stop`). Also live: a **context-retrieval** layer (per-task `context_refs` manifest → `/comms/artifacts/<id>/section` hydration → Board Catalog → client-side AI-Router summaries) and a **memory-consolidation** layer (relevance-gated 💡 channel, near-duplicate dedup + a manual reflection pass via `/comms/consolidate`). Only **P3** (parallel: across-goal lanes → worktree fan-in) remains. Design + roadmap live in `pathly/plans/comms-board/` (see `ROADMAP.md`). Details: [src/pathly_orchestrator/CLAUDE.md](src/pathly_orchestrator/CLAUDE.md).

---

## Feature plans (feature-centric layout)

Storage mirrors board scope — **one home per feature**. New features live under
`pathly/features/<name>/`. Legacy `pathly/plans/<name>/` is still *resolved* for back-compat
(the resolver + Studio discovery probe both) until the Phase-3 migration deletes the fallback.
Design + phases: [pathly/features/storage-restructure/plans/SPEC.md](pathly/features/storage-restructure/plans/SPEC.md).

```
pathly/features/<name>/            FEATURE scope
  plans/                           team pipeline
    STATE.json                     current FSM state
    EVENTS.jsonl                   append-only event log
    PROGRESS.md                    conversation status table (TODO / DONE)
    CONVERSATION_PROMPTS.md        per-conversation builder prompts
    USER_STORIES.md                acceptance criteria
    IMPLEMENTATION_PLAN.md
    feedback/                      REVIEW_FAILURES.md, TEST_FAILURES.md
  goals/<slug>/                    per-goal decompose (planner/plan → nested here)
  debugs/<slug>/  explorations/<slug>/  fixes/<slug>/
  .archive/<name>/                 completed features (mirrors the shape above)
pathly/project/                    PROJECT scope (cross-feature): goals/, board-artifacts/, lessons/
~/.pathly/                         GLOBAL scope (cross-project): pathly.db, lessons/

# Legacy, still resolved until Phase 3: pathly/plans/<name>/ + pathly/plans/.archive/
```

---

## Cross-cutting commands

```bash
# Python package
python -m pytest tests/ -q
python -m build                     # rebuilds all adapters from core
python3 scripts/check_version_sync.py

# Install / propagate agent+skill changes to ~/.claude
pathly-setup claude --apply           # first install
pathly-setup claude --apply --repair  # update already-installed files (fragments, skills, agents)
```

---

## Code architecture — SOLID rules

These rules apply to all Python in `src/pathly_orchestrator/` and all TypeScript in `studio/src/`. Claude Code must enforce them when writing or reviewing code.

**1. Single Responsibility — one file, one domain.**
- A blueprint file owns exactly one HTTP domain (messages, tasks, artifacts, runs, goals, settings).
- A module file owns exactly one concern (DB queries, embeddings, output parsing, …).
- **Hard limit: 400 lines per file.** If a file approaches this, split it before adding more code.

**2. Open/Closed — extend by adding files, not by growing existing ones.**
- New endpoints → new file in the correct domain subpackage. Never append to an already-large file.
- New query type → new file under `db/queries/`, not a longer `comms.py`.

**3. Layer dependency rule (no upward imports).**
```
db/ → (nothing internal)
runner/ → db/
supervisor/ → db/, runner/
http_server/ → all (lazy imports inside route handlers only)
```
- Imports that violate this direction are architecture bugs, not style issues.
- All supervisor/db imports inside Flask route functions (`from X import Y` inside the `def`), never at module top-level — prevents circular imports and keeps startup fast.

**4. Blueprint domain map — where each route family lives.**
```
blueprints/
  core/       health, fsm (FSM lifecycle)
  runner/     api (runner control), streams (SSE)
  flows/      defs (flow CRUD), stage_configs (per-stage overrides)
  catalog/    items (file-tree catalog)
  skills/     editor (skill notebook routes)
  comms/      messages, tasks, artifacts, runs, goals, settings (board subsystems)
  ops/        telemetry, menu, db_api, chat (operational/infra)
```
A new endpoint goes into the matching domain file. If no domain matches, create a new domain file — do not add it to an unrelated file.

**5. Shared helpers belong in `_helpers.py`, not copy-pasted.**
- Constants, regex, and pure utility functions shared across files in a subpackage → `<subpackage>/_helpers.py`.
- Never duplicate a helper across files.

---

## Commit policy

- **Never push to master without explicit user request.**
- Always confirm branch target before pushing.
- Plans go in `pathly/features/<feature>/plans/` (feature-centric layout), never bare `plans/<feature>/`. Legacy `pathly/plans/<feature>/` is still resolved for back-compat, but new plans do NOT go there.
- `studio/*.tsbuildinfo` files are build artifacts — do not commit them.

---

## Telemetry

Stop hook (`src/pathly_hooks/stop_telemetry.py`) fires after every Claude Code session.
It reads the session usage payload (tokens, cost) from stdin, finds the most recently
active feature in the central SQLite DB (`~/.pathly/pathly.db`), and appends a
`BILLING_UPDATE` event (patching the last `AGENT_DONE` with real cost) so Studio can
display API-accurate costs. It always exits 0 — telemetry failure never blocks the user.
