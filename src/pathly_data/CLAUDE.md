# pathly_data — Data & Adapters Layer

Canonical source of truth for all agent role contracts, skill definitions, plan templates, and adapter configs.

## Core structure

```
core/
  agents/       agent role contracts, grouped by function:
                  building/   builder, designer
                  planning/   architect, planner, po
                  quality/    reviewer, tester
                  research/   scout, explorer, web-researcher
                  support/    orchestrator, quick, human
                  director.md (top-level router)

  skills/       skill markdown, grouped by category:
                  flow/         ff, back, pause, end, status
                  development/  build, review, test, design, debug, explore, fix
                  planning/     plan, po, prd-import, storm, retro
                  team/         discover, plan, design, build, review, test
                  utilities/    archive, log, log-agent-done, lessons, meet,
                                verify-state, fsm-call, scout-path

  templates/    plan file templates:
                  plan/   USER_STORIES, IMPLEMENTATION_PLAN, CONVERSATION_PROMPTS,
                          FEATURE_INDEX, PROGRESS, EDGE_CASES, FLOW_DIAGRAM,
                          HAPPY_FLOW, ARCHITECTURE_PROPOSAL, MERMAID_DIAGRAM
                  pipeline-walkthrough/   01-PIPELINE-FLOW, 02-TOKEN-USAGE, 03-ARTIFACT-MAP

  flows/        flow YAML files read by the FSM:
                  team.flow.yaml      full pipeline (STORM→PLAN→DESIGN→BUILD→REVIEW→TEST→RETRO→DONE)
                  debug.flow.yaml     debug flow
                  explore.flow.yaml   exploration flow
                  test.flow.yaml      test-only flow
                  quick-fix.flow.yaml nano/lite fast path

  design/       UI/UX design subsystem — powers `pathly-design` command:
                  data/   colors.csv, fonts.csv, styles.csv, typography.csv,
                          ux-guidelines.csv, charts.csv, products.csv,
                          stacks/  (react, nextjs, vue, svelte, swiftui, flutter, …)
                  scripts/  design_system.py, core.py, search.py
                  cli.py

adapters/
  claude/       Claude Code adapter
                  _meta/          agent YAMLs + skill YAMLs (one per agent/skill)
                  .claude-plugin/ plugin.json, marketplace.json
  codex/        Codex adapter (_meta/ agent + skill YAMLs)
  copilot/      Copilot adapter (_meta/ agent + skill YAMLs)
```

## Adapters

Three adapters derive from `core/`:

| Adapter | Install destination |
|---|---|
| `claude/` | `~/.claude/agents/` and `~/.claude/skills/pathly-*/` |
| `codex/` | `~/.codex/agents/`, `~/.agents/skills/`, and `~/.codex/plugins/pathly/` |
| `copilot/` | `~/.vscode/extensions/pathly/agents/` and `~/.vscode/extensions/pathly/skills/` |

Each adapter's `_meta/` directory holds per-agent and per-skill YAML files that supply host-specific metadata (model name, tool list, `can_spawn` flag, install destination). `pathly-setup <host> --apply` stitches `core/` content with `_meta/` and writes deployable files.

## FSM response contract

`/next_action` returns `agent_hint` as the primary routing contract for all adapters:
- `agent_hint.role` — `"worker"` or `"explorer"` (host-neutral delegation signal)
- `agent_hint.instructions` — full prompt for the next agent
- `decision` — `"continue"` / `"block"` / `"escalate"` (automation gate)
- `codex_subagent` — **frozen legacy field**; present for backward compat only — new adapters must read `agent_hint`, not `codex_subagent`

## Adapter sync rule — CRITICAL

`core/` is the **single source of truth**. The three adapters (`claude/`, `codex/`, `copilot/`) are derived outputs.

**Any change to a core agent or skill must be reflected in all three adapter `_meta/` directories.**

The right way to do this:

```bash
# After editing any core file:
pathly-setup claude --apply    # syncs to ~/.claude/ and regenerates claude adapter
python -m build                # rebuilds the package (all adapters)
```

If you manually edit `_meta/` files in one adapter, you **must** make the same change in the other two, or run the build step above. Never patch one adapter and leave the others stale.

## Editing an agent or skill

1. Edit the **core file**: `core/agents/<category>/<role>.md` or `core/skills/<category>/<skill>.md`
2. Run `pathly-setup claude --apply` to propagate to `~/.claude/` and the claude adapter
3. Run `python -m build` to rebuild all adapters (codex, copilot) from core
4. Never edit `~/.claude/skills/pathly-*/SKILL.md` directly — those are generated outputs

## Design subsystem

`core/design/` is separate from agents/skills. It provides the data and scripts behind `pathly-design "…" --design-system`. When adding new colors, fonts, or stacks, edit the relevant CSV in `core/design/data/`, not any adapter file.
