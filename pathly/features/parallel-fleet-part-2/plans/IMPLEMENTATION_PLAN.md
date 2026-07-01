---
name: Implementation Plan
---
# Parallel Fleet Part 2 — Implementation Plan

## Overview

Add a `/fleet/*` control API and `/events/fleet` SSE stream to the existing Pathly HTTP server (port 8765), then wire a Studio HQ Fleet Dashboard that consumes them. The Python backend is three conversations: thin control endpoints (Conv 1), the SSE twin + crash reconciliation (Conv 2), and the Studio dashboard (Conv 3). The FSM, supervisor, and fleet coordinator phase loop are untouched — this plan owns only the HTTP surface and Studio UI.

## Layer Architecture

```
fleet_coord.py (part-1)        ──call sites──►  _broadcast_fleet(feature, payload)
  FleetState + phase loop                              │  queue.Queue per client
         │ mutated by                                  ▼
http_server.py                           GET /events/fleet?feature=
  /fleet/* thin endpoints                              │
         │ reads/writes FleetState                     ▼ (SSE)
         ▼                               Studio fleetStore (Zustand)
  FleetCoordinator registry                    │ useFleetDashboard.ts
                                               ▼
                                       HQ/FleetDashboard/ components
                                          FleetControlBar → POST /fleet/*
                                          LaneRow → drill-in /events/runner?topic=
                                          EscalationBanner → POST /fleet/resolve-escalation
```

**Dependency direction:** Dashboard → control API → FleetCoordinator → FSM/supervisor (one-way). `fleet_coord.py` imports nothing from the HTTP layer beyond the broadcast hook.

---

## Architectural Rules (apply in every phase)

- **Twin pattern**: `/fleet/*` and `/events/fleet` are built exactly like `/runner/*` and `/events/runner`. Clone the route-decorator pattern, CORS handling, and SSE machinery. Do not modify the runner or menu SSE registries.
- **Thin endpoints**: every `/fleet/*` handler mutates `FleetState` (or calls a `FleetCoordinator` method) and returns immediately. Never block a request thread.
- **Separate broadcast**: `_broadcast_fleet` uses its own `threading.Lock`-guarded dict of `queue.Queue` objects, independent of `_broadcast_sse` and `_broadcast_runner`.
- **Studio rules** (Conv 3 only): CSS Modules only, theme tokens, `type="button"`, ARIA, ~150-line component limit.

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1
**File:** none (verification only)
**Done when:** baseline green, all upstream dependencies confirmed present.
**Depends on:** `parallel-fleet-part-1` CI gate green; `multi-adapter-runner` Conv 3 shipped.
**Enables:** Phase 1 (safe to edit `http_server.py`).
**Details:**
- Run `python -m pytest tests/ -q`. Record any pre-existing failures as baseline — do NOT fix them.
- Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`. Record baseline typecheck errors — do NOT fix them.
- Confirm `fleet_coord.py` exists: `glob src/pathly_orchestrator/fleet_coord.py`. If absent, STOP — `parallel-fleet-part-1` has not shipped.
- Confirm `FleetState` is importable: `python -c "from pathly_orchestrator.fleet_coord import FleetState; print('ok')"`. If it fails, STOP.
- Confirm `FleetState` fields: `fleet_id`, `feature`, `phase`, `lanes`, `merge_order`, `integration_branch`, `escalations`. If any field is missing, write `OPEN: FleetState schema mismatch` in `pathly/plans/parallel-fleet-part-2/feedback/HUMAN_QUESTIONS.md` and STOP.
- Confirm `http_server.py` has `_broadcast_sse` and `/events/runner` (grep) — the SSE twin pattern depends on this code existing to clone.
- Confirm `http://127.0.0.1:8765/runner/status` returns any HTTP response (a 405 counts).
**Verify:** `python -m pytest tests/ -q`

---

