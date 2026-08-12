# Flow Gate Preview — Brief (input to DESIGN)

## Problem
Single-agent, task, and loop runs get a **gate preview** before spawning (`SendPreviewModal`:
meta rows + a collapsible `PromptBanner` + a **Sections** button that opens `SkillSplitModal`
in `assemble` mode). But **flows** — launched from the board's Run-above-input (Flow tab),
the team goal-executor, and the consultation-in-Evaluate — **start immediately with no preview**.
You can't see or trim the per-stage prompts before a multi-stage flow runs.

## Goal
A **flow-specific gate preview** that looks like the current gate, plus a **small vertical stage
stepper** at the top (the flow's stages as a vertical line). Clicking a stage swaps everything
below to *that stage's* composed prompt (same collapse/expand `PromptBanner`); clicking
**Sections** opens *that stage's* prompt in the `SkillSplitModal` assemble modal. Confirm →
run the flow.

## Confirmed decisions (do not re-litigate)
- **Single-agent / task / loop executors keep the CURRENT gate** (`SendPreviewModal`). No change.
- **Flows** get the new gate. Flow entry points: (1) board Run → Flow tab (`FlowForm` →
  `commsStore.startBoardFlow`), (2) team goal-executor, (3) consultation-in-Evaluate
  (`EvaluateBoardButton` decompose paths).
- **Per-stage trim = DEFAULT + USE-ONCE**, modeled on the analyze/diagram config: each stage's
  banner **pre-fills** from that stage's saved config (the default), and any Sections trim at the
  gate applies to **that run only** (transient) — it is **NOT** persisted to `stage_configs` and
  does NOT show up in the phase inspector. (Contrast: `ConfigurePhaseModal` writes the PERSISTENT
  per-stage `stage_configs.{ability_ids, excluded_sections}`.)

## Reuse (don't reinvent)
- `shared/SendPreviewModal/SendPreviewModal.tsx` — the current gate shell (meta + `PromptBanner`
  + Sections → `SkillSplitModal`). The flow gate should reuse `PromptBanner` +
  `SkillSplitModal` (assemble mode), adding the stepper + per-stage state.
- `shared/PromptPreview/PromptPreview.tsx` (`PromptBanner`) — the collapse/expand prompt banner.
- `shared/SkillSplitModal/SkillSplitModal.tsx` — the Sections modal (`assemble` prop).
- `Monitor/FlowStepsPanel/flowSteps.ts` (`deriveFlowSteps`) + `FlowStepper/` — derives a flow's
  ordered stages from `pipelineStates`/`stageRoles`; the vertical stepper already exists here and
  should be reused or mirrored.
- `services/skillCompose.ts` (`composeSkillPrompt(skillRel, {projectRoot})`) — composes one
  skill's prompt + segments. See `GoalsView/useDecomposePreview.ts` for the exact pattern of
  composing a stage prompt for a preview gate (maps a mode → a skill ref, composes, appends the
  task directive). Compose EACH stage's skill this way to fill the banner.

## Composition — how to get each stage's prompt
A flow's stages map to skills (via the flow def's stage→role/skill). To preview all stages
up-front you must compose each stage's skill (`composeSkillPrompt`) — the same way
`useDecomposePreview` composes the planner skill for the goal gate. Determine the per-stage skill
ref from the flow definition. Server flow-def endpoints live under `blueprints/flows/`
(`/flows`, `/flows/<name>`); the FSM's `agent_hint.instructions` are per-transition at runtime,
so up-front you compose from the skill refs, not the runtime hint.

## Backend — the transient per-run per-stage override channel (the hard part)
Use-once means each stage's (possibly trimmed) prompt is sent **verbatim for that stage, that run
only**, without touching `stage_configs`. There is currently NO transient per-stage override
channel: `/runner/start` (`apiStartFlow` → `POST /runner/start`) takes no per-stage prompts, and
`stage_configs.prompt_override` is PERSISTENT. Design a transient channel:
`/runner/start` accepts a `stage_overrides: {<state>: <prompt_text>}` map, stored on the run
(runner state), and the per-stage prompt assembly (`fsm_compose.build_prompt` /
`supervisor` stage spawn) uses the override verbatim for that state when present — analogous to
how a single-agent/goal run threads `prompt_override`, but keyed per stage and per-run (not stored).
Mirror the single-agent override semantics (`sectionsUsed` → send override; plain submit → let the
server compose). Respect the layer rules (db→runner→supervisor→http_server; lazy imports in routes).

## Suggested phasing (architect may adjust)
- P1: the frontend `FlowGatePreview` (stepper + per-stage `PromptBanner` + per-stage Sections),
  composing each stage, wired into the **board Run → Flow tab** path; collect per-stage transient
  overrides.
- P2: the backend transient `stage_overrides` channel end-to-end (so trims actually apply at spawn).
- P3: wire the same gate into the team goal-executor + consultation-in-Evaluate entry points.

## Constraints (Pathly conventions — enforce)
- Studio UI rules (`studio/CLAUDE.md`): one component per folder (`Name/Name.tsx` +
  `Name.module.css`), ≤150 lines/file, **no inline styles** (CSS modules + `tokens.css` vars),
  explicit `type="button"`, ARIA spread pattern, responsive (min-width:0, no fixed widths).
- Python SOLID rules (root `CLAUDE.md`): ≤400 lines/file, one domain per blueprint, layer
  dependency direction, shared helpers in `_helpers.py`.
- The ✦ Sparkles icon now means "AI-spawn control" — the gate's run button is an AI spawn.
- Update the matching living doc (studio/orchestrator CLAUDE.md) in the SAME change.
- Verify: renderer `tsc -p studio/tsconfig.web.json`; Python `pytest`; the file-backed prompt
  parser + compose paths have tests to mirror.

## Deliverable
`DESIGN.md` in this folder: component/module breakdown (files to add/change with responsibilities),
the transient-override data flow (client → `/runner/start` → per-stage spawn), the composition
approach, and the P1/P2/P3 cut. Then BUILD implements P1 (+P2 if tractable), REVIEW checks it.
