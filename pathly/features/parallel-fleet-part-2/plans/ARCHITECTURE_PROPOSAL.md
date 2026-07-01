---
name: Architecture Proposal
---
# Parallel Fleet Part 2 — Architecture Proposal

## Problem Statement

The parallel fleet coordinator (`parallel-fleet-part-1`) runs lanes, merges branches, and escalates conflicts — but it does all of this invisibly inside a daemon thread. There is no HTTP surface to start or stop a fleet, no event stream to observe it, and no Studio panel to interact with it. This feature closes that gap by adding a control and observability layer that treats the fleet exactly like the existing runner is treated: a `/fleet/*` REST API and `/events/fleet` SSE stream on the existing 8765 server, mirrored in a Studio dashboard.

## Proposed Solution

Clone the `/runner/*` + `/events/runner` pattern already delivered by `multi-adapter-runner`, specialized for fleet-level semantics:

- **7 thin `/fleet/*` endpoints** delegating to `FleetCoordinator` methods.
- **`_broadcast_fleet(feature, payload)`** — a third SSE broadcast function alongside `_broadcast_sse` (menus) and `_broadcast_runner` (runner). Own lock, own registry, own client queues.
- **`GET /events/fleet?feature=`** — SSE stream cloning `/events/runner` handler logic.
- **Restart reconciliation** — a `fleet_coord.py` startup pass that marks stale fleets `escalated` and prunes orphan worktrees.
- **Studio `HQ/FleetDashboard/`** — a component subtree under the existing HQ panel, consuming `/events/fleet` via a `useFleetDashboard` hook that mirrors `useHQ.ts`.

## Layer Breakdown

```
Layer A   pathly/plans/parallel-fleet-part-2/ (feature definition)
     │  "phase": "fleet"
     ▼
Layer B   src/pathly_orchestrator/http_server.py
     │  /fleet/* thin endpoints — mutate FleetState, return immediately
     │  GET /events/fleet — SSE stream, _broadcast_fleet twin
     ▼
Layer C   src/pathly_orchestrator/fleet_coord.py  (part-1 — unmodified logic)
     │  FleetCoordinator + FleetState + phase loop
     │  call sites for _broadcast_fleet added here (call sites only)
     │  reconciliation pass on __init__
     ▼
Runtime / existing HTTP server (port 8765)
     │
     ▼
Layer D   studio/src/renderer/src/store/fleetStore.ts (Zustand)
     │  receives SSE events via useFleetDashboard hook
     ▼
Layer E   studio/.../HQ/FleetDashboard/ (React components)
     │  FleetDashboard, LaneRow, EscalationBanner, FleetControlBar
     │  POST to /fleet/* endpoints
```

## Key Design Decisions

### Decision 1: `/fleet/*` as a twin of `/runner/*`, not an extension
- **Options considered**: (A) add fleet routes alongside runner routes in the same section; (B) a separate Flask Blueprint or file; (C) a twin section in `http_server.py` following the same structural pattern as runner.
- **Chosen**: C — twin section in `http_server.py`.
- **Rationale**: keeps all HTTP handling in one file (matches existing codebase), makes the parallelism explicit and auditable, and avoids a build-system change. The `/runner/*` code is recent and well-structured; cloning it is low-risk.

### Decision 2: Separate `_broadcast_fleet` registry
- **Options considered**: (A) reuse `_broadcast_runner` with a feature-prefix on the topic key; (B) separate registry + lock.
- **Chosen**: B.
- **Rationale**: runner topics are per-run identifiers; fleet features are feature-level identifiers. Sharing a registry would blur the semantic boundary and require the consumer to filter. A separate registry is 10 lines and is structurally unambiguous.

### Decision 3: No self-HTTP for fan-out
- **Options considered**: (A) `/fleet/pause` calls `http://127.0.0.1:8765/runner/pause` for each lane; (B) `/fleet/pause` calls the supervisor Python API directly.
- **Chosen**: B.
- **Rationale**: self-HTTP adds network round-trip overhead, requires the server to be fully started before the request handler runs, and creates a failure mode where the fan-out silently fails if the connection is refused. Direct Python call is synchronous, testable with a mock, and avoids all of these.

