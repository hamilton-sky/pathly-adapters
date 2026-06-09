# Pathly Adapters — Claude Code Context

## What this repo is

`pathly-adapters` is the monorepo for the **Pathly AI development framework**:
- Python package (`pathly-adapters` v2.x) — FSM orchestrator, telemetry, install CLI
- Electron app (`studio/`) — visual flow builder and AI chat panel
- Agent/skill source (`src/pathly_data/`) — canonical role contracts, skill markdown, adapter configs

Features move through: **STORM → PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE**

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
     → pathly/plans/<feature>/ filesystem state

Studio → Start button          FlowControlBar → POST /runner/start
       → supervisor/            drives FSM + spawns agents as visible terminals
       → TERMINAL_SPAWN SSE    Studio opens a PTY tab (node-pty) per pipeline stage
       → terminal:spawn IPC    argv injected: ['claude', '-p', '<full prompt>', '--print', ...]
       → PTY exits             POST /runner/terminal/result → FSM continues
     → EVENTS.jsonl         Claude writes AGENT_DONE with `summary` mid-run; supervisor reads it after PTY exits as the authoritative semantic result (stdout only used for session_id + cost_usd)
```

**Adapter install step:** `pathly-setup <host> --apply` stitches `core/agents/` and `core/skills/` with adapter-specific `_meta/*.yaml` files and writes deployable files to the host's install directory. Three adapters: `claude` → `~/.claude/`, `codex` → `~/.codex/` + `~/.agents/`, `copilot` → `~/.vscode/extensions/pathly/`.

**Skill delivery — two modes:**

| Mode | Trigger | How prompt reaches CLI | Skill files needed on disk? |
|---|---|---|---|
| **Interactive** | User types `/pathly build` | CLI reads `~/.claude/skills/pathly-build.md` | Yes — run `pathly-setup claude --apply` |
| **Runner** | Studio Start button | `supervisor/` injects full prompt via `-p` argv | No — prompt assembled in Python at runtime |

In runner mode Pathly is the single source of truth for skill content. The CLI receives the complete prompt as a command-line argument and exits when done — it never reads a skill file.

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
| po | sonnet | interactive requirements / scope discussion |
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

## Feature plans

```
pathly/plans/
  <feature>/
    STATE.json              current FSM state
    EVENTS.jsonl            append-only event log
    PROGRESS.md             conversation status table (TODO / DONE)
    CONVERSATION_PROMPTS.md per-conversation builder prompts
    USER_STORIES.md         acceptance criteria
    IMPLEMENTATION_PLAN.md
    feedback/               REVIEW_FAILURES.md, TEST_FAILURES.md
  .archive/                 completed features
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

## Commit policy

- **Never push to master without explicit user request.**
- Always confirm branch target before pushing.
- Plans go in `pathly/plans/<feature>/`, never in `plans/<feature>/`.
- `studio/*.tsbuildinfo` files are build artifacts — do not commit them.

---

## Telemetry

Stop hook (`src/pathly_hooks/stop_telemetry.py`) fires after every Claude Code session.
Appends token usage to the feature's `02-TOKEN-USAGE.md` pipeline walkthrough file.
