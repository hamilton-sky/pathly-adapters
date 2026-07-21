# Flow Gate Preview — DESIGN

Technical design for the flow-specific gate preview. Grounded in the real code (not assumptions):
the current gate is `SendPreviewModal`; the running-flow stepper is `FlowStepsPanel`; the per-stage
compose pattern is `useDecomposePreview`; the single-agent transient-override precedent is
`board_run.start_board_run(prompt_override=…)`.

---

## 0. The one hard constraint that shapes everything

`skills/abilities.py::ability_segments` is *"the single helper shared by `POST /skills/compose`
and `board_run._compose_skill_body`, so the gate preview and the actual spawn can never disagree."*
(src/pathly_data/CLAUDE.md). The flow gate must preserve that invariant **per stage**: what the
banner shows == what the stage spawns. We get this for free by composing each stage from the SAME
`composeSkillPrompt` (→ `/skills/compose`) the server uses, and by sending any trim back **verbatim**
through a transient channel that mirrors `prompt_override` — never a second, divergent assembly.

### The faithful-override rule (mirrors `board_run`)

`board_run.start_board_run` already solved "use-once prompt" for single agents:

```
prompt_override present ─► _inject(prompt_override)          # var-substitute the human's text
                          + server-only tail (board ctx,     # NEVER shown verbatim at the gate,
                            cadence, cwd)                     #   so it is appended, not replaced
prompt_override absent   ─► compose skill + fragments + …    # let the server compose
```

For a **flow stage** the exact analogue lives in `fsm_compose.build_prompt`, whose return is:

```
agent_text  (skill + fragments + abilities + persistent trim)   ← the CLIENT-knowable part
  + context  (runner contract: "supervisor owns the FSM")       ─┐
  + history  (this run's own inter-stage progress)               │ server-only tail —
  + board_block (live board context)                             │ always appended,
  + code_block  (code-structure channel)                        ─┘ never in the gate
```

So the transient per-stage override must replace **only `agent_text`** and let `build_prompt`
append the tail. That single fact is why the override is applied *inside* `build_prompt` (P2),
not by swapping `instructions` in the supervisor — a supervisor-level swap would drop the runner
contract + live board context and cause the double-advance / blind-agent failures those blocks exist
to prevent.

---

## 1. Component / module breakdown

### 1a. Frontend — NEW (all under `studio/src/renderer/src/components/shared/FlowGatePreview/`)

The gate is **run-agnostic**: it collects a `{state: prompt}` override map and calls
`onConfirm(overrides)`. It never starts a run itself — so P3 reuses it by wiring a different
`onConfirm`. Folder-per-component, ≤150 lines/file, CSS modules + `tokens.css`, no inline styles.

| File | Responsibility | Budget |
|---|---|---|
| `FlowGatePreview.tsx` | Modal shell orchestrator: header (flow name + meta), stepper region on top, per-stage `PromptBanner`, footer (`Sections` · `Cancel` · ✦ `Run flow`). Owns `splitOpen`; renders `SkillSplitModal` (assemble) for the selected stage. Wires the two hooks below. `createPortal` like `SingleAgentButton`. | ≤150 |
| `FlowGatePreview.module.css` | Modal-shell styling (backdrop / header / stepper region / banner wrap / footer). Mirrors `SendPreviewModal.module.css` vocabulary; kept local (no cross-folder CSS import). | — |
| `useFlowGateStages.ts` | **Data hook** (returns data only, no setters — studio rule). Fetches the flow graph, derives ordered steps via `deriveFlowSteps`, composes each composable stage via `composeSkillPrompt`. Returns `{ steps, stageOf(state)→{skillRef, role, prompt, segments}, loading }`. | ≤110 |
| `useFlowGateState.ts` | **UI-state hook**: `selectedState`, per-state edited `text`, per-state `sectionsUsed`, handlers (`selectStage`, `editText`, `applySections`). Seeds `text[state]` from the composed prompt when it arrives. Exposes `buildOverrides()` → `{state: text}` for `sectionsUsed` states only. | ≤90 |
| `flowGraph.ts` | Tiny service: `fetchFlowGraph(name)` → `{ states, agentMap, roleMap }` by parsing `GET /flows/<name>/graph` (`{graph:{states, agent_map, role_map, …}}`). Isolates the API/parse concern; unit-testable. | ≤50 |
| `FlowGateStepper/FlowGateStepper.tsx` | Presentational vertical stepper: takes `steps: FlowStep[]`, `selectedState`, `onSelect`. Renders `<ol>` of a small inlined `GateStepRow` (rail dot + connector + clickable label), marking `selectedState` active. | ≤90 |
| `FlowGateStepper/FlowGateStepper.module.css` | Rail / dot / connector / selected styling. | — |

