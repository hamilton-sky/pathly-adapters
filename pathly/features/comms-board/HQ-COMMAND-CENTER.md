# HQ Command Center — fleet / oversight dashboard (later, separate)

**Status:** parked / future. **Depends on:** multi-adapter routing (P1-rider) + P2 board UI.

> This doc is the **Goals-DAG-context framing + the reason it's deferred**. The older
> parallel-fleet "Studio HQ Fleet Dashboard" plan it overlapped was deleted as superseded
> (it was built on a fleet coordinator that was never built); a detailed build plan, when
> this is picked up, starts from here.

## What it is
A Studio **"mission control"** for a fleet of runs across adapters — the human oversight
layer for when work routes to multiple CLIs (Claude / Codex / Copilot / Antigravity) and/or
runs multiple goals at once.

## Why it's later (not P1)
The routing **plumbing** (adapter per stage/goal) is mostly built and rides the P1
dispatcher. The HQ dashboard is the **visualization/steering** layer on top of it — only
worth building once multiple adapters/goals are actively producing runs to look at. A
dashboard built before the routing is exercised would have nothing to show.

## What it would include
- **Fleet view** — every active run + which adapter/CLI each is on, live status (`/events/runner` SSE exists)
- **Per-adapter cost/token rollups** — telemetry already lands `BILLING_UPDATE` events
- **Reroute** — move a stage/goal to a different adapter mid-run (`POST /runner/reroute` exists)
- **Goals overview** — goals as groupings across boards (fed by the P2 board UI)
- **Health** — rate-limit / provider-down signals → suggest rerouting

## Must exist first
1. Multi-adapter routing **populated** (`adapter_map` set in flows; per-goal adapter in the dispatcher)
2. **P2 board UI** (goals as groupings; executor + adapter selectors)
3. (already exist) `/runner/reroute`, `BILLING_UPDATE` telemetry, `/events/runner` SSE

## Relationship to existing plans
- **Parallel mechanics:** lane parallelism shipped in fsm-fan-out (`../.archive/fsm-fan-out/`); worktree isolation is the `WorktreeIsolation` stub in `supervisor/isolation.py`.
- **Locked design decisions** for the multi-adapter/fleet work live in the project memory
  (FSM stays passive; supervisor is the active layer; routing is deterministic code, never an LLM).

## Out of scope until then
Anything before the P1 dispatcher + P2 board UI ship.
