# Pathly Adapters — Claude Code Context

## What this repo is

`pathly-adapters` is the monorepo for the **Pathly AI development framework**:
- Python package (`pathly-adapters` v2.24.x) — FSM orchestrator, telemetry, install CLI
- Electron app (`studio/`) — the supervisory **board / Command Center** through which a human drives *headless* multi-agent runs (the visual flow builder + AI chat panel are surfaces within it)
- Agent/skill source (`src/pathly_data/`) — canonical role contracts, skill markdown, adapter configs

Features move through: **PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE** (PLANNING is the seed state; STORMING/brainstorm is the interactive `/pathly storm` on-ramp, not a headless team-flow stage)

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
       → supervisor/            drives FSM + delegates every agent spawn to the spawn host
       → TERMINAL_SPAWN SSE    a SPAWN HOST opens a process per pipeline stage. Two implement the
                               same contract: Studio (node-pty tab) and `pathly-pty-host`
                               (src/pathly_orchestrator/pty_host/, plain pipes — server/CI, no
                               desktop). Run exactly one; the supervisor can't tell them apart.
       → terminal:spawn IPC    argv injected from adapters.yaml headless template, e.g.
                               claude: ['claude', '-p', '{prompt}', '--model', '{model}', '--output-format', 'json', '--dangerously-skip-permissions']
                               codex:  ['codex', 'exec', '--skip-git-repo-check', '--json', '--sandbox', 'workspace-write', '--model', '{model}', '--', '{prompt}']
       → process exits         POST /runner/terminal/result → FSM continues
     → fsm_events (DB)      Claude writes AGENT_DONE with `summary` mid-run to the central DB; supervisor reads it after PTY exits as the authoritative semantic result (stdout only used for session_id + cost_usd); EVENTS.jsonl is a downstream DB→disk export