**Reuse (not reinvented):** `PromptBanner` (`shared/PromptPreview`), `SkillSplitModal` + `cellsToMarkdown`
(`shared/SkillSplitModal`, `assemble` mode), `composeSkillPrompt` + `headingLayers` + `ComposedSegment`
(`services/skillCompose`), and the **pure** `deriveFlowSteps` + `FlowStep`/`StepStatus` types
(`Monitor/FlowStepsPanel/flowSteps.ts`).

> **Stepper decision — reuse the util, mirror the row.** `deriveFlowSteps` is a pure function (no
> store import) → import it directly. `StepRow`/`FlowStepper` are store-coupled to the *running*
> flow (`useStore(s => s.pipelineStates…)`) and live under `Monitor/` — a `shared/` component
> importing a `Monitor/` component is the wrong dependency direction, and the gate needs a
> *selected* (not FSM-active) highlight + a "Preview" affordance. So `GateStepRow` is a ~30-line
> mirror inside the gate folder. Net: pure logic reused, ~40 lines of rail CSS duplicated — a
> deliberate trade for clean layering + self-containment.

### 1b. Frontend — CHANGE (P1 wiring on the board Run → Flow path)

| File | Change | Budget note |
|---|---|---|
| `SingleAgentButton/FlowForm.tsx` | "Run flow" opens the gate (local `gateOpen` bool) instead of running immediately; renders `<FlowGatePreview flow={flowKey} boardKey interactive onConfirm={(ov)=>{ onRunFlow(flowKey,{interactive,stageOverrides:ov}); onClose() }} onCancel=… />`. `onRunFlow` type gains `stageOverrides?`. | +~8 lines; stays <150 |
| `SingleAgentButton/SingleAgentButton.tsx` | `onRunFlow` prop type gains `stageOverrides?: Record<string,string>`. | +1 line |
| `CommsPanel/CommsPanel.tsx` | `handleRunFlow(flow, opts)` forwards `opts.stageOverrides` to `startBoardFlow` (the `startBoardFlow` branch only; the `decompose*` consultation branches stay untouched → P3). | +2 lines |
| `store/commsStore.ts` | `startBoardFlow(key, flow, opts?)` — `opts` gains `stageOverrides?`; passed to `apiStartFlow`. | +2 lines |
| `store/commsApi.ts` | `StartFlowOpts` gains `stageOverrides?: Record<string,string>`; `apiStartFlow` puts it on the body as `stage_overrides` when non-empty. | +3 lines |

### 1c. Backend — CHANGE (P2 transient channel; each change is a few lines, layer-safe)

| File (layer) | Change | Budget |
|---|---|---|
| `supervisor/state.py` | `RunnerState` gains `stage_overrides: dict = field(default_factory=dict)` (in-memory, per-run — never persisted). | +1 line, file 149→~150 |
| `supervisor/api.py::start_run` | New param `stage_overrides: Optional[dict] = None`; stored on the `RunnerState(...)`. | +2 lines |
| `http_server/blueprints/runner/api_lifecycle.py::runner_start` | Read + **validate** `stage_overrides` from the body (dict[str,str], bounded — see §4), pass into `_sup.start_run(...)`. | +~12 lines, file ~419→~431 |
| `supervisor/orchestrator.py::_loop` | Add `stage_overrides` to the `fhc.next_action({...})` payload **only when non-empty** (common case = empty = zero overhead). | +2 lines |
| `fsm_ops.py::next_action` | `ov = (args.get("stage_overrides") or {}).get(state_info["current_state"])`; pass `stage_override=ov` to `build_prompt(...)`. | +3 lines |
| `fsm_compose.py::build_prompt` | New param `stage_override: str = ""`. When set: `agent_text = stage_override` (skip compose **and** `_apply_stage_selection`); still run `_inject_prompt_vars` + append `context/history/board/code`. | +~8 lines, file 547→~555 |

