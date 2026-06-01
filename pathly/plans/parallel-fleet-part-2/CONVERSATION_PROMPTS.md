---
name: Conversation Guide
---
# Parallel Fleet Part 2 — Conversation Guide

Split into 3 conversations (strict order `1 → 2 → 3`). Each produces runnable, tested code.
After each conversation, **commit your changes** before starting the next.

**Upstream dependencies:** `parallel-fleet-part-1` CI gate must be green; `hq-panel` and `multi-adapter-runner` must be shipped. Confirm all three in Phase 0 before touching any file.

---

## Conversation 1: `/fleet/*` control endpoints (Phases 0–2)

**Stories delivered:** S1

**Prompt to paste:**
```
Read pathly/plans/parallel-fleet-part-2/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Parallel Fleet Part 2 Conversation 1 (Phases 0–2) from pathly/plans/parallel-fleet-part-2/IMPLEMENTATION_PLAN.md.

Before editing anything: glob/read the live repo to confirm every file path listed below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.
Read CLAUDE.md and src/pathly_orchestrator/CLAUDE.md for project-specific rules before implementing.

Phase 0 (pre-flight — complete before any edit):
1. Run `python -m pytest tests/ -q`. Record any pre-existing failures as baseline — do NOT fix them.
2. Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`. Record baseline typecheck errors — do NOT fix them.
3. Confirm `src/pathly_orchestrator/fleet_coord.py` exists (glob it). If absent, STOP and report — parallel-fleet-part-1 has not shipped.
4. Run `python -c "from pathly_orchestrator.fleet_coord import FleetState; print('ok')"`. If it fails, STOP.
5. Confirm FleetState has fields: fleet_id, feature, phase, lanes, merge_order, integration_branch, escalations. If any field is missing, write an OPEN item to pathly/plans/parallel-fleet-part-2/feedback/HUMAN_QUESTIONS.md and STOP.
6. Grep src/pathly_orchestrator/http_server.py for `_broadcast_sse` and `/events/runner`. If either is absent, STOP — multi-adapter-runner has not shipped.

Codebase files this conversation touches:
- `src/pathly_orchestrator/http_server.py` — add 7 `/fleet/*` route handlers
- `tests/test_fleet_endpoints.py` (NEW) — fleet control endpoint tests

Phase 1 (`/fleet/*` endpoints in `http_server.py`):
- Follow the existing route-decorator + CORS/OPTIONS pattern from the `/runner/*` routes. Read that section of http_server.py first to match conventions exactly.
- `POST /fleet/start`: parse {feature, fleet_yaml|fleet_plan_path, base_branch, max_iterations, max_cost_usd, autonomy}. Return 400 if max_iterations or max_cost_usd is absent. Return 409 if a fleet for that feature is already active. Otherwise call FleetCoordinator.start(...) and return {"fleet_id": <str>} with 200.
- `GET /fleet/status?feature=`: look up FleetState; 404 if not found; serialize all FleetState fields as JSON.
- `POST /fleet/pause`: fan out to each active lane via the supervisor registry (Python call — no self-HTTP). Return 409 if phase is not `fleet` or `merging`.
- `POST /fleet/resume`: mirror of pause. Return 409 if phase is not `paused` or `escalated`.
- `POST /fleet/abort`: call FleetCoordinator.abort(feature). Return 200.
- `POST /fleet/retry-lane`: parse {feature, lane}. Return 400 if lane status is not `failed`. Call FleetCoordinator.retry_lane(feature, lane). Return 200.
- `POST /fleet/resolve-escalation`: parse {feature, ...resolution fields}. Return 400 if no escalation is pending. Call FleetCoordinator.resolve_escalation(feature, resolution). Return 200.
- All seven handlers: return 404 for unknown feature.
- Do NOT add _broadcast_fleet or /events/fleet yet — that is Conversation 2.

