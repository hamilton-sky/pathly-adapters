---
name: Conversation Guide
---
# DBExplorer Trends Tab — Conversation Guide

Split into 3 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Backend — db/queries + HTTP endpoint + IPC handler (Phases 1–4)

**Stories delivered:** S1

**Prompt to paste:**
```
Read pathly/plans/dbexplorer-trends-tab/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement DBExplorer Trends Tab Conversation 1 (Phases 1–4) from pathly/plans/dbexplorer-trends-tab/IMPLEMENTATION_PLAN.md.
Read ARCHITECTURE_PROPOSAL.md for layer rules and design decisions before editing anything.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.
In particular: read studio/src/renderer/src/types/global.d.ts around line 179 to confirm
`window.pathly.db.trends` is declared. Read studio/src/main/ipc/ to find the correct file for
the new IPC handler and match the existing handler pattern exactly.

Scope:

- Phase 1: Create `src/pathly_orchestrator/db/queries/trends.py` with a single function
  `get_daily_trends(conn, feature: str, days: int = 126) -> list[dict]`.
  Query: SELECT from `agent_invocations` WHERE feature = ? AND started_at >= date('now', '-N days').
  GROUP BY strftime('%Y-%m-%d', started_at, 'localtime').
  Per bucket return: bucket (YYYY-MM-DD string), count, total_tokens, input_tokens,
  cache_read_tokens, cache_write_tokens, cost_usd_reported (SUM where cost_usd > 0),
  has_estimated_rows (1 if any row has cost_usd IS NULL OR cost_usd = 0, else 0).
  COALESCE all nullable token columns to 0. Return [] on empty result, never raise.
  Re-export from `src/pathly_orchestrator/db/queries/__init__.py`.

- Phase 2: Add `GET /telemetry/trends` to `src/pathly_orchestrator/http_server/blueprints/telemetry.py`.
  Required query param: `feature` (return 400 if absent).
  Optional: `days` (int, default 126, clamped to 1–365).
  Call get_daily_trends lazily (import inside the function, matching existing blueprint style).
  Always return { "trends": [...] } — never 404 or 500 for an unknown feature.
  On DB exception: log + return { "trends": [] } with 200.

- Phase 3: Add the IPC handler for `window.pathly.db.trends(feature, days?)` in the main process.
  Read studio/src/main/ipc/ to find the correct file and mirror the existing handler pattern.
  The handler fetches `http://127.0.0.1:8765/telemetry/trends?feature={feature}&days={days}`.
  On success: return parsed JSON. On fetch error: return null.
  Confirm the handler is registered (wired into the ipcMain.handle call site).

Architectural rules to observe:
- Read CLAUDE.md and src/pathly_orchestrator/CLAUDE.md for layer rules.
- db/queries/trends.py must NOT import from runner/, http_server/, or supervisor/.
- The blueprint imports db/queries lazily (inside the route function) — do not add a top-level import.
- Do not modify any existing query helper, migration, or IPC handler.

Do NOT touch: any Studio React component, FeatureModal.tsx, any migration file,
any existing telemetry route handler, any adapter _meta/ file.

Verify:
  pathly-fsm-http (start the server), then:
    curl "http://127.0.0.1:8765/telemetry/trends?feature=<known-feature>" → { "trends": [...] }
    curl "http://127.0.0.1:8765/telemetry/trends?feature=unknown-xyz" → { "trends": [] }
    curl "http://127.0.0.1:8765/telemetry/trends" → 400
  IPC (in Electron renderer DevTools):
    await window.pathly.db.trends('known-feature') → non-null object with trends array

After done, update pathly/plans/dbexplorer-trends-tab/PROGRESS.md phases 1–4 to DONE.
If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** The backend is complete and independently testable. A curl to
`GET /telemetry/trends` returns daily aggregate data. The IPC channel is wired so the
renderer can call `window.pathly.db.trends()` and receive data.

**Files touched:** `db/queries/trends.py`, `db/queries/__init__.py`,
`blueprints/telemetry.py`, main-process IPC handler file

---

## Conversation 2: Frontend core — TrendsTab + daily cost bar chart + heatmap + CSV export (Phases 5–9)

**Stories delivered:** S2, S3, S4, S5