```

**Adapter install step:** `pathly-setup <host> --apply` stitches `core/agents/` and `core/skills/` with adapter-specific `_meta/*.yaml` files and writes deployable files to the host's install directory. Four adapters: `claude` → `~/.claude/`, `codex` → `~/.codex/` + `~/.agents/`, `copilot` → `~/.vscode/extensions/pathly/`, `antigravity` → `~/.gemini/antigravity-cli/`.

**Skill delivery — two modes:**

| Mode | Trigger | How prompt reaches CLI | Skill files needed on disk? |
|---|---|---|---|
| **Interactive** | User types `/pathly build` | CLI reads `~/.claude/skills/pathly-build.md` | Yes — run `pathly-setup claude --apply` |
| **Runner** | Studio Start button | `supervisor/` injects full prompt via `-p` argv | No — prompt assembled in Python at runtime |

In runner mode Pathly is the single source of truth for skill content. The CLI receives the complete prompt as a command-line argument and exits when done — it never reads a skill file.

**Dash-safety:** prompts delivered via CLI argv must never start with `---` (claude parses it as an unknown option). Three mirror implementations enforce this: `_dash_safe_prompt` in `src/pathly_orchestrator/adapters.py` (applied in `resolve_command`); `_strip_leading_frontmatter` in `src/pathly_orchestrator/skills/compose_base.py` (applied during skill composition, re-exported from `skills/compose.py`); and `dashSafePrompt` in `studio/src/renderer/src/services/cliEngine.ts` (applied in `buildHeadlessArgv`).

**Studio CLI spawn scheduler (`studio/src/main/ipc/terminal.ts`, with its concerns split across `studio/src/main/ipc/terminal/`):** a dual-cap concurrency gate controls how many CLI engine processes run simultaneously. Default caps: global ≤ 8, headless ≤ 5, interactive ≤ 5 (all configurable at runtime via the SpawnQueuePanel). Headless one-shots are queued (FIFO + priority); interactive sessions are rejected over cap with a toast. A headless run the *provider* refused (rate limit / quota / "at capacity" / 5xx — classified by `main/ipc/engineFailure.ts`, which requires a non-zero exit **or** an engine abort marker so an agent merely writing about rate limits isn't misread) arms a cooldown **and** is re-run up to 2× with backoff, re-entering the gate rather than bypassing it; the retry short-circuits `onExit` so consumers still see one exit per attempt chain. On Windows, headless argv is encoded as a PowerShell temp-script; `codex` headless additionally pipes `$null` as stdin to prevent it stalling on terminal input.

**FSM response contract (`agent_hint`):** Every `/next_action` response includes:
- `agent_hint.role` — `"worker"` or `"explorer"` (host-neutral delegation signal)
- `agent_hint.instructions` — full prompt for the next agent (Pathly role, phase, artifacts, limits)
- `AGENT_DONE.summary` in the central DB (`fsm_events`) — authoritative semantic result text (not truncated by PTY buffer); `--output-format=json` stdout is only used for `session_id` and `cost_usd`
- `AGENT_DONE.outcome` — `"success"` or `"failed"` (+ `error`); the authoritative pass/fail signal the supervisor's loop executor reads via `_outcome_is_failure`. A clean process exit that self-reports `outcome:"failed"` still fails the task (silent-failure guard #2)
- `decision` — `"continue"` / `"block"` / `"escalate"` (automation gate)
- `codex_subagent` — legacy compat field with frozen keys; new adapters should read `agent_hint`

**Ground truth — `command_gate` measures what other gates take on trust.** Four of the five FSM
transition gates read state an *agent produced*: `require_artifact` (a file exists), `verify_gate`
(the file's line 1 is `RESULT: PASS`), `require_tasks_done` (tasks marked done), `scope_gate` (the
git footprint matches the declared one). `command_gate` (`fsm/gates/command.py`) is the one that
**executes** — it runs the project's own verify command, reads the process exit code, and routes the
real stdout/stderr back as feedback. So a builder that writes `RESULT: PASS` over code that does not
compile no longer advances the flow. Configure per project with `PUT /db/settings/verify.build` /
`verify.test`; **unconfigured means the gate skips**, so it is inert until a project opts in. Wired
into `team`/`team-build` at `BUILDING->REVIEWING` (`verify.build` → `BUILD_FAILURES.md`) and
`TESTING->RETRO` (`verify.test` → `TEST_FAILURES.md`). Detail:
[src/pathly_orchestrator/CLAUDE.md](src/pathly_orchestrator/CLAUDE.md).

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

A DB-backed message board (`comms_messages` + `comms_artifacts` tables, `/comms/*` routes) where agents and humans post decisions, discoveries, artifacts, and DAG tasks. It is the Studio **Command Center** surface and is injected into every agent prompt as governance + semantic context (`retrieve_board_context`). The **Board → Goals → per-goal Task-DAG → pluggable-executors** model is **live** (`goal_id`/`executor` columns; executors = `single`/`loop`/`team`, dispatched by `supervisor/goal_executor.py` (`goal_run.py` is a thin re-export shim; goals decompose via `goal_decomposer.py`); goals decompose via planner/consultation, run with a per-goal executor + CLI-engine selector, and stop via `/comms/goals/stop`). **Since fsm-fan-out Phase E, `loop` and `team` are both FSM runs** — `loop` runs the `goal-loop` flow (one fan-out `DRAINING` state; flat by design, no review/test round-trip), `team` runs `team-build` (reviewed); only `single` is agent-driven, via `development/drain-dag`. Also live: a **context-retrieval** layer (per-task `context_refs` manifest → `/comms/artifacts/<id>/section` hydration → Board Catalog → client-side AI-Router summaries) and a **memory-consolidation** layer (relevance-gated context channel, near-duplicate dedup + a manual reflection pass via `/comms/consolidate`). Only **P3** (parallel: across-goal lanes → worktree fan-in) remains. Design + roadmap live in `pathly/features/comms-board/` (see `ROADMAP.md`). Details: [src/pathly_orchestrator/CLAUDE.md](src/pathly_orchestrator/CLAUDE.md).

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
  STATE.json                       current FSM state (DB→disk export; git-trackable)
  BOARD.json                       comms board export (gitignored; DB stays authoritative)
  EVENTS.jsonl                     event-log export (gitignored; DB→disk via event_mirror)
  USER_STORIES.md                  acceptance criteria
  IMPLEMENTATION_PLAN.md           phase-by-phase plan; each phase → one board task (build work-list = board DAG)
  feedback/                        REVIEW_FAILURES.md, TEST_FAILURES.md
  goals/<slug>/                    per-goal decompose (planner/plan)
pathly/features/.archive/<name>/   completed features (mirrors the shape above)
pathly/project/                    PROJECT scope: artifacts/, SEQUENCING.md, BOARD.json (board mirror),
                                   and PROJECT-board runs under <kind>/<slug>/ (kind ∈ goals|debugs|explorations|fixes)
pathly/board-artifacts/            cross-feature board artifacts (e.g. BOARD_EVAL.md)
pathly/lessons/                    promoted lessons (cross-feature)
pathly/pipeline-walkthrough/<slug>/  point-in-time pipeline records (never sync these)

# Retired (board-scoped-storage P2+P3): the shared top-level buckets pathly/debugs/,
# pathly/explorations/, pathly/fixes/ — runs now nest under their board
# (features/<f>/<kind>/<slug> or project/<kind>/<slug>); discovery no longer scans the old roots.
~/.pathly/                         GLOBAL scope (cross-project): pathly.db, lessons/, global/BOARD.json

# Legacy, still resolved for back-compat: pathly/plans/<name>/
```

### Disk-file classification (state-one-authority)

*The SQLite DB is the single runtime authority. Every per-feature disk file is a SEED read
once into the DB or an EXPORT written DB→disk for git/audit — never round-tripped for a
runtime decision. Runtime code reads the DB (or a DB-first, allow-listed fallback), never
the mirror.* Enforced by `scripts/check_no_mirror_reads.py` (+ `scripts/mirror_reads_allowlist.txt`)
in the lint `consistency` job.

| File | Scope | Class | Direction | DB authority |
|---|---|---|---|---|
| `STATE.json` | feature | EXPORT (git-trackable) | DB→disk (atomic) | `fsm_state` |
| `BOARD.json` | feature/project/global | EXPORT (gitignored) | DB→disk (debounced) | `comms_*` |
| `EVENTS.jsonl` | feature | EXPORT (gitignored, like `BOARD.json` — the exporter rewrites it on every server start) | DB→disk (debounced) | `fsm_events` |
| `ARTIFACTS.jsonl` | feature | **DROPPED** (metadata lives in `BOARD.json`; also gitignored) | — | `comms_artifacts` |
| `*.flow.yaml` | core (packaged) | SEED | disk→DB on server start | `flow_nodes`/`flow_yaml` |
| `abilities/*.md`, `prompts/*.md` | project/global | SEED (file *is* authority) | disk→compose | n/a |

---

## Cross-cutting commands

```bash
# Python package
python -m pytest tests/ -q
python -m build                     # rebuilds all adapters from core
python3 scripts/check_version_sync.py
python3 scripts/check_file_size.py    # 400-line SOLID ratchet (--update after a split)
python scripts/gen_test_index.py    # regenerate tests/*/INDEX.md after adding/moving tests