### Decision 4: Reconciliation on `FleetCoordinator.__init__`
- **Options considered**: (A) a background polling daemon; (B) a one-time startup pass.
- **Chosen**: B.
- **Rationale**: the failure mode (server restart mid-fleet) is rare. A startup pass is sufficient: it runs once, fixes stale state, and exits. A daemon adds complexity and CPU overhead for a case that should be exceptional.

### Decision 5: `fleetStore` separate from `runnerStore`
- **Options considered**: (A) extend `runnerStore` with fleet fields; (B) a separate Zustand store.
- **Chosen**: B.
- **Rationale**: fleet state (phase, lanes[], escalations[]) has no semantic overlap with runner state (single-topic, cost, decision menu). Merging them would create an over-broad store and make selective Zustand selectors harder to reason about.

## Key Components

| Component | New/Modified | Description |
|---|---|---|
| `http_server.py` | MODIFY | 7 `/fleet/*` route handlers + `_broadcast_fleet` + `GET /events/fleet` |
| `fleet_coord.py` | MODIFY | `_broadcast_fleet` call sites + reconciliation pass in `__init__` |
| `tests/test_fleet_endpoints.py` | NEW | 400/409/200 path tests for all 7 endpoints + regression |
| `tests/test_fleet_sse.py` | NEW | Broadcast queue test, disconnect test, reconciliation test |
| `studio/.../store/fleetStore.ts` | NEW | Zustand store for fleet phase, lanes, merge results, escalations |
| `studio/.../HQ/FleetDashboard/FleetDashboard.tsx` | NEW | Root dashboard component + `useFleetDashboard` SSE hook |
| `studio/.../HQ/FleetDashboard/LaneRow.tsx` | NEW | Per-lane row with status badge + drill-in button |
| `studio/.../HQ/FleetDashboard/EscalationBanner.tsx` | NEW | Conflict escalation alert with resolve action |
| `studio/.../HQ/FleetDashboard/FleetControlBar.tsx` | NEW | Start/Pause/Resume/Abort with phase-driven disabled logic |

## Interface Design

### `/fleet/start` request / response
```
POST /fleet/start
Body: { feature: str, fleet_yaml?: str, fleet_plan_path?: str, base_branch: str,
        max_iterations: int, max_cost_usd: float, autonomy: bool }
200: { fleet_id: str }
400: { error: "max_iterations and max_cost_usd are required" }
409: { error: "fleet already active for feature <feature>" }
```

### `FleetState` JSON snapshot (`GET /fleet/status`)
```
{
  fleet_id: str, feature: str,
  phase: "planning"|"foundation"|"fleet"|"merging"|"done"|"escalated",
  lanes: [{ lane: str, branch: str, worktree: str, status: str }],
  merge_order: [str], integration_branch: str,
  escalations: [{ reason: str, ... }]
}
```

### `fleetStore` public API (TypeScript)
```ts
setFleetState(partial: Partial<FleetStoreState>): void
resetFleet(): void
upsertLane(lane: LaneState): void        // insert or update by lane.lane
upsertMergeResult(r: MergeResult): void  // insert or update by r.branch
addEscalation(e: Escalation): void
clearEscalations(): void
```

## Risks

- **Circular import between `http_server.py` and `fleet_coord.py`**: `fleet_coord.py` needs `_broadcast_fleet` from `http_server.py`, but `http_server.py` imports `FleetCoordinator`. Mitigation: use the deferred-import or callback-injection pattern already used by `supervisor.py` → `http_server.py` in `multi-adapter-runner`. Builder must read that pattern before implementing.
- **`FleetState` schema mismatch**: `parallel-fleet-part-1` might ship a different field set than assumed. Mitigation: Phase 0 explicitly checks all required fields and halts if any are missing.
- **`git worktree remove --force` failure during reconciliation**: worktree directory may already be gone. Mitigation: wrap in try/except, log, continue — reconciliation is best-effort.
