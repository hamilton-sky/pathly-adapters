# Design — Unified Control Plane · read-only Pipelines pane (P0 UX)

> Stage 4 (Designer) · interactive consultation · 2026-07-24 · Stack: Electron + React (Studio renderer)
> Scope: UX/layout + component specs for the P0 **read-only** `components/Pipelines/` pane sketched in
> ARCHITECTURE.md §6. P1 live-overlay affordances are called out inline as seams, **not** redesigns.

This is a **UX/layout + component-spec** pass. It designs the seventh Studio panel *within Studio's
existing design system* — no new palette, type scale, or font. Every color, radius, spacing, badge,
and reused component below already ships in `tokens.css` and `components/Monitor/`.

---

## Design System Output

**This design generates NO new design system.** It works entirely within Studio's shipped system.

### Tokens reused (from `styles/tokens.css`)
- **Surfaces:** `--surface-app` / `--bg-base` (pane bg), `--surface-card` / `--bg-surface0` (rows, cards),
  `--surface-raised` / `--bg-surface1` (hover, tab bar), `--surface-well` / `--bg-terminal` (log wells).
- **Text:** `--text-primary` (feature/values), `--text-secondary` (body/snippets), `--text-muted` (meta,
  queued, labels), `--text-disabled` (canceled).
- **Signal hues (status + kind, ALL existing):** `--runtime` (running), `--green` (succeeded),
  `--red` (failed), `--orange` (aborted / reviewing), `--accent` sky (flow, selection, focus),
  `--purple` (loop), `--yellow` (decompose), `--blue`. Pipeline-state tints via `--state-*` +
  `stageColor()`.
- **Borders/rings:** `--border` / `--border-color`, `--border-subtle`, `--focus-ring`, `--accent-border`.
- **Spacing:** `--space-2…--space-12`. **Radius:** `--radius-sm/md/lg/full`. **Shadow:** `--shadow-sm`
  (row hover), `--shadow-modal` (detail overlay if modal). **Motion:** `--transition-base`,
  `--transition-fast`, `--ease-out`. **Type:** `--font-family-mono` (ids/costs/logs/features),
  `--font-family-base`, the `--font-size-xs…lg` scale, `--type-label-*` pattern.

### Components / utilities reused (from `components/Monitor/` + `utils/`)
| Reuse | Source | Used by |
|---|---|---|
| `deriveFlowSteps()` (pure) + `StepRow` (presentational) | `Monitor/FlowStepsPanel/flowSteps.ts`, `.../FlowStepper/StepRow.tsx` | **StagesTab** |
| `FlowStepper` (parameterized — see §3.1) | `Monitor/FlowStepsPanel/FlowStepper/` | **StagesTab** (live P1) |
| `RunCostBadge` readout shape (`$x.xxx` · `k tok` · `N agents`) | `Monitor/RunCostBadge/` | **RunDetail header + CostTab** |
| `CategoryBadge` tint recipe (mono-uppercase `color-mix` pill, `data-*`) | `Monitor/EngineBoard/CategoryBadge/` | **KindBadge** (extends w/ `decompose`) |
| `AdapterBadge` + `ADAPTER_COLOR` + `adapterFromProvider()` | `Monitor/EngineBoard/AdapterBadge/`, `constants.ts`, `hooks/useRecentEngines.ts` | **run header, RunRow** |
| `StatusDot` (`--dot` custom prop, blink @ reduced-motion) | `Monitor/EngineBoard/StatusDot/` | **StatusBadge** (running/queued pulse) |
| `StagePill` + `stageColor()` / `--state-*` | `Monitor/EngineBoard/StagePill/` | **StagesTab, LogsTab stage rail** |
| `statusColor()` / `statusLabel()` — **extend** to the 6-badge set (§2) | `Monitor/EngineBoard/constants.ts` | **StatusBadge** |
| Timestamps: `<Timestamp>`, `formatRelative`, `formatClock`, `formatAbsolute` | `utils/timestamp.ts`, `components/Timestamp/` | all "when" columns, log rows |
| `EngineCard` horizontal `data-view='banner'` row grammar | `Monitor/EngineBoard/EngineCard/` | **RunRow** layout model |