# Install / propagate agent+skill changes to ~/.claude
pathly-setup claude --apply           # first install
pathly-setup claude --apply --repair  # update already-installed files (fragments, skills, agents)
```

**Test layout:** tests live in domain folders under `tests/` (index: [tests/INDEX.md](tests/INDEX.md)), each with a generated `INDEX.md`. A new test goes in the matching domain folder. To locate a repo file, import `REPO_ROOT`/`SRC`/`SNAPSHOT_DIR` from `tests/_paths.py` (or use the `repo_root`/`snapshot_dir` fixtures) — never `Path(__file__).parent.parent`, which silently resolves to `tests/` once a file is nested. Rerun `scripts/gen_test_index.py` after adding, moving, or removing a test (`--check` fails if an index is stale).

---

## Code intelligence — query through Pathly

Understanding code structure or finding code (who calls X, a file's symbols, blast radius)?
Query **Pathly's `/code/query` proxy** first, not raw Grep — it's the same path Pathly's
agents use: it **self-heals the graph index** (re-indexes on demand), caches, and logs real
queries to the board as shared context. Use a **parenthesized `scope` like `(interactive)`**
for ad-hoc exploration — those are NOT board-logged, so they add no board noise.

```bash
# TARGET must be a FILE PATH (the graph is keyed by file — a bare symbol name misses).
# op ∈ impact | callers | chain | context | symbol | pattern ; role=architect → full tier.
curl -s -X POST http://127.0.0.1:8765/code/query -H 'Content-Type: application/json' \
 -d '{"op":"impact","target":"src/pathly_orchestrator/http_server/sse.py","role":"architect","project_root":"<repo-root>","scope":"(interactive)"}'
