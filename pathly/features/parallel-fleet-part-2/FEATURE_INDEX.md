---
name: Feature Index
---
# Parallel Fleet Part 2 — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What this feature does

Delivers the **control and observability surface** for the parallel multi-agent fleet introduced in `parallel-fleet-part-1`. Three pieces:

1. A `/fleet/*` control API in `http_server.py` — seven thin endpoints (start, status, pause, resume, abort, retry-lane, resolve-escalation) wired to `fleet_coord.py`, mirroring the existing `/runner/*` pattern.
2. A `GET /events/fleet` SSE stream with `_broadcast_fleet` — a twin of `_broadcast_sse`/`_broadcast_runner`, emitting fleet-level and per-lane events via the exact schema below.
3. A Studio **HQ Fleet Dashboard** — a new panel under the HQ component tree that subscribes to `/events/fleet`, renders per-lane status and merge progress, surfaces conflict escalations, and posts controls to `/fleet/*`. Drill-in to an individual lane reuses the existing `/events/runner?topic=<feature>__<lane>` view.

This is **part 2 of 2**. `parallel-fleet-part-1` owns the fleet coordinator and worktree lifecycle. This feature owns the HTTP surface and Studio UI only.

---

## Dependencies — hard gates

| Upstream feature | What it provides | Must ship before |
|---|---|---|
| `parallel-fleet-part-1` | `fleet_coord.py` with `FleetCoordinator` + `FleetState` (fields: `fleet_id`, `feature`, `phase ∈ {planning,foundation,fleet,merging,done,escalated}`, `lanes[]`, `merge_order`, `integration_branch`, `escalations`) + `FLEET_STATE.json` mirror + the phase loop daemon thread. Hard CI gate (toy-repo end-to-end with clean worktree teardown) must be green. | Conv 1 Phase 0 |
| `hq-panel` | Studio HQ panel + `runnerStore` + `EventSource` pattern from `/events/runner`; the per-lane runner view at `/events/runner?topic=<feature>__<lane>` is already wired. | Conv 3 Phase 0 |
| `multi-adapter-runner` (transitive) | HTTP server on port 8765 with SSE machinery (`_broadcast_sse`, per-client `queue.Queue`, lock-guarded registry, keepalive) + `/runner/*` + `/events/runner`. | Conv 1 Phase 0 |

> **Builder:** Phase 0 of every conversation confirms these dependencies exist before touching any file. If any gate is missing, stop and report.

---

## /events/fleet SSE event schema — exact fields (embed in every prompt)

```
{"type":"connected"}
{"type":"FLEET_STATUS","feature":str,"phase":"foundation|fleet|merging|done|escalated"}
{"type":"LANE_STARTED","feature":str,"lane":str,"branch":str,"worktree":str}
{"type":"LANE_STATUS","feature":str,"lane":str,"status":"running|done|failed|aborted"}
{"type":"MERGE_PROGRESS","feature":str,"branch":str,"result":"clean|conflict|test_pass|test_fail"}
{"type":"CONFLICT_ESCALATION","feature":str,"branch":str,"file":str,"kind":"textual|semantic|test"}
{"type":"WORKTREE","feature":str,"lane":str,"action":"created|removed|orphan_pruned"}
```

All payloads are JSON. The `"connected"` frame is sent immediately on client connect (same pattern as `/events/menu`).

---

## Architecture guardrails (locked — do not deviate)

- `/fleet/*` and `/events/fleet` are a **twin** of `/runner/*` and `/events/runner`. They share the SSE infrastructure but have **separate** broadcast functions and **separate** client registries. A topic must never mean both a runner topic and a fleet feature — use distinct namespaces.
- The FSM and supervisor are **untouched** by this feature.
- `fleet_coord.py` gains **only** a restart-reconciliation pass (Phase 5) and `_broadcast_fleet` call sites. The phase loop and merge logic are owned by `parallel-fleet-part-1`.
- HQ drills into a single lane via the **existing** `/events/runner?topic=<feature>__<lane>` — no changes to that endpoint.
- Studio UI rules apply to all new components: CSS Modules only, theme tokens, `type="button"`, ARIA, ~150-line component limit.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (all present)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Fleet control API design, SSE twin pattern, reconciliation approach |
| `EDGE_CASES.md` | yes | Crash/orphan recovery, 409, lane failures, SSE disconnect |
| `HAPPY_FLOW.md` | yes | Golden-path: start a fleet, watch lanes converge, resolve a conflict |
| `FLOW_DIAGRAM.md` | yes | HTTP control → fleet_coord → SSE → Studio dashboard |

---

## Codebase touchpoints

**Verify each path exists before editing (glob it).**

| Codebase file | Conv | What changes |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | 1, 2 | Conv 1: 7 `/fleet/*` endpoints. Conv 2: `_broadcast_fleet` + `GET /events/fleet` SSE handler. |
| `src/pathly_orchestrator/fleet_coord.py` | 2 | Add `_broadcast_fleet` call sites at phase transitions and lane events; add restart-reconciliation pass. |
| `tests/` | 1, 2 | Conv 1: fleet control endpoint tests. Conv 2: SSE emission test + reconciliation test. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/FleetDashboard.tsx` (NEW) | 3 | Fleet-level overview panel: lane rows, merge progress, escalation affordance. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/FleetDashboard.module.css` (NEW) | 3 | Paired CSS Module. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/LaneRow.tsx` (NEW) | 3 | Per-lane status row with drill-in trigger. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/LaneRow.module.css` (NEW) | 3 | Paired CSS Module. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/EscalationBanner.tsx` (NEW) | 3 | "Needs you" banner for CONFLICT_ESCALATION events; posts to `/fleet/resolve-escalation`. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/EscalationBanner.module.css` (NEW) | 3 | Paired CSS Module. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/FleetControlBar.tsx` (NEW) | 3 | Start/Pause/Resume/Abort buttons posting to `/fleet/*`. |
| `studio/src/renderer/src/components/HQ/FleetDashboard/FleetControlBar.module.css` (NEW) | 3 | Paired CSS Module. |
| `studio/src/renderer/src/store/fleetStore.ts` (NEW) | 3 | Zustand store for fleet state; EventSource lifecycle in `useFleetDashboard.ts`. |
| `studio/src/renderer/src/store/index.ts` | 3 | Add `fleetStore` to root merge. |

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | `/fleet/*` control endpoints | S1 | TODO | `http_server.py`, `tests/` |
| 2 | `/events/fleet` SSE + reconciliation | S2 | TODO | `http_server.py`, `fleet_coord.py`, `tests/` |
| 3 | Studio HQ Fleet Dashboard | S3 | TODO | `HQ/FleetDashboard/`, `fleetStore.ts`, `store/index.ts` |

**Dependency:** `1 → 2 → 3` (strict). After Conv 2 confirm with `curl -N http://127.0.0.1:8765/events/fleet?feature=test` before starting Conv 3.

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/parallel-fleet-part-2/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