Phase 2 (tests in `tests/test_fleet_endpoints.py`):
- Use a FleetCoordinator stub/mock injected into the server — do not require a live coordinator.
- Test POST /fleet/start: 400 on missing max_iterations; 400 on missing max_cost_usd; 409 on double-start for the same feature; 200 on valid request.
- Test POST /fleet/pause: 409 when fleet phase is `done`.
- Test POST /fleet/abort: 200 + confirm abort method was called on the coordinator stub.
- Test POST /fleet/retry-lane: 400 when lane status is not `failed`.
- Test POST /fleet/resolve-escalation: 400 when no escalation is pending.
- Test that existing /runner/start and /events/runner routes are still registered (route existence check).

SSE event schema for reference (embed this — you will need it in Conv 2):
{"type":"connected"}
{"type":"FLEET_STATUS","feature":str,"phase":"foundation|fleet|merging|done|escalated"}
{"type":"LANE_STARTED","feature":str,"lane":str,"branch":str,"worktree":str}
{"type":"LANE_STATUS","feature":str,"lane":str,"status":"running|done|failed|aborted"}
{"type":"MERGE_PROGRESS","feature":str,"branch":str,"result":"clean|conflict|test_pass|test_fail"}
{"type":"CONFLICT_ESCALATION","feature":str,"branch":str,"file":str,"kind":"textual|semantic|test"}
{"type":"WORKTREE","feature":str,"lane":str,"action":"created|removed|orphan_pruned"}

Architectural rules:
- Thin endpoints — mutate FleetState or call coordinator, then return immediately. Never block a request thread.
- Do NOT call /runner/* via HTTP self-calls. Fan out via the Python supervisor registry directly.
- Do NOT add _broadcast_fleet, /events/fleet, or any Studio files yet.

Do NOT touch: fleet_coord.py (beyond importing FleetCoordinator), anything under studio/, supervisor.py core logic, or any SSE machinery.
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/parallel-fleet-part-2/PROGRESS.md phases 0–2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Seven `/fleet/*` routes in `http_server.py`; a test file with failure-case + regression coverage; all existing tests still pass.
**Files touched:** `src/pathly_orchestrator/http_server.py`, `tests/test_fleet_endpoints.py`

---

## Conversation 2: `/events/fleet` SSE + crash reconciliation (Phases 3–6)

**Stories delivered:** S2

**Prompt to paste:**
```
Read pathly/plans/parallel-fleet-part-2/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Parallel Fleet Part 2 Conversation 2 (Phases 3–6) from pathly/plans/parallel-fleet-part-2/IMPLEMENTATION_PLAN.md. Conversation 1 (the /fleet/* control endpoints) is complete.

Before editing anything: glob/read the live repo to confirm every file path listed below exists. Correct any discrepancy before proceeding.
Re-read http_server.py — study _broadcast_sse, _broadcast_runner, and the /events/runner and /events/menu handlers to understand the per-client queue.Queue + lock-guarded registry + keepalive pattern you are cloning.
Re-read fleet_coord.py to understand where phase transitions and lane events occur — those are the call-site locations for _broadcast_fleet.

Codebase files this conversation touches:
- `src/pathly_orchestrator/http_server.py` — add _broadcast_fleet + GET /events/fleet handler
- `src/pathly_orchestrator/fleet_coord.py` — add _broadcast_fleet call sites + reconciliation pass
- `tests/test_fleet_sse.py` (NEW) — SSE + reconciliation tests

Phase 3 (_broadcast_fleet + SSE handler in http_server.py):
- Add `_fleet_sse_clients: dict[str, list[queue.Queue]]` and `_fleet_sse_lock: threading.Lock` at module level. These are SEPARATE from the runner and menu SSE registries — do not share them.
- `_broadcast_fleet(feature, payload)`: acquire _fleet_sse_lock; iterate _fleet_sse_clients.get(feature, []); put json.dumps(payload) into each queue. Mirror _broadcast_runner exactly.
- `GET /events/fleet?feature=`: clone the /events/runner handler. Register a new queue.Queue in _fleet_sse_clients[feature] on connect; send {"type":"connected"} immediately; enter the generator loop (dequeue with 20s timeout, send keepalive comment on timeout); deregister on GeneratorExit. Content-Type: text/event-stream, Cache-Control: no-cache, CORS headers.
- Do NOT modify /events/runner, /events/menu, or /events/stream.

Phase 4 (broadcast call sites in fleet_coord.py):
- Inject _broadcast_fleet via deferred import or callback (check how supervisor.py calls _broadcast_runner — use the same pattern to avoid circular imports).
- Add call sites:
  - Fleet phase transition → {"type":"FLEET_STATUS","feature":f,"phase":p}
  - Lane thread starts → {"type":"LANE_STARTED","feature":f,"lane":l,"branch":b,"worktree":w}
  - Lane status change (done/failed/aborted) → {"type":"LANE_STATUS","feature":f,"lane":l,"status":s}
  - Merge attempt result → {"type":"MERGE_PROGRESS","feature":f,"branch":b,"result":r}
  - Conflict detected → {"type":"CONFLICT_ESCALATION","feature":f,"branch":b,"file":file,"kind":k}
  - Worktree created/removed/pruned → {"type":"WORKTREE","feature":f,"lane":l,"action":a}
- Do NOT modify phase loop logic, merge logic, or lane orchestration. Call sites only.

Phase 5 (reconciliation pass in fleet_coord.py):
- On FleetCoordinator.__init__ (or a reconcile() method called at server start): load all pathly/plans/*/FLEET_STATE.json files.
- For each fleet with phase "fleet" or "merging": set phase = "escalated", append escalation {"reason":"server_restart","phase_at_crash":<original>}, write FLEET_STATE.json back.
- Run `git worktree list --porcelain`; parse worktree paths. For any path under the feature's worktree root whose branch is NOT in FleetState.lanes[].branch: run `git worktree remove --force <path>` and emit WORKTREE{action:"orphan_pruned"}. Catch subprocess errors and log — do not crash.
- Missing/malformed FLEET_STATE.json: log warning, skip — do not crash.

