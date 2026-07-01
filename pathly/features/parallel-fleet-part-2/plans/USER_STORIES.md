---
name: User Stories
---
# Parallel Fleet Part 2 — User Stories

## Context

When the parallel fleet coordinator (`parallel-fleet-part-1`) launches multiple worktree lanes in parallel, the user currently has no way to observe progress, intervene in conflicts, or control the fleet lifecycle from outside the terminal. This feature closes that gap by delivering a `/fleet/*` HTTP control surface, a `/events/fleet` SSE stream, and a Studio HQ Fleet Dashboard that puts all lane activity — running, merging, escalating — in one observable, actionable view.

The feature targets developers running a Pathly fleet from Studio. They need to know which lanes are running, whether a merge is clean or conflicted, and when human intervention is required — and they need the controls (pause, resume, abort, retry-lane, resolve-escalation) to act on what they see.

---

## Stories

### Story S1: Fleet Control API
**As a** developer running a parallel fleet, **I want** HTTP endpoints to start, inspect, pause, resume, abort, retry, and resolve escalations on a fleet, **so that** I can drive the fleet programmatically and from the Studio UI without terminal interaction.

**Acceptance Criteria:**
- [ ] `POST /fleet/start` with `{feature, fleet_yaml|fleet_plan_path, base_branch, max_iterations, max_cost_usd, autonomy}` returns `{"fleet_id": <str>}` and 200.
- [ ] `POST /fleet/start` for a feature that already has an active fleet returns 409 with a descriptive error body.
- [ ] `POST /fleet/start` missing `max_iterations` or `max_cost_usd` returns 400.
- [ ] `GET /fleet/status?feature=<feature>` returns a `FleetState` snapshot as JSON (all fields: `fleet_id`, `feature`, `phase`, `lanes`, `merge_order`, `integration_branch`, `escalations`).
- [ ] `POST /fleet/pause` fans out to each active lane's `/runner/pause` and returns 200.
- [ ] `POST /fleet/resume` fans out to each active lane's `/runner/resume` and returns 200.
- [ ] `POST /fleet/abort` aborts all active lanes and marks worktrees for teardown; returns 200.
- [ ] `POST /fleet/retry-lane` with `{feature, lane}` recreates the failed lane's worktree and restarts it; returns 200.
- [ ] `POST /fleet/resolve-escalation` with `{feature, ...}` unblocks the coordinator and resumes the merge phase; returns 200.
- [ ] All seven endpoints are thin — they mutate `FleetState` and return immediately; the phase loop continues on its own daemon thread.
- [ ] All existing `/runner/*` and `/events/*` endpoints are unchanged and pass their existing tests.

**Edge Cases:**
- `/fleet/pause` or `/fleet/resume` on a fleet that is not in `running`/`paused` phase returns 409.
- `/fleet/retry-lane` for a lane that is not in `failed` status returns 400.
- `/fleet/resolve-escalation` when no escalation is pending returns 400.
- Unknown `feature` in any endpoint returns 404.

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Fleet SSE Stream and Crash Reconciliation
**As a** developer (or Studio client), **I want** a live event stream for fleet activity and a guarantee that server restarts leave no orphan worktrees or stale "running" state, **so that** my dashboard reflects reality even after unexpected failures.

