# pathly_data — Data & Adapters Layer

Canonical source of truth for all agent role contracts, skill definitions, plan templates, and adapter configs.

## Core structure

```
core/
  agents/       agent role contracts, grouped by function:
                  building/   builder, designer
                  planning/   architect, planner, po
                  quality/    reviewer, tester
                  research/   scout, explorer, web-researcher, evaluator
                  support/    orchestrator, quick, human
                  director.md (top-level router)

  skills/       skill markdown, grouped by category:
                  controls/     start, go, ff, back, pause, end, status, pathly
                  development/  build, review, test, design, debug, explore, fix,
                                quick-fix, execute-task, drain-dag, analyze, split,
                                summarize (+ -gist / -detailed), commit
                  planning/     plan, po, prd-import, storm, retro, evaluate,
                                consolidate, create-feature, dag-sketch, feature-decompose
                  team/         team, discover, plan, design, architect, research,
                                build, review, test, retro
                  utilities/    archive, log, log-agent-done, lessons, meet,
                                verify-state, fsm-call, scout-path, reflect,
                                dispatch, help
                  fix/          fix (blocked-feedback quick fix)
                  custom/       user-defined custom skills
                  debug/        debug-specific skills (build, verify)
                  fragments/    reusable prompt fragments

  templates/    plan file templates:
                  plan/   USER_STORIES, IMPLEMENTATION_PLAN, CONVERSATION_PROMPTS,
                          FEATURE_INDEX, PROGRESS, EDGE_CASES, FLOW_DIAGRAM,
                          HAPPY_FLOW, ARCHITECTURE_PROPOSAL, MERMAID_DIAGRAM
                  pipeline-walkthrough/   01-PIPELINE-FLOW, 02-TOKEN-USAGE, 03-ARTIFACT-MAP
                  summary/   gist.md, topic-map.md, detailed.md — depth-format contracts
                             injected as <summary_format> by POST /skills/compose;
                             also served raw by GET /skills/summary-format/<style>

  flows/        flow YAML files read by the FSM:
                  team.flow.yaml         full pipeline (STORMING→PLANNING→DESIGNING→BUILDING→REVIEWING→TESTING→RETRO→DONE)
                  team-build.flow.yaml   trimmed team flow used by the goal `team` executor
                  consultation.flow.yaml PO→architect→researcher→designer→planner goal decompose
                  debug.flow.yaml        debug flow
                  explore.flow.yaml      exploration flow
                  test.flow.yaml         test-only flow
                  quick-fix.flow.yaml    nano/lite fast path

  design/       UI/UX design subsystem — powers `pathly-design` command:
                  data/   colors.csv, google-fonts.csv, styles.csv, typography.csv,
                          ux-guidelines.csv, charts.csv, products.csv, icons.csv,
                          landing.csv, app-interface.csv, react-performance.csv, … (14 CSVs)
                          stacks/  (react, nextjs, vue, svelte, swiftui, flutter, …)
                  scripts/  design_system.py, core.py, search.py
                  cli.py

adapters/
  claude/        Claude Code adapter
                   _meta/          agent YAMLs + skill YAMLs (one per agent/skill)
                   .claude-plugin/ plugin.json, marketplace.json
  codex/         Codex adapter (_meta/ agent + skill YAMLs)
  copilot/       Copilot adapter (_meta/ agent + skill YAMLs)
  antigravity/   Antigravity CLI adapter (_meta/ agent + skill YAMLs; Gemini models)
```

## Adapters

Four adapters derive from `core/`:

| Adapter | Install destination |
|---|---|
| `claude/` | `~/.claude/agents/` and `~/.claude/skills/pathly-*/` |
| `codex/` | `~/.codex/agents/`, `~/.agents/skills/`, and `~/.codex/plugins/pathly/` |
| `copilot/` | `~/.vscode/extensions/pathly/agents/` and `~/.vscode/extensions/pathly/skills/` |
| `antigravity/` | `~/.gemini/antigravity-cli/agents/` and `~/.gemini/antigravity-cli/skills/` |

Each adapter's `_meta/` directory holds per-agent and per-skill YAML files that supply host-specific metadata (model name, tool list, `can_spawn` flag, install destination). `pathly-setup <host> --apply` stitches `core/` content with `_meta/` and writes deployable files.

