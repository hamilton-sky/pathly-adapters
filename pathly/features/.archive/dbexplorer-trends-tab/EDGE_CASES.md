---
name: Edge Cases
---
# DBExplorer Trends Tab — Edge Cases

## Category 1: Empty database / no agent runs

### EC-1.1: Feature has zero AGENT_DONE rows
- **Trigger:** User opens Trends tab for a newly created feature that has never been run
- **Expected behavior:** `GET /telemetry/trends?feature=X` returns `{ "trends": [] }`.
  The IPC call returns an empty object. `useTrends` produces empty arrays for all three
  derived datasets. Each section renders its empty-state element (no crash, no blank container).
  The heatmap renders all 126 cells at level-0. The CSV button renders; clicking it downloads
  a header-only file.
- **Handled in:** S1, S5 (Conv 1 backend + Conv 2 frontend)

### EC-1.2: Feature name unknown to the database
- **Trigger:** The modal is opened with a feature name that has no rows in `agent_invocations`
  (e.g., a feature that only has STATE.json but has never been run through the pipeline)
- **Expected behavior:** Same as EC-1.1. The backend must not return 404 or 500 for an unknown
  feature — it returns `{ "trends": [] }`.
- **Handled in:** S1 acceptance criterion ("unknown feature name returns `{ 'trends': [] }`")

---

## Category 2: Divide-by-zero in cache efficiency

### EC-2.1: Individual invocation with zero cacheable input
- **Trigger:** An AGENT_DONE event has `cache_read_tokens = 0` AND `input_tokens = 0`
  (e.g., a no-op or stub invocation)
- **Expected behavior:** `cache_read_tokens + input_tokens = 0` → the point's rate is `null`,
  not `0`. The Recharts LineChart with `connectNulls={false}` renders a visible gap at this
  point. No `NaN` or `Infinity` in the rendered output.
- **Handled in:** S6 acceptance criterion ("point is omitted — no gap-fill with 0%")

### EC-2.2: All invocations have zero cacheable input
- **Trigger:** A feature whose agents never emit cache tokens (e.g., a model that does not
  support prompt caching)
- **Expected behavior:** Every point is null → no line segments render. The chart shows its
  axes and a "No cache data" label. The summary stat above the chart also shows "No cache data"
  rather than "0.0% overall cache hit rate" (which would be actively misleading).
- **Handled in:** S6 acceptance criterion (empty/all-null state)

### EC-2.3: Global denominator zero for summary stat
- **Trigger:** Same as EC-2.2 — sum of all `(cache_read_tokens + input_tokens)` across the
  feature is 0
- **Expected behavior:** Summary stat reads "No cache data" (string), not a division result.
  No `NaN` in the DOM.
- **Handled in:** S6 (CacheEfficiencyChart summary stat logic)

---

## Category 3: Null / zero cost_usd rows

### EC-3.1: All rows have cost_usd = 0 or null
- **Trigger:** Provider did not report costs (e.g., all runs through a provider that doesn't
  return cost, or early data before cost tracking was added)
- **Expected behavior:** `cost_usd_reported = 0.0` and `has_estimated_rows = true` for every
  bucket. The bar chart falls back to `computeCost` for all bars. If `pricingTable` is also
  null, bars are labeled "unpriced" with a distinct visual. The daily total is never silently 0.
- **Handled in:** S2 (DailyCostChart fallback + labeling)

### EC-3.2: Mixed rows — some reported, some not
- **Trigger:** Some invocations return `cost_usd > 0`; others have `cost_usd = 0`
- **Expected behavior:** The backend returns `cost_usd_reported` (sum of reported-only rows)
  and `has_estimated_rows = true`. The frontend adds the estimated portion from `computeCost`
  on top. The bar visually distinguishes the two components (e.g., stacked or colored
  differently). Consistent with how AgentsTab labels cost source.
- **Handled in:** S2 (useTrends cost derivation + DailyCostChart rendering)

### EC-3.3: pricingTable null at render time
- **Trigger:** `/telemetry/pricing` endpoint is unreachable (FSM server was down when the
  modal loaded its pricing table)
- **Expected behavior:** `computeCost` cannot run; rows with `cost_usd = 0` are labeled
  "unpriced" (not "estimated"). The bar chart renders `cost_usd_reported` bars only; unpriced
  days show a visual indicator. This matches existing AgentsTab and InspectTab behavior for
  the same condition.