No blueprint-domain, layer-direction, or 400-line rule is violated: the override travels **downward
as a parameter** (http_server → supervisor → fsm_ops → fsm_compose); `build_prompt` never reads the
registry (it *can't* — `fsm_compose` is imported *by* `supervisor`), which is exactly why the
override is passed in, not looked up.

### 1d. Docs (same-change, per the doc-sync rule)

- `studio/CLAUDE.md` — one line under the run-controls area: the Flow tab now gates through
  `FlowGatePreview` (stepper + per-stage banner + Sections), collecting transient per-stage overrides.
- `src/pathly_orchestrator/CLAUDE.md` — document `stage_overrides` on `/runner/start` +
  `RunnerState`, and the `build_prompt(stage_override=…)` verbatim-per-state behavior (contrast with
  the *persistent* `stage_configs` trim).

---

## 2. The transient per-run per-stage override data flow

Exact functions/routes, end to end. `{}` = the override map `{ <STATE>: <prompt_text> }`.

```
  GATE (P1)                          WIRE (P1 client / P2 server)                 SPAWN (P2)
  ─────────                          ────────────────────────────                 ──────────
FlowGatePreview
  useFlowGateState.buildOverrides()   ── only sectionsUsed stages ──►  { PLANNING: "…trimmed…" }
        │ onConfirm({})
        ▼
FlowForm ► onRunFlow(flow,{interactive, stageOverrides})
        ▼
CommsPanel.handleRunFlow ► startBoardFlow(key, flow, { stageOverrides })      [store]
        ▼
commsApi.apiStartFlow ► POST /runner/start  body.stage_overrides = {}         [client]
════════════════════════════════════════════════════════════════════════════ HTTP
runner/api_lifecycle.runner_start ► validate {} ► _sup.start_run(stage_overrides={})
        ▼
supervisor.api.start_run ► RunnerState.stage_overrides = {}   (in-memory, per-run, NOT persisted)
        ▼
supervisor.orchestrator._loop  (per stage):
     fhc.next_action({flow, topic, project_root, goal_id,
                      stage_overrides: state.stage_overrides})   ◄─ only if non-empty
        ▼
════════════════════════════════════════════════════════════════════════════ HTTP (or in-proc degrade)
core/fsm.next_action_endpoint ► passes whole body ► fsm_ops.next_action(args)
     ov = args["stage_overrides"].get(current_state)     e.g. current_state == "PLANNING" ► ov set
        ▼
fsm_compose.build_prompt(..., stage_override=ov):
     if ov:  agent_text = ov                       ◄── verbatim, replaces ONLY the composed body
     else:   agent_text = compose_skill(...) [+ _apply_stage_selection]   (persistent stage_configs)
     agent_text = _inject_prompt_vars(agent_text, …)      ◄── <feature>/<board>/<fsm_feature>/<out_path>
     return agent_text + context + history + board_block + code_block      ◄── server-only tail preserved
        ▼
  (supervisor may still append _decompose_directive on top — P3 goal runs — nothing lost)
```

Key properties:

- **In-memory, per-run, not persisted.** Lives only on `RunnerState.stage_overrides`; dies with the
  run. Never touches `stage_configs` (the persistent flow-phase-inspector selection) — so it never
  shows up in `ConfigurePhaseModal`. This is exactly the analyze/diagram "default + use-once" model
  the brief names.
- **Verbatim, keyed per state.** `build_prompt` substitutes the override in place of `agent_text` for
  *that* state only; every other state composes normally. Raw fragment placeholders
  (`<feature>`, `<fsm_feature>`, `<board>`, `<out_path>`) inside the override are resolved by the
  same `_inject_prompt_vars` that would run for a composed body — so an overridden `completion-report`
  still writes a correctly-keyed `AGENT_DONE` (no vanished/unbilled run).
- **No route-signature surgery.** `/next_action` already forwards `request.get_json()` wholesale to
  `fsm_ops.next_action`, and `fhc.next_action` json-dumps the whole payload (and the in-process
  degrade path passes the same dict) — so `stage_overrides` rides through both transports untouched.
- **Zero-cost when unused.** `sectionsUsed` gates map membership; a plain-submit run sends `{}` and
  `_loop` omits the field, so nothing changes on the wire or in `build_prompt` for the common path.
- **Dash-safety** is already handled downstream (`adapters._dash_safe_prompt` on every headless argv
  build), so an edited override that starts with `---` can't break the spawn.

---

## 3. Composition approach — filling each stage's banner

Mirrors `useDecomposePreview` (which composes `planning/plan` for the goal gate), but generalized to
*every* stage of an arbitrary flow.

1. **Resolve stages from the flow def.** `fetchFlowGraph(name)` → `GET /flows/<name>/graph` returns
   `{ graph: { states[], agent_map, role_map, adapter_map, … } }` (verified against
   `consultation.flow.yaml` / `team.flow.yaml`). `graph.agent_map[state]` is the per-stage **skill
   ref** (`team/build`, `planning/plan`, `planning/po`, …) — the exact key `build_prompt` reads.
2. **Order + decorate** with the pure `deriveFlowSteps(states, role_map, null, [])` — `fsmState=null`,
   `events=[]` → all steps `pending`, and its filter drops gate/terminal pseudo-states
   (`NO_DAG_SEEDED`, keeps `DONE`) exactly as the running-flow dock does. The gate composes only
   states that have an `agent_map` entry (skip `DONE`).
3. **Compose each stage** with `composeSkillPrompt(skillRef, { projectRoot })` → `{ prompt, segments }`
   — the SAME `/skills/compose` (skill body + Pathly fragments + any abilities) the spawn uses. The
   composed prompt carries raw `<feature>`/`<board>` placeholders (substituted server-side at spawn),
   which is correct and identical to how `board_run` treats an override.
4. **Fill the banner + Sections.** The selected stage's `prompt` seeds `PromptBanner` (collapse/expand,
   eye/pencil edit). `Sections` opens `SkillSplitModal` with `rawContent={text[selected]}`, `assemble`,
   and `headingLayers={headingLayers(segments[selected])}` — so the platform-fragment **lock**
   (`## Completion report` etc. uncheckable) holds per stage. `onConfirm(cells)` →
   `editText(selected, cellsToMarkdown(cells))` + mark `sectionsUsed[selected]` = the single-agent
   `sectionsUsed` semantics, per stage.
