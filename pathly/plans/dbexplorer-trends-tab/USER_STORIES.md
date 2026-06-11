---
name: User Stories
---
# DBExplorer Trends Tab — User Stories

## Context

Studio's DBExplorer shows per-invocation cost and event breakdowns (AgentsTab, InspectTab),
but every view is point-in-time. A maintainer auditing a feature's pipeline run cannot tell
whether cost is trending up, whether the cache is actually being hit, or how work was
distributed across days — without manually scanning the raw events table.

This feature adds a **Trends** tab to the existing `FeatureModal`, scoped strictly to the
currently-open feature. It renders four sections: a daily cost bar chart, a cache efficiency
line chart, an 18-week activity heatmap, and a CSV export button. The cost logic reuses
`costUtils.ts` exactly, so numbers stay consistent with AgentsTab.

---

## Stories

### Story S1: Backend data contract — daily aggregates endpoint
**As a** frontend component, **I want** a `GET /telemetry/trends?feature=X&days=126`
endpoint returning daily aggregates from `agent_invocations`, **so that** the bar chart and
heatmap can render without the renderer computing raw SQL.

**Acceptance Criteria:**
- [ ] `GET /telemetry/trends?feature=X&days=126` returns `{ "trends": [...] }` where each
  element has: `bucket` (YYYY-MM-DD), `count` (int), `total_tokens` (int),
  `input_tokens` (int), `cache_read_tokens` (int), `cache_write_tokens` (int),
  `cost_usd_reported` (float — sum of rows where `cost_usd > 0`),
  `has_estimated_rows` (bool — true when any row in the bucket has `cost_usd = 0` or null)
- [ ] An unknown feature name returns `{ "trends": [] }`, not a 404 or 500
- [ ] The route is implemented in `http_server/blueprints/telemetry.py` and queries via
  `db/queries/trends.py` — it does not inline SQL
- [ ] `db/queries/trends.py` uses `strftime('%Y-%m-%d', started_at, 'localtime')` for day
  bucketing (local time — consistent with heatmap and CSV)
- [ ] COALESCE is applied to all nullable token columns so null rows contribute 0, not null
- [ ] The new IPC handler in the main process calls this endpoint and returns its JSON to
  the renderer via `window.pathly.db.trends(feature, days?)`

**Edge Cases:**
- Feature has no agent runs → `{ "trends": [] }` returned cleanly
- All `cost_usd` rows are null/0 → `cost_usd_reported = 0.0`, `has_estimated_rows = true`
- FSM server down when IPC is called → IPC handler returns null; renderer shows empty state

**Delivered by:** Conversation 1

---

### Story S2: Daily cost bar chart with reported/estimated distinction
**As a** developer auditing a feature's spend, **I want** a bar chart showing total cost per
calendar day with a visual distinction between reported and estimated cost, **so that** I can
see spending trends and know when numbers are derived rather than provider-reported.

**Acceptance Criteria:**
- [ ] The bar chart renders one bar per calendar day in the feature's active range
- [ ] Calendar days with zero activity **between** the first and last active day are included
  as zero-height bars (no compressed timeline)
- [ ] Days containing any estimated cost rows render with a distinct visual treatment
  (different bar color, opacity, or pattern) consistent with how AgentsTab labels cost source
- [ ] The bar chart uses Recharts `<BarChart>` — no other chart library
- [ ] Cost values are computed by: sum of `cost_usd_reported` from the endpoint + calling
  `computeCost(model, inputTokens, outputTokens, pricingTable)` for estimated rows — the
  same `costUtils.ts` functions used in AgentsTab and InspectTab
- [ ] No inline `style={{...}}` except documented CSS-custom-property exceptions; colors
  from `tokens.css` variables
- [ ] `npm run typecheck` passes for all new files

**Edge Cases:**
- Feature active for a single day → chart renders one bar; axis does not break
- Feature with 200+ active days → chart scrolls horizontally or truncates gracefully;
  no crash and no blank render
- `pricingTable` is null (pricing endpoint down) → estimated rows labeled "unpriced"
  (same as AgentsTab behavior)

**Delivered by:** Conversation 2

---

### Story S3: Activity heatmap — 18-week GitHub-style grid
**As a** developer reviewing a feature's history, **I want** a GitHub-contributions-style
heatmap showing agent run count per day over the trailing 18 weeks, **so that** I can see
at a glance when the feature was active and how intensive each period was.

**Acceptance Criteria:**
- [ ] The heatmap renders exactly **18 columns × 7 rows** = 126 cells, trailing 18 weeks
  ending today (current date at render time)
- [ ] Each cell represents one calendar day; day-of-week ordering matches GitHub style
  (columns = weeks, rows = Mon–Sun or Sun–Sat — pick one and document it)
- [ ] Cell color is driven by `data-level` attributes (not inline styles): five discrete
  levels — `0` (no runs), `1` (1–2 runs), `2` (3–5 runs), `3` (6–9 runs), `4` (10+ runs)
- [ ] Each cell has a `title` attribute of the form `"YYYY-MM-DD: N runs"` for hover
  accessibility
- [ ] Days outside the feature's activity window render as level-0 cells (not hidden)
- [ ] The component file is under 150 lines; it receives `trends` data as a prop
- [ ] Day bucketing uses local time, consistent with S1's endpoint and the CSV export

