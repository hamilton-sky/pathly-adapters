# Three-Tier Telemetry — Brief

**Feature:** `telemetry-three-tier`
**Tier:** feature-scope (avoids the project-scope path-collapse bug until slug/scope split lands)
**Rigor:** lite ("fast mode") — consultation → build → light verify

## Problem

Telemetry (`otel_spans`, `agent_invocations`) is written by exactly one site —
`_write_stage_telemetry` in `runner/api_lifecycle.py` — and that site is gated on a
live `RunnerState`. Only FSM/team runs register a `RunnerState`, so **board / single /
loop runs never produce span or invocation rows**, even though every one of them already
writes `AGENT_DONE` to the universal sink `fsm_events`.

Separately, the Studio **DB Explorer** is **feature-keyed only**: `/db/features` →
per-feature `events|agents|otel|runs`. There is **no project or global roll-up view and
no `scope_tier` dimension**. So even the telemetry we *do* capture cannot be observed at
the project or global level in the app.

## Goal

Full feature → project → global observability for **every** agent Pathly spawns, visible
in the DB Explorer.

## Design decision — aggregate-on-read, NOT roll-up-on-write

The naive model ("write the cost into a feature counter, a project counter, and a global
counter") is rejected for three reasons:

1. **Costs are corrected after the fact.** The Stop hook patches the last `AGENT_DONE`
   with the real API cost via `BILLING_UPDATE`. Triple-counters would go stale on every
   correction; one row per fact means one row to correct.
2. **The loop executor runs N workers in parallel.** Incrementing shared counters is a
   race needing locks on the hot path. One append-only INSERT per invocation is
   contention-free.
3. **Roll-up-on-write double-counts the global total.** A feature row + a project mirror
   are both seen by the global query → cost counted twice. Aggregate-on-read literally
   cannot double-count: global is `SUM` over the same rows project reads.

**Model:** one append-only invocation row per agent, addressed by
`(project_root, feature, scope_tier)` and threaded into a goal/run trace. The three levels
are three `GROUP BY`s over that one table:

| Level | Query |
|---|---|
| feature | `WHERE feature = X` |
| project | `WHERE project_root = Y` (sums every feature + project-tier topic under it) |
| global | whole table / `GROUP BY project_root` |

## Mechanism

1. **`scope_tier` tag** (`feature` \| `project` \| `global`) on `agent_invocations` +
   `otel_spans` — additive migration. The level is a *tag*, not separate rows.
2. **Universal projector** — write one `agent_invocation` from every `AGENT_DONE` (the
   sink all five run types already hit), instead of the `RunnerState`-gated write. This is
   the change that lights up board/single/loop.
3. **goal = trace, task = span** — a goal run becomes a trace (root = `goal_id`), each
   task agent a span (parent = the goal). Gives a real multi-agent trace tree for DAG runs.
4. **Aggregation endpoints + DB Explorer roll-up UI** — `/db/rollup` (project + global,
   broken down by `scope_tier`) and a Studio tab that shows feature → project → global.

## Acceptance (the "map with the DB Explorer" criterion)

After a loop/board run, the DB Explorer shows non-empty agent/otel rows for that run AND
a project/global roll-up that sums them without double-counting.
