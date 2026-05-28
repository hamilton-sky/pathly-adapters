# Pathly Adapters — Claude Code Context

## What this repo is

`pathly-adapters` is the monorepo for the **Pathly AI development framework**:
- Python package (`pathly-adapters` v2.x) — FSM orchestrator, telemetry, install CLI
- Electron app (`studio/`) — visual flow builder and AI chat panel
- Agent/skill source (`src/pathly_data/`) — canonical role contracts, skill markdown, adapter configs

Pathly is a structured feature-development pipeline for AI coding agents.
Features move through: **STORM → PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE**.

---

## Key directories

```
src/pathly_data/
  core/agents/          canonical agent role contracts (building/, planning/, quality/, research/, support/)
  core/skills/          canonical skill markdown (flow/, development/, planning/, team/, utilities/)
  core/templates/       plan file templates (USER_STORIES, IMPLEMENTATION_PLAN, etc.)
  adapters/claude/      Claude Code adapter — _meta/ YAML frontmatter for each agent
  adapters/codex/       Codex adapter
  adapters/copilot/     Copilot adapter

pathly/plans/           active and archived feature plans
  <feature>/
    STATE.json          current FSM state (PLANNING, BUILDING, REVIEWING, etc.)
    EVENTS.jsonl        append-only event log
    PROGRESS.md         conversation status table (TODO / DONE)
    CONVERSATION_PROMPTS.md  per-conversation builder prompts
    USER_STORIES.md     acceptance criteria
    IMPLEMENTATION_PLAN.md
    PROGRESS.md
    feedback/           open feedback files (REVIEW_FAILURES.md, TEST_FAILURES.md)
  .archive/             completed features

studio/                 Electron + React + Vite desktop app
  src/main/             Electron main process (IPC handlers)
  src/renderer/         React UI (components, stores, styles)
  tsconfig.web.json     renderer TypeScript config
```

---

## Pipeline architecture

```
User → /pathly <cmd>           skills (installed at ~/.claude/skills/pathly-*)
     → pathly-fsm MCP server   HTTP FSM at http://127.0.0.1:8765
     → Agent(subagent_type=…)  Claude Code sub-agents (architect, builder, reviewer, tester, …)
     → pathly/plans/<feature>/ filesystem state
```

**Agents** (from `src/pathly_data/core/agents/`) are Claude Code sub-agent roles:

| Role | Model | Job |
|---|---|---|
| director | sonnet | routes intent, chooses rigor |
| architect | opus | technical design |
| planner | sonnet | user stories, conversation breakdown |
| builder | sonnet | implementation |
| reviewer | sonnet | adversarial review → REVIEW_FAILURES.md |
| tester | sonnet | acceptance criteria → TEST_FAILURES.md |
| designer | sonnet | UI/UX design systems |
| quick / scout | haiku | fast lookups |
| orchestrator | haiku | deterministic FSM recovery |

**Rigor levels:** `nano` (1 conv, no review/test) · `lite` (plan+build) · `standard` (full pipeline) · `strict` (standard + audit)

---

## FSM HTTP server

Runs as MCP server (`pathly-fsm` in `.claude/settings.json`) and HTTP server on port 8765.

```bash
# Health check
curl http://127.0.0.1:8765/health

# Current state
curl -s -X POST http://127.0.0.1:8765/next_action \
  -H "Content-Type: application/json" \
  -d '{"flow":"team","topic":"<feature>","project_root":"C:/Users/Yafit/pathly-adapters"}'

# Advance state
curl -s -X POST http://127.0.0.1:8765/complete_stage \
  -H "Content-Type: application/json" \
  -d '{"flow":"team","topic":"<feature>","project_root":"C:/Users/Yafit/pathly-adapters"}'
```

Always verify FSM is running before starting a pipeline:  `Skill(pathly-fsm-call)` → health

---

## Common commands

```bash
# Python package (from repo root)
python -m pytest tests/ -q
python -m build                          # produces build/lib/pathly_data/

# Studio (from studio/)
npm run typecheck                        # tsc --noEmit on renderer
npx electron-vite build                  # full Electron build
node_modules/.bin/tsc --noEmit -p tsconfig.web.json

# Pathly CLI tools
pathly-setup claude --apply              # re-install skills/agents to ~/.claude
pathly-status                            # show active feature state
pathly-ff                                # fast-forward FSM state
pathly-back                              # roll back FSM state
pathly-design "…" --design-system        # UI/UX design system generation

# Version sync check
python3 scripts/check_version_sync.py
```

---

## Editing agent or skill definitions

1. Edit the **core file** first: `src/pathly_data/core/agents/<role>.md` or `core/skills/<category>/<skill>.md`
2. Re-run `pathly-setup claude --apply` (or `python -m build` + install) to propagate to `~/.claude/`
3. Never edit `~/.claude/skills/pathly-*/SKILL.md` directly — those are generated outputs

---

## Commit policy

- **Never push to master without explicit user request.**
- Always confirm branch target before pushing.
- Plans go in `pathly/plans/<feature>/`, never in `plans/<feature>/`.
- `studio/tsconfig.web.tsbuildinfo` is a build artifact — do not commit it.

---

## Studio TypeScript

The renderer (`studio/src/renderer/`) uses React + Vite. Type-check with:
```bash
node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
```
Run from the repo root (not `studio/`). The `tsconfig.web.json` is the renderer config; `tsconfig.node.json` is for the main process.

---

## Telemetry

Stop hook (`src/pathly_hooks/stop_telemetry.py`) fires automatically after every Claude Code session.
Reads token usage and appends to the feature's `02-TOKEN-USAGE.md` pipeline walkthrough file.