5. **Fail-soft.** `composeSkillPrompt` returns `null` on any server error → the banner shows a stub
   (`# <role>\n_(the <skill> skill composes at spawn.)_`, like `useDecomposePreview`), the stage stays
   plain-submit (no override), and the server composes it normally. Run is never blocked by a bad
   compose.

```
GET /flows/team-build/graph
   states:    [PLANNING, BUILDING, REVIEWING, TESTING, DONE]
   agent_map: {PLANNING: team/plan, BUILDING: team/build, REVIEWING: team/review, TESTING: team/test}
        │
        ▼  deriveFlowSteps(states, role_map, null, [])  →  ● PLANNING  ● BUILDING  ● REVIEWING  ● TESTING  ○ DONE
        ▼  composeSkillPrompt(agent_map[state])          →  per-stage {prompt, segments}
   click a step ─► banner + Sections swap to THAT stage's composed prompt
```

---

## 4. The P1 / P2 / P3 cut

```
 P1  frontend gate + compose, board Run→Flow path (startBoardFlow), collect overrides
 ────────────────────────────────────────────────────────────────────────────────────
 P2  backend transient channel end-to-end — trims actually apply at spawn
 ────────────────────────────────────────────────────────────────────────────────────
 P3  same gate into team goal-executor + consultation-in-Evaluate entry points
```

### P1 — Frontend gate + compose, wired into board Run → Flow

**In:** all of §1a (new `FlowGatePreview` + hooks + stepper + `flowGraph`), and the §1b wiring so the
Flow tab's "Run flow" gates through it. Compose every stage; per-stage `PromptBanner`; per-stage
`Sections` → `SkillSplitModal` (assemble, locked fragments); collect `{state: prompt}` for
`sectionsUsed` stages; thread it onto `apiStartFlow` body as `stage_overrides`.