**Edge Cases:**
- Feature with no runs → all 126 cells render at level-0 (empty state, no crash)
- Feature whose entire activity predates the 18-week window → all cells level-0 by design;
  the bar chart (S2) still shows the full historical range
- Single-day feature → exactly one non-zero cell

**Delivered by:** Conversation 2

---

### Story S4: CSV export of all agent invocations
**As a** developer or billing analyst, **I want** a button that downloads all agent
invocation rows for this feature as a CSV file, **so that** I can do offline analysis,
share with teammates, or reconcile against provider billing.

**Acceptance Criteria:**
- [ ] A "Export CSV" button (type="button") is visible in the Trends tab
- [ ] Clicking it triggers a client-side Blob download — no server round-trip, no native
  save dialog; mechanism mirrors the existing `exportJson` pattern in `FeatureModal.tsx`
- [ ] The downloaded file is named `<feature>-agent-runs.csv`
- [ ] The CSV contains one row per `AGENT_DONE` / `agent_invocations` row for this feature,
  with columns in this order: `ts`, `agent`, `model`, `provider`, `input_tokens`,
  `output_tokens`, `total_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`,
  `cost_source`, `wall_seconds`, `feature`
- [ ] The CSV derives its data from `window.pathly.db.events(feature.name)` (the AGENT_DONE
  events the modal already loads) — no new IPC channel required
- [ ] `cost_source` is populated using the same three-way logic as AgentsTab:
  `cost_usd > 0` → `"provider_reported"`, `computeCost` returns value → `"estimated"`, else `"unpriced"`

**Edge Cases:**
- Feature has no AGENT_DONE events → button still renders; clicking it downloads a
  header-only CSV (one row: column names, no data rows)
- Feature name contains spaces or special characters → filename sanitization applied
  (replace spaces with hyphens, strip path separators)

**Delivered by:** Conversation 2

---

### Story S5: Empty state — graceful degradation for features with no runs
**As a** developer opening the Trends tab for a newly created feature, **I want** all four
sections to show a clear empty state rather than errors or blank areas, **so that** the UI
feels intentional and does not mislead me into thinking the data failed to load.

**Acceptance Criteria:**
- [ ] When the feature has no agent runs, each section renders a short message consistent
  with the AgentsTab "No AGENT_DONE events yet" tone
- [ ] No console errors are thrown for an empty-data render
- [ ] The heatmap still renders its 126-cell grid (all level-0); the cost bar chart and
  cache line chart show their axes with an "No data" label rather than an empty container
- [ ] The CSV button renders but is not hidden; downloading it produces a header-only file

**Edge Cases:**
- IPC call returns null (FSM server down) → same empty state as zero-runs; no unhandled promise

**Delivered by:** Conversation 2

---

### Story S6: Cache efficiency line chart
**As a** developer trying to understand cache warming behavior, **I want** a line chart
showing cache hit rate per agent invocation in chronological order, **so that** I can see
whether the cache is warming up, cooling off, or consistently at a given rate.

**Acceptance Criteria:**
- [ ] The chart renders one data point per agent invocation, in `ts` ascending order
- [ ] Each point's Y value is `cache_read_tokens / (cache_read_tokens + input_tokens) * 100`,
  expressed as a percentage 0–100
- [ ] When `cache_read_tokens + input_tokens = 0`, **the point is omitted** (no gap-fill
  with 0% — a false "zero cache" reading is actively misleading)
- [ ] A summary stat above the chart shows the **overall feature cache hit rate** (sum of
  all cache_read_tokens / sum of all (cache_read_tokens + input_tokens) across all invocations,
  formatted as "X.X% overall cache hit rate")
- [ ] The chart uses Recharts `<LineChart>` — no other chart library; the line has `connectNulls={false}`
  so omitted points produce visible gaps
- [ ] Data is derived client-side from the AGENT_DONE events already loaded by the modal
  (`window.pathly.db.events`) — no additional IPC call
- [ ] No inline `style={{...}}` except documented CSS-custom-property exceptions

**Edge Cases:**
- All invocations have zero cacheable input → all points omitted; chart renders with
  Y-axis and "No cache data" label (no crash, no empty container)
- Single invocation → chart renders a single point (not a line, but valid and not broken)
- Feature with hundreds of invocations → chart renders without performance issues for MVP
  (no virtualization required for standard feature sizes)

**Delivered by:** Conversation 3

---

### Story S7: Trends tab wired into FeatureModal
**As a** developer using DBExplorer, **I want** a "Trends" tab to appear alongside the
existing tabs in the FeatureModal, **so that** I can access all four trend views for any
feature without leaving the modal.

**Acceptance Criteria:**
- [ ] `TabId` union in `FeatureModal.tsx` includes `'trends'`
- [ ] The `tabs` array includes `{ id: 'trends', label: 'Trends' }` entry
- [ ] Selecting the Trends tab renders `<TrendsTab featureName={feature.name} events={data.rawEvents} pricingTable={pricingTable} />`
- [ ] `TrendsTab` props are `{ featureName: string; events: DbEvent[]; pricingTable: PricingTable | null }` — `featureName` is required for the IPC call and CSV filename
- [ ] `npm run typecheck` passes for the modified `FeatureModal.tsx`
- [ ] Opening and switching to the Trends tab does not affect the behavior of any existing tab

**Edge Cases:**
- Switching tabs rapidly → no stale data, no double-fetch
- Modal opened for a feature name that returns no trends data → Trends tab renders empty
  states (S5) rather than crashing

**Delivered by:** Conversation 3
