---
name: Edge Cases
---
# Parallel Fleet Part 2 — Edge Cases

## Category 1: Fleet start and caps

### EC-1.1: `/fleet/start` missing caps
- **Trigger**: `POST /fleet/start` body omits `max_iterations` or `max_cost_usd`.
- **Expected behavior**: 400 with `{"error": "max_iterations and max_cost_usd are required"}`. No fleet is created.
- **Handled in**: Phase 1 / Conv 1.

### EC-1.2: Double-start for the same feature
- **Trigger**: `POST /fleet/start` for a feature that already has an active fleet in the `FleetCoordinator` registry.
- **Expected behavior**: 409 with a descriptive error body. The running fleet is unaffected.
- **Handled in**: Phase 1 / Conv 1. Tested in Phase 2.

### EC-1.3: Unknown feature in any endpoint
- **Trigger**: any `/fleet/*` endpoint receives a `feature` that has no entry in the `FleetCoordinator` registry.
- **Expected behavior**: 404. No state mutation occurs.
- **Handled in**: Phase 1 / Conv 1.

---

## Category 2: State-gated control operations

### EC-2.1: Pause when fleet is not running
- **Trigger**: `POST /fleet/pause` when fleet `phase` is `done` or `escalated`.
- **Expected behavior**: 409.
- **Handled in**: Phase 1 / Conv 1.

### EC-2.2: Resume when fleet is not paused
- **Trigger**: `POST /fleet/resume` when fleet `phase` is `fleet` (already running).
- **Expected behavior**: 409.
- **Handled in**: Phase 1 / Conv 1.

### EC-2.3: Retry-lane on a non-failed lane
- **Trigger**: `POST /fleet/retry-lane` for a lane whose status is `running` or `done`.
- **Expected behavior**: 400.
- **Handled in**: Phase 1 / Conv 1.

### EC-2.4: Resolve-escalation with no pending escalation
- **Trigger**: `POST /fleet/resolve-escalation` when `FleetState.escalations` is empty.
- **Expected behavior**: 400.
- **Handled in**: Phase 1 / Conv 1.

---

## Category 3: Crash and reconciliation

### EC-3.1: Server restart mid-fleet (running lanes)
- **Trigger**: server process killed while `FLEET_STATE.json` has `phase: "fleet"` or `phase: "merging"` and lane threads are gone.
- **Expected behavior**: on next startup, reconciliation marks the fleet `escalated`. `GET /fleet/status` returns `escalated`, not `running` or `fleet`. No orphan worktrees remain.
- **Handled in**: Phase 5 / Conv 2. Tested in Phase 6.

### EC-3.2: `FLEET_STATE.json` missing on startup
- **Trigger**: `pathly/plans/<feature>/FLEET_STATE.json` does not exist when reconciliation runs.
- **Expected behavior**: log warning, skip — no crash. Server starts normally.
- **Handled in**: Phase 5 / Conv 2.

### EC-3.3: `FLEET_STATE.json` malformed on startup
- **Trigger**: `FLEET_STATE.json` contains invalid JSON.
- **Expected behavior**: log warning, skip — no crash. Server starts normally.
- **Handled in**: Phase 5 / Conv 2.

### EC-3.4: `git worktree remove` fails during reconciliation
- **Trigger**: orphan worktree directory was already deleted before reconciliation runs.
- **Expected behavior**: `git worktree remove --force` raises a subprocess error; catch it, log, continue. No crash. Other orphans are still pruned.
- **Handled in**: Phase 5 / Conv 2.

---

## Category 4: SSE

### EC-4.1: Multiple SSE clients for the same feature
- **Trigger**: two Studio instances (or browser tabs) connect to `/events/fleet?feature=same`.
- **Expected behavior**: both clients receive all events. The `_fleet_sse_clients[feature]` list holds both queues.
- **Handled in**: Phase 3 / Conv 2.

### EC-4.2: SSE client disconnect
- **Trigger**: Studio closes the `EventSource` connection (tab closed, component unmounted).
- **Expected behavior**: the per-client queue is deregistered from `_fleet_sse_clients` under the lock. Subsequent `_broadcast_fleet` calls do not attempt to write to the removed queue. No memory leak.
- **Handled in**: Phase 3 / Conv 2. Tested in Phase 6.

### EC-4.3: Backend not reachable when Studio opens `FleetDashboard`
- **Trigger**: Studio opens `FleetDashboard` but the HTTP server on 8765 is not running.
- **Expected behavior**: `EventSource` `onerror` fires immediately; `fleetStore.errorMessage` is set to `"Reconnecting…"`; an error state renders in the dashboard (no crash, no blank screen). After 3 seconds a reconnect attempt is made.
- **Handled in**: Phase 8 / Conv 3.

### EC-4.4: `CONFLICT_ESCALATION` arrives while banner is already visible
- **Trigger**: a second conflict event arrives before the first is resolved.
- **Expected behavior**: `addEscalation` appends to the array; `EscalationBanner` shows the latest escalation (or a count). No duplicate rendering crash.
- **Handled in**: Phase 9 / Conv 3.

### EC-4.5: Fleet transitions to `done` while `EscalationBanner` is displayed
- **Trigger**: `FLEET_STATUS{phase:"done"}` arrives while `escalations.length > 0`.
- **Expected behavior**: `clearEscalations()` is called (or the banner derives its visibility from `phase !== "done"`); banner disappears.
- **Handled in**: Phase 9 / Conv 3.

---

## Category 5: Studio UI

### EC-5.1: Empty lane list on dashboard open
- **Trigger**: fleet just started; no `LANE_STARTED` events have arrived yet.
- **Expected behavior**: `FleetDashboard` renders a loading/empty placeholder, not an empty array crash.
- **Handled in**: Phase 8 / Conv 3.

### EC-5.2: FleetControlBar disabled state inconsistency
- **Trigger**: `phase` changes rapidly (foundation → fleet → merging) while the user is about to click a button.
- **Expected behavior**: disabled logic derives directly from `fleetStore.phase` selector — no stale closures. The button that was enabled is now visually disabled if phase changed before the click lands.
- **Handled in**: Phase 9 / Conv 3 (Zustand selector is reactive).

### EC-5.3: LaneRow drill-in with no navigation handler
- **Trigger**: `onDrillIn` callback is not provided to `LaneRow`.
- **Expected behavior**: "View lane" button is rendered but clicking it is a no-op (or the callback is optional and guarded). No crash.
- **Handled in**: Phase 9 / Conv 3.

---

## Known Limitations (out of scope for this plan)

- **Per-lane cost tracking in the fleet view** — the dashboard shows lane status, not per-lane cost. Cost is visible in the drill-in runner view via `runnerStore`.
- **Fleet-level cost cap enforcement** — caps are per-lane (via runner), not fleet-wide. A fleet-level cap is a future enhancement.
- **Conflict resolution UI** — the "Resolve" button in `EscalationBanner` posts to `/fleet/resolve-escalation` but does not present a diff or merge editor. The coordinator receives the resolution signal; the human resolves the conflict externally.
- **Multi-fleet observability** — the dashboard shows one fleet at a time (keyed by `feature`). Switching between active fleets requires re-mounting with a different `feature` prop.