**Out (deferred):** the server honoring the map (P2) — in P1 the field rides the wire and the server
ignores it (behavior-identical to today). The consultation branches of `handleRunFlow`
(`decompose*`) are **not** gated (P3). Persistent `stage_configs` pre-fill (see §5-Q1).

**Verify:** `tsc -p studio/tsconfig.web.json` clean; manual — open Flow tab, pick a flow, see the
stepper + per-stage banners, trim a stage, Run (run starts unchanged since server ignores).

### P2 — Backend transient `stage_overrides` channel

**In:** all of §1c. `/runner/start` accepts + validates `stage_overrides`; `RunnerState` carries it;
`_loop` forwards it to `next_action`; `build_prompt(stage_override=…)` applies it verbatim per state,
preserving the server-only tail. After P2, a gate trim on the board Run→Flow path **actually changes
what the stage spawns**.

**Validation (in `runner_start`):** `stage_overrides` must be a dict; keys are declared flow states
(coerce/ignore unknowns); values are strings; drop empties; cap total size (e.g. ≤ 256 KB) and per-
value length so a pathological body can't blow the argv/PowerShell path. Malformed → ignore silently
(compose normally), never 500.

**Out:** goal-run + decompose entry points (P3).

**Verify:** `pytest` — a `build_prompt(stage_override="X")` unit test asserts `agent_text=="X"` and
that `context`/`history`/board tail are still appended and `<feature>` is substituted; an integration
test drives one real FSM transition with a `stage_overrides` map and asserts the spawned prompt for
that state is the override (mirrors the existing compose-path tests the brief cites).

### P3 — Other two entry points (reuse the SAME gate + channel)

The P2 channel (`RunnerState.stage_overrides` → `build_prompt`) is built **once**; P3 only adds more
callers that populate it, plus opening `FlowGatePreview` from those UIs (each with its own `onConfirm`).

- **Team goal-executor:** goal card Run (executor `team`). Thread `stage_overrides` through
  `apiRunGoal` → `POST /comms/goals/run` (`blueprints/comms/goals.py`) → `goal_executor.start_goal_run`
  → (team) `start_run(flow='team-build', stage_overrides=…)`. Open the gate for `team-build` from the
  goal Run control.
- **Consultation-in-Evaluate:** `EvaluateBoardButton` decompose paths →
  `decomposeGoal('consultation')` / `decomposeFeature('consultation')` / `decomposeProject('consultation')`
  → `/comms/goals/decompose` · `/comms/features/decompose` · `/comms/project/decompose`
  (`comms/goals.py`, `comms/features.py`, `comms/project.py`) → `goal_decomposer.start_goal_decompose`
  → `start_run(flow='consultation'|'feature-consultation'|'project-consultation', stage_overrides=…)`.
  Open the gate for the relevant consultation flow from the Evaluate config. **Note:** the supervisor
  still appends `_decompose_directive` after `build_prompt`, so a consultation planner override does
  **not** need to carry the "seed THIS goal" directive (unlike the single-agent decompose gate, where
  the override replaces the *whole* prompt and `useDecomposePreview` must inline the directive).

**Out of scope for this feature:** the top-bar `FlowControlBar` Start button and the interactive
`/pathly` slash path (both can adopt the same gate later — the channel already supports it).

---

## 5. Risks / open questions for the builder

- **Q1 (P1 scope) — pre-fill vs. persistent `stage_configs`.** The brief says the banner "pre-fills
  from that stage's saved config." P1 composes a **fresh** full skill (fragments + abilities) and does
  NOT subtract a stage's persistent `excluded_sections`. Run behavior is still correct (plain submit →
  server applies `stage_configs`; trim → override supersedes). Faithful pre-fill would need the gate to
  fetch each stage's `stage_configs` and pass `initialUnchecked` to `SkillSplitModal`. **Recommend:**
  ship P1 with fresh compose; add persistent-trim reflection as a P1.5 refinement. Confirm acceptable.

- **R2 — re-sending the map each `next_action`.** `_loop` forwards `stage_overrides` on every stage's
  `next_action` call. Mitigated because the map holds *only* `sectionsUsed` stages (usually 0–1), and
  `_loop` omits it when empty — so the common path is zero overhead. A user who trims every stage of a
  big flow sends ~all stage prompts a few times per run (bounded by the ≤256 KB cap). Acceptable; note
  it. (A later optimization could stash the map server-side keyed by run and have `next_action` read it,
  but that reintroduces a persistence/cleanup concern the in-memory design avoids.)

