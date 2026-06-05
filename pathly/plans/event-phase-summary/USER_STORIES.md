# User Stories — event-phase-summary

## Overview

Delivered by: Conv 1 (backend), Conv 2 (backend), Conv 3 (frontend)

---

## Story 1 — PHASE_SUMMARY event persisted to SQLite

**Who:** The Pathly pipeline supervisor and agent processes  
**What:** Can write a `PHASE_SUMMARY` event to the feature's SQLite `fsm_events` table via the existing `append_event` helper  
**Why:** So mid-phase progress notes are stored durably and can be replayed to reconnecting SSE clients via the catch-up mechanism

**Acceptance criteria:**

1. A row inserted by `append_event(conn, feature, {"type": "PHASE_SUMMARY", "phase": "scout", "agent": "planner", "text": "Found 3 relevant files", "ts": "...", "schema_version": 1})` produces a row in `fsm_events` where the `type` column is `"PHASE_SUMMARY"` and `payload` contains a `"text"` key.
2. `read_events(conn, feature, since_seq=0)` returns that row with `seq` populated.
3. No schema migration is required — the existing `fsm_events` table schema accommodates the new event type without DDL changes. Verify by inserting into an existing test DB and confirming no error.

**Edge cases:**
- `text` field may be empty string — endpoint must not reject it, but supervisor auto-notes must not emit empty-text events.
- `phase` field is optional for PHASE_SUMMARY (a summary may not be phase-scoped). Endpoint must accept a missing `phase` field.

**Delivered by:** Conversation 1 (backend foundation)

---

## Story 2 — /record_phase_summary HTTP endpoint

**Who:** Agents and the supervisor process  
**What:** Can POST to `/record_phase_summary` with a JSON body to write a PHASE_SUMMARY event to the feature's SQLite DB (same path as `db.append_event`)  
**Why:** Agents need an HTTP endpoint to emit progress notes during long-running phases, just as they call `/record_phase` for PHASE_START/PHASE_DONE

**Acceptance criteria:**

1. `POST /record_phase_summary` with body `{"feature": "my-feat", "agent": "builder", "text": "finished DB layer", "project_root": "/path/to/root"}` returns HTTP 200 `{"status": "recorded", "seq": <int>}` and inserts a `PHASE_SUMMARY` row in `<project_root>/pathly/plans/my-feat/pathly.db`.
2. Missing `feature` or `text` field returns HTTP 400 with an `{"error": "..."}` body describing which field is missing.
3. `text` field exceeding 2000 characters returns HTTP 400.
4. Optional fields `phase` and `conv` (integer) are stored in the event payload when present; the endpoint does not reject requests that omit them.
5. `project_root` defaults to the `PATHLY_PROJECT_ROOT` environment variable when the field is absent from the body.
6. If the feature directory does not exist, the endpoint returns HTTP 400 with `{"error": "Feature directory does not exist: ..."}`.
7. The inserted event is immediately visible to an active `_tail_events` SSE thread (no explicit flush needed — the SQLite poll interval is 100ms).

**Verify command:**
```bash
curl -s -X POST http://127.0.0.1:8765/record_phase_summary \
  -H "Content-Type: application/json" \
  -d "{\"feature\":\"smoke-test\",\"agent\":\"builder\",\"text\":\"hello\",\"project_root\":\"C:/Users/Yafit/pathly-adapters\"}" \
  | python -m json.tool
# Expected: {"seq": <int>, "status": "recorded"}
```

**Edge cases:**
- Body is not valid JSON → HTTP 400.
- `phase` value outside the known phase set is allowed (PHASE_SUMMARY is less strict than PHASE_START/PHASE_DONE about phase names).
- Concurrent calls from two threads must not corrupt the SQLite DB (the existing `_get_write_lock` mechanism covers this).

**Delivered by:** Conversation 1 (backend foundation)

---

## Story 3 — Supervisor auto-writes PHASE_SUMMARY at key lifecycle boundaries

**Who:** A user watching the Studio Monitor panel during a pipeline run  
**What:** Sees automatic PHASE_SUMMARY notes appear without any agent needing to call the endpoint — the supervisor writes them at defined lifecycle points  
**Why:** Even if an agent never calls `/record_phase_summary`, the timeline should show progress notes at phase boundaries so the user understands what just happened

