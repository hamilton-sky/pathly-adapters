---
name: Architecture Proposal
---
# DBExplorer Trends Tab — Architecture Proposal

## Problem Statement

The DBExplorer FeatureModal shows per-invocation cost and event data but has no time-series
view. Four new visualizations (daily cost bar chart, cache efficiency line chart, 18-week
activity heatmap, CSV export) require both a new backend aggregation query and new frontend
components. The work crosses three layers: Python db/queries, Python HTTP blueprint, Electron
IPC, and the React renderer — each with established conventions that must not be violated.

## Proposed Solution

A minimal additive layer across all three tiers:

1. A new `db/queries/trends.py` helper that executes the daily GROUP BY query
2. A new `GET /telemetry/trends` route in the existing telemetry blueprint
3. A new IPC handler in the main process that wraps the HTTP fetch
4. A new `TrendsTab/` component tree in the renderer, wired into `FeatureModal.tsx`

The cache efficiency line chart and CSV rows derive client-side from `window.pathly.db.events()`
— the AGENT_DONE payloads the modal already loads — so no second data source is needed.

## Layer Diagram

```
Renderer (React)
  FeatureModal.tsx
    └── TrendsTab.tsx (new)
          ├── useTrends.ts          ← IPC call + cost derivation
          ├── DailyCostChart.tsx    ← Recharts BarChart
          ├── ActivityHeatmap.tsx   ← CSS grid
          └── CacheEfficiencyChart.tsx  ← Recharts LineChart (events prop, no IPC)
                │
                │  window.pathly.db.trends(feature, days)
                ▼
Main process IPC handler (new)
  db:trends → fetch('http://127.0.0.1:8765/telemetry/trends?...')
                │
                ▼
Python HTTP server
  blueprints/telemetry.py  GET /telemetry/trends
                │
                ▼
  db/queries/trends.py    get_daily_trends(conn, feature, days)
                │
                ▼
  ~/.pathly/pathly.db   agent_invocations table
```

## Key Design Decisions

### Decision 1: Per-invocation cache series stays client-side

**Options considered:**
- (A) Include per-invocation rows in `/telemetry/trends` response
- (B) Derive cache series from `window.pathly.db.events()` already loaded by the modal

**Chosen:** B

**Rationale:** The modal already calls `window.pathly.db.events(feature.name)` and holds all
AGENT_DONE payloads including `cache_read_tokens` and `input_tokens`. Deriving the series
client-side avoids a second data fetch and keeps the HTTP endpoint small (daily aggregates
only). The four views stay numerically consistent with AgentsTab because they share the same
underlying events data. (PO_NOTES.md: "implementation's choice, but the four views must be
consistent with the cost numbers already shown in AgentsTab.")

### Decision 2: featureName source in TrendsTab

**Options considered:**
- (A) Read feature name from the first AGENT_DONE event's `feature` field in the `events` prop
- (B) Pass `featureName` as an explicit prop from `FeatureModal.tsx` alongside `events`

**Chosen:** B — pass as explicit prop

**Rationale:** AGENT_DONE events may be empty for a brand-new feature (Story S5 empty-state
requirement). If the `events` array is empty, option A has no feature name to derive. The
modal already holds `feature.name` (the name the modal was opened with) and can pass it down
directly. This removes the ambiguity and is consistent with how AgentsTab and InspectTab
receive their data.

**Impact on IMPLEMENTATION_PLAN.md Phase 12:** The tab panel becomes:
```tsx
{activeTab === 'trends' && (
  <TrendsTab
    featureName={feature.name}
    events={data.rawEvents}
    pricingTable={pricingTable}
  />
)}
```
And `TrendsTab` props become `{ featureName: string; events: DbEvent[]; pricingTable: PricingTable | null }`.

**Note for builder:** Verify whether the existing `AgentsTab`/`InspectTab` receive a
`featureName` prop or derive it from events — mirror that exact pattern. If those tabs
derive from events, option A is valid. The builder must read `FeatureModal.tsx` before
deciding.

### Decision 3: Day bucketing timezone — local time

**Options considered:**
- (A) UTC throughout backend and frontend
- (B) Local time throughout (backend SQL + frontend JS)

**Chosen:** B — local time

**Rationale:** The primary user is a developer looking at their own run history. Days should
correspond to what they experienced on their local calendar, not UTC. Applied uniformly:
- Backend: `strftime('%Y-%m-%d', started_at, 'localtime')`
- Frontend heatmap: `new Date(ts).toLocaleDateString('en-CA')` (returns YYYY-MM-DD in local tz)
- CSV: `ts` column is the raw stored value (ISO string); the `bucket` date is local

This matches the PO_NOTES.md best-guess recommendation and must be applied identically in
all three places so the bar chart, heatmap, and CSV agree.

### Decision 4: No new IPC channel for cache/CSV data

The cache efficiency points and CSV rows are derived in the renderer from the `events` prop
— the same AGENT_DONE array the modal already loaded. This avoids adding a `db:invocations`
or similar IPC channel for what is purely a client-side transformation. The only new IPC
channel is `db:trends` (which calls the new HTTP endpoint for daily aggregates).

(Constraint from PO_NOTES.md: "No new IPC channel if the data can come from the existing
`window.pathly.db.events()` path.")

### Decision 5: Recharts, not CSS bars or SVG polylines

The scout findings noted CSS-only bars as an option (matching AgentsTab's technique). However,
PO_NOTES.md explicitly names Recharts as the required library for both the bar chart
(`<BarChart>`) and the line chart (`<LineChart>`). The heatmap remains pure CSS grid (no
chart library needed for a fixed grid of colored cells).

## Key Components

- `db/queries/trends.py` — `get_daily_trends(conn, feature, days)` → list of daily aggregate dicts
- `blueprints/telemetry.py` additions — `GET /telemetry/trends` route (two new route handler functions)
- Main process IPC — `db:trends` handler (fetch wrapper)
- `TrendsTab/useTrends.ts` — data hook: IPC call + cost derivation + gap-fill + heatmap cell generation
- `TrendsTab/DailyCostChart.tsx` — Recharts BarChart; reported vs estimated distinction
- `TrendsTab/ActivityHeatmap.tsx` — 18×7 CSS grid; `data-level` attribute coloring
- `TrendsTab/CacheEfficiencyChart.tsx` — Recharts LineChart; null points for zero-denominator invocations
- `TrendsTab/TrendsTab.tsx` — root component; CSV export via Blob + object-URL

## Risks

- **`global.d.ts` already declares `window.pathly.db.trends`** (scout finding line 179) but the
  main-process handler may not yet exist. The builder must verify the IPC handler exists before
  assuming the declaration is wired. If not wired, Conv 1 must add it.
- **FeatureModal path ambiguity** — the exact import paths for `DbEvent`, `PricingTable`, and
  the `data.rawEvents` shape must be read from `FeatureModal.tsx` before implementing TrendsTab
  props. Guessing type names causes typecheck failures.
- **Recharts `connectNulls`** — the default for Recharts LineChart is `connectNulls={true}`,
  which draws a line through gaps. The builder must explicitly set `connectNulls={false}` on the
  `<Line>` element (not the `<LineChart>`), or null cache points will be silently bridged.
- **CSS variable availability** — color tokens used for heatmap levels must exist in `tokens.css`.
  The builder must verify token names before using them. If suitable tokens do not exist,
  define new ones in `tokens.css` rather than hardcoding hex values.