- **R3 — bare-agent `agent_map` values.** All in-scope flows (team, team-build, consultation family,
  debug, explore, test, quick-fix) use `cat/skill` refs, which `composeSkillPrompt` handles. A flow
  whose `agent_map[state]` is a bare agent name (not `x/y`) won't compose → the stub banner shows and
  that stage stays plain-submit. Acceptable + fail-soft; flag if a target flow ever needs it.

- **R4 — `build_prompt` override skips `_apply_stage_selection` by design.** When an override is
  present the persistent `ability_ids`/`excluded_sections` are intentionally NOT re-applied (the human
  already sees/edits the final text at the gate). Builder must not "helpfully" re-apply them — that
  would double-trim. Covered by the unit test in P2.

- **R5 — argv/PowerShell size.** A composed stage prompt can be large; several verbatim overrides in
  one body compound it. The Windows headless path already writes a temp `.ps1` (no 32 KB `-EncodedCommand`
  limit for the *prompt*), but keep the `runner_start` size cap (R-P2) as the guard so `/runner/start`
  itself can't be flooded.

- **R6 — `deriveFlowSteps` needs `role_map`.** Its pseudo-state filter is a no-op when a flow declares
  no roles (falls back to `STAGE_AGENTS`). The consultation family + team flows all carry `role_map`, so
  the filter works; a role-less custom flow would show gate states, but they simply won't compose (no
  `agent_map` skill) — cosmetic only.

---

## Summary

A **run-agnostic** `FlowGatePreview` modal (stepper on top → per-stage `PromptBanner` → per-stage
`Sections`/`SkillSplitModal`) reuses the exact preview + compose machinery the single-agent gate and
the running-flow dock already use, so gate-shown == spawned per stage. Trims are collected as a
`{state: prompt}` map keyed off `sectionsUsed` (single-agent semantics, per stage) and threaded on
`/runner/start` as a transient, in-memory `RunnerState.stage_overrides` — the flow analogue of
`prompt_override` — which `fsm_compose.build_prompt` applies **verbatim in place of `agent_text` for
that state only**, preserving the runner-contract + live-board tail. P1 ships the frontend + board
Run→Flow wiring; P2 makes the server honor the channel; P3 reuses both for the goal-executor and
consultation-in-Evaluate entry points with no new channel.

### P1 file list (exact)

**Add** (`studio/src/renderer/src/components/shared/FlowGatePreview/`):
1. `FlowGatePreview.tsx`
2. `FlowGatePreview.module.css`
3. `useFlowGateStages.ts`
4. `useFlowGateState.ts`
5. `flowGraph.ts`
6. `FlowGateStepper/FlowGateStepper.tsx`
7. `FlowGateStepper/FlowGateStepper.module.css`

**Change:**
8. `studio/src/renderer/src/components/CommandCenter/CommsPanel/SingleAgentButton/FlowForm.tsx` — run button opens the gate; `onRunFlow` type + call gain `stageOverrides`.
9. `studio/src/renderer/src/components/CommandCenter/CommsPanel/SingleAgentButton/SingleAgentButton.tsx` — `onRunFlow` prop type gains `stageOverrides?`.
10. `studio/src/renderer/src/components/CommandCenter/CommsPanel/CommsPanel/CommsPanel.tsx` — `handleRunFlow` forwards `stageOverrides` on the `startBoardFlow` branch.
11. `studio/src/renderer/src/store/commsStore.ts` — `startBoardFlow` opts gain `stageOverrides`.
12. `studio/src/renderer/src/store/commsApi.ts` — `StartFlowOpts` + `apiStartFlow` send `stage_overrides`.
13. `studio/CLAUDE.md` — one-line doc for the Flow-tab gate (same change).

*(P2 backend file list — for the next stage: `supervisor/state.py`, `supervisor/api.py`,
`http_server/blueprints/runner/api_lifecycle.py`, `supervisor/orchestrator.py`, `fsm_ops.py`,
`fsm_compose.py`, `src/pathly_orchestrator/CLAUDE.md`.)*