## Skill composition

`src/pathly_orchestrator/skills/compose.py` assembles stage skills from reusable fragments. One resolver serves both skill-delivery modes — runtime (runner builds the prompt in Python) and build-time (`pathly-setup` writes installed skills to disk).

**Manifest:** `core/skills/composition.yaml` is the authoritative map. Keys are core-skills-relative paths without `.md` (e.g. `team/build`, `development/build`).

**Agnosticism principle — skill = *what*, fragments = *how it connects to Pathly*.** A skill `.md` body must be the agnostic TASK: no board endpoints, no `/comms/*` or `/runner/*` calls, no FSM transitions baked in. ALL connection to Pathly comes from fragments (selected by the skill's work-kind + the spawn context — together its *profile*). Two categories are the deliberate exception, where the board/FSM call IS the job: (1) operational/utility skills (`log-*`, `fsm-call`, `commit`, the control skills); (2) **board-native skills** whose purpose is board orchestration — `development/drain-dag`, `planning/evaluate`, `planning/consolidate`, `planning/feature-decompose`, and the DAG-drain path inside `team/build`/`development/build` (they claim/complete tasks or seed goals — the board IS their domain). `planning/plan` keeps only its decomposer-specific goal find-or-create in-body (per-task posting is the `task-dag-post` fragment). **Migrated** — `team/architect` + `team/research` now take board write-back from the `comms-post` fragment instead of a body curl (unified-cli-finish Phase 1). See `pathly/features/unified-cli-finish/plans/SPEC.md`.

**Composition contract:**

```
assembled = _strip_leading_frontmatter(skill body) + defaults fragments + per-skill fragments
```

- `defaults` applies to every skill listed in the `skills:` map (currently `progress-logging`).
- A skill **absent** from `skills:` is returned **raw and unchanged** — no fragments, no defaults. Skills are converted incrementally; not all are in the map yet.
- `no_defaults: true` on a skill entry opts it out of the global defaults entirely. Used on nine skills: the five pure-transform derivations (`development/summarize`, `development/summarize-gist`, `development/summarize-detailed`, `development/analyze`, `development/split`) plus four task/board skills with no pipeline phases (`planning/create-feature`, `development/drain-dag`, `development/execute-task`, `planning/feature-decompose`) — where `progress-logging` is dead weight in their prompt.
- A fragment entry is a bare name (`feedback-protocol`) or a gated object (`{ name: spawn-rules, requires: can_spawn }`). Gated entries are dropped when the adapter's capability flag is false.
- `blocks:` is an optional top-level key for named fragment lists (`full-build`, `lite-build`, `review-strict`) — callers resolve these via `compose_skill_with_block()`. *(The unified-cli-composition plan renames `blocks:` → `profiles:` — a profile being a named, context-selected fragment bundle — but that rename is plan P1d, not yet built; `blocks:` remains the live manifest key and helper name.)*

**Skills currently in the manifest (converted):** `team/build`, `team/review`, `team/test`, `team/plan`, `team/design`, `team/retro`, `team/architect`, `team/research`, `development/build`, `development/review`, `development/test`, `development/design`, `development/explore`, `development/debug`, `development/summarize`, `development/summarize-gist`, `development/summarize-detailed`, `development/analyze`, `development/split`, `debug/build`, `debug/verify`, `fix/build`, `planning/plan`, `planning/po`, `planning/create-feature`, `planning/dag-sketch`, `planning/evaluate`, `planning/consolidate`, `planning/retro`, `planning/feature-decompose`, `development/execute-task`. (`development/drain-dag` composes `code-query` + `completion-report` (`no_defaults`) — it does its board CRUD inline as the `single` executor's drain loop. The `loop` executor's per-task agents compose `development/execute-task` → `comms-post` + `code-query` + `completion-report` (`no_defaults` — a per-task agent has no pipeline phases). Per-task **progress** is NOT a fragment: it is guaranteed **server-side** — the loop via `scheduler._post_task_status`, the single via the `/comms/tasks/{claim,complete,fail}` handlers (`blueprints/comms/_helpers.post_task_status`) — so an agent-side progress fragment would only duplicate it.) The `completion-report` fragment requires the `AGENT_DONE` it writes to set an explicit `outcome: success|failed` (+ `error`) — the supervisor's loop executor reads it as the authoritative pass/fail signal, so a clean exit over failed work is not counted as success.

**Dash-safety — `_strip_leading_frontmatter`:** several skill bodies begin with `---` (empty/doubled horizontal rule, or real YAML frontmatter). A prompt delivered via `claude -p <prompt>` is parsed as a CLI argument; an argument starting with `--` is rejected as an unknown option (`error: unknown option '---...'`). `_strip_leading_frontmatter` removes any leading `--- … ---` block before the skill body is used in a composed prompt. Two mirror implementations enforce this:
- Python: `src/pathly_orchestrator/skills/compose.py` — `_strip_leading_frontmatter` (called in `compose_skill`, `compose_skill_with_block`)
- Python: `src/pathly_orchestrator/adapters.py` — `_dash_safe_prompt` in `resolve_command` (covers raw/absent skills and any other prompt source)
- TypeScript: `studio/src/renderer/src/services/cliEngine.ts` — `dashSafePrompt` in `buildHeadlessArgv`

## FSM response contract

`/next_action` returns `agent_hint` as the primary routing contract for all adapters:
- `agent_hint.role` — `"worker"` or `"explorer"` (host-neutral delegation signal)
- `agent_hint.instructions` — full prompt for the next agent
- `decision` — `"continue"` / `"block"` / `"escalate"` (automation gate)
- `preferred_adapter` — per-stage adapter from the flow's `adapter_map` (passive relay; FSM never launches processes)
- `codex_subagent` — **frozen legacy field**; present for backward compat only — new adapters must read `agent_hint`, not `codex_subagent`

## Canonical `adapter_map` shape

`adapter_map` is an **optional** top-level key in any `.flow.yaml`. When present it tells the FSM which CLI adapter should handle each pipeline stage. The FSM emits `preferred_adapter` in every `/next_action` response — passive relay only; it never launches processes.

```yaml
adapter_map:
  default: claude          # REQUIRED if adapter_map is present; must be in {claude, codex, copilot, antigravity}
  BUILDING: codex          # optional per-state override; key must be a declared state
  REVIEWING: claude
```

**Resolution precedence (highest → lowest):**
1. *(reserved: per-feature STATE.json override — follow-up, not implemented yet)*
2. `adapter_map[current_state]`
3. `adapter_map["default"]`
4. `""` — no `adapter_map`; fully backward-compatible

**Known adapter set:** `claude`, `codex`, `copilot`, `antigravity`. The FSM validator (`state.py`) enforces this set and requires `default`. Studio serializer (`utils.ts`) must conform to this exact shape — a round-trip test enforces it.

---

## Adapter sync rule — CRITICAL

`core/` is the **single source of truth**. The four adapters (`claude/`, `codex/`, `copilot/`, `antigravity/`) are derived outputs.

**Any change to a core agent or skill must be reflected in all four adapter `_meta/` directories.**

The right way to do this:

```bash
# After editing any core file for the FIRST TIME (new installs):
pathly-setup claude --apply    # syncs to ~/.claude/ and regenerates claude adapter

# After editing a core file that is ALREADY INSTALLED (updates fragments, skill bodies, agents):
pathly-setup claude --apply --repair   # --repair overwrites existing Pathly-owned files

# Rebuild all adapters (codex, copilot) from core:
python -m build
```

> **Why `--repair`?** `--apply` alone skips files already tracked in the manifest. Use `--repair`
> every time you update an existing core agent, skill, or fragment — otherwise installed files
> stay stale and the changes never reach the running agent.

If you manually edit `_meta/` files in one adapter, you **must** make the same change in the other three, or run the build step above. Never patch one adapter and leave the others stale.

## Editing an agent or skill

1. Edit the **core file**: `core/agents/<category>/<role>.md` or `core/skills/<category>/<skill>.md`
2. Run `pathly-setup claude --apply` to propagate to `~/.claude/` and the claude adapter
3. Run `python -m build` to rebuild all adapters (codex, copilot) from core
4. Never edit `~/.claude/skills/pathly-*/SKILL.md` directly — those are generated outputs

## Design subsystem

`core/design/` is separate from agents/skills. It provides the data and scripts behind `pathly-design "…" --design-system`. When adding new colors, fonts, or stacks, edit the relevant CSV in `core/design/data/`, not any adapter file.
