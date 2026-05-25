# pathly-commands-v2 — Feature Index

## What this feature is

**Read `pathly/plans/STRATEGY.md` first — it explains the dual-engine goal
this plan serves.**

Five new commands plus a `meet` enhancement and deferred contextual menu for
four entry-point skills. Commands that need no LLM reasoning are Python CLI
scripts; the one that spawns an agent is a full LLM skill.

All commands work with **both routing engines** (LLM-driven and Python FSM).
They read `engine` from `STATE.json` and route accordingly.

## Why it matters

The current command set (`team`, `debug`, `explore`, `go`, `pause`, `end`,
`start`) covers pipeline execution but has no lightweight operations for
inspection, correction, or shortcutting. Developers must open a full
conversation just to check what state they are in, or manually edit STATE.json
to roll back. These commands close that gap.

## Prior work this builds on

- `http-fsm-driver` — MUST be complete. `next_action` and `complete_stage` HTTP
  tools are called by `fix.md` and the updated entry-point skills.
- `fsm-transition-actions` — DONE. `transition_actions` in flow YAMLs is what
  `pathly-ff` warns about before advancing state.

## Command map

| Command | Type | Conversation |
|---------|------|-------------|
| `pathly-status` | Python CLI + skill wrapper | Conv 1 |
| `pathly-log` | Python CLI + skill wrapper | Conv 1 |
| `pathly-back` | Python CLI + skill wrapper | Conv 2 |
| `pathly-ff` | Python CLI + skill wrapper | Conv 2 |
| `fix` | LLM skill only | Conv 3 |
| `meet` step 5 | Edit existing skill | Conv 4 |
| `go`/`pause`/`end`/`start` | Edit existing skills | Conv 5 |

## Key file paths

**New Python modules:**
- `src/pathly_orchestrator/status_cli.py` — cross-feature dashboard
- `src/pathly_orchestrator/log_cli.py` — EVENTS.jsonl timeline renderer
- `src/pathly_orchestrator/back_cli.py` — one-state rollback
- `src/pathly_orchestrator/ff_cli.py` — fast-forward via `complete_stage`

**New entry points (pyproject.toml):**
- `pathly-status = "pathly_orchestrator.status_cli:main"`
- `pathly-log    = "pathly_orchestrator.log_cli:main"`
- `pathly-back   = "pathly_orchestrator.back_cli:main"`
- `pathly-ff     = "pathly_orchestrator.ff_cli:main"`

**New core skill files:**
- `src/pathly_data/core/skills/status.md` — thin wrapper (calls `pathly-status`)
- `src/pathly_data/core/skills/log.md` — thin wrapper (calls `pathly-log`)
- `src/pathly_data/core/skills/back.md` — thin wrapper (calls `pathly-back`)
- `src/pathly_data/core/skills/ff.md` — thin wrapper (calls `pathly-ff`)
- `src/pathly_data/core/skills/fix.md` — full LLM skill

**New adapter YAML files (all three adapters — claude, codex, copilot):**
- `src/pathly_data/adapters/<adapter>/_meta/status_skill.yaml`
- `src/pathly_data/adapters/<adapter>/_meta/log_skill.yaml`
- `src/pathly_data/adapters/<adapter>/_meta/back_skill.yaml`
- `src/pathly_data/adapters/<adapter>/_meta/ff_skill.yaml`
- `src/pathly_data/adapters/<adapter>/_meta/fix_skill.yaml`

**Edited skill files:**
- `src/pathly_data/core/skills/meet.md` — Step 5 gets [5] Escalate to pipeline
- `src/pathly_data/core/skills/go.md` — add contextual panel
- `src/pathly_data/core/skills/pause.md` — add read-only panel
- `src/pathly_data/core/skills/end.md` — add read-only summary panel
- `src/pathly_data/core/skills/start.md` — add panel on option [4]

## Verify command (after all conversations complete)

```bash
python -c "from pathly_orchestrator.status_cli import main; print('OK')"
python -c "from pathly_orchestrator.log_cli import main; print('OK')"
python -c "from pathly_orchestrator.back_cli import main; print('OK')"
python -c "from pathly_orchestrator.ff_cli import main; print('OK')"
grep "pathly-status\|pathly-log\|pathly-back\|pathly-ff" pyproject.toml
grep "complete_stage" src/pathly_data/core/skills/fix.md
grep "Escalate to pipeline" src/pathly_data/core/skills/meet.md
grep "next_action" src/pathly_data/core/skills/go.md
pytest -q
```
