# Implementation Plan — Three-Tier Telemetry

File-level, dependency-ordered. Hot path = `runner/api_lifecycle.py` + the universal
`AGENT_DONE` sink — change carefully, verify with pytest after each task.

## T1 — `scope_tier` column (P0, no deps)
**Files:** `src/pathly_orchestrator/db/migrations_incremental.py`
- Add `("agent_invocations", "scope_tier", "TEXT DEFAULT 'feature'")` and
  `("otel_spans", "scope_tier", "TEXT DEFAULT 'feature'")` to the additive-column list.
- Default `'feature'` so existing rows read sensibly.
**Verify:** start server (migrations run); `PRAGMA table_info` shows the columns.

## T2 — Universal AGENT_DONE → agent_invocation projector (dep: T1)
**Files:** new `src/pathly_orchestrator/db/queries/invocations.py` helper +
`src/pathly_orchestrator/db/queries/fsm_events.py` (or a thin projector module).
- Add `write_agent_invocation` support for `scope_tier`.
- Add `project_invocation_from_agent_done(conn, project_root, feature, payload, scope_tier)`
  that maps an `AGENT_DONE` payload → an `agent_invocations` row (run_id, stage, agent_role,
  tokens, cost_usd, session_id, summary).
- Call it from the single point where `AGENT_DONE` is appended after a board/single/loop
  agent finishes (so all five run types flow through one writer). Best-effort, never raises.
**Verify:** unit test — appending an `AGENT_DONE` yields exactly one invocation row.

## T3 — Executor scope_tier tagging (dep: T2)
**Files:** `src/pathly_orchestrator/supervisor/scheduler.py`,
`src/pathly_orchestrator/supervisor/goal_run.py`, `supervisor/board_run.py`.
- Thread the executor's `board` (feature|project|global) → `scope_tier` into the projector.
- single/loop/team/board each pass their known tier.
**Verify:** a loop run tags rows `scope_tier` from its board.

## T4 — goal = trace / task = span (dep: T1, T3)
**Files:** `src/pathly_orchestrator/supervisor/scheduler.py` (+ otel_spans helper).
- On goal-run start, mint a `trace_id` (root span = goal). Each task worker writes an
  `otel_span` with that `trace_id` and `parent_span_id` = the goal span.
**Verify:** a loop run's spans share one `trace_id`, children point at the goal span.

## T5 — Aggregation endpoints (dep: T2)
**Files:** new `src/pathly_orchestrator/http_server/blueprints/ops/db_api_rollup.py`
(register in the db_api blueprint).
- `GET /db/rollup?project_root=…` → `{ project: {by_tier, totals}, global: {by_tier, totals} }`
  using `GROUP BY scope_tier` over `agent_invocations`. Pure aggregation, no stored counters.
- Keep under the 400-line SRP limit; new domain file, not appended to `db_api_explorer.py`.
**Verify:** sums equal the feature rows; global ⊇ project with no double-count.

## T6 — DB Explorer roll-up UI (dep: T5)
**Files:** `studio/src/renderer/src/components/**` DB Explorer panel + service.
- New "Roll-up" view: feature → project → global, `scope_tier` breakdown.
- Add the `scope_tier` column to the existing Agents/OTel tables.
**Verify:** renderer typecheck clean; panel renders the rollup payload.

## T7 — Tests (dep: T2, T5)
**Files:** `tests/test_runner_endpoints.py` or new `tests/test_telemetry_three_tier.py`.
- Projector writes a row for a synthetic board/single/loop `AGENT_DONE`.
- Aggregation: feature sums = project total; global has no duplicate facts.
**Verify:** `python -m pytest tests/ -q` green.

## Dependency graph
```
T1 ──┬─> T2 ──┬─> T3 ──> T4
     │        ├─> T5 ──> T6
     └────────┘   └─> T7
                  T2 ──> T7
```
