# Implementation Plan — event-phase-summary

## Architecture notes

**Existing infrastructure — use it, don't duplicate:**
- `db.append_event(conn, feature, event_dict)` already stores any event type in SQLite `fsm_events`. No schema changes needed.
- `_tail_events` in `http_server.py` polls SQLite every 100ms and broadcasts to SSE clients. PHASE_SUMMARY events stored via `append_event` are automatically delivered — no new SSE plumbing needed.
- The catch-up block in `events_stream()` replays from SQLite on reconnect using `Last-Event-ID`. PHASE_SUMMARY events stored in SQLite are replayed for free.
- `EventLog.tsx` in `studio/src/renderer/src/components/Monitor/` already exists, already handles PHASE_START/PHASE_DONE/AGENT_DONE, and already subscribes to `store.events`. Only two additions are needed: a new case in `eventColorClass()` and a new case in `formatEvent()`.
- `FsmEvent` type in `types/index.ts` has `[key: string]: unknown` open index, so adding `text` to a PHASE_SUMMARY event requires no type-file change.

**Important discrepancy — do not introduce new inconsistency:**
`/record_phase` (existing endpoint for PHASE_START/PHASE_DONE) writes to EVENTS.jsonl, not SQLite. The new `/record_phase_summary` endpoint must write to **SQLite** (not EVENTS.jsonl) so the catch-up mechanism replays it correctly. The supervisor's auto-writes must also use `db.append_event`, not file append.

---

## Phase 1 — Backend: /record_phase_summary endpoint

**Files changed:**
- `src/pathly_orchestrator/http_server.py`

**What to add:**

Add a new route `/record_phase_summary` after the existing `/record_phase` endpoint (around line 874). It must:

1. Validate body: `feature` (required, non-empty string), `text` (required, string, max 2000 chars), `agent` (required, non-empty string). Optional: `phase` (string), `conv` (integer), `project_root` (string, falls back to `PATHLY_PROJECT_ROOT` env var).
2. Resolve the feature directory as `Path(project_root) / "pathly" / "plans" / feature`. Return HTTP 400 if it does not exist.
3. Call `db.get_db(feature_dir)` to get a connection, then call `db.append_event(conn, feature, event_dict)` where `event_dict` is:
   ```python
   {
     "schema_version": 1,
     "type": "PHASE_SUMMARY",
     "feature": feature,
     "agent": agent,
     "text": text,
     "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
     # + "phase": phase if provided
     # + "conv": conv if provided
   }
   ```
4. Return `{"status": "recorded", "seq": <seq>}` HTTP 200.

**Done-when:**
- `POST /record_phase_summary` with valid body returns 200 `{"status": "recorded", "seq": <int>}`
- Missing `feature` returns 400
- Missing `text` returns 400
- `text` > 2000 chars returns 400
- Inserted row visible via `SELECT type, payload FROM fsm_events WHERE type='PHASE_SUMMARY'` on the feature DB

**Verify:**
```bash
# Start the FSM server, then:
curl -s -X POST http://127.0.0.1:8765/record_phase_summary \
  -H "Content-Type: application/json" \
  -d "{\"feature\":\"smoke-test\",\"agent\":\"builder\",\"text\":\"test note\",\"project_root\":\"C:/Users/Yafit/pathly-adapters\"}"
```

---

## Phase 2 — Backend: supervisor auto-writes PHASE_SUMMARY

**Files changed:**
- `src/pathly_orchestrator/supervisor.py`

**What to add:**

Locate the two key lifecycle points in `supervisor.py`:

1. **After emitting `TERMINAL_SPAWN` SSE** — where `supervisor.py` broadcasts `TERMINAL_SPAWN` and then waits for PTY result. After the broadcast call, add a helper call that writes a PHASE_SUMMARY event to SQLite:
   ```python
   _write_supervisor_phase_summary(
       project_root=state.project_root,
       topic=state.topic,
       stage=state.current_state,
       agent=agent_role,
       text=f"Starting {stage_normalized} — {agent_role} agent spawned",
   )
   ```

