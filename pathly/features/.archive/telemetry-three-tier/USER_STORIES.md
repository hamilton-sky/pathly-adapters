# User Stories — Three-Tier Telemetry

## US-01 — Board/single/loop agents are observed
**As** a supervisor watching a DAG run,
**I want** every spawned agent (board, single, loop — not just FSM/team) to write an
`agent_invocation` row,
**so that** the DB Explorer's Agents tab is non-empty for goal runs.

**Acceptance:**
- A `single` and a `loop` run each produce ≥1 `agent_invocations` row.
- Rows carry `project_root`, `feature`, `cost_usd`/`tokens` when available from `AGENT_DONE`/stdout.
- No `RunnerState` is required for the row to be written.

## US-02 — Every invocation is tagged with its scope tier
**As** an analyst,
**I want** each invocation/span tagged `scope_tier ∈ {feature, project, global}`,
**so that** a project-board `analyze`/`split`/comment agent and a feature-board agent are
distinguishable yet roll up together.

**Acceptance:**
- `agent_invocations.scope_tier` and `otel_spans.scope_tier` exist (additive migration; old rows default sensibly).
- The executor sets the tier from the board/scope it ran under.

## US-03 — Feature → project → global roll-up by query
**As** an analyst,
**I want** project and global totals derived by aggregation, never by stored counters,
**so that** billing corrections stay consistent and global never double-counts.

**Acceptance:**
- `/db/rollup` returns project-level and global-level sums (cost, tokens, invocation count), broken down by `scope_tier`.
- Summing feature rows = the project total = the relevant slice of global (no duplicate fact rows).

## US-04 — A DAG run is a trace tree
**As** a supervisor,
**I want** a goal run to appear as one trace with a span per task agent,
**so that** I can see the shape of a multi-agent loop/team run.

**Acceptance:**
- A loop run writes `otel_spans` with a shared `trace_id` (root = goal) and one child span per task (`parent_span_id` = goal span).

## US-05 — Roll-up is visible in the DB Explorer (the headline)
**As** a user in Studio,
**I want** a project/global roll-up view with a `scope_tier` breakdown in the DB Explorer,
**so that** "full telemetry observation" is something I can actually see in the app.

**Acceptance:**
- A new DB Explorer surface shows feature → project → global totals.
- The per-feature Agents/OTel tabs show the new `scope_tier` column.
