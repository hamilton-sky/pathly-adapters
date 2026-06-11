# DBExplorer Trends Tab — Retrospective

Feature: `dbexplorer-trends-tab`
Pipeline completed: 2026-06-11
Rigor: standard

---

## What we built

A Trends tab added to the DBExplorer FeatureModal, wired through a clean three-layer stack:
a Python `get_daily_trends()` query, a `GET /telemetry/trends` HTTP blueprint route, and an IPC
`db:trends` handler. The frontend delivers a daily cost bar chart distinguishing reported vs
estimated spend, an 18-week GitHub-style activity heatmap (126 cells, data-level hover), a
cache efficiency line chart with null gaps for zero-denominator days (EC-2.1), and a CSV export
of all agent invocations — all rendered via Recharts and surfaced as a new tab in FeatureModal
alongside the existing tabs.

---

## What went well

- 3-conversation architecture was clean: backend (Conv 1), frontend core charts (Conv 2),
  cache chart + modal wiring (Conv 3) — each left the codebase runnable.
- Recharts installed and rendered correctly on the first attempt with no compatibility issues.
- EC-2.1 null-gap pattern (return `null` for zero-denominator days, `connectNulls` off) was
  implemented correctly in Conv 3 without iteration.
- Layer isolation held: `db/queries/`, `blueprints/telemetry.py`, and IPC handlers were each
  touched exactly once and did not bleed into adjacent concerns.
- All seven stories reached DONE status; tester PASS on first run.

---

## What was hard

- **IPC call-site drift:** The existing `CostChart.tsx` was a silent consumer of the old
  `db:trends` IPC contract. Changing the handler signature in Conv 1 broke it without a
  compile error; the reviewer caught it in a fix cycle.
- **costEstimated hardcoded to 0:** `trendUtils` initially returned `0` for estimated cost
  rather than calling `computeCost` per-event from the `DbEvent[]` prop. Found by the tester,
  not the reviewer.
- **Inline styles in Recharts Tooltip:** `CacheEfficiencyChart` repeated the same
  `contentStyle` inline-styles violation that `DailyCostChart` had in Conv 2. The pattern was
  fixed twice instead of once.
- **FSM gate (DESIGNING → BUILDING):** The `on_content` condition checks for a
  `## Design System Output` header in `DESIGN.md`. When the designer omits that header, the
  transition silently stalls. Worked around manually this run.

---

## What to do differently next time

- **Grep all call sites before closing an IPC-change conversation.** When a handler signature
  changes, search the entire `studio/src/` tree for the channel name before marking the phase
  done. One grep prevents a review fix cycle.
- **gapFill / cost utilities: accept pricingTable from the start.** When the spec explicitly
  calls out `costEstimated`, the data hook should wire `computeCost` in the initial
  implementation, not default to `0` as a placeholder.
- **Shared CSS-var reader utility for Recharts.** The `getComputedStyle` + `--color-*` pattern
  was duplicated in every chart component. Extract a `useCssVar(name: string): string` hook
  once, reuse everywhere.
- **Inline `## Design System Output` into the designer prompt.** The DESIGNING → BUILDING FSM
  gate depends on that header. The designer prompt should instruct the designer to include it
  so the gate fires without manual intervention.

---

## Token usage summary

| Agent | Tokens | Cost (USD) |
|---|---|---|
| planner | 179,305 | $0.97 |
| designer | 36,979 | $0.20 |
| builder (Conv 1) | 121,034 | $0.65 |
| reviewer (Conv 1) | 210,925 | $1.14 |
| builder (Conv 2) | 118,276 | $0.64 |
| reviewer (Conv 2) | 61,696 | $0.33 |
| builder (Conv 3) | 59,176 | $0.32 |
| reviewer (Conv 3) | 38,032 | $0.21 |
| tester | 110,549 | $0.60 |
| **Total** | **935,972** | **$5.06** |

Note: reviewer Conv 1 (210k tokens) was the most expensive stage — 2 fix cycles from the
CostChart call-site miss and the empty-feature edge case. The IPC grep habit (see above)
should reduce this on the next similar feature.
