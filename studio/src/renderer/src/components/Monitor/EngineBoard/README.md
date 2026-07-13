# EngineBoard

The live **engine board** inside the Pipeline panel (`components/Monitor/`). Every spawned CLI
engine is a card, grouped by **how it runs** — Flow / Loop / Single — the same mechanism the
Command Center uses to group messages by scope. Clicking a card opens a detail modal where the
**contextual controls** live (so the board itself stays scannable). It uses only design-system
CSS variables (`var(--accent)`, `var(--border-color)`, `var(--radius-md)`, …) and `lucide-react`.

## Structure

```
EngineBoard/
  index.ts                    barrel export
  types.ts                    MonitorEngine + unions
  constants.ts                category / stage / status / adapter meta + color helpers
  MonitorBoard/               top-level composition (state: filters + open card)
  CategoryFilterBar/          segmented All/Flow/Loop/Single + adapter chips
  EngineSection/              one category band (heading + count + card grid)
  EngineCard/                 clickable ticket
  EngineDetailModal/          portal detail view (metrics + live log + controls)
  EngineControls/             contextual control row + controlsForEngine() logic
  CategoryBadge/              tinted category label
  AdapterBadge/               host-CLI badge
  StagePill/                  FSM stage pill
  StatusDot/                  live status dot
```

Each component owns its `*.module.css`. All are pure/presentational except `MonitorBoard`
(holds filter + open-card state).

## How it's wired

The Pipeline panel (`Monitor/index.tsx`) renders `<MonitorBoard>` as its live section, below the
FSM stage timeline. Rows come from **`Monitor/hooks/useMonitorEngines.ts`**, which projects the
authoritative spawn-gate list (`terminalStore.spawnQueue.engines` — the same `RunningEngine[]`
`CliMonitorBar` reads) into `MonitorEngine[]`, **filtered to the active feature**:

- `category` / `feature` / `role` ride on `RunningEngine` (set in the main process at spawn from
  the runner topic or `meta.telemetry`). A registered runner tab → `flow`; everything else →
  `single`. (Loop is reserved for debug/explore cycles — not yet split out from flow.)
- token/cost read `-` for live engines (unsettled until `AGENT_DONE`); flow engines inherit the
  panel's current FSM stage.

`onAction(engineId, actionId)` is handled in `Monitor/index.tsx` and every verb maps to a real
handler — `open` (open terminal), `abort`/`stop` (kill + release slot), `cancel`/`up` (spawn-queue
control), and `configure` (the cross-link: open `ConfigurePhaseModal` for the stage the engine is
running). See `EngineControls/controlsForEngine.ts` for the per-state verb set.

## Design decisions

- **Controls are per-engine, in the detail modal** — not a global control bar. The old bar's
  Start/Pause/Abort acted on a single runner while many engines run concurrently.
  `controlsForEngine(status, category)` returns only verbs the runtime can honor: flow →
  open/configure/abort, loop/single → open/stop, queued → move-up/cancel.
- **Category is the primary grouping**, adapter is a secondary filter (chips).
- **Colors never hand-picked** — category/stage/status resolve to DS tokens; adapter brand colors
  are the only hex values, injected as an `--adapter` custom property. Per-element dynamic colors
  use the CSS-var-injection pattern (`style={{ '--x': color }}`), never a direct `style` prop.
