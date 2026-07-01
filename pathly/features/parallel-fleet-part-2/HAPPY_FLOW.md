---
name: Happy Flow
---
# Parallel Fleet Part 2 — Happy Flow

## Overview

A developer has a large feature to build. They open Studio, navigate to the HQ panel, and use the Fleet Dashboard to launch a parallel fleet across three lanes. They watch the lanes converge through the SSE stream, observe a clean merge, and mark the feature done — all without touching a terminal. This is the ideal scenario this feature enables.

---

## Step-by-Step Happy Flow

### Step 1: Navigate to Fleet Dashboard
- **User does**: opens Studio, clicks the HQ panel, sees the Fleet Dashboard tab (or it is the default view when no runner topic is active).
- **System does**: `FleetDashboard` mounts; `useFleetDashboard("my-feature")` opens an `EventSource` to `/events/fleet?feature=my-feature`; receives `{"type":"connected"}`; renders empty lane list with placeholder text.
- **State after**: `fleetStore.phase` is `null`; `lanes` is `[]`; `FleetControlBar` shows Start enabled, all others disabled.

### Step 2: Start the fleet
- **User does**: clicks the Start button in `FleetControlBar`.
- **System does**: `FleetControlBar` POSTs `{feature, fleet_plan_path, base_branch, max_iterations: 10, max_cost_usd: 2.0, autonomy: true}` to `POST /fleet/start`; server calls `FleetCoordinator.start(...)`; returns `{"fleet_id": "fleet-abc123"}` with 200; coordinator begins the foundation phase on a daemon thread.
- **State after**: `fleetStore.phase` → `"foundation"` (from `FLEET_STATUS` SSE event); Start is now disabled; Pause, Resume, Abort buttons update per disabled logic.

### Step 3: Foundation phase completes, lanes start
- **User does**: nothing — observing.
- **System does**: `fleet_coord.py` completes the foundation phase; emits `FLEET_STATUS{phase:"fleet"}`; starts three lane threads; emits three `LANE_STARTED` events with lane name, branch, and worktree path.
- **State after**: `fleetStore.phase` → `"fleet"`; `fleetStore.lanes` has three `LaneState` entries, each `status: "running"`; three `LaneRow` components render with pulsing/running status badges.

### Step 4: Lanes run and complete
- **User does**: nothing — watching lane rows update.
- **System does**: each lane's subprocess finishes; `fleet_coord.py` emits `LANE_STATUS{lane, status:"done"}` for each; eventually all three lanes are done.
- **State after**: all three `LaneRow` entries show `done` status (green badge); `fleetStore.phase` → `"merging"` (from `FLEET_STATUS` event).

### Step 5: Merge phase — clean
- **User does**: nothing — watching merge progress indicators.
- **System does**: coordinator merges the first lane; emits `MERGE_PROGRESS{branch:"lane-auth", result:"clean"}`; merges the second: `MERGE_PROGRESS{branch:"lane-api", result:"clean"}`; merges the third: `MERGE_PROGRESS{branch:"lane-ui", result:"clean"}`; all lanes merged clean; emits `FLEET_STATUS{phase:"done"}`.
- **State after**: three merge result badges show `clean`; `fleetStore.phase` → `"done"`; all `FleetControlBar` buttons are disabled except Start (ready for next fleet).

### Step 6: Fleet complete
- **User does**: reads the completed state; optionally clicks a lane's "View lane" button to review the builder's output.
- **System does**: `LaneRow`'s "View lane" button calls `onDrillIn("my-feature__lane-auth")`; the HQ panel switches to the per-lane runner view using the existing `/events/runner?topic=my-feature__lane-auth` connection.
- **State after**: user is now in the per-lane runner view; Fleet Dashboard is still mounted in background store state.

---

## End State

The parallel fleet ran three lanes in parallel, all merged cleanly, and the developer observed the entire lifecycle — phase transitions, lane status, merge results — from the Studio HQ Fleet Dashboard without any terminal interaction.

## Success Indicators

- [ ] `POST /fleet/start` returns 200 with a `fleet_id`.
- [ ] `LANE_STARTED` events cause `LaneRow` components to appear in real time.
- [ ] `LANE_STATUS{status:"done"}` updates the correct row's badge.
- [ ] `MERGE_PROGRESS` indicators render per-branch.
- [ ] `FLEET_STATUS{phase:"done"}` disables all control buttons.
- [ ] "View lane" drill-in opens the existing runner SSE view for that lane.
- [ ] `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0 throughout.
- [ ] `python -m pytest tests/ -q` is green throughout.
