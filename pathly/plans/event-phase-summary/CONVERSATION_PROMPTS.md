# Conversation Prompts — event-phase-summary

---

## Conversation 1 — Backend: /record_phase_summary endpoint

**Stories delivered:** Story 1 (PHASE_SUMMARY in SQLite), Story 2 (/record_phase_summary endpoint), Story 5 (reconnect replay — free property)

**Files to change:** `src/pathly_orchestrator/http_server.py` only

---

You are implementing the `/record_phase_summary` HTTP endpoint for the Pathly FSM server.

### Context

The FSM server (`src/pathly_orchestrator/http_server.py`) runs on port 8765. It already has:
- `db.append_event(conn, feature, event_dict)` — inserts any event dict into the `fsm_events` SQLite table and returns the new `seq` (integer)
- `db.get_db(feature_dir)` — returns a cached SQLite connection for a feature directory
- `/record_phase` endpoint (around line 817) — adds PHASE_START/PHASE_DONE events to EVENTS.jsonl; use this as a structural reference only
- `_tail_events` thread — polls SQLite every 100ms and broadcasts new rows to SSE clients automatically; no changes needed

The new endpoint must write to **SQLite via `db.append_event`**, not to EVENTS.jsonl.

### What to build

Add a new route `POST /record_phase_summary` to `http_server.py` directly after the `/record_phase` endpoint.

**Request body (JSON):**
- `feature` — required, non-empty string
- `agent` — required, non-empty string
- `text` — required, string, max 2000 characters
- `phase` — optional string (not validated against a fixed set; PHASE_SUMMARY is phase-agnostic)
- `conv` — optional integer
- `project_root` — optional string; falls back to `os.environ.get("PATHLY_PROJECT_ROOT", "")`

**Validation rules:**
- Missing or empty `feature`, `agent`, or `text` → HTTP 400 `{"error": "Missing required field: '<field>'"}`
- `text` longer than 2000 characters → HTTP 400 `{"error": "Field 'text' must not exceed 2000 characters"}`
- Non-JSON body or missing body → HTTP 400 `{"error": "Missing JSON body"}`
- Feature directory does not exist → HTTP 400 `{"error": "Feature directory does not exist: <path>"}`

**Event shape to store:**
```python
event: dict = {
    "schema_version": 1,
    "type": "PHASE_SUMMARY",
    "feature": feature,
    "agent": agent,
    "text": text,
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
# Add "phase": phase if provided and non-empty
# Add "conv": conv if provided (must be int or castable to int; skip if not)
```

**Success response:** HTTP 200 `{"status": "recorded", "seq": <int>}` where `seq` is the return value of `db.append_event`.

**Error handling:** Wrap the entire handler in `try/except Exception` and log with `logging.exception("record_phase_summary error")`, returning HTTP 500 `{"error": str(e), "type": type(e).__name__}`.

### Acceptance check

After implementing, verify with:
```bash
# Requires FSM server running and smoke-test feature directory to exist
# Create the dir first if needed:
mkdir -p pathly/plans/smoke-test

curl -s -X POST http://127.0.0.1:8765/record_phase_summary \
  -H "Content-Type: application/json" \
  -d "{\"feature\":\"smoke-test\",\"agent\":\"builder\",\"text\":\"test note\",\"project_root\":\"C:/Users/Yafit/pathly-adapters\"}"
# Must return: {"seq": <int>, "status": "recorded"}

curl -s -X POST http://127.0.0.1:8765/record_phase_summary \
  -H "Content-Type: application/json" \
  -d "{\"feature\":\"smoke-test\",\"agent\":\"builder\"}"
# Must return 400: {"error": "Missing required field: 'text'"}
```

Also run: `python -m pytest tests/ -q` — all existing tests must pass.

---

## Conversation 2 — Backend: supervisor auto-writes PHASE_SUMMARY

**Stories delivered:** Story 3 (supervisor lifecycle notes)

**Files to change:** `src/pathly_orchestrator/supervisor.py` only

---

You are adding automatic PHASE_SUMMARY event writes to the Pathly pipeline supervisor.

### Context

`supervisor.py` drives the pipeline by polling `/next_action` and calling the FSM to advance stages. Each stage goes through this lifecycle:
1. `supervisor.py` emits a `TERMINAL_SPAWN` SSE event → Studio opens a PTY tab
2. PTY runs the agent → when done, Studio POSTs `/runner/terminal/result`
3. `supervisor.py` receives the result and calls `/complete_stage` (or `/next_action`)

The supervisor should write a PHASE_SUMMARY event to SQLite at two points in this lifecycle:
- When a new terminal is spawned (stage starts)
- When a stage completes successfully (exit code 0, FSM advanced)

The `/record_phase_summary` endpoint now exists and writes to SQLite. The supervisor can write directly via the `db` module without going through HTTP.

### What to build

**Step 1:** Add a private helper function `_write_supervisor_phase_summary` near the top of `supervisor.py` (after imports):