### Phase 1: `/fleet/*` control endpoints   ← Conversation: 1
**File:** `src/pathly_orchestrator/http_server.py` — MODIFY
**Done when:** all seven `/fleet/*` routes exist, are thin, return the correct status codes, and existing endpoints remain unchanged.
**Delivers stories:** S1
**Depends on:** Phase 0
**Enables:** Phase 2 (SSE broadcasts needed by the endpoints' call sites)
**Details:**
- Follow the existing route-decorator + CORS/OPTIONS pattern from the `/runner/*` routes.
- `POST /fleet/start`: parse `{feature, fleet_yaml|fleet_plan_path, base_branch, max_iterations, max_cost_usd, autonomy}`. Return 400 if `max_iterations` or `max_cost_usd` absent. Return 409 if a fleet for that feature is already active in the `FleetCoordinator` registry. Otherwise call `FleetCoordinator.start(...)` and return `{"fleet_id": <str>}` with 200.
- `GET /fleet/status?feature=`: look up the `FleetState` for that feature; return 404 if not found; otherwise serialize all `FleetState` fields as JSON.
- `POST /fleet/pause`: for each active lane in `FleetState.lanes`, call the existing `/runner/pause` (via the supervisor registry — do NOT make HTTP self-calls; call the Python API directly). Return 200. Return 409 if phase is not `fleet` or `merging`.
- `POST /fleet/resume`: mirror of pause. Return 409 if phase is not `paused`.
- `POST /fleet/abort`: call `FleetCoordinator.abort(feature)` which aborts all lanes and marks worktrees for teardown. Return 200.
- `POST /fleet/retry-lane`: parse `{feature, lane}`. Return 400 if lane status is not `failed`. Call `FleetCoordinator.retry_lane(feature, lane)`. Return 200.
- `POST /fleet/resolve-escalation`: parse `{feature, ...resolution fields}`. Return 400 if no escalation is pending for that feature. Call `FleetCoordinator.resolve_escalation(feature, resolution)`. Return 200.
- All seven handlers: return 404 for unknown feature.
**Verify:** `python -m pytest tests/ -q`

---

### Phase 2: Tests for `/fleet/*` endpoints   ← Conversation: 1
**File:** `tests/` — ADD test file (e.g., `tests/test_fleet_endpoints.py`)
**Done when:** tests cover all required failure paths and at least one success path per endpoint; all pass.
**Delivers stories:** S1 (failure-case ACs)
**Depends on:** Phase 1
**Details:**
- Test `POST /fleet/start`: 400 on missing caps; 409 on double-start for the same feature.
- Test `POST /fleet/pause`: 409 when fleet phase is `done`.
- Test `POST /fleet/abort`: 200 + lane abort fan-out (mock supervisor registry).
- Test `POST /fleet/retry-lane`: 400 when lane status is not `failed`.
- Test `POST /fleet/resolve-escalation`: 400 when no escalation pending.
- Test that existing `/runner/start` and `/events/runner` routes are still registered (route existence check — no behavior regression).
- Use a `FleetCoordinator` stub/mock that is injected into the server rather than requiring a live coordinator.
**Verify:** `python -m pytest tests/ -q`

---

### Phase 3: `_broadcast_fleet` + per-client SSE registry   ← Conversation: 2
**File:** `src/pathly_orchestrator/http_server.py` — MODIFY
**Done when:** `_broadcast_fleet(feature, payload)` exists with its own lock-guarded `queue.Queue` registry; `GET /events/fleet?feature=` streams events with correct Content-Type and keepalive.
**Delivers stories:** S2
**Depends on:** Phase 2 (Conv 1 complete)
**Enables:** Phase 4 (fleet_coord.py can call broadcast)
**Details:**
- Add `_fleet_sse_clients: dict[str, list[queue.Queue]]` and `_fleet_sse_lock: threading.Lock` at module level (separate from the runner registry).
- `_broadcast_fleet(feature, payload)`: acquire `_fleet_sse_lock`; iterate `_fleet_sse_clients.get(feature, [])`; put `json.dumps(payload)` into each queue. Mirror `_broadcast_runner` exactly.
- `GET /events/fleet?feature=`: clone the `/events/runner` handler. On connect: register a new `queue.Queue` in `_fleet_sse_clients[feature]` under the lock; send `data: {"type":"connected"}\n\n`; enter the generator loop (dequeue with 20s timeout, send keepalive comment on timeout); on GeneratorExit: deregister the queue under the lock. `Content-Type: text/event-stream`, `Cache-Control: no-cache`, CORS headers.
- Emit SSE events in the exact schema from FEATURE_INDEX.md (all seven types).
**Verify:** `python -m pytest tests/ -q`

---

### Phase 4: `fleet_coord.py` broadcast call sites   ← Conversation: 2
**File:** `src/pathly_orchestrator/fleet_coord.py` — MODIFY
**Done when:** `_broadcast_fleet` is called at every fleet phase transition and lane event; no other logic in `fleet_coord.py` changes.
**Delivers stories:** S2
**Depends on:** Phase 3
**Enables:** Phase 5 (reconciliation pass)
**Details:**
- Import `_broadcast_fleet` from `http_server` — use a deferred/lazy import or a callback injection to avoid circular imports (check existing pattern in supervisor.py → http_server first).
- Add call sites at:
  - Fleet phase transitions → `FLEET_STATUS`
  - Lane thread start → `LANE_STARTED`
  - Lane status change (done/failed/aborted) → `LANE_STATUS`
  - Merge attempt start/result → `MERGE_PROGRESS`
  - Conflict detection → `CONFLICT_ESCALATION`
  - Worktree created/removed/pruned → `WORKTREE`
- Each call: `_broadcast_fleet(feature, {"type": "<TYPE>", ...fields per schema})`.
- Do NOT modify the phase loop, merge logic, or lane orchestration — call sites only.
**Verify:** `python -m pytest tests/ -q`

---

### Phase 5: Restart reconciliation pass   ← Conversation: 2
**File:** `src/pathly_orchestrator/fleet_coord.py` — MODIFY
**Done when:** on `FleetCoordinator` init (or server startup hook), a reconciliation pass runs, marks stale-running fleets as `escalated`, and prunes orphan worktrees; after a simulated crash `GET /fleet/status` reports `escalated`.
**Delivers stories:** S2 (reconciliation ACs)
**Depends on:** Phase 4
**Enables:** Conv 2 complete
**Details:**
- On `FleetCoordinator.__init__` (or a `reconcile()` method called at server start): load all `FLEET_STATE.json` files from `pathly/plans/*/FLEET_STATE.json`.
- For each fleet whose `phase` is `"fleet"` or `"merging"`: set `phase = "escalated"`, add an escalation entry `{"reason": "server_restart", "phase_at_crash": <original>}`, write `FLEET_STATE.json`.
- Run `git worktree list --porcelain`; parse worktree paths. For any worktree path whose directory is under the feature's worktree root but whose branch is NOT in `FleetState.lanes[].branch`, run `git worktree remove --force <path>` and emit `WORKTREE{action:"orphan_pruned"}`. Catch errors and log — do not crash.
- Missing or malformed `FLEET_STATE.json`: log warning, skip — do not crash.
**Verify:** `python -m pytest tests/ -q`

---

### Phase 6: Tests for SSE + reconciliation   ← Conversation: 2
**File:** `tests/` — ADD
**Done when:** SSE emission test passes; reconciliation test passes; all existing tests still pass.
**Delivers stories:** S2 (failure-case ACs)
**Depends on:** Phase 5
**Details:**
- SSE test: call `_broadcast_fleet("test-feature", {"type":"FLEET_STATUS","feature":"test-feature","phase":"fleet"})` with a registered mock client queue; assert the mock queue received the correct serialized JSON.
- Reconciliation test: write a synthetic `FLEET_STATE.json` with `phase: "fleet"` to a temp directory; instantiate `FleetCoordinator` (or call `reconcile()`) pointing to that directory; assert `phase` is now `"escalated"`.
- Client disconnect test: register a client queue, then simulate disconnect (deregister); call `_broadcast_fleet`; assert no error and the deregistered queue receives nothing.
**Verify:** `python -m pytest tests/ -q`

---

### Phase 7: Pre-flight (Conv 3) and `fleetStore`   ← Conversation: 3
**File:** `studio/src/renderer/src/store/fleetStore.ts` — CREATE
**Done when:** `fleetStore` is importable; added to `store/index.ts`; typecheck exits 0.
**Delivers stories:** S3
**Depends on:** Conv 2 complete and `GET /events/fleet` reachable on port 8765.
**Enables:** Phase 8 (components read from store)
**Details:**
- Pre-flight: run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` — record baseline. Confirm `GET http://127.0.0.1:8765/events/fleet?feature=test` returns `text/event-stream` (a 200 with correct content-type). If not, STOP and report.
- Confirm `studio/src/renderer/src/components/HQ/` exists (hq-panel shipped). Confirm `runnerStore.ts` exists (hq-panel shipped). If either is absent, STOP.
- Create `fleetStore.ts` using Zustand `create`:
  ```ts
  type FleetPhase = 'planning' | 'foundation' | 'fleet' | 'merging' | 'done' | 'escalated' | null
  type LaneStatus = 'running' | 'done' | 'failed' | 'aborted'

  interface LaneState {
    lane: string
    branch: string
    worktree: string
    status: LaneStatus
  }

  interface MergeResult {
    branch: string
    result: 'clean' | 'conflict' | 'test_pass' | 'test_fail'
  }

  interface Escalation {
    branch: string
    file: string
    kind: 'textual' | 'semantic' | 'test'
  }

  interface FleetState {
    phase: FleetPhase
    lanes: LaneState[]
    mergeResults: MergeResult[]
    escalations: Escalation[]
    errorMessage: string | null
  }
  ```
- Actions: `setFleetState(partial: Partial<FleetState>)`, `resetFleet()`, `upsertLane(lane: LaneState)`, `upsertMergeResult(result: MergeResult)`, `addEscalation(e: Escalation)`, `clearEscalations()`.
- Add `fleetStore` to `studio/src/renderer/src/store/index.ts` root merge.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 8: `FleetDashboard` + `useFleetDashboard`   ← Conversation: 3
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/FleetDashboard.tsx` — CREATE
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/FleetDashboard.module.css` — CREATE
**Done when:** `FleetDashboard` renders the fleet phase, lane list, merge results, and `EscalationBanner`; SSE client opens on mount; typecheck exits 0.
**Delivers stories:** S3
**Depends on:** Phase 7
**Enables:** Phase 9 (sub-components wired)
**Details:**
- Create `useFleetDashboard(feature: string)` hook inside `FleetDashboard.tsx` (or as `useFleetDashboard.ts` alongside):
  - Mirror `useHQ.ts`'s `EventSource` pattern: open `new EventSource(\`http://127.0.0.1:8765/events/fleet?feature=${feature}\`)` in `useEffect([feature])`. Close on cleanup.
  - Dispatch SSE events to `fleetStore`:
    - `FLEET_STATUS` → `setFleetState({ phase })`
    - `LANE_STARTED` → `upsertLane({ lane, branch, worktree, status: 'running' })`
    - `LANE_STATUS` → `upsertLane({ lane, branch: existing, worktree: existing, status })`
    - `MERGE_PROGRESS` → `upsertMergeResult({ branch, result })`
    - `CONFLICT_ESCALATION` → `addEscalation({ branch, file, kind })`
    - `WORKTREE{action:"orphan_pruned"}` → no store change, but log to console
  - `onerror`: `setFleetState({ errorMessage: 'Reconnecting…' })` + 3s flat retry (cancel on cleanup).
- `FleetDashboard` component:
  - Accepts `feature: string` prop.
  - Renders fleet phase label at the top.
  - Renders `<FleetControlBar feature={feature} />` (Phase 9).
  - Renders `<EscalationBanner />` when `escalations.length > 0` (Phase 9).
  - Maps `lanes` to `<LaneRow key={lane.lane} lane={lane} />` (Phase 9).
  - Renders merge result indicators (a simple list: branch + result badge).
  - Error state: when `errorMessage` is non-null, renders a `role="alert"` message instead of the lane list.
  - Empty lanes: renders a loading/empty state (not a crash).
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 9: `LaneRow`, `EscalationBanner`, `FleetControlBar`   ← Conversation: 3
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/LaneRow.tsx` — CREATE
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/LaneRow.module.css` — CREATE
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/EscalationBanner.tsx` — CREATE
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/EscalationBanner.module.css` — CREATE
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/FleetControlBar.tsx` — CREATE
**File:** `studio/src/renderer/src/components/HQ/FleetDashboard/FleetControlBar.module.css` — CREATE
**Done when:** All three sub-components render without errors; disabled states are correct; typecheck exits 0.
**Delivers stories:** S3 (all remaining ACs)
**Depends on:** Phase 8
**Enables:** Feature complete
**Details:**

**LaneRow:**
- Props: `lane: LaneState`.
- Renders lane name, branch, and status badge (color: running=`var(--accent)`, done=`var(--green)`, failed=`var(--red)`, aborted=`var(--text-muted)`).
- "View lane" `<button type="button" aria-label="View lane <lane.lane>">` — on click, triggers navigation to the runner view for `topic=<feature>__<lane.lane>` (emit a custom event or call a passed-in `onDrillIn` callback — keep it simple; the exact navigation mechanism is up to the builder as long as it opens the existing runner SSE view).
- Keep under ~150 lines.

**EscalationBanner:**
- Reads `escalations` from `fleetStore`; renders when `escalations.length > 0`.
- Displays the latest escalation: branch, file, and kind.
- `role="alert"` on the banner container (announced on appearance).
- "Resolve" `<button type="button" aria-label="Resolve escalation">` — on click, POSTs `{ feature, branch: escalation.branch, file: escalation.file }` to `http://127.0.0.1:8765/fleet/resolve-escalation`. On 200: call `clearEscalations()` in `fleetStore`. On non-2xx: set `errorMessage`.
- When `escalations` is empty (including after `phase` transitions to `done`): renders nothing.

**FleetControlBar:**
- Reads `phase` and `errorMessage` from `fleetStore`.
- Renders: Start, Pause, Resume, Abort — each `type="button"`, each with `aria-label`.
- Disabled logic:
  - Start: disabled when phase is not null and not `done` and not `escalated`.
  - Pause: disabled when phase !== `fleet` and phase !== `merging`.
  - Resume: disabled when phase !== `escalated` (post-reconciliation or post-resolve).
  - Abort: disabled when phase is null or `done`.
- Each button POSTs to the matching `/fleet/<action>` with `{ feature }` in the body. On non-2xx: `setFleetState({ errorMessage })`.
- Disabled style: `opacity: 0.45; cursor: not-allowed` via CSS Module class.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 10: Launch verification   ← Conversation: 3
**File:** none (verification step)
**Done when:** typecheck exits 0 and Studio launches with `FleetDashboard` visible and reactive.
**Delivers stories:** S3 (manual verification ACs)
**Depends on:** Phase 9
**Details:**
- Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` — must exit 0.
- Launch Studio. Navigate to the HQ panel. Confirm `FleetDashboard` renders (phase label, empty lane list, `FleetControlBar` buttons).
- If the backend is running, start a fleet and verify lane rows appear as `LANE_STARTED` events arrive.
- If verification fails and the fix is in-scope (a TypeScript error in a file this conversation touched), fix it. If out-of-scope, stop and report.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Prerequisites

- `parallel-fleet-part-1` shipped and CI gate green (`fleet_coord.py`, `FleetState`, `FLEET_STATE.json`, phase loop).
- `hq-panel` shipped (HQ panel + `runnerStore` + `useHQ.ts` SSE pattern + per-lane runner view).
- `multi-adapter-runner` shipped (HTTP server on 8765, `/runner/*`, `_broadcast_runner`, SSE infrastructure).
- `python -m pytest tests/ -q` green at baseline before Conv 1.
- `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` at baseline before Conv 3.

## Key Decisions

- **`/fleet/*` and `/events/fleet` are a strict twin of `/runner/*` and `/events/runner`**, not an extension of runner scope. Lanes and features have separate namespaces to avoid semantic ambiguity.
- **`_broadcast_fleet` has its own registry.** Sharing with `_broadcast_runner` would couple unrelated lifecycle scopes.
- **No self-HTTP calls.** `/fleet/pause` calls the Python supervisor registry directly, not via curl to `/runner/pause`. Avoids latency and circular failure modes.
- **Reconciliation is a startup pass, not a background daemon.** Fleet crashes are rare and detected on next boot; a daemon would add complexity for marginal gain.
- **Studio SSE hook mirrors `useHQ.ts` exactly.** Same 3s flat retry, same `useEffect([feature])` pattern, same cleanup. Deviating from the established pattern creates maintenance burden.
- **`fleetStore` is separate from `runnerStore`.** Fleet-level state (phase, lanes[], escalations) is distinct from runner state (single topic, cost, decision menu). Merging would create an over-broad store.