### House rules honored
150-line component cap → the tree below is ≤14 leaf files, none near the cap · folder-per-component +
`.module.css` · **no inline styles** except CSS custom props carrying data (`--dot`, `--stage`, `--adapter`)
· tokens-only colors · responsive-to-container ≤200px (§6) · explicit `type="button"` · `data-*` variant
attributes over class cascades · timestamps only through the util.

---

## 1. Pane shape (the one-surface model)

Azure/GitHub-Actions convention (RESEARCH §1): **one surface serves both live and terminal runs** —
no separate "monitor" vs "history". The pane is a **master–detail split**, matching the idiomatic
`run-list → run-detail → stages → per-stage log` drill-down we already mirror.

```
┌ Pipelines ────────────────────────────────────────────────┐
│ ┌ RunList (master) ─────┐ ┌ RunDetail (detail) ──────────┐ │
│ │ ▸ toolbar: title +    │ │ header: kind·feature·adapter │ │
│ │   count · scope filter│ │         ·status·cost·duration│ │
│ │ ─────────────────────  │ ├──────────────────────────────┤ │
│ │ RunRow  (running▸pin) │ │ Tabs: Stages·Logs·Board·Cost │ │
│ │ RunRow                │ │ ┌──────────────────────────┐ │ │
│ │ RunRow  (selected)    │ │ │  active tab body         │ │ │
│ │ …                     │ │ │                          │ │ │
│ │ [empty | loading |    │ │ └──────────────────────────┘ │ │
│ │  error state]         │ │ [no selection → placeholder] │ │
│ └───────────────────────┘ └──────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

- **Split ratio:** RunList `flex: 0 0 clamp(220px, 34%, 380px)`; RunDetail `flex: 1 1 0; min-width: 0`.
  Below ~640px pane width the split **stacks** (RunList collapses to a top strip; selecting a run swaps
  to detail with a `‹ Runs` back button) — same reflow discipline as the other panels.
- **Data:** `useRuns` → `GET /runs?project_root=…` (DB on mount + 8s poll, mirrors `useRecentEngines`);
  `useRunDetail` → `GET /runs/<id>` on selection. **Never** the live SSE stores in P0 (read-only; the
  DB-on-mount invariant is what makes AC-5 reload-safe). P1 layers an EventSource *onto* this baseline.
- **Panel wiring:** one new `PANELS` entry in `sidebar/shell/BottomNav.tsx` + `IconStrip.tsx`, id
  `pipelines`, icon `History` (lucide — reads as "run record/history"; alt `Workflow`/`Route`). Monitor /
  CliMonitorBar / CommsPanel / FlowControlBar are **not touched** (AC-7).

---

## 2. Status badge mapping (the load-bearing vocabulary)

RESEARCH §1 says adopt a `queued/running/succeeded/failed/skipped/canceled` set. Mapped onto Pathly's
**real** run statuses (`run_history.status` + `overlay_live_status` registry + `AGENT_DONE.outcome`), the
canonical set is **6 badges — every color an existing token**. This *extends* the shipped `statusColor()`
(which had only running/queued/done/failed); recommend growing `statusColor`/`statusLabel` in
`EngineBoard/constants.ts` **or** a Pipelines-local `runStatus.ts` — never a parallel palette.

| Badge `data-status` | Label | Token (reused) | Dot motion | Real sources folded in |
|---|---|---|---|---|
| `queued` | QUEUED | `--text-muted` | blink (reduced-motion gated) | concurrency-gate queued spawn (registry; no terminal row yet) |
| `running` | RUNNING | `--runtime` | pulse | `run_history` `running`; `finalizing`; live-registry `running` (overlay) |
| `succeeded` | SUCCEEDED | `--green` | none | `run_history` `done` + `AGENT_DONE.outcome='success'` (or no failure signal) |
| `failed` | FAILED | `--red` | none | `run_history` `error` / `blocked`; `AGENT_DONE.outcome='failed'` |
| `aborted` | ABORTED | `--orange` | none | `run_history` `aborted` (user Stop on a live run); a paused run stopped |
| `canceled` | CANCELED | `--text-disabled` (dim, 0.6α) | none | a **queued** run canceled before it ever spawned (gate cancel) |

**Fold-in / omissions (stated so the builder doesn't invent a 7th color):**
- `finalizing` → render **running**. `paused` / `blocked` on a top-level headless run are interactive-only
  and rare → render **running** with a muted "paused" sub-note; a paused run that ends stopped → **aborted**.
- Azure's `skipped` has **no** P0 equivalent (no persisted skip status; `ff`/fast-forward is a *transition*,
  not a run status) → **omitted**. If a per-stage `ff`/SKIP signal is surfaced later, add
  `skipped`=`--text-muted` italic.
- `idle` is not a run status (an un-started plan folder, à la FlowStepsPanel's idle tabs). P0 lists only real
  `run_history` runs → out of scope; a dimmed no-badge row is reserved for a later parity pass.

**StatusBadge component:** tinted mono-uppercase pill built on the exact `CategoryBadge` recipe
(`color-mix(in srgb, var(--tok) 15%, transparent)` fill + `var(--tok)` text, `data-status` selector). For
`running`/`queued` it prefixes the reused `StatusDot` (pulse/blink) so live rows read at a glance; terminal
badges are dot-less. One `data-*` attribute, zero class cascade.

---

## 3. RunList (master)

### 3.1 Toolbar (sticky, `--surface-chrome`)
`Pipelines` title · muted count (`N runs`) · **scope filter** — reuse the EngineBoard `ScopeFilter`
segmented control shape (All · Feature · Project · Global) driving the `board_scope` facet. No run-start
control (P0 is read-only; the P2 `[+ New Run]` launcher slots here later — reserve the trailing slot).

### 3.2 RunRow — layout & density
A `role="button"` row (Enter/Space to select, like `EngineCard`), horizontal grammar borrowed from
EngineCard's `data-view='banner'`. **Scan order = kind · feature · status · cost · when:**

```
[KindBadge]  feature-slug ………………………  [StatusBadge]  $0.42  ·  2m ago
 flex-0       flex:1 1 0; min-width:0; ellipsis   flex-0    mono    <Timestamp relative>