**Prompt to paste:**
```
Read pathly/plans/dbexplorer-trends-tab/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement DBExplorer Trends Tab Conversation 2 (Phases 5–9) from pathly/plans/dbexplorer-trends-tab/IMPLEMENTATION_PLAN.md.
Conversation 1 is complete: `window.pathly.db.trends()` IPC is wired and returns data.
Read ARCHITECTURE_PROPOSAL.md (Decisions 2–5) and EDGE_CASES.md before implementing.

**Before editing anything:** glob/read the live repo.
- Read studio/src/renderer/src/components/DBExplorer/AgentsTab/AgentsTab.tsx to understand
  the empty-state pattern, cost-source labeling, and CSS module conventions to mirror.
- Read studio/src/renderer/src/components/DBExplorer/costUtils.ts to confirm exact signatures
  for computeCost and PricingTable — import exactly as AgentsTab does.
- Read studio/src/renderer/src/types/global.d.ts to confirm DbEvent, DbTrendPoint, and
  TrendsResponse type shapes.
- Read studio/src/renderer/src/components/DBExplorer/FeatureModal.tsx briefly to confirm
  how pricingTable is passed down and how rawEvents is shaped.

Create the following new files under `studio/src/renderer/src/components/DBExplorer/TrendsTab/`:

- Phase 5: `useTrends.ts` — data hook.
  Signature: useTrends(featureName: string, events: DbEvent[], pricingTable: PricingTable | null)
  Calls window.pathly.db.trends(featureName, 126) on mount.
  Derives DailyCostPoint[] with gap-fill (all calendar days min→max of active range, zero for gaps).
  DailyCostPoint: { date: string; costReported: number; costEstimated: number; hasEstimated: boolean }
  costEstimated = sum of computeCost() for invocations in the bucket where cost_usd = 0.
  IMPORTANT: when pricingTable is null, costEstimated = 0 and mark the bucket unpriced.
  Derives HeatmapCell[126] for the trailing 18 weeks (local time, ending today).
  Level thresholds: 0→level 0, 1–2→level 1, 3–5→level 2, 6–9→level 3, 10+→level 4.
  Derives CsvRow[] from events filtered to AGENT_DONE type (columns per USER_STORIES.md S4).
  Returns { dailyCost, heatmapCells, csvRows, loading, error }.

- Phase 6: `DailyCostChart.tsx` — Recharts BarChart sub-component.
  Props: { data: DailyCostPoint[] }
  Two <Bar> entries: costReported (solid accent color) + costEstimated (lighter/dashed).
  X-axis: abbreviated date (MMM DD). Y-axis: $ to 4 decimal places.
  Empty state: <p className={styles.empty}>No cost data</p>
  All colors from var(--*) CSS variables — no hardcoded hex.
  Under 150 lines. Every <button> has type="button" if any buttons are present.

- Phase 7: `ActivityHeatmap.tsx` — CSS grid heatmap sub-component.
  Props: { cells: HeatmapCell[] } (always 126 elements passed in)
  Renders a 18-columns × 7-rows CSS grid.
  Each cell: <div data-level={cell.level} title={`${cell.date}: ${cell.count} runs`} />
  No inline styles. data-level drives color via CSS attribute selectors in TrendsTab.module.css.
  Under 100 lines.

- Phase 8: `TrendsTab.tsx` — root component + CSV export.
  Props: { featureName: string; events: DbEvent[]; pricingTable: PricingTable | null }
  (featureName is passed explicitly — see ARCHITECTURE_PROPOSAL.md Decision 2)
  Calls useTrends(); renders all three sections with headings.
  CSV export: build CSV string from csvRows, create Blob(['text/csv']), trigger object-URL
  download as `${sanitizedFeatureName}-agent-runs.csv`.
  Sanitize: spaces → hyphens, strip / \ and other path chars.
  Every <button> has type="button". Under 150 lines.

- Phase 8 also: `TrendsTab.module.css`
  Layout styles for the four sections.
  Heatmap grid: display:grid; grid-template-columns: repeat(18, 1fr); gap: 3px.
  data-level attribute selectors: [data-level="0"] through [data-level="4"] using
  CSS variables for color intensity. Check tokens.css for suitable variables; if none exist,
  define them.
  .empty: color: var(--text-muted) — matching AgentsTab empty state style.

Architectural rules:
- Follow studio/CLAUDE.md component rules: per-component subfolder, CSS modules, no inline styles,
  ~150-line cap, one component one job, data fetching in useTrends only.
- Recharts must be installed first (it is NOT in studio/package.json yet). Run: `cd studio && npm install recharts` before writing any chart component. Then use it for bar and line charts.
- No inline style={{...}} except documented CSS-custom-property exceptions.
- All TypeScript — no .js files in the renderer.

Do NOT touch: FeatureModal.tsx (Conv 3), CacheEfficiencyChart.tsx (Conv 3),
any Python backend file, any IPC handler file, any adapter _meta/ file.

Verify:
  Import TrendsTab in a temporary test location or check in DevTools that:
    useTrends returns DailyCostPoint[] with gap-filled dates
    ActivityHeatmap renders exactly 126 cells
    CSV button downloads a file with correct headers
  npm run typecheck (in studio/) → 0 errors

After done, update pathly/plans/dbexplorer-trends-tab/PROGRESS.md phases 5–9 to DONE.
If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** The TrendsTab component tree is complete except for the cache efficiency
chart. Daily cost bars render with reported/estimated distinction. The heatmap shows 18×7
cells. CSV download works. All sections show empty state when data is absent. Typecheck passes.

**Files touched:** `TrendsTab/TrendsTab.tsx`, `TrendsTab/TrendsTab.module.css`,
`TrendsTab/useTrends.ts`, `TrendsTab/DailyCostChart.tsx`, `TrendsTab/ActivityHeatmap.tsx`

---

## Conversation 3: Frontend cache — cache efficiency line chart + FeatureModal wiring (Phases 10–13)

**Stories delivered:** S6, S7

**Prompt to paste:**
```
Read pathly/plans/dbexplorer-trends-tab/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement DBExplorer Trends Tab Conversation 3 (Phases 10–13) from pathly/plans/dbexplorer-trends-tab/IMPLEMENTATION_PLAN.md.
Conversations 1–2 are complete: backend IPC is wired, TrendsTab renders bar chart + heatmap + CSV.
Read ARCHITECTURE_PROPOSAL.md (all decisions) and EDGE_CASES.md (Category 2) before implementing.

