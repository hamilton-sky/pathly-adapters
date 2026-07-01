---
name: Feature Index
---
# DBExplorer Trends Tab — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

> **Scope note:** This plan adds a new "Trends" tab to the existing `FeatureModal` in DBExplorer.
> It is self-contained — three conversations: backend (Python), frontend core (React/TS), frontend cache+wiring.
> The tab is scoped strictly to the currently-open feature; no cross-feature views are in scope.
> Tech constraints: Recharts for charts, CSS modules, no inline styles, `costUtils.ts` for all cost logic.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Cross-layer design decisions (IPC → backend → db/queries) |
| `EDGE_CASES.md` | Planner | Builder, Tester | Edge cases and failure modes per section |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/db/queries/trends.py` | Conv 1 | CREATE: `get_daily_trends(feature, days)` query helper |
| `src/pathly_orchestrator/db/queries/__init__.py` | Conv 1 | MODIFY: re-export trends helper |
| `src/pathly_orchestrator/http_server/blueprints/telemetry.py` | Conv 1 | MODIFY: add `GET /telemetry/trends` route |
| `studio/src/main/ipc/` (handler file TBD) | Conv 1 | MODIFY: add `db:trends` IPC handler calling the HTTP endpoint |
| `studio/src/preload/index.ts` (or similar) | Conv 1 | MODIFY: expose `window.pathly.db.trends` to renderer |
| `studio/src/renderer/src/components/DBExplorer/FeatureModal.tsx` | Conv 3 | MODIFY: add `'trends'` to TabId union, tabs array, tab panel |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/TrendsTab.tsx` | Conv 2 | CREATE: root component; daily cost bar chart + heatmap + CSV export |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/TrendsTab.module.css` | Conv 2 | CREATE: layout + bar chart + heatmap styles |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/useTrends.ts` | Conv 2 | CREATE: data hook — fetches IPC trends + derives cost |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/DailyCostChart.tsx` | Conv 2 | CREATE: Recharts BarChart sub-component |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/ActivityHeatmap.tsx` | Conv 2 | CREATE: 18×7 CSS grid heatmap sub-component |
| `studio/src/renderer/src/components/DBExplorer/TrendsTab/CacheEfficiencyChart.tsx` | Conv 3 | CREATE: Recharts LineChart sub-component |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Backend: db/queries + HTTP endpoint + IPC handler | S1, S2 (data contract) | TODO | `db/queries/trends.py`, `blueprints/telemetry.py`, IPC handler |
| 2 | Frontend core: TrendsTab + daily cost bar chart + heatmap + CSV export | S2, S3, S4, S5 | TODO | `TrendsTab.tsx`, `DailyCostChart.tsx`, `ActivityHeatmap.tsx`, `useTrends.ts` |
| 3 | Frontend cache: cache efficiency line chart + FeatureModal wiring | S6, S7 | TODO | `CacheEfficiencyChart.tsx`, `FeatureModal.tsx` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/dbexplorer-trends-tab/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