```

- **KindBadge** = `CategoryBadge` extended with a 4th `data-kind='decompose'` variant (`--yellow` tint;
  flow=`--accent`, single=`--runtime`, loop=`--purple` already exist). Labels: FLOW · SINGLE · LOOP · DECOMPOSE.
- **feature** — `--font-family-mono`, `--text-primary`, single-line ellipsis (`min-width:0` is what lets it
  shrink); `board_scope` shown as a muted `·suffix` when it differs from feature.
- **cost** — mono, `--green` when `> 0`, `--text-muted` `–` when zero/unpriced (mirrors EngineCard
  `.cost[data-empty]`). **when** — `<Timestamp mode="relative">` off `finished_at ?? started_at`.
- **stage_count** — for flow/decompose, a muted `⋯ 6 stages` micro-meta under the feature (single/loop omit).
- **Row height** ~44px; `--border-subtle` divider; hover → `--surface-raised` + `--shadow-sm`; selected →
  `--accent` left-border (3px) + `--accent-bg` wash; focus-visible → `--focus-ring`.

### 3.3 Running-run affordance
Running rows **pin to the top** (sort: running/queued first, then `finished_at` desc — mirrors
FlowStepsPanel "running tabs sort first"), carry the **pulsing** `StatusBadge` dot and a 3px `--runtime`
left-edge accent. In read-only P0 the affordance is "select to watch" — the row opens RunDetail, which in
**P1** live-tails via `/events/runs`. A Stop control is **display-only/absent** in P0 (`capabilities:['abort']`
from `overlay_live_status` is reserved for the P3 `RunControls`); do **not** render a live Stop yet.

### 3.4 Sort / grouping
Single flat list, `running → queued → terminal(finished desc)`. No date dividers in P0 (list is `limit`-capped
at 50); if it grows, add `dayKey` dividers via the timestamp util (already available) — noted, not built.

---

## 4. RunDetail (detail)

### 4.1 Run header
One row, wraps gracefully: `KindBadge` · **feature** (mono, `--text-primary`) · `AdapterBadge`
(`adapterFromProvider(run.adapter/provider)`) · `StatusBadge` · **duration** (`formatRelative` of
`finished−started`, or "running Xm" live) · **cost** = the reused `RunCostBadge` readout inline
(`$cost · tok · N agents`). `run_id` shown as a mono `--text-muted` copyable monospace tail (truncated,
full in `title`).

### 4.2 Tab shell
Four tabs — **Stages · Logs · Board · Cost** — as a segmented `role="tablist"` on `--surface-raised`
(reuse the `SegmentedControl` pattern from `ConfigurePhaseModal/components/SegmentedControl`). Active tab:
`--accent` underline + `--text-primary`; idle: `--text-muted`. Body scrolls independently
(`overflow: auto; min-height: 0`). Artifacts are folded into Logs/Board in P0 (per §6 of ARCHITECTURE).

### 4.3 StagesTab — reuse the stepper
Renders `detail.stages[]` as the **vertical stepper**. Reuse:
- the **pure** `deriveFlowSteps()` for a *live* run (feed it the run's own `pipelineStates`/`stageRoles`/
  `events` from the detail payload), and
- **`StepRow`** (presentational) for every row — completed steps carry the green check, the failed stage a
  `--red` dot, the live stage the pulsing accent dot.
- **Recommendation (small, backward-compatible):** give `FlowStepper` an optional `steps?: FlowStep[]` prop
  that falls back to its current store read. Then the live dock and this historical tab render through the
  **same** component — DRY, no fork. Map a terminal stage's `run_history`/`AGENT_DONE.outcome` →
  `StepStatus` (`succeeded→completed`, `failed→` a new `failed` decoration reusing `--red`; `active` only for
  a live run).
- Each StepRow's click target here **cross-links to LogsTab** for that stage (not the Configure modal — that
  affordance is live-flow-only). Per-stage `adapter` + `cost` shown as trailing meta (reuse `.role`/`.cost`
  grammar). Empty → "No stages recorded for this run." For single/loop: one step (itself).

### 4.4 LogsTab — the per-stage transcript
Two-part: a **stage rail** (reused `StagePill` list, or a `select` at ≤320px) selecting the active stage,
and the selected stage's **log stack**:

1. **Prompt sent** — collapsible (`<details>`, collapsed by default), mono in a `--surface-well` well,
   `overflow:auto`. Header note: *"Composed prompt (`instructions`) sent to the CLI."*
   **Secret-sink caveat (RESEARCH §3):** a subtle `--orange` inline hint — *"may contain paths/tokens pulled
   into context; don't export blindly."* No copy/export button in P0.
2. **Board context** — P0 note only: a muted callout *"Injected board context is embedded inside the prompt
   above (delimited)."* (`board_context_injected` is NULL in P0 per ARCHITECTURE §2.3; the panel becomes a
   discrete block in P1 with zero layout change — same well, populated).
3. **stdout** — mono `--surface-well` well, the run's log body. **Mandatory honest label** (RESEARCH §1):
   a header chip *"PTY tail — may be truncated by the buffer"* (`--text-muted`, `title` explains the
   ~500-chunk rolling cap). **Escape hatch:** a *More* menu (⋯) with **Raw log** (opens plain text) ·
   **Download** (`.log`) · **Timestamps** toggle (prefix each line via `formatClock` — off by default),
   mirroring Azure's per-step actions. `stdin` shown only when non-null (usually absent — argv delivery).
4. **Empty stdout** (silent run / board-run that POSTed no result) → *"No stdout captured for this stage."*
   (the spawn-half row still exists — a silent run still has a record).

**P1 live-tail seam (no redesign):** the stdout well gains `data-live` + an autoscroll "▼ Following" pill;
`useRunDetail` opens `GET /events/runs?run_id=` and **appends** to the same well. RESEARCH §2: honor
`Last-Event-ID` off `fsm_events.seq` so a reconnect resumes cleanly. Nothing about the P0 layout changes.

### 4.5 BoardTab — correlated posts
The run's correlated `comms_messages` (`run_id`-when-present, time-window-when-NULL per ARCHITECTURE §4.3),
newest-last, as compact **PostRow**s: a type badge (reuse the comms post `type` color language —
`decision`/`discovery`/`warning`/`artifact`/`constraint`), `from_agent` (mono), the text (2-line clamp,
expand on click), and `<Timestamp mode="relative">`. If a CommsPanel message-card component exists, reuse it;
else PostRow follows the same tint grammar. **Empty state (AC-3):** a centered muted
*"No board posts correlated to this run."* — never a spinner or error. Artifacts listed here show
`{title · type · path}` only, **no hydrate** (AC-4): md may offer an inline preview affordance; anything else
renders *"preview unavailable for `<type>`"*.

### 4.6 CostTab — reuse the readout
Top: the `RunCostBadge` shape enlarged (`$cost` `--green` · `k tok` · `N agents/invocations`). Below: a
per-stage breakdown table (`stage · adapter · tokens · cost`) summing to the run total — this makes the
**parity** contract (§1.1: flow-row cost = Σ stage costs = Σ RECENT cards) legible. Zero-cost/unpriced rows
show `–` (`--text-muted`) with a `title` *"not yet priced"* (never a misleading `$0`, per the telemetry
lesson). Empty → the badge alone reads `$0.000 · 0 tok`.

---

## 5. State matrix (every surface)

| Surface | Loading | Empty | Error | Terminal (populated) | Running (populated) |
|---|---|---|---|---|---|
| **RunList** | 3–4 skeleton rows (shimmer on `--bg-surface1`) | "No runs yet for this project." + hint | inline `--red` strip "Couldn't load runs — retrying…" (poll keeps trying; last-good stays) | flat sorted list | running/queued pinned top, pulsing dot |
| **RunDetail (no sel.)** | — | placeholder: muted icon + "Select a run to see its stages, logs, board posts, and cost." | — | tabs populated | header shows live duration + pulse |
| **StagesTab** | skeleton step rail | "No stages recorded." | "Stage data unavailable." | steps completed/failed | live stage = pulsing accent (deriveFlowSteps) |
| **LogsTab** | skeleton well | "No stdout captured for this stage." | "Log unavailable." | prompt + tail + actions | tail well `data-live`, "▼ Following" (P1) |
| **BoardTab** | skeleton post rows | **"No board posts correlated to this run."** (AC-3) | "Couldn't load board posts." | PostRows | new posts append live (P1) |
| **CostTab** | skeleton badge | `$0.000 · 0 tok` | "Cost unavailable." | badge + per-stage table | badge live; running stages `–` until settle |

**Terminal-vs-running rule:** running is signaled *only* by the reused animated `StatusDot` (pulse) + the
`--runtime` accent + a live duration; terminal state is fully static (no motion), all figures settled. A
renderer reload re-fetches `GET /runs` and repopulates from the DB — no orphan blank (AC-5).

---

## 6. Responsive (≤200px, per studio/CLAUDE.md)

- **No fixed widths.** RunList `flex-basis` is a `clamp()`; every text cell that must shrink carries
  `min-width: 0` + ellipsis (feature slug, snippet, board text). Badges/dots/costs are `flex-shrink: 0`.
- **RunRow progressive disclosure:** at narrow widths drop the relative-time first, then the cost-to-a-second-
  line; **KindBadge + feature + StatusBadge always survive** (they carry the row's identity). `flex-wrap` on
  the meta cluster, never horizontal page scroll.
- **Split → stack** below ~640px pane width (RunList becomes a top strip; detail gets a `‹ Runs` back
  affordance). Tabs become a horizontally-scrollable `role="tablist"` (`overflow-x:auto`) or a `select` at the
  tightest widths — never wrap into two rows that clip.
- **Every section container** uses `overflow: hidden` (or `auto` for the scroll wells); no `overflow: visible`
  near menus. Log/prompt wells scroll internally (`overflow:auto; min-height:0`) so they never blow out the
  pane.
- Verified mentally at 200px: a RunRow = `[FLOW] feat… [RUN]` with cost/time dropped; the detail body is a
  single scrolling column. All flex children shrink; nothing escapes.

---

## 7. Component tree (folder-per-component, ≤150 lines each)

```
components/Pipelines/
  Pipelines.tsx                     shell: RunList | RunDetail + selection state (useState runId)
  Pipelines.module.css
  hooks/
    useRuns.ts                      GET /runs?project_root=… (DB on mount + 8s poll)
    useRunDetail.ts                 GET /runs/<id> on selection (P1: + EventSource overlay)
  runStatus.ts                      the §2 badge map (labels + token per data-status) — or extend Monitor/constants
  RunList/
    RunList.tsx                     toolbar + list + list-level states
    RunList.module.css
    RunRow/RunRow.tsx               the §3.2 row (reuses KindBadge, StatusBadge, Timestamp)
    RunRow/RunRow.module.css
  StatusBadge/StatusBadge.tsx       §2 pill (reuses StatusDot; CategoryBadge recipe)
  StatusBadge/StatusBadge.module.css
  KindBadge/KindBadge.tsx           CategoryBadge + data-kind='decompose'
  KindBadge/KindBadge.module.css
  RunDetail/
    RunDetail.tsx                   header + tab shell (SegmentedControl pattern)
    RunDetail.module.css
    RunHeader/RunHeader.tsx         §4.1 (reuses AdapterBadge, RunCostBadge shape, StatusBadge)
    StagesTab/StagesTab.tsx         §4.3 (reuses deriveFlowSteps + StepRow / FlowStepper w/ steps prop)
    LogsTab/LogsTab.tsx             §4.4 stage rail + log stack
    LogsTab/LogWell/LogWell.tsx     reusable mono well (prompt / stdout) + More menu
    BoardTab/BoardTab.tsx           §4.5 PostRows + empty state
    CostTab/CostTab.tsx             §4.6 RunCostBadge shape + per-stage table
```

Every leaf is a single job under the 150-line cap; shared state/effects go in `hooks/`; the badge token map
is the one shared constant. No file duplicates a helper — `deriveFlowSteps`, `adapterFromProvider`,
`stageColor`, and the timestamp utils are imported, never re-implemented.

---

## 8. Open UX decisions (advisory — non-blocking)
- **Detail placement:** inline right-split (spec'd) vs. a full-height overlay modal. Inline is chosen for the
  "one surface, live + terminal" model and cheaper reloads; revisit if the pane proves too narrow at common
  Studio widths.
- **Scope filter default:** `All` (spec'd) so a fresh project shows every run; a per-project persisted last
  choice (`localStorage pathly:pipelinesScope`) is a cheap follow-on.
- **Secret redaction:** the RESEARCH §3 caveat is surfaced as a *hint* only; an actual redaction pass + an
  export-guard on LogsTab are known **post-MVP** follow-ons (out of P0).
