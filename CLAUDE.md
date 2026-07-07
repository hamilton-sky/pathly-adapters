# Pathly Adapters — Claude Code Context

## What this repo is

`pathly-adapters` is the monorepo for the **Pathly AI development framework**:
- Python package (`pathly-adapters` v2.19.x) — FSM orchestrator, telemetry, install CLI
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
     → pathly/features/<feature>/  filesystem state (legacy: pathly/plans/<feature>/)

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
- `AGENT_DONE.outcome` — `"success"` or `"failed"` (+ `error`); the authoritative pass/fail signal the supervisor's loop executor reads via `_outcome_is_failure`. A clean process exit that self-reports `outcome:"failed"` still fails the task (silent-failure guard #2)
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
| evaluator | sonnet | classifies a board's context (CODE/RESEARCH/BOTH) → analysis artifact + next-step task posts |
| quick / scout | haiku | fast lookups |
| orchestrator | haiku | deterministic FSM recovery |
| human | — | placeholder for human-in-the-loop steps |

**Rigor levels:** `nano` (1 conv, no review/test) · `lite` (plan+build) · `standard` (full pipeline) · `strict` (standard + audit)

---

## Comms board (orchestration substrate)

A DB-backed message board (`comms_messages` + `comms_artifacts` tables, `/comms/*` routes) where agents and humans post decisions, discoveries, artifacts, and DAG tasks. It is the Studio **Command Center** surface and is injected into every agent prompt as governance + semantic context (`retrieve_board_context`). The **Board → Goals → per-goal Task-DAG → pluggable-executors** model is **live** (`goal_id`/`executor` columns; executors = `single`/`loop`/`team`, dispatched by `supervisor/goal_executor.py` (`goal_run.py` is a thin re-export shim; goals decompose via `goal_decomposer.py`); goals decompose via planner/consultation, run with a per-goal executor + CLI-engine selector, and stop via `/comms/goals/stop`). Also live: a **context-retrieval** layer (per-task `context_refs` manifest → `/comms/artifacts/<id>/section` hydration → Board Catalog → client-side AI-Router summaries) and a **memory-consolidation** layer (relevance-gated context channel, near-duplicate dedup + a manual reflection pass via `/comms/consolidate`). Only **P3** (parallel: across-goal lanes → worktree fan-in) remains. Design + roadmap live in `pathly/features/comms-board/` (see `ROADMAP.md`). Details: [src/pathly_orchestrator/CLAUDE.md](src/pathly_orchestrator/CLAUDE.md).

---

## Feature plans (feature-centric layout)

Storage mirrors board scope — **one home per feature**. New features live under
`pathly/features/<name>/` (flat — no `plans/` subfolder). Phase 3 migrated all feature *data*
out of `pathly/plans/` and dropped the feature-discovery fallback; the `pathly/plans/` path is
still referenced by a few subsystems (event log, artifact hydration, feedback/health probes),
so it is not fully removed from the code.
Design + phases: [pathly/features/storage-restructure/SPEC.md](pathly/features/storage-restructure/SPEC.md).

```
pathly/features/<name>/            FEATURE scope — team pipeline files live DIRECTLY here
  STATE.json                       current FSM state
  EVENTS.jsonl                     append-only event log
  PROGRESS.md                      conversation status table (TODO / DONE)
  CONVERSATION_PROMPTS.md          per-conversation builder prompts
  USER_STORIES.md                  acceptance criteria
  IMPLEMENTATION_PLAN.md
  feedback/                        REVIEW_FAILURES.md, TEST_FAILURES.md
  goals/<slug>/                    per-goal decompose (planner/plan)
pathly/features/.archive/<name>/   completed features (mirrors the shape above)
pathly/project/                    PROJECT scope: artifacts/, SEQUENCING.md
pathly/board-artifacts/            cross-feature board artifacts (e.g. BOARD_EVAL.md)
pathly/lessons/                    promoted lessons (cross-feature)
pathly/debugs/<slug>/  pathly/explorations/<slug>/   standalone (non-feature) investigations
pathly/pipeline-walkthrough/<slug>/  point-in-time pipeline records (never sync these)
~/.pathly/                         GLOBAL scope (cross-project): pathly.db, lessons/

# Legacy, still resolved for back-compat: pathly/plans/<name>/
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
  comms/      messages, tasks, artifacts, runs, goals, settings, context (board subsystems)
  ops/        telemetry, menu, db_api, chat, export (operational/infra)
  code/       query (codebase-intelligence query)
```
A new endpoint goes into the matching domain file. If no domain matches, create a new domain file — do not add it to an unrelated file.