```

The result is an **advisory** block (symbols + caller/callee counts) that says *"verify
before acting"* — the graph can lag recent edits, so confirm against live code (Read/Grep)
before relying on it. It returns **safe-null** (never 500s) when the FSM server is down or
the backend is off → then just use Grep/Read. (`pathly-fsm-call code-query --op … --target …`
is a shim, but the HTTP form passes `project_root`, which the proxy needs to resolve
relative targets.)

Two backends sit behind the one proxy — pick per request with `"engine": "graph" | "lsp" | "both"`
(omit → the `code_context.backend` setting decides — default `auto` (detect the installed
backend), else `off` | `cli` | `lsp` | `both`):

| Engine | Backend | Strength | Freshness | Cost | Use for |
|---|---|---|---|---|---|
| `graph` | codebase-memory-mcp (whole-repo index) | breadth — whole repo | can **lag** recent edits (advisory; self-heals via `maybe_reindex`) | fast every call | "who calls X", impact, blast radius, architecture |
| `lsp` | Serena (LSP, no index) | precision — one symbol's exact defn/refs | **always fresh** | ~1-min warm-up **once** per project, then fast | a specific symbol, **especially right after an edit** |
| `both` | union of the two | breadth + precision | mixed | slowest | need both and can wait |

The `lsp` backend boots ONE long-lived Serena MCP session **server-side** on first use
(`runner/code_context_lsp.py`), so the FIRST `engine=lsp` query for a project returns `null`
(~1 min warm-up → degrade to Grep); later calls are fast, and the session is torn down on root
change / exit. Serena is ALSO wired as a direct agent MCP tool via
`src/pathly_data/adapters/*/_mcp/serena.json` (independent of the proxy). Fallback when the FSM
server isn't running: query the graph directly (`codebase-memory-mcp cli <tool> …`).

**Code-intelligence setup on a new machine.** Both `/code/query` backends are **external tools —
NOT in this repo and NOT pip/npm deps** — but code-intel **defaults to `auto`** (`_resolve_backend`):
it probes `shutil.which` and turns on whichever backend is installed (`codebase-memory-mcp` on PATH
→ `graph`; else `uvx` → `lsp`; else `none`). So on a fresh machine it just-works once a backend is
present — **no manual toggle**. It stays **optional**: with neither tool, every caller safely
degrades to Grep/Read. Per-project graph indexes cache in `~/.cache/codebase-memory-mcp/<project>.db`
(**per-machine, not git-tracked** → a fresh machine re-indexes).

- **`graph` — `codebase-memory-mcp`** (`runner/code_context_cli.py::CliProvider`, found via
  `shutil.which`): a standalone binary from **GitHub → [`DeusData/codebase-memory-mcp`](https://github.com/DeusData/codebase-memory-mcp)**
  (OS-native GitHub Releases; the Windows build here is a ~269 MB self-contained
  `…/Python313/Scripts/codebase-memory-mcp.exe`, v0.8.1). Setup: download the OS-native build from
  `…/releases/latest` onto PATH (or run its own `codebase-memory-mcp update`) → `codebase-memory-mcp
  install` (self-registers into Claude Code + Codex/Gemini/Zed/…) → `codebase-memory-mcp cli
  index_repository '{"repo_path":"<repo>"}'` (or let `maybe_reindex` / `auto_index` build it).
- **`lsp` — Serena** (`runner/code_context_lsp.py`; also a direct agent MCP tool via
  `adapters/*/_mcp/serena.json`): launched via **`uvx --from git+https://github.com/oraios/serena
  serena start-mcp-server …`**, so the only prerequisite is **`uv`/`uvx`**
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — `uvx` auto-fetches Serena, **no binary
  download, no index** (always fresh; ~1-min cold warm-up per project).
- **Override the `auto` default** per project via app_settings (DB, **per-machine**):
  `PUT /db/settings {"code_context.backend":"off|cli|lsp|both"}` (or Studio → Settings → Code
  Intelligence). The **code default is `auto`** so it travels via git; the DB setting does not.

---

## Code architecture — SOLID rules

These rules apply to all Python in `src/pathly_orchestrator/` and all TypeScript in `studio/src/`. Claude Code must enforce them when writing or reviewing code.

**1. Single Responsibility — one file, one domain.**
- A blueprint file owns exactly one HTTP domain (messages, tasks, artifacts, runs, goals, settings).
- A module file owns exactly one concern (DB queries, embeddings, output parsing, …).
- **Hard limit: 400 lines per file.** If a file approaches this, split it before adding more code.
- **Gated in CI** by `scripts/check_file_size.py` (lint `consistency` job) as a *ratchet* against
  `scripts/file_size_baseline.txt`: the 28 files already over the limit are frozen at their current
  size and may only shrink. A NEW oversized file fails, and so does **growing an already-oversized
  one** — which is rule #2 mechanically enforced. Adding a new file is always allowed. When a
  baseline file drops to 400 or under, the check fails until you run
  `python3 scripts/check_file_size.py --update`, so the debt can never silently creep back.

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
  control/    runs_read (unified run read API: GET /runs, /runs/<id>) · runs_control (POST /runs/<id>/stop — run_id-addressed stop · POST /runs/<id>/<action> for pause|resume|advance|reroute|retry|abort — run_id-addressed control, mirrors /runner/* — board-lock runs support only abort)
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

**Billing authority — the spawn gate, run-keyed, adapter-agnostic.** Every runner spawn
(any adapter) flows through ONE chokepoint: `POST /runner/terminal/result`
(`blueprints/runner/api_lifecycle.py`). That handler parses the CLI stdout with the
**spawn-time adapter** (sent by `terminal.ts`, not the racy live `current_adapter`) and
writes the authoritative `BILLING_UPDATE` for THAT run via `_patch_last_agent_done(...,
run_id=…)` — so the invocation projection folds the REAL cost/tokens onto the run's
`AGENT_DONE`, overriding the agent's (often-wrong) self-estimate. claude → real
`total_cost_usd`; codex → tokens (cost estimated downstream). This fires reliably even
when the supervisor's own `_reconcile_billing_now` races run completion (which is why
consultation codex stages + the no-subagent planner used to show `$0`).

**Every run gets a row, even one that self-reports nothing.** `BILLING_UPDATE` *patches an
existing* `AGENT_DONE`; a run that writes none has nothing to patch → no projected invocation →
it never appears in the Monitor's RECENT list and its cost is lost. This bit the board
**evaluator** + **consolidate** runs (their `planning/evaluate` / `planning/consolidate` skills
lacked the `completion-report` fragment, unlike every other terminal emitter). Two fixes close
it: (1) both skills now compose `completion-report`, and `supervisor/board_run.py`
(`_inject_board_prompt_vars`) substitutes the `<fsm_feature>`/`<feature_path>` placeholders it
needs (board runs bypass `fsm_compose`); (2) a safety net — `supervisor/terminal.py`
(`_synthesize_agent_done_if_missing`) writes a synthetic `AGENT_DONE` for any **executor-owned**
run (board/single/loop) whose agent self-reported none, keyed by `run_id` and run *before*
`_reconcile_billing_now` so the `BILLING_UPDATE` folds onto it (not a stale same-feature event).
So a missing `completion-report` no longer means "vanished + unbilled."

**Run TYPE is a stamped column, not a guess.** The Monitor's RECENT list buckets finished runs
into `flow` / `single` / `loop`, but the invocation's `scope_tier` (feature/project/global) is the
board tier, not the run type — so board/single runs used to mis-bucket as `flow`. Now
`agent_invocations.category` carries the real type, stamped INTO the `AGENT_DONE` event (so it
survives the startup backfill): `completion-report` writes `<run_category>`, substituted to `flow`
by `fsm_compose._inject_prompt_vars` (default) and to `single` by
`board_run._inject_board_prompt_vars`; Fix A's synthetic `AGENT_DONE` stamps `single` (or `loop`
for `flow=='goal-loop'`). The projection guards it to the valid set (an unsubstituted placeholder →
NULL), and `useRecentEngines` prefers it, falling back to the old `scope_tier` heuristic only when
NULL.

Stop hook (`src/pathly_hooks/stop_telemetry.py`) is now a **fallback for INTERACTIVE claude
only**. It fires after every Claude Code session, but runner spawns carry
`PATHLY_GATE_BILLED` (set in `terminal.ts` for `runnerTabMeta` tabs), so the hook **skips
them** — it would otherwise double-bill / mis-attribute (it can only guess the target via
"the most recently active feature", racy under concurrent/goal runs). Interactive claude
(no runner tab, no result callback) has no other cost source, so the hook still bills it:
reads the session usage from stdin, finds the active feature, appends a `BILLING_UPDATE`.
Always exits 0 — telemetry failure never blocks the user.

**`agent_invocations` is a projection of the `AGENT_DONE` event stream** (telemetry-reconciliation).
The DB-explorer roll-up (`/db/rollup`), header strip (`/db/stats`), feature cards
(`/db/features`), per-flow rollup (`/db/runs/<run_id>/cost`) and cost chart
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
`/db/stats` and `/db/features` both honor `project_root` (scoped SUM/GROUP BY over the
same table), so the header total always equals the sum of the feature cards for that
project.

**Two strategies: token-counting is universal, cost is per-provider.** Tracking every CLI
spawn's usage splits into two independent layers so a rate change never disturbs token
extraction and a new engine never disturbs pricing: **Strategy A — token counting**
(`runner/output.py::extract_tokens` + the per-adapter `_TOKEN_STRATEGIES` registry: claude →
result-envelope `usage`/`modelUsage`, codex → JSONL usage event, antigravity/agy → a local
`estimate_tokens_from_text` char heuristic since it emits no usage; unknown adapter → the
claude/generic parser) answers *how many tokens*; **Strategy B — cost pricing** (`db/pricing.py`,
below) answers *how many dollars*. Adding an engine = one entry in `_TOKEN_STRATEGIES`; changing
a rate = one entry in `PRICING`. Tokens are the must-capture primitive — cost is always derivable
from them via Strategy B when the CLI reports none.

**Large claude envelopes survive the PTY tail buffer — `parse_result` truncation recovery.** A run
with heavy cache reads emits a big `--output-format=json` envelope; Studio's rolling PTY tail
(`terminal.ts`, last ~500 chunks) can drop its opening brace, so `_extract_json_payload` falls back
to an inner `modelUsage` entry and the structured parse reads cost=0 / tokens=0 — which recorded a
**headless board single-agent run at `$0`** despite a real $1.25 (the cost was right there in the
CLI's own JSON, just past the truncation point). `runner/output.py::parse_result` regex-recovers
`total_cost_usd` (or summed per-model `costUSD`) + the camelCase `modelUsage` token fields from the
raw text, firing ONLY when the structured parse yields 0 (so a full envelope is never double-counted).

**Cost is priced from tokens when the CLI reports none — `db/pricing.py` (Strategy B).** The
pricing table/`PricingRegistry`/`estimate_cost`/`infer_provider` live in
`db/pricing.py` (the layer-safe home — the projector is in `db/` and cannot import
upward into `http_server/`); `http_server/telemetry_registry.py` re-exports them for
back-compat. The projector applies a `_price_if_needed` chokepoint on every projected
row (idempotent: only fires when `cost_usd==0` and `tokens_in+tokens_out>0`; a
provider-reported or already-estimated cost is never re-priced). Per-adapter behavior:
`codex exec --json` (JSONL events on stdout) never reports a dollar cost, so its token
strategy (`runner/output.py::_codex_tokens` → `_codex_usage`) scans the stream for a
token-usage event (defensive — the exact field shape is unconfirmed, several layouts are
tolerated) and the chokepoint estimates cost from those tokens (`cost_source="estimated"`);
`agy` (Antigravity) reports no usage, so its strategy estimates output tokens locally and the
chokepoint prices them, while a genuinely token-less row is marked
`cost_source="unavailable"` rather than a misleading `$0`. `model`/`run_id` are now
threaded into `BILLING_UPDATE` (`runner/events.py::_patch_last_agent_done` →
`supervisor/terminal.py::_reconciliation_window`) so the projected row's `provider` and
`run_id` columns get stamped even when the originating `AGENT_DONE` didn't carry them. `model`/`run_id` are now
threaded into `BILLING_UPDATE` (`runner/events.py::_patch_last_agent_done` →
`supervisor/terminal.py::_reconciliation_window`) so the projected row's `provider` and
`run_id` columns get stamped even when the originating `AGENT_DONE` didn't carry them.

**Renderer one-shots (editor Diagram/Analyze) get the same codex treatment via a parallel
path**, because they post to `/db/invocation` (`source_seq NULL`) and so bypass the event
projector + its `_price_if_needed`. Two mirrors close the gap: (1) the Studio spawn gate parses
the codex stream itself — `studio/src/main/ipc/codexJson.ts::parseCodexResult` (mirror of
`_codex_usage`) so a codex one-shot reports tokens instead of `0`; (2) the one-shot writer
`runner/telemetry.py::project_agent_done` estimates cost from those tokens via
`db/pricing.py::estimate_cost_for` — keyed by the **adapter slug** (`codex`→`gpt-5` family),
since a one-shot spawns with no explicit `--model`. Same outcome: codex → `cost_source="estimated"`,
token-less agy → `"unavailable"`.

**Spawn-parse-unification — the server is the single telemetry parser.** The two-parser design
above (Python `parse_result` for runner spawns; Studio `parseClaudeJsonResult`/`parseCodexResult`
for one-shots) is why **claude editor one-shots recorded `$0`**: the *Studio* parser bailed to
`null` when a large envelope overflowed the PTY tail buffer (the `"type":"result"` marker fell off
the front) — the same truncation the Python parser now regex-recovers. Closed on both sides: (1)
`parseClaudeJsonResult` (`claudeJson.ts`) gained the same regex recovery (`recoverClaudeUsage`,
using the once-per-run camelCase `modelUsage` token fields, never the per-turn snake `usage`, so
stream-json never double-counts); (2) more fundamentally, `terminal.ts` now sends the **raw
`stdout_tail`** on the `/db/invocation` post, and `db_api_invocation.py` parses it with the **one**
robust server parser (`runner/output.py::parse_result`) and PREFERS it over the client-parsed
cost/tokens (kept only as a fallback). So the same parser (incl. truncation recovery) now backs
BOTH the runner path (`/runner/terminal/result`) and the one-shot path (`/db/invocation`); the
Studio parsers remain for the live terminal display.
