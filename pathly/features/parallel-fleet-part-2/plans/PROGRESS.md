---
name: Progress
---
# Parallel Fleet Part 2 — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | Fleet Control API | Conv 1 | TODO |
| S2 | Fleet SSE + Crash Reconciliation | Conv 2 | TODO |
| S3 | Studio HQ Fleet Dashboard | Conv 3 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 0, 1, 2 | S1 | TODO | `python -m pytest tests/ -q` |
| 2 | 3, 4, 5, 6 | S2 | TODO | `python -m pytest tests/ -q` |
| 3 | 7, 8, 9, 10 | S3 | TODO | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 0 — Pre-flight | none | Baseline pytest + typecheck; confirm fleet_coord.py + FleetState + SSE machinery exist | All dependency checks pass, baseline recorded | TODO |
| 1 | 1 — /fleet/* endpoints | `src/pathly_orchestrator/http_server.py` | 7 thin route handlers wired to FleetCoordinator | All 7 routes return correct status codes; existing routes unchanged | TODO |
| 1 | 2 — Endpoint tests | `tests/test_fleet_endpoints.py` | 400/409 failure cases + regression check | All new tests pass, no pre-existing tests broken | TODO |
| 2 | 3 — _broadcast_fleet + /events/fleet | `src/pathly_orchestrator/http_server.py` | SSE twin with own registry | GET /events/fleet streams correct event types with keepalive | TODO |
| 2 | 4 — Broadcast call sites | `src/pathly_orchestrator/fleet_coord.py` | _broadcast_fleet called at phase/lane/merge/worktree events | All 6 event types emitted at correct lifecycle points | TODO |
| 2 | 5 — Reconciliation pass | `src/pathly_orchestrator/fleet_coord.py` | Startup pass marks stale fleets escalated + prunes orphan worktrees | After simulated crash, /fleet/status reports escalated; no orphan worktrees | TODO |
| 2 | 6 — SSE + reconciliation tests | `tests/test_fleet_sse.py` | Broadcast, disconnect, reconciliation tests | All 3 new tests pass | TODO |
| 3 | 7 — Pre-flight + fleetStore | `studio/src/renderer/src/store/fleetStore.ts` | Baseline typecheck; confirm /events/fleet reachable; create fleetStore | fleetStore importable, added to index.ts, typecheck passes | TODO |
| 3 | 8 — FleetDashboard | `studio/.../HQ/FleetDashboard/FleetDashboard.tsx` | Fleet phase label, lane list, merge results, SSE hook | FleetDashboard renders; SSE hook opens/closes correctly | TODO |
| 3 | 9 — Sub-components | `studio/.../HQ/FleetDashboard/LaneRow.tsx`, `EscalationBanner.tsx`, `FleetControlBar.tsx` | Lane rows, escalation banner, control buttons | All 3 sub-components render; disabled logic correct; ARIA present | TODO |
| 3 | 10 — Launch verification | none | Typecheck exits 0; Studio launches with dashboard visible | tsc exits 0; FleetDashboard visible in Studio HQ panel | TODO |

## Prerequisites

- `parallel-fleet-part-1` CI gate green (`fleet_coord.py`, `FleetState`, `FLEET_STATE.json`, phase loop, toy-repo end-to-end test)
- `hq-panel` shipped (HQ panel, `runnerStore`, `useHQ.ts` SSE pattern, per-lane runner view)
- `multi-adapter-runner` shipped (HTTP server on 8765, `_broadcast_runner`, `/runner/*`, `/events/runner`)

## Blocked By

- `parallel-fleet-part-1` — must ship first (hard dependency)
- `hq-panel` — must ship first (Studio HQ panel is the parent component)
- `multi-adapter-runner` — transitive dependency (SSE infrastructure and port 8765 server)