**5. Shared helpers belong in `_helpers.py`, not copy-pasted.**
- Constants, regex, and pure utility functions shared across files in a subpackage → `<subpackage>/_helpers.py`.
- Never duplicate a helper across files.

---

## Commit policy

- **Never push to master without explicit user request.**
- Always confirm branch target before pushing.
- Plans go in `pathly/features/<feature>/` (feature-centric layout — files directly under the feature dir, no `plans/` subfolder), never bare `plans/<feature>/`. Legacy `pathly/plans/<feature>/` is still resolved for back-compat, but new plans do NOT go there.
- `studio/*.tsbuildinfo` files are build artifacts — do not commit them.

---

## Documentation sync

**When you change code, update the matching *living* doc in the same change.** These docs are contracts about the *current* codebase and are loaded into agent context — drift silently misleads both humans and agents.

| Code you touched | Living doc to check |
|---|---|
| Root behavior / architecture / pipeline | this `CLAUDE.md` |
| Frontend (Electron/React) | [studio/CLAUDE.md](studio/CLAUDE.md) |
| Data / adapters / skills / composition | [src/pathly_data/CLAUDE.md](src/pathly_data/CLAUDE.md) |
| FSM / orchestrator / HTTP / supervisor | [src/pathly_orchestrator/CLAUDE.md](src/pathly_orchestrator/CLAUDE.md) |
| User-facing behavior / install / value | `README.md`, [docs/WHAT_IS_PATHLY.md](docs/WHAT_IS_PATHLY.md) |

- **Verify-then-fix, don't rewrite:** check each claim against the code and change only what's demonstrably stale — a blind rewrite introduces drift instead of removing it.
- **Records are off-limits:** `pathly/features/*/SPEC.md`, retros, `pipeline-walkthrough/`, and `.archive/` are point-in-time records — never "sync" them to current code.
- A doc fix rides in the **same commit** as the code change it describes, not a separate pass.

---

## Telemetry

Stop hook (`src/pathly_hooks/stop_telemetry.py`) fires after every Claude Code session.
It reads the session usage payload (tokens, cost) from stdin, finds the most recently
active feature in the central SQLite DB (`~/.pathly/pathly.db`), and appends a
`BILLING_UPDATE` event (patching the last `AGENT_DONE` with real cost) so Studio can
display API-accurate costs. It always exits 0 — telemetry failure never blocks the user.

**`agent_invocations` is a projection of the `AGENT_DONE` event stream** (telemetry-reconciliation).
The DB-explorer roll-up (`/db/rollup`), header strip (`/db/stats`) and cost chart
(`/telemetry/trends`) all read `agent_invocations` — but the authoritative per-agent
cost/tokens live in `fsm_events` (each agent writes `AGENT_DONE`; the stop hook /
reconciliation window appends a `BILLING_UPDATE` that **supersedes** it). So the
projector (`db/queries/invocation_projection.py`) writes exactly one invocation row
per `AGENT_DONE`, keyed by its `fsm_events.seq` (`source_seq`), with the superseding
`BILLING_UPDATE` folded in (billing wins when priced — never summed, so no
double-count). It runs two ways: a **live hook** in `append_event` (every
`AGENT_DONE`/`BILLING_UPDATE` write projects immediately) and an **idempotent startup
backfill** (`_run_migrations` → `backfill_invocations_from_events`). Editor/chat
one-shots posted via `/db/invocation` (feature `"(project)"`, no event) keep
`source_seq IS NULL` and are a disjoint, untouched population. Because of this, the
writers in `runner/telemetry.py` (`project_agent_done`, called with
`write_invocation=False`) and `api_lifecycle._write_stage_telemetry` now write only the
OTel **span** (for the Traces tab) — the invocation comes from the event projection.