**Acceptance Criteria:**
- [ ] `GET /events/fleet?feature=<feature>` returns `Content-Type: text/event-stream` with an immediate `{"type":"connected"}` frame.
- [ ] Every fleet phase transition emits a `FLEET_STATUS` event with the exact schema from FEATURE_INDEX.md.
- [ ] Every lane start emits `LANE_STARTED`; every lane status change emits `LANE_STATUS` — both with the exact schema.
- [ ] Every merge attempt emits `MERGE_PROGRESS`; every conflict emits `CONFLICT_ESCALATION` — both with the exact schema.
- [ ] Every worktree lifecycle event emits `WORKTREE` — exact schema.
- [ ] `_broadcast_fleet(feature, payload)` is a distinct function from `_broadcast_sse` and `_broadcast_runner`; it uses its own per-client `queue.Queue` registry under its own `threading.Lock`.
- [ ] SSE client disconnect deregisters the client's queue (no leak); confirmed by the existing `/events/menu` pattern test analogy.
- [ ] On coordinator or server restart, a reconciliation pass runs `git worktree list`, cross-references against `FLEET_STATE.json`, marks any fleet with `phase` still `"fleet"` or `"merging"` as `"escalated"`, and prunes orphan worktrees (`git worktree remove --force`).
- [ ] After a simulated crash mid-fleet, `GET /fleet/status?feature=<feature>` reports `"escalated"` (not `"running"` or `"fleet"`).
- [ ] After reconciliation, `git worktree list` contains no worktrees whose path prefix matches the feature's worktree directory but whose branch is not in the `lanes` list.

**Edge Cases:**
- Two concurrent SSE clients for the same feature both receive all events (registry supports multiple subscribers per feature).
- `FLEET_STATE.json` missing or malformed on startup — reconciliation logs a warning and continues; no crash.
- Worktree directory already removed before reconciliation prune — `git worktree remove` failure is caught and logged; no crash.

**Delivered by:** Phases 2–5 → Conversation 2

---

### Story S3: Studio HQ Fleet Dashboard
**As a** developer watching a parallel fleet from Studio, **I want** a dashboard panel that shows all lane statuses, merge progress, and conflict escalations in real time, with controls to pause/resume/abort the fleet and resolve escalations, **so that** I never need to switch to a terminal to manage a running fleet.

**Acceptance Criteria:**
- [ ] A `FleetDashboard` component renders inside the Studio HQ panel, subscribing to `GET /events/fleet?feature=<feature>`.
- [ ] Each lane in `fleetStore.lanes` is rendered as a `LaneRow` showing: lane name, branch, current status (`running`/`done`/`failed`/`aborted`), and a "View lane" drill-in button that opens the existing runner view for that lane.
- [ ] `FLEET_STATUS` events update the fleet phase indicator in real time.
- [ ] `LANE_STATUS` events update the matching `LaneRow` status in real time.
- [ ] `MERGE_PROGRESS` events render a merge result indicator per branch (clean / conflict / test_pass / test_fail).
- [ ] When a `CONFLICT_ESCALATION` event arrives, an `EscalationBanner` renders with `role="alert"`, displaying the branch, file, and conflict kind, with a "Resolve" button that posts to `/fleet/resolve-escalation`.
- [ ] `FleetControlBar` renders Start, Pause, Resume, and Abort buttons wired to the matching `/fleet/*` endpoints; disabled state follows fleet phase (Start disabled when fleet is active; Pause disabled when not running; Resume disabled when not paused; Abort always enabled when a fleet is active).
- [ ] `fleetStore` is a Zustand store with fields: `phase`, `lanes` (array of `{lane, branch, status}`), `mergeResults` (map of branch → result), `escalations` (array), `errorMessage`.
- [ ] SSE EventSource mirrors the `/events/runner` pattern in `useHQ.ts` — open on mount, close on unmount, 3-second flat reconnect on error.
- [ ] `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0.
- [ ] All new components use CSS Modules only (no inline styles), theme tokens, `type="button"`, and ARIA labels.
- [ ] No component file exceeds ~150 lines; sub-components extracted as needed.

**Edge Cases:**
- Backend not reachable on component mount — SSE `onerror` sets `fleetStore.errorMessage`; an error state renders instead of an empty lane list; no crash.
- `CONFLICT_ESCALATION` arrives when `EscalationBanner` is already visible — banner updates in place (feature + branch + file from the latest event).
- Fleet phase transitions to `"done"` while a `CONFLICT_ESCALATION` is displayed — banner is cleared.
- Empty lane list (fleet just started, no `LANE_STARTED` events yet) — renders a loading or empty state, not a crash.

**Delivered by:** Phases 6–9 → Conversation 3
