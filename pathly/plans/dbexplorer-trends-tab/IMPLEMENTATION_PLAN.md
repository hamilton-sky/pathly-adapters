---
name: Implementation Plan
---
# DBExplorer Trends Tab — Implementation Plan

## Guiding Principles

- **Reuse before building.** `costUtils.ts` owns all pricing logic. `window.pathly.db.events()`
  already loads AGENT_DONE payloads the modal needs — the cache efficiency line and CSV derive
  from that without new IPC.
- **Layer discipline.** `db/queries/trends.py` imports nothing from `runner/` or `http_server/`.
  The blueprint imports the query helper lazily. The renderer calls IPC, not HTTP directly.
- **One component, one job.** Each sub-component file stays under 150 lines. Data fetching
  lives in `useTrends.ts`; UI state (if needed) in a separate hook.
- **Recharts required — not yet installed.** Conv 1 must add it: `cd studio && npm install recharts`.
  Use it for bar and line charts. The heatmap is pure CSS grid (no SVG, no library).
- **Local time consistently.** Day bucketing in the backend uses `strftime('%Y-%m-%d', started_at, 'localtime')`.
  The frontend heatmap and CSV use `new Date().toLocaleDateString('en-CA')` (YYYY-MM-DD equivalent).

---

## Conversation 1: Backend — db/queries + HTTP endpoint + IPC handler

**Stories delivered:** S1 (data contract), prerequisite for S2, S3

### Phase 1 — db/queries/trends.py
Create `src/pathly_orchestrator/db/queries/trends.py`.

```
get_daily_trends(conn, feature: str, days: int = 126) -> list[dict]
```

- SELECT from `agent_invocations` WHERE `feature = ?` AND `started_at >= date('now', '-N days')`
- GROUP BY `strftime('%Y-%m-%d', started_at, 'localtime')`
- Per bucket: `count(*) as count`, `SUM(COALESCE(total_tokens,0))`, `SUM(COALESCE(input_tokens,0))`,
  `SUM(COALESCE(cache_read_tokens,0))`, `SUM(COALESCE(cache_write_tokens,0))`,
  `SUM(CASE WHEN cost_usd > 0 THEN cost_usd ELSE 0 END) AS cost_usd_reported`,
  `MAX(CASE WHEN cost_usd IS NULL OR cost_usd = 0 THEN 1 ELSE 0 END) AS has_estimated_rows`
- Returns list of dicts with keys: `bucket`, `count`, `total_tokens`, `input_tokens`,
  `cache_read_tokens`, `cache_write_tokens`, `cost_usd_reported`, `has_estimated_rows`
- Empty result (unknown feature or no rows in window) → return `[]`, never raise

Re-export from `db/queries/__init__.py`.

### Phase 2 — GET /telemetry/trends route
Modify `src/pathly_orchestrator/http_server/blueprints/telemetry.py`.

Add route: `GET /telemetry/trends`
- Required query param: `feature` (400 if absent)
- Optional: `days` (int, default 126, max 365)
- Calls `get_daily_trends(conn, feature, days)` via lazy import
- Returns `{ "trends": [...] }` — always a valid JSON object
- Error handling: DB exception → log + return `{ "trends": [] }` with 200

### Phase 3 — IPC handler in main process
Locate the IPC handler directory (likely `studio/src/main/ipc/`). Add a handler for the
channel `db:trends` (matching the `window.pathly.db.trends` declaration in `global.d.ts`).

- Handler signature: `(feature: string, days?: number) => Promise<TrendsResponse | null>`
- Makes a `fetch('http://127.0.0.1:8765/telemetry/trends?feature=X&days=N')` call
- On success: returns parsed JSON
- On fetch error (server down, timeout): returns `null`
- Pattern: mirrors the existing `db:events` or `fetchPricingTable` fetch patterns

### Phase 4 — Verify (Conv 1 done-when)
```
# Backend unit test
GET /telemetry/trends?feature=<known-feature> → { "trends": [...] } valid JSON
GET /telemetry/trends?feature=unknown-xyz → { "trends": [] }
GET /telemetry/trends → 400 (missing feature param)

# IPC smoke test (manual)
In renderer DevTools: await window.pathly.db.trends('known-feature') → non-null object
```

---

## Conversation 2: Frontend core — TrendsTab + daily cost bar chart + heatmap + CSV export

**Stories delivered:** S2, S3, S4, S5

### Phase 5 — useTrends.ts data hook
Create `studio/src/renderer/src/components/DBExplorer/TrendsTab/useTrends.ts`.

```typescript
useTrends(featureName: string, events: DbEvent[], pricingTable: PricingTable | null)
  -> { dailyCost: DailyCostPoint[]; heatmapData: HeatmapCell[]; csvRows: CsvRow[]; loading: boolean; error: string | null }
```

- Calls `window.pathly.db.trends(featureName, 126)` on mount; sets loading/error state
- `DailyCostPoint`: `{ date: string; costReported: number; costEstimated: number; hasEstimated: boolean }`
  - `costReported` = `cost_usd_reported` from endpoint
  - `costEstimated` = sum of `computeCost(model, inputTokens, outputTokens, pricingTable)` for rows
    where `has_estimated_rows` is true. When pricingTable is null, `costEstimated = 0` with a flag.
  - Calendar gap-fill: generate all YYYY-MM-DD keys from `min(bucket)` to `max(bucket)` inclusive;
    missing dates get zero values
