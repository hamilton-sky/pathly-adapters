---
name: Flow Diagram
---
# Parallel Fleet Part 2 — Flow Diagram

## Happy Path: Start fleet → lanes run → clean merge

```
Developer (Studio)
        │
        │  click Start
        ▼
FleetControlBar
        │  POST /fleet/start {feature, caps}
        ▼
http_server.py: POST /fleet/start handler
        │  validate caps (400 if missing)
        │  check registry (409 if active)
        │  FleetCoordinator.start(feature, ...)
        │  return {"fleet_id": ...}
        ▼
FleetCoordinator (daemon thread — part-1 logic, unchanged)
        │
        ├─ foundation phase ──► _broadcast_fleet(FLEET_STATUS{phase:"foundation"})
        │                                │
        │                                ▼
        │                       GET /events/fleet?feature=  ──► fleetStore.phase="foundation"
        │
        ├─ spawn lane threads
        │       │
        │       ├─ lane "auth"  ──► _broadcast_fleet(LANE_STARTED{lane,branch,worktree})
        │       ├─ lane "api"   ──► _broadcast_fleet(LANE_STARTED{...})
        │       └─ lane "ui"    ──► _broadcast_fleet(LANE_STARTED{...})
        │                                │
        │                                ▼
        │                       LaneRow components appear (status: running)
        │
        ├─ lanes finish
        │       │
        │       └─ each lane ──► _broadcast_fleet(LANE_STATUS{status:"done"})
        │                                │
        │                                ▼
        │                       LaneRow status badge → done (green)
        │
        ├─ merging phase ──► _broadcast_fleet(FLEET_STATUS{phase:"merging"})
        │       │
        │       ├─ merge lane-auth ──► _broadcast_fleet(MERGE_PROGRESS{result:"clean"})
        │       ├─ merge lane-api  ──► _broadcast_fleet(MERGE_PROGRESS{result:"clean"})
        │       └─ merge lane-ui   ──► _broadcast_fleet(MERGE_PROGRESS{result:"clean"})
        │                                │
        │                                ▼
        │                       merge result badges → clean
        │
        └─ done ──► _broadcast_fleet(FLEET_STATUS{phase:"done"})
                             │
                             ▼
                    FleetControlBar: Start enabled, others disabled
```

---

## Conflict Escalation Flow

```
Merging phase
        │
        ├─ merge lane-api ──► conflict detected
        │       │
        │       └─► _broadcast_fleet(CONFLICT_ESCALATION{branch,file,kind:"textual"})
        │                        │
        │                        ▼
        │               fleetStore.addEscalation(...)
        │                        │
        │                        ▼
        │               EscalationBanner appears (role="alert")
        │               shows: branch, file, kind
        │               "Resolve" button enabled
        │
        │  (coordinator is blocked — waiting for resolve_escalation)
        │
Developer sees banner
        │
        │  click "Resolve"
        ▼
EscalationBanner
        │  POST /fleet/resolve-escalation {feature, branch, file}
        ▼
http_server.py: POST /fleet/resolve-escalation handler
        │  validate escalation pending (400 if none)
        │  FleetCoordinator.resolve_escalation(feature, resolution)
        │  return 200
        ▼
FleetCoordinator resumes coordinator thread
        │  clears escalation, continues merge
        │
        └─► _broadcast_fleet(MERGE_PROGRESS{result:"clean"})
                    │
                    ▼
        EscalationBanner: clearEscalations() → banner disappears
```

---

## Crash / Restart Reconciliation Flow

```
Server killed mid-fleet
        │
        │  FLEET_STATE.json: { phase: "fleet", ... }
        │  worktrees: [lane-auth, lane-api, lane-ui] + orphan "lane-old"
        │
Server restarts
        │
        ▼
FleetCoordinator.__init__ / reconcile()
        │
        ├─ load all pathly/plans/*/FLEET_STATE.json
        │
        ├─ for fleet with phase "fleet" or "merging":
        │       phase = "escalated"
        │       append escalation {reason:"server_restart"}
        │       write FLEET_STATE.json
        │
        ├─ run `git worktree list --porcelain`
        │
        ├─ for worktree "lane-old" (not in FleetState.lanes[].branch):
        │       `git worktree remove --force <path>`
        │       _broadcast_fleet(WORKTREE{action:"orphan_pruned"})
        │                            ├─ subprocess error? → log + continue
        │
        └─ reconciliation complete
                │
                ▼
GET /fleet/status?feature=<feature>
        │
        └─► { phase: "escalated", ... }  (truthful — not "fleet")
```

---

## SSE Client Lifecycle (per client)

```
Studio mounts FleetDashboard
        │
        ▼
useFleetDashboard(feature)
        │  new EventSource(`.../events/fleet?feature=${feature}`)
        ▼
http_server.py: GET /events/fleet handler
        │  register new queue.Queue in _fleet_sse_clients[feature]
        │  send: data: {"type":"connected"}
        │
        │  (generator loop)
        │  ┌──────────────────────────────────────────┐
        │  │  queue.get(timeout=20)                   │
        │  │    ├─ got event → send data: <json>      │
        │  │    └─ timeout  → send: : keepalive\n\n   │
        │  └──────────────────────────────────────────┘
        │
Studio unmounts / EventSource.close()
        │
        ▼
GeneratorExit raised in generator
        │
        └─► deregister queue from _fleet_sse_clients[feature] under _fleet_sse_lock
```

---

## Component Legend

| Symbol / Name | Role in this feature |
|---|---|
| `FleetCoordinator` | Owns fleet lifecycle (part-1). This feature adds broadcast call sites only. |
| `http_server.py /fleet/*` | Thin control API. Mutates FleetState, returns immediately. |
| `_broadcast_fleet` | Pushes JSON payloads to all registered SSE client queues for a feature. |
| `GET /events/fleet` | SSE stream handler. Per-client queue, keepalive, deregister on disconnect. |
| `fleetStore` | Zustand store. Single source of truth for fleet state in Studio. |
| `useFleetDashboard` | Hook. Opens/closes EventSource; dispatches SSE events to fleetStore. |
| `FleetDashboard` | Root dashboard component. Renders phase, lane list, merge results. |
| `LaneRow` | Per-lane status row. Status badge + drill-in to runner view. |
| `EscalationBanner` | role="alert" conflict notice. Resolve button posts to /fleet/resolve-escalation. |
| `FleetControlBar` | Start/Pause/Resume/Abort. Phase-driven disabled logic. |