**Acceptance criteria:**

1. When `supervisor.py` emits a `TERMINAL_SPAWN` SSE event for a new stage, it also writes a `PHASE_SUMMARY` event to the feature's SQLite DB with `text` = `"Starting <stage> — <agent> agent spawned"`, `phase` = the normalized stage name in lowercase, `agent` = `"supervisor"`.
2. When `supervisor.py` receives a successful PTY result (exit code 0) and advances the FSM, it writes a `PHASE_SUMMARY` event with `text` = `"<stage> complete — <agent> finished"`, `phase` = the normalized stage name, `agent` = `"supervisor"`.
3. Both supervisor-written events appear in the Studio EventLog within 2 seconds of the actual lifecycle event (SSE delivery latency ≤ 200ms + 100ms SQLite poll).
4. Supervisor PHASE_SUMMARY events do not duplicate any PHASE_START or PHASE_DONE events — they are additive, appearing alongside them in the timeline.
5. If writing the PHASE_SUMMARY event fails (e.g. DB not yet initialized), supervisor logs the exception at DEBUG level and continues without raising.

**Edge cases:**
- Stage name may include uppercase or hyphens — supervisor normalizes to lowercase for the `phase` field.
- `project_root` may not be set on the supervisor state at the time of writing — fall back to `os.environ.get("PATHLY_PROJECT_ROOT", "")` before skipping silently.

**Delivered by:** Conversation 2 (supervisor integration)

---

## Story 4 — EventLog renders PHASE_SUMMARY rows with distinct formatting

**Who:** A user watching the Monitor panel Events tab in Studio  
**What:** Sees PHASE_SUMMARY events in the live-scrolling event log with a distinctive color and a formatted line that shows the timestamp, label, agent, and text  
**Why:** So progress notes are immediately distinguishable from structural events (PHASE_START/PHASE_DONE) and from agent completion events (AGENT_DONE)

**Acceptance criteria:**

1. A `PHASE_SUMMARY` event appears in the EventLog as a line matching the pattern: `HH:MM:SS  SUMMARY         <agent>  <text>` (where `SUMMARY` is the 14-char-padded label and agent/text come from the event payload).
2. `PHASE_SUMMARY` lines use a distinct CSS color class — not the same class as PHASE_START/PHASE_DONE (`evColorPhase`) and not the same as AGENT_DONE (`evColorBlue`/`evColorGreen`).
3. When `densePhases` mode is active (default), PHASE_SUMMARY events are **shown** (not filtered out) — they are considered user-facing notes, not internal noise.
4. When a new PHASE_SUMMARY event arrives via SSE, the EventLog auto-scrolls to it (same behavior as all new events).
5. The EventLog's compact/all-phases toggle does not hide PHASE_SUMMARY events in either state.

**Edge cases:**
- `text` field missing from payload → display `(no text)` in place of the text.
- `agent` field missing → display `?` in place of agent name.
- Very long `text` value (> 120 chars) — the CSS for `evLine` must not break layout; line wraps or truncates gracefully (CSS `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` is acceptable, or `word-break: break-word`).

**Delivered by:** Conversation 3 (frontend)

---

## Story 5 — PHASE_SUMMARY events survive SSE reconnection

**Who:** A Studio user who briefly loses connection to the FSM server (e.g. server restart)  
**What:** After reconnecting, all previously emitted PHASE_SUMMARY events appear in the EventLog in their correct chronological position  
**Why:** The catch-up mechanism uses SQLite `read_events` with `Last-Event-ID` — PHASE_SUMMARY events stored in SQLite are replayed automatically, same as any other event type

**Acceptance criteria:**

1. Given: 3 PHASE_SUMMARY events written to SQLite at seq 5, 7, 9. When Studio reconnects with `Last-Event-ID: 4`, the SSE stream replays events at seq 5, 7, 9 (plus any other events in that range).
2. Replayed PHASE_SUMMARY events are rendered by the EventLog in the same visual format as live events.
3. No new endpoint, no new API field, and no change to the EventSource setup in `useMonitorSession.ts` is required for this story — it is a free property of storing events in SQLite.

**Delivered by:** Conversation 1 (backend foundation) — this is a free property of using `append_event`; no extra implementation needed. AC is a verification story only.