2. **After a successful PTY result and FSM advance** — where `supervisor.py` calls `/complete_stage` or advances FSM state. After the advance, add:
   ```python
   _write_supervisor_phase_summary(
       project_root=state.project_root,
       topic=state.topic,
       stage=state.current_state,
       agent=agent_role,
       text=f"{stage_normalized} complete — {agent_role} finished",
   )
   ```

Add a small helper function `_write_supervisor_phase_summary(*, project_root, topic, stage, agent, text)` in `supervisor.py` that:
- Resolves `feature_dir = Path(project_root) / "pathly" / "plans" / topic`
- Calls `from pathly_orchestrator import db as _db; conn = _db.get_db(feature_dir); _db.append_event(conn, topic, {...})`
- Wraps everything in `try/except Exception` and logs at DEBUG level on failure
- Does nothing if `project_root` is empty or feature_dir does not exist

**Done-when:**
- Run a pipeline stage; two PHASE_SUMMARY rows (one spawn, one complete) appear in the feature's SQLite DB under the topic
- `SELECT type, agent, payload FROM fsm_events WHERE type='PHASE_SUMMARY'` returns rows with `agent='supervisor'`

**Verify:**
```bash
# After running a pipeline stage, query the DB:
python -c "
import sqlite3, json
db = sqlite3.connect('pathly/plans/<topic>/pathly.db')
for r in db.execute(\"SELECT seq, payload FROM fsm_events WHERE type='PHASE_SUMMARY'\").fetchall():
    print(r[0], json.loads(r[1])['text'])
"
```

---

## Phase 3 — Frontend: render PHASE_SUMMARY in EventLog

**Files changed:**
- `studio/src/renderer/src/components/Monitor/EventLog.tsx`
- `studio/src/renderer/src/components/Monitor/Monitor.module.css`

**What to add:**

In `EventLog.tsx`:

1. Add a new case in `eventColorClass()`:
   ```ts
   case 'PHASE_SUMMARY': return styles.evColorSummary
   ```

2. Add a new case in `formatEvent()`:
   ```ts
   case 'PHASE_SUMMARY': {
     const agent = (ev as Record<string, unknown>).agent as string | undefined ?? '?'
     const text = (ev as Record<string, unknown>).text as string | undefined ?? '(no text)'
     return `${ts}  ${pad('SUMMARY', 14)}  ${agent}  ${text}`
   }
   ```

3. In `visibleEvents` filter: `PHASE_SUMMARY` events must not be filtered out by the `densePhases` filter (that filter only suppresses inner-phase PHASE_START/PHASE_DONE). Confirm the filter condition `ev.type !== 'PHASE_START' && ev.type !== 'PHASE_DONE'` already passes PHASE_SUMMARY through — no change needed.

In `Monitor.module.css`:

4. Add a new CSS class `evColorSummary` that uses a distinct color — suggested: `var(--accent-secondary)` or a warm amber tone to visually separate it from PHASE events (cyan-ish) and AGENT_DONE events (blue/green). If `--accent-secondary` does not exist in tokens.css, use a hardcoded design-system color consistent with the existing color palette.

**Done-when:**
- A PHASE_SUMMARY event in the store renders as `HH:MM:SS  SUMMARY         <agent>  <text>` in a distinct color
- Toggle dense/all-phases: PHASE_SUMMARY always appears in both modes
- TypeScript compiles without error: `npm run typecheck`

**Verify:**
```bash
# From repo root:
npm run typecheck
```

---

## Conversation breakdown

| Conv | Phase(s) | Stories | Files | Done-when |
|---|---|---|---|---|
| 1 | Backend endpoint | Stories 1, 2, 5 | `http_server.py` | `/record_phase_summary` returns 200 + seq; SQLite row exists |
| 2 | Supervisor integration | Story 3 | `supervisor.py` | Two PHASE_SUMMARY rows in DB after one pipeline stage |
| 3 | Frontend rendering | Story 4 | `EventLog.tsx`, `Monitor.module.css` | Typecheck passes; PHASE_SUMMARY renders in correct color |