- **Handled in:** S2 (useTrends + DailyCostChart; mirrors costUtils.ts null-pricing path)

---

## Category 4: Sparse / edge-case timeline shapes

### EC-4.1: Feature active for a single calendar day
- **Trigger:** All invocations happened on the same day (common for a one-shot test)
- **Expected behavior:** The bar chart renders one non-zero bar. Calendar gap-fill still
  applies between the first and last active day, but since they are the same day, only one
  bar appears. The axis does not show a broken or NaN range.
- **Handled in:** S2, S3

### EC-4.2: Feature active across many days (200+)
- **Trigger:** A long-running feature with invocations spanning many months
- **Expected behavior:** The bar chart renders all active-range days (including zero days
  in between). For very wide charts, horizontal scroll is acceptable for MVP; the chart
  must not crash or render a blank container. The heatmap still covers exactly 18 weeks;
  early activity simply falls off the trailing window by design.
- **Handled in:** S2, S3

### EC-4.3: Feature's entire activity is older than 18 weeks
- **Trigger:** A feature that was built and closed months ago; all runs are outside the
  heatmap's trailing window
- **Expected behavior:** The heatmap shows all 126 cells at level-0 (activity fell off the
  window). The bar chart still covers the feature's full historical range (no 18-week limit
  on the bar chart). Both views are correct and not misleading.
- **Handled in:** S3 (heatmap design spec — trailing window is intentional)

---

## Category 5: Network / IPC failures

### EC-5.1: FSM HTTP server is down when Trends tab is opened
- **Trigger:** The user opens DBExplorer while `pathly-fsm-http` is not running
- **Expected behavior:** The IPC call to `db:trends` returns null (fetch timeout/error).
  `useTrends` receives null, sets `error` state, and each chart section renders an empty
  state consistent with EC-1.1. No unhandled promise rejection. No spinner that never resolves.
- **Handled in:** S1, S5 (IPC error handling + useTrends error state)

### EC-5.2: Trends IPC call returns a partial or malformed response
- **Trigger:** Network interruption mid-response, or backend bug returns unexpected JSON shape
- **Expected behavior:** `useTrends` treats a non-array `trends` field as empty. TypeScript
  type guards or safe array access prevent crashes on unexpected shapes. Falls through to
  empty state.
- **Handled in:** Conv 2 (useTrends defensive parsing)

---

## Category 6: CSV export edge cases

### EC-6.1: Feature name contains spaces or special characters
- **Trigger:** Feature is named "my feature (v2)" or similar
- **Expected behavior:** The download filename is sanitized: spaces → hyphens, path separators
  (`/`, `\`) and characters invalid in filenames stripped. Result: `my-feature-v2-agent-runs.csv`.
  The CSV content itself is unaffected.
- **Handled in:** S4 (TrendsTab CSV filename sanitization)

### EC-6.2: AGENT_DONE event payload missing expected fields
- **Trigger:** An older event payload has null or missing `cache_read_tokens`, `provider`,
  `cost_source`, etc.
- **Expected behavior:** Missing fields default to `""` or `0` in the CSV row. No crash.
  The resulting CSV is valid (no unclosed quotes, no injected commas).
- **Handled in:** S4 (TrendsTab CSV row mapping with null-coalescing)

### EC-6.3: Very large number of invocations
- **Trigger:** A feature with 5,000+ AGENT_DONE rows
- **Expected behavior:** The CSV is generated entirely in memory as a string and downloaded
  via Blob. For MVP, memory-bound generation is acceptable (this is a developer tool, not
  a production reporting pipeline). No streaming required.
- **Handled in:** S4 (acknowledged limitation — acceptable for MVP)

---

## Known Limitations (not edge cases — accepted product decisions)

- **No drill-down from heatmap cells or bar chart bars** — clicking a cell does not filter
  the raw events view. Out of scope for MVP per PO_NOTES.md.
- **No date-range picker** — bar chart always shows the feature's full active range;
  heatmap always shows trailing 18 weeks. Fixed windows are a design choice.
- **Heatmap trailing window ends today** — older activity silently falls off the grid.
  The bar chart preserves full history; this is consistent with GitHub's contribution graph.
- **Cache line chart density** — with hundreds of invocations, line points become dense and
  readability suffers. Acceptable for MVP; virtualization or thinning is a follow-up.