```python
def _write_supervisor_phase_summary(
    *,
    project_root: str,
    topic: str,
    stage: str,
    agent: str,
    text: str,
) -> None:
    """Write a PHASE_SUMMARY event to the feature's SQLite DB. Silent on failure."""
    import time as _time
    if not project_root or not topic:
        return
    try:
        from pathly_orchestrator import db as _db
        feature_dir = Path(project_root) / "pathly" / "plans" / topic
        if not feature_dir.exists():
            return
        conn = _db.get_db(feature_dir)
        phase = stage.lower().replace("-", "_") if stage else ""
        event: dict = {
            "schema_version": 1,
            "type": "PHASE_SUMMARY",
            "feature": topic,
            "agent": agent,
            "text": text,
            "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        if phase:
            event["phase"] = phase
        _db.append_event(conn, topic, event)
    except Exception:
        logger.debug("_write_supervisor_phase_summary failed", exc_info=True)
```

**Step 2:** Locate where `supervisor.py` broadcasts `TERMINAL_SPAWN`. After the broadcast call (not before — the SSE must go out first), call:
```python
_write_supervisor_phase_summary(
    project_root=state.project_root,
    topic=state.topic,
    stage=state.current_state or "",
    agent=agent_role,
    text=f"Starting {(state.current_state or 'stage').lower()} — {agent_role} agent spawned",
)
```
Replace `agent_role` with whatever variable holds the current agent name at that call site.

**Step 3:** Locate where `supervisor.py` successfully advances the FSM after a stage completes (exit code 0, non-error path). After the advance call, add:
```python
_write_supervisor_phase_summary(
    project_root=state.project_root,
    topic=state.topic,
    stage=state.current_state or "",
    agent=agent_role,
    text=f"{(state.current_state or 'stage').lower()} complete — {agent_role} finished",
)
```

**Important:** Wrap both call sites in the existing error-handling context if any. If `agent_role` is not available at a particular call site, read it from `state` or the `next_action` response dict.

### Acceptance check

After a single pipeline stage runs end-to-end:
```bash
python -c "
import sqlite3, json
db = sqlite3.connect('pathly/plans/<topic>/pathly.db')
rows = db.execute(\"SELECT seq, payload FROM fsm_events WHERE type='PHASE_SUMMARY' AND json_extract(payload, '$.agent')='supervisor'\").fetchall()
for seq, p in rows:
    print(seq, json.loads(p)['text'])
"
# Must show at least two rows: one 'Starting...' and one '...complete...'
```

Run: `python -m pytest tests/ -q` — all existing tests must pass.

---

## Conversation 3 — Frontend: render PHASE_SUMMARY in EventLog

**Stories delivered:** Story 4 (PHASE_SUMMARY rendering in Studio)

**Files to change:**
- `studio/src/renderer/src/components/Monitor/EventLog.tsx`
- `studio/src/renderer/src/components/Monitor/Monitor.module.css`

---

You are adding PHASE_SUMMARY event rendering to the Studio Monitor panel's EventLog component.

### Context

`EventLog.tsx` (`studio/src/renderer/src/components/Monitor/EventLog.tsx`) already renders a live-scrolling event log from `store.events`. It has two switch functions:
- `eventColorClass(ev)` — returns a CSS class name from `Monitor.module.css` based on `ev.type`
- `formatEvent(ev)` — returns a formatted string for display

Events are shown as monospace lines. The dense/compact toggle (`densePhases` state) hides inner-phase PHASE_START/PHASE_DONE events. It does NOT hide PHASE_SUMMARY — those are always visible (this is by design; no filter change needed).

`FsmEvent` type already has `[key: string]: unknown` so `text` can be read from the payload without any type file change.

### What to build

**In `EventLog.tsx`:**

1. In `eventColorClass()`, add before the `default` case:
   ```ts
   case 'PHASE_SUMMARY': return styles.evColorSummary
   ```

2. In `formatEvent()`, add before the `default` case:
   ```ts
   case 'PHASE_SUMMARY': {
     const agent = (ev as Record<string, unknown>).agent as string | undefined ?? '?'
     const text = (ev as Record<string, unknown>).text as string | undefined ?? '(no text)'
     return `${ts}  ${pad('SUMMARY', 14)}  ${agent}  ${text}`
   }
   ```

No changes to the `visibleEvents` filter — the existing filter only suppresses inner-phase PHASE_START/PHASE_DONE; PHASE_SUMMARY passes through automatically.

**In `Monitor.module.css`:**

3. Add a new CSS class `.evColorSummary`. Use an amber/warm tone to distinguish it from:
   - PHASE events: cyan (`.evColorPhase`)
   - AGENT_DONE events: blue/green (`.evColorBlue`, `.evColorGreen`)
   - Muted events: gray (`.evColorMuted`)

   Suggested rule (adjust to match existing color token patterns in the file):
   ```css
   .evColorSummary { color: #F59E0B; }
   ```
   If the existing module uses CSS custom properties for colors, use `var(--color-amber, #F59E0B)` or the equivalent token from `tokens.css`. Check `Monitor.module.css` first to match the existing pattern exactly.

### Studio rules reminder
- No inline styles in JSX.
- The `evColorSummary` class goes in `Monitor.module.css`, referenced as `styles.evColorSummary`.
- Do not change `FsmEvent` type — the open index already covers `text`.

### Acceptance check

```bash
# From repo root — must pass with zero errors:
npm run typecheck
```

Manual check: in a running Studio session with an active pipeline, confirm PHASE_SUMMARY events appear in the Events tab in amber, formatted as `HH:MM:SS  SUMMARY         <agent>  <text>`.
