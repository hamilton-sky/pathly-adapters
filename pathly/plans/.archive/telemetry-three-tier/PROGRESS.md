# Progress — Three-Tier Telemetry

| Task | Title | Status |
|---|---|---|
| T1 | scope_tier migration | ✅ DONE |
| T2 | universal AGENT_DONE projector | ✅ DONE |
| T3 | executor scope_tier tagging | ✅ DONE |
| T4 | goal=trace / task=span | ✅ DONE |
| T5 | /db/rollup aggregation endpoint | ✅ DONE |
| T6 | DB Explorer roll-up UI | ✅ DONE |
| T7 | tests | ✅ DONE |

**Flow:** STORM (skipped, design done) → PLAN ✅ → DESIGN (folded into plan) → BUILD ✅
**Rigor:** lite / fast mode

## Build summary

| Task | Files |
|---|---|
| T1 | `db/migrations_incremental.py` — `scope_tier` on agent_invocations + otel_spans |
| T2 | `runner/telemetry.py` (new projector) + `db/queries/{invocations,otel_spans}.py` (scope_tier) + `supervisor/terminal.py` (`_emit_executor_telemetry`, gated on `executor_owned_telemetry`) |
| T3 | `supervisor/state.py` (4 fields) + `goal_executor._run_loop` + `board_run._default_spawn` set scope_tier |
| T4 | `_run_loop` mints goal trace + `write_goal_root_span`; each task span parents the goal span |
| T5 | `http_server/blueprints/ops/db_api_rollup.py` (new) — `GET /db/rollup`, aggregate-on-read |
| T6 | `DBExplorer/RollupView/` (new) + `db:rollup` IPC (main/preload/global.d.ts) + Σ toggle |
| T7 | `tests/test_telemetry_three_tier.py` — projector, goal=trace, no-double-count rollup |

**Verification:** `test_telemetry_three_tier.py` green; regression sweep 168 passed; renderer + main typecheck clean.

**Activation:** restart the FSM server (runs the `scope_tier` migration + registers `/db/rollup`); reload/rebuild Studio for the Σ roll-up view.

**Known follow-ups:** (1) early-advance executor runs record cost from the pre-reconciliation
AGENT_DONE — accurate-cost patch in `_reconciliation_window` is a refinement. (2) The Agents
tab is `AGENT_DONE`-event-sourced, so its per-row `scope_tier` column needs a data-source
switch to `db.agents` (the endpoint now returns the field).
