# Architecture Proposal — Flow Steps Dock

**Author:** architect · **Feature:** flow-steps-panel · **Date:** 2026-07-16

## Thesis
**Frontend-only.** The backend already supports everything: `POST /runner/reroute` exists and
the supervisor loop honors a reroute target (`state._reroute_adapter` in `supervisor/orchestrator.py`);
flow definitions expose `states` + `transitions` via `GET /flows/<name>`; the runner SSE +
spawn-gate engine list already carry the running flow's topic, current stage, adapter, and role.
So this is a **UI composition over existing data** — no new endpoint, no server change.

## Data sources (all existing)
| Need | Source |
|---|---|
| the flow's ordered `states` + `transitions` | `GET /flows/<name>` (`blueprints/flows/defs.py`) — DB-first, seeded from the flow YAML |
| which flow is running + current stage | `runnerStore` (runner SSE) + the spawn-gate engine (`RunningEngine{ feature, role, runId, category:'flow' }`) |
| reroute | `POST /runner/reroute` `{ topic, target_state[, adapter] }` (`blueprints/runner/api_control.py`) |

## Component tree (`studio/src/renderer/src/components/Monitor/FlowStepsPanel/`)
- `FlowStepsPanel.tsx` — the dock: collapse state + which running flow is selected; renders
  header + stepper + reroute footer, or a thin rail when collapsed.
- `FlowStepper/FlowStepper.tsx` + `StepRow` — the vertical stepper; maps the flow's `states` →
  done / current / upcoming from the run's current stage.
- `RerouteControl/RerouteControl.tsx` — the reachable-next `<select>` + Reroute button → `/runner/reroute`.
- `hooks/useFlowDock.ts` — UI state (collapsed, selected flow).
- `hooks/useFlowStates.ts` — data: fetch `GET /flows/<name>`, derive done/current/next from `transitions[current]`.
- `services/reroute.ts` — the `/runner/reroute` client (reuse an existing one if present).

## Layout change (the relocation)
- **Remove** the fixed top pipeline bar — its stepper header + the `FlowControlBar` controls at
  the top of the Pipeline panel.
- **Mount** `FlowStepsPanel` as a right-side dock in the Monitor/Pipeline container, sibling to
  the board, collapsible exactly like `SkillComposition/SkillSidebar`.
- The runner controls (play/pause/reroute/abort) **re-home** into the dock footer — reuse the
  existing runner control calls (`/runner/pause|resume|abort|reroute`), do not reinvent them.

## Deriving the stepper (pure)
`states.map(s => s === current ? 'now' : idx(s) < idx(current) ? 'done' : 'next')`, with
`transitions[current]` = the reroute options; gate states (`NO_*`) filtered out of the displayed
steps. Any **user-created** flow works unchanged because it's the flow's *own* `states` — nothing
is hardcoded.

## Layer / rules
Frontend only; obeys `studio/CLAUDE.md` (component-per-subfolder + `.module.css`, no inline
styles → tokens.css vars, ≤150 lines/file, data-* variants, responsive/min-width:0, collapse
pattern). No `db/runner/supervisor` change. tsc-verified before commit.

## Risks
- The reroute control was stubbed off (`EngineBoard/EngineControls/controlsForEngine.ts`:
  "the runtime can't yet honor (pause/reroute/rerun)"). **Verify `/runner/reroute` actually
  reroutes a live run** before wiring the button; if the loop honors only adapter-reroute (not an
  arbitrary target state), scope the control to what it supports and disable the rest with a reason.
- Removing the top bar must not orphan pause/resume/abort — re-home them in the dock in the same change.
