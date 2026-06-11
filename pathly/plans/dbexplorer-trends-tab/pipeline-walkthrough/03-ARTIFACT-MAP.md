# 03 — Artifact Map: dbexplorer-trends-tab

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | 7 acceptance criteria S1–S7 |
| IMPLEMENTATION_PLAN.md | Planner | Builder agents | 13 phases across 3 conversations |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim builder prompts |
| ARCHITECTURE_PROPOSAL.md | Planner | Builder, Reviewer | Layer rules, IPC contract, 4 design decisions |
| FEATURE_INDEX.md | Planner | Builder agents | Codebase path index for orientation |
| EDGE_CASES.md | Planner | Builder, Reviewer | EC-2.1 null gap rule (cache divide-by-zero) |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status checkpoint |
| DESIGN.md | Designer | Builder Conv 2 | Color palette, typography, heatmap levels, layout rules |
| VERIFY.md | Builder | Orchestrator | Per-stage pass/fail checkpoint |
| RETRO.md | Planner (retro) | Humans, /lessons | What we learned |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| `feedback/REVIEW_FAILURES.md` (Conv 1, cycle 1) | Reviewer | Builder | CostChart.tsx called db.trends() with old number-first signature |
| `feedback/REVIEW_FAILURES.md` (Conv 1, cycle 2) | Reviewer | Builder | empty feature="" guard returned 400 instead of 200+[] |
| `feedback/REVIEW_FAILURES.md` (Conv 2, cycle 1) | Reviewer | Builder | useTrends.ts 183 lines (>150 cap); hardcoded hex in Recharts contentStyle |
| `feedback/TEST_FAILURES.md` (test cycle 1) | Tester | Builder | costEstimated=0 always; label format mismatch; S7 missing featureName prop spec |

---

## Source files changed

### Backend (Python)

| File | Stories | What changed |
|---|---|---|
| `src/pathly_orchestrator/db/queries/trends.py` | S1 | NEW — `get_daily_trends(conn, feature, days=126)` GROUP BY day query |
| `src/pathly_orchestrator/db/queries/__init__.py` | S1 | Added `from .trends import get_daily_trends` re-export |
| `src/pathly_orchestrator/http_server/blueprints/telemetry.py` | S1 | Added `GET /telemetry/trends` route with feature/days params |

### Electron main process (TypeScript)

| File | Stories | What changed |
|---|---|---|
| `studio/src/main/ipc/db.ts` | S1 | Updated `db:trends` handler: new signature `(feature, days?)`, calls `/telemetry/trends` |
| `studio/src/main/preload/index.ts` | S1 | Added `DailyTrendBucket` + `TrendsResponse` interfaces; updated `trends` method signature |

### Renderer types

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/types/global.d.ts` | S1 | Added `DailyTrendBucket`, `TrendsResponse`; updated `Window.pathly.db.trends` |

### Renderer components — existing (modified)

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/components/DBExplorer/CostChart/CostChart.tsx` | S1 | Added `featureName` prop; updated IPC call; new `bucketToPoint` mapper for `DailyTrendBucket` |
| `studio/src/renderer/src/components/DBExplorer/DBExplorer.tsx` | S1 | Passes `featureName=""` to `<CostChart>` for global view |
| `studio/src/renderer/src/components/DBExplorer/FeatureModal/FeatureModal.tsx` | S7 | Added `'trends'` to `TabId`; added Trends tab entry; wired `<TrendsTab>` in tab panel |
| `studio/src/renderer/src/styles/tokens.css` | S3 | Added `--heatmap-level-0` through `--heatmap-level-4` (dark + light theme) |

### Renderer components — new (TrendsTab/)

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/useTrends.ts` | S2,S3,S4,S5 | NEW (74 lines) — data hook: IPC call, DailyCostPoint[], HeatmapCell[126], CsvRow[] |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/trendUtils.ts` | S2,S3,S4,S5 | NEW (114 lines) — `countToLevel`, `gapFill`, `buildHeatmap`, `buildCsvRows` |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/DailyCostChart.tsx` | S2 | NEW (84 lines) — Recharts BarChart, two Bar series (reported/estimated), `$0.0000` y-axis |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/ActivityHeatmap.tsx` | S3 | NEW (22 lines) — 18×7 CSS grid, `data-level` cells, `title` tooltip |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/TrendsTab.tsx` | S4,S5,S7 | NEW (89 lines) — root component, CSV export, renders all sub-charts |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/CacheEfficiencyChart.tsx` | S6 | NEW (103 lines) — Recharts LineChart, `connectNulls={false}`, null on zero-denom |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/TrendsTab.module.css` | S2,S3,S5 | NEW — heatmap grid, data-level selectors, empty-state style |

---

## Artifact flow diagram

```
USER_STORIES.md          ←── 7 stories: daily cost, heatmap, cache, CSV, empty state, wiring
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── 3 conversations × 13 phases; layer rules
       │
       ▼
ARCHITECTURE_PROPOSAL.md ←── layer diagram, IPC contract, EC-2.1 null gap
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompts with scope, rules, verify steps
       │
       ▼
DESIGN.md                ←── color tokens, heatmap level vars, chart heights, UX rules
       │
       ▼
PROGRESS.md              ←── conv 1/2/3 TODO→DONE tracking
       │
       ▼
RETRO.md                 ←── lessons: grep call sites, wire costEstimated upfront, shared CSS-var hook
       │
       ▼
pipeline-walkthrough/dbexplorer-trends-tab/  ←── this folder
```