**Before editing anything:** glob/read the live repo.
- Read studio/src/renderer/src/components/DBExplorer/FeatureModal.tsx in full to confirm:
  (a) the exact TabId union definition and where to add 'trends'
  (b) how pricingTable is typed and passed to other tab components
  (c) the shape of data.rawEvents and whether feature.name is available in scope
  (d) the existing tabs array format
- Confirm that TrendsTab/TrendsTab.tsx exists from Conv 2.
- Confirm that TrendsTab.tsx already accepts featureName as an explicit prop (Decision 2).

Phase 10: Create `studio/src/renderer/src/components/DBExplorer/TrendsTab/CacheEfficiencyChart.tsx`
  Props: { events: DbEvent[] }
  Filter events to AGENT_DONE type, sort by ts ascending.
  Map each to: { index: number; rate: number | null }
    rate = cache_read_tokens / (cache_read_tokens + input_tokens) * 100
    When denominator = 0: rate = null (NEVER 0 — see EDGE_CASES.md EC-2.1)
  Summary stat: sum(cache_read_tokens) / sum(cache_read_tokens + input_tokens) * 100
    When global denominator = 0: display "No cache data" string, not a number.
  Recharts <LineChart> with <Line connectNulls={false}> — this attribute goes on <Line>, not <LineChart>.
  Y-axis domain [0, 100], tick formatter appends "%".
  All-null/empty state: render axes + "No cache data" label; no crash.
  Under 150 lines. No inline styles.

Phase 11: Verify TrendsTab.tsx featureName prop
  Read TrendsTab/TrendsTab.tsx. If featureName is already an explicit prop (from Conv 2),
  no change needed. If it is derived from events, update the prop interface and derivation
  to match ARCHITECTURE_PROPOSAL.md Decision 2 (explicit prop is required).

Phase 12: Wire TrendsTab into FeatureModal.tsx
  Add 'trends' to the TabId union.
  Add { id: 'trends', label: 'Trends' } to the tabs array.
  Add to the tab panel section:
    {activeTab === 'trends' && (
      <TrendsTab
        featureName={feature.name}
        events={data.rawEvents}
        pricingTable={pricingTable}
      />
    )}
  Add <CacheEfficiencyChart> inside TrendsTab.tsx after the heatmap section and before the CSV button.
  Import CacheEfficiencyChart from './CacheEfficiencyChart'.
  Import TrendsTab from './TrendsTab/TrendsTab' in FeatureModal.tsx.
  Do not modify any existing tab panel, tab definition, or modal behavior.

Architectural rules:
- Follow studio/CLAUDE.md rules. No inline styles.
- connectNulls={false} is critical on the <Line> element — verify before committing.
- Do not add any new IPC channels or HTTP calls. Cache data derives from the events prop.

Do NOT touch: useTrends.ts, DailyCostChart.tsx, ActivityHeatmap.tsx (done in Conv 2),
any Python backend file, any IPC handler file, any adapter _meta/ file.

Verify:
  Open FeatureModal for a known feature → "Trends" tab appears in the tab strip.
  Click Trends → all four sections render.
  CacheEfficiencyChart: for a feature with zero-input invocations, verify those points
    appear as gaps in the line (not as 0% points). Check browser console — no errors.
  Summary stat above the cache chart matches hand-calculated overall hit rate.
  Open Trends for a new feature with no runs → all sections show empty state, no errors.
  npm run typecheck (in studio/) → 0 errors.
  Existing tabs (Timeline, Events, Agents, Traces, Inspect) are unaffected.

After done, update pathly/plans/dbexplorer-trends-tab/PROGRESS.md phases 10–13 to DONE
and set Status to COMPLETE.
If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** All four Trends sections render correctly for features with data and
for features with no data. The Trends tab appears in FeatureModal alongside existing tabs.
Cache gaps are visible for zero-denominator invocations. Typecheck passes. Existing tabs are
unaffected.

**Files touched:** `TrendsTab/CacheEfficiencyChart.tsx`, `TrendsTab/TrendsTab.tsx` (add cache chart),
`FeatureModal.tsx`