Phase 6 (tests):
- Test _broadcast_fleet: register a mock queue; call _broadcast_fleet; assert the queue received the correct JSON.
- Test SSE client disconnect: register a queue, deregister it, call _broadcast_fleet; assert no error and the deregistered queue receives nothing.
- Test reconciliation: write a synthetic FLEET_STATE.json with phase "fleet" to a tmp directory; run reconcile(); assert phase is now "escalated".

Do NOT touch: the /runner/* or /events/runner handlers, supervisor.py, adapters.py, or anything under studio/.
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/parallel-fleet-part-2/PROGRESS.md phases 3–6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `_broadcast_fleet` + `GET /events/fleet` in `http_server.py`; broadcast call sites in `fleet_coord.py`; reconciliation pass that marks stale fleets `escalated` and prunes orphans; three new test cases passing.
**Files touched:** `src/pathly_orchestrator/http_server.py`, `src/pathly_orchestrator/fleet_coord.py`, `tests/test_fleet_sse.py`

---

## After Conversation 2 — verification gate before Studio

Before starting Conv 3, confirm the full Python surface is working:
```bash
curl -s http://127.0.0.1:8765/fleet/status?feature=test   # expect 404 or JSON
curl -N http://127.0.0.1:8765/events/fleet?feature=test   # expect text/event-stream + {"type":"connected"}
```
If either fails, resolve before starting Conv 3.

---

## Conversation 3: Studio HQ Fleet Dashboard (Phases 7–10)

**Stories delivered:** S3

**Prompt to paste:**
```
Read pathly/plans/parallel-fleet-part-2/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Parallel Fleet Part 2 Conversation 3 (Phases 7–10) from pathly/plans/parallel-fleet-part-2/IMPLEMENTATION_PLAN.md. Conversations 1–2 are complete — /fleet/* endpoints and /events/fleet SSE are live on port 8765.

Before editing anything: glob/read the live repo to confirm every file path listed below exists. Correct any discrepancy before proceeding.
Read studio/CLAUDE.md — Studio UI rules are non-negotiable and apply to every file you touch:
  - NO inline styles. CSS Modules only. All colors from tokens.css custom properties.
  - One component per folder with a paired *.module.css. ~150-line component limit; extract sub-components if needed.
  - Every <button> must carry type="button".
  - ARIA on all interactive elements: aria-label on icon-only buttons, aria-live="polite" on streaming content, aria-disabled mirrors disabled prop, aria-hidden="true" on decorative chips.
  - Disabled state: opacity: 0.45 + cursor: not-allowed — never same visual as enabled.
Read studio/src/renderer/src/components/HQ/useHQ.ts to mirror the EventSource lifecycle pattern exactly (open on mount, close on cleanup, 3s flat reconnect, event dispatch to store).
Read studio/src/renderer/src/store/runnerStore.ts to mirror the Zustand store pattern for fleetStore.

Codebase files this conversation touches:
- `studio/src/renderer/src/store/fleetStore.ts` (NEW)
- `studio/src/renderer/src/store/index.ts` — add fleetStore
- `studio/src/renderer/src/components/HQ/FleetDashboard/FleetDashboard.tsx` (NEW)
- `studio/src/renderer/src/components/HQ/FleetDashboard/FleetDashboard.module.css` (NEW)
- `studio/src/renderer/src/components/HQ/FleetDashboard/LaneRow.tsx` (NEW)
- `studio/src/renderer/src/components/HQ/FleetDashboard/LaneRow.module.css` (NEW)
- `studio/src/renderer/src/components/HQ/FleetDashboard/EscalationBanner.tsx` (NEW)
- `studio/src/renderer/src/components/HQ/FleetDashboard/EscalationBanner.module.css` (NEW)
- `studio/src/renderer/src/components/HQ/FleetDashboard/FleetControlBar.tsx` (NEW)
- `studio/src/renderer/src/components/HQ/FleetDashboard/FleetControlBar.module.css` (NEW)

Phase 7 (pre-flight + fleetStore):
- Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`. Record baseline — do NOT fix pre-existing errors.
- Confirm `GET http://127.0.0.1:8765/events/fleet?feature=test` returns Content-Type: text/event-stream. If not, STOP and report.
- Confirm `studio/src/renderer/src/components/HQ/` exists (hq-panel shipped). If absent, STOP.
- Create fleetStore.ts:
  ```ts
  type FleetPhase = 'planning'|'foundation'|'fleet'|'merging'|'done'|'escalated'|null
  type LaneStatus = 'running'|'done'|'failed'|'aborted'
  interface LaneState { lane: string; branch: string; worktree: string; status: LaneStatus }
  interface MergeResult { branch: string; result: 'clean'|'conflict'|'test_pass'|'test_fail' }
  interface Escalation { branch: string; file: string; kind: 'textual'|'semantic'|'test' }
  interface FleetStoreState {
    phase: FleetPhase; lanes: LaneState[]; mergeResults: MergeResult[];
    escalations: Escalation[]; errorMessage: string | null
  }
  ```
  Actions: setFleetState, resetFleet, upsertLane, upsertMergeResult, addEscalation, clearEscalations.
- Add fleetStore to store/index.ts.

Phase 8 (FleetDashboard + useFleetDashboard):
- Create useFleetDashboard(feature: string) hook that mirrors useHQ.ts:
  - Open EventSource(`http://127.0.0.1:8765/events/fleet?feature=${feature}`) in useEffect([feature]). Close on cleanup.
  - FLEET_STATUS → setFleetState({ phase })
  - LANE_STARTED → upsertLane({ lane, branch, worktree, status: 'running' })
  - LANE_STATUS → upsertLane with updated status (merge with existing lane data)
  - MERGE_PROGRESS → upsertMergeResult({ branch, result })
  - CONFLICT_ESCALATION → addEscalation({ branch, file, kind })
  - WORKTREE{action:"orphan_pruned"} → console.log only
  - onerror: setFleetState({ errorMessage: 'Reconnecting…' }) + 3s setTimeout retry (cancel on cleanup)
- Create FleetDashboard component (accepts feature: string prop):
  - Calls useFleetDashboard(feature).
  - Renders: fleet phase label, FleetControlBar, EscalationBanner (when escalations.length > 0), lane rows mapped to LaneRow, merge result list.
  - Error state: role="alert" message when errorMessage is non-null.
  - Empty lanes: renders a placeholder (not a crash).

Phase 9 (LaneRow, EscalationBanner, FleetControlBar):
LaneRow (props: lane: LaneState, feature: string, onDrillIn?: (topic: string) => void):
  - Renders lane name, branch, status badge. Status colors: running=var(--accent), done=var(--green), failed=var(--red, or fallback token), aborted=var(--text-muted).
  - "View lane" button type="button" aria-label="View lane <lane.lane>" — calls onDrillIn(`${feature}__${lane.lane}`) on click.

EscalationBanner (reads fleetStore):
  - Renders when escalations.length > 0. Shows latest escalation: branch, file, kind.
  - role="alert" on container.
  - "Resolve" button type="button" aria-label="Resolve escalation" — POSTs {feature, branch, file} to http://127.0.0.1:8765/fleet/resolve-escalation. On 200: clearEscalations(). On non-2xx: setFleetState({ errorMessage }).
  - Clears itself when phase transitions to "done" (derive from store).

FleetControlBar (reads phase + errorMessage from fleetStore; accepts feature: string prop):
  - Renders Start, Pause, Resume, Abort — each type="button" with aria-label.
  - Disabled logic:
    - Start: disabled when phase is not null and not "done" and not "escalated"
    - Pause: disabled when phase !== "fleet" && phase !== "merging"
    - Resume: disabled when phase !== "escalated" && phase !== "paused"
    - Abort: disabled when phase is null || phase === "done"
  - Disabled style: opacity: 0.45; cursor: not-allowed via CSS Module class.
  - Each button POSTs {feature} to http://127.0.0.1:8765/fleet/<action>. On non-2xx: setFleetState({ errorMessage }).

Phase 10 (launch verification):
- Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` — must exit 0.
- Launch Studio. Navigate to the HQ panel. Confirm FleetDashboard renders with phase label, empty lane list, and FleetControlBar buttons visible.

SSE event schema (exact — your EventSource handlers must dispatch exactly these shapes):
{"type":"connected"}
{"type":"FLEET_STATUS","feature":str,"phase":"foundation|fleet|merging|done|escalated"}
{"type":"LANE_STARTED","feature":str,"lane":str,"branch":str,"worktree":str}
{"type":"LANE_STATUS","feature":str,"lane":str,"status":"running|done|failed|aborted"}
{"type":"MERGE_PROGRESS","feature":str,"branch":str,"result":"clean|conflict|test_pass|test_fail"}
{"type":"CONFLICT_ESCALATION","feature":str,"branch":str,"file":str,"kind":"textual|semantic|test"}
{"type":"WORKTREE","feature":str,"lane":str,"action":"created|removed|orphan_pruned"}

Do NOT touch: any Python files, runnerStore.ts, useHQ.ts, or any existing HQ component.
Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
Then launch Studio and confirm FleetDashboard renders.
After done, update pathly/plans/parallel-fleet-part-2/PROGRESS.md phases 7–10 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `fleetStore.ts` + `store/index.ts` updated; `FleetDashboard/` with five components (FleetDashboard, LaneRow, EscalationBanner, FleetControlBar — each with paired CSS Module); `useFleetDashboard` hook dispatching all seven SSE event types; typecheck exits 0; Studio launches with the dashboard visible.
**Files touched:** `studio/src/renderer/src/store/fleetStore.ts`, `studio/src/renderer/src/store/index.ts`, `studio/src/renderer/src/components/HQ/FleetDashboard/` (10 files)