- `HeatmapCell`: `{ date: string; count: number; level: 0|1|2|3|4 }`
  - 126 cells: trailing 18 weeks ending today (local date)
  - Level thresholds: 0→level 0, 1–2→level 1, 3–5→level 2, 6–9→level 3, 10+→level 4
- `csvRows`: derived from `events` filtered to AGENT_DONE type, mapped to the 13-column spec

### Phase 6 — DailyCostChart.tsx
Create `studio/src/renderer/src/components/DBExplorer/TrendsTab/DailyCostChart.tsx`.

- Props: `{ data: DailyCostPoint[] }`
- Recharts `<BarChart>` with two `<Bar>` entries: reported (solid) + estimated (dashed/lighter)
- X-axis: abbreviated date label (`MMM DD`); Y-axis: `$` formatted to 4 decimal places
- Empty state: `<p className={styles.empty}>No cost data</p>` (per AgentsTab pattern)
- All colors via `var(--token-*)` CSS variables — no hardcoded hex values
- Under 150 lines

### Phase 7 — ActivityHeatmap.tsx
Create `studio/src/renderer/src/components/DBExplorer/TrendsTab/ActivityHeatmap.tsx`.

- Props: `{ cells: HeatmapCell[] }` (always 126 elements)
- Renders a CSS grid: 18 columns × 7 rows
- Each cell: `<div data-level={cell.level} title={`${cell.date}: ${cell.count} runs`} />`
- No inline styles; `data-level` drives color via CSS attribute selector
- Under 100 lines

### Phase 8 — TrendsTab.tsx root + CSV export
Create `studio/src/renderer/src/components/DBExplorer/TrendsTab/TrendsTab.tsx`.

- Props: `{ events: DbEvent[]; pricingTable: PricingTable | null }`
- Extracts `featureName` from events (or from a prop if the parent passes it explicitly —
  see ARCHITECTURE_PROPOSAL.md for the decision)
- Calls `useTrends(featureName, events, pricingTable)` — never fetches directly
- Renders: section heading + `<DailyCostChart>`, section heading + `<ActivityHeatmap>`,
  CSV export button
- CSV export: builds CSV string from `csvRows`, creates `Blob(['text/csv'])`, triggers
  object-URL download as `${featureName}-agent-runs.csv`
- Every `<button>` has `type="button"`
- Under 150 lines

### Phase 9 — Verify (Conv 2 done-when)
```
# Visual check
Open FeatureModal for a known feature → Trends tab stub visible
DailyCostChart renders bars with data
ActivityHeatmap renders 18×7 grid, hover shows title
CSV button → downloads .csv file with correct columns

# Typecheck
npm run typecheck → 0 errors (in studio/)
```

---

## Conversation 3: Frontend cache — cache efficiency line chart + FeatureModal wiring

**Stories delivered:** S6, S7

### Phase 10 — CacheEfficiencyChart.tsx
Create `studio/src/renderer/src/components/DBExplorer/TrendsTab/CacheEfficiencyChart.tsx`.

- Props: `{ events: DbEvent[] }` (AGENT_DONE events in chronological order)
- Derives data inline (no hook): filter AGENT_DONE events, map to `{ index: number; rate: number | null }`
  - `rate = cache_read_tokens / (cache_read_tokens + input_tokens) * 100`
  - When denominator is 0: `rate = null` (point omitted, not rendered as 0%)
- Summary stat above the chart: `sum(cache_read_tokens) / sum(cache_read_tokens + input_tokens) * 100`
  — or "No cache data" when denominator is globally 0
- Recharts `<LineChart>` with `connectNulls={false}`; Y-axis 0–100 with `%` tick formatter
- Empty / all-null state: label "No cache data" (no crash)
- Under 150 lines

### Phase 11 — Extend useTrends for featureName prop
Confirm the feature name is available in TrendsTab. If `events` always include the feature
field on AGENT_DONE payloads, derive it from there. Otherwise `FeatureModal` must pass
`featureName` as an explicit prop alongside `events`. Resolve the ambiguity by reading
`FeatureModal.tsx` before implementing (see ARCHITECTURE_PROPOSAL.md Decision 2).

### Phase 12 — Wire TrendsTab into FeatureModal.tsx
Modify `studio/src/renderer/src/components/DBExplorer/FeatureModal.tsx`.

- Add `'trends'` to the `TabId` union
- Add `{ id: 'trends', label: 'Trends' }` to the `tabs` array
- Add tab panel: `{activeTab === 'trends' && <TrendsTab events={data.rawEvents} pricingTable={pricingTable} />}`
- Import `TrendsTab` from `./TrendsTab/TrendsTab`
- Do not change any existing tab's behavior

### Phase 13 — Verify (Conv 3 done-when)
```
# Visual check
Open FeatureModal → "Trends" tab appears in tab strip
Click Trends → renders all four sections for a feature with data
CacheEfficiencyChart: points visible; invocations with 0 input tokens show as gaps
Summary stat above chart matches hand-calculated overall hit rate

# Typecheck
npm run typecheck → 0 errors

# Empty-feature check
Open Trends for a new feature with no runs → all sections show empty state, no console errors
```
