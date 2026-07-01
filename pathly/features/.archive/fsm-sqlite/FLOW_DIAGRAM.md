---
name: Flow Diagram
---
# fsm-sqlite — Flow Diagram

## Before: File-Based Control Plane

```
FSM engine (fsm.py)
    │  write_state()
    ▼
eventlog.py
    │  .tmp + fsync + rename ──────────► STATE.json  (risk: partial write on crash)
    │  fcntl lock + append ────────────► EVENTS.jsonl (risk: no lock on Windows)
    │
supervisor.py
    │  direct open + write ────────────► EVENTS.jsonl (race: bypasses lock)
    │  write_text() ───────────────────► RUNNER_STATE.json (risk: partial write)
    │
http_server.py
    │  file seek + read new bytes ─────► EVENTS.jsonl (risk: breaks on truncation)
    │
runner.py
    └─ scan lines reverse ─────────────► EVENTS.jsonl (risk: O(n) on large logs)
```

## After: SQLite Control Plane (this feature)

```
FSM engine (fsm.py)
    │  write_state()  [API unchanged]
    ▼
eventlog.py
    │  db.write_state() ───────────────┐
    │  db.append_event() ──────────────┤
    │                                  ▼
supervisor.py                    db.py  (NEW)
    │  eventlog.append_event() ───────►│  get_db() → pathly.db (WAL mode)
    │  db.write_runner_state() ───────►│
    │  db.mark_stale_runners() ───────►│
    │                                  │
http_server.py                         │
    │  db.read_events(since_seq) ─────►│
    │                                  │
runner.py                              │
    └─ db.read_last_agent_done() ─────►│
                                       ▼
                              pathly/plans/<feature>/
                                  pathly.db
                                  ├── fsm_events  (seq, type, payload)
                                  ├── fsm_state   (current, convs_done, ...)
                                  └── runner_state (status, cost_usd_so_far, ...)
```

## Fallback Flow (old plans without pathly.db)

```
eventlog.read_state(feature)
        │
        ├─ pathly.db exists? ──YES──► db.read_state()  ──► return dict
        │
        └─ NO ──────────────────────► read STATE.json  ──► return dict

eventlog.read_events(feature)
        │
        ├─ pathly.db exists? ──YES──► db.read_events()  ──► return list
        │
        └─ NO ──────────────────────► read EVENTS.jsonl ──► return list

supervisor.recover_stale_mirrors()
        │
        ├─ pathly.db exists? ──YES──► db.mark_stale_runners()
        │
        └─ NO ──────────────────────► read/rewrite RUNNER_STATE.json (legacy)
```

## SSE Tail: Before vs After

```
BEFORE (file seek):
  http_server._tail_events()
        │
        ├─ open EVENTS.jsonl
        ├─ seek to saved position
        ├─ read new bytes ──► parse lines ──► yield SSE
        └─ RISK: seek invalid if file truncated

AFTER (seq polling):
  http_server._tail_events()
        │
        ├─ last_seq = Last-Event-ID header (or 0)
        ├─ loop:
        │    db.read_events(since_seq=last_seq)
        │    for event in results:
        │        yield f"id: {seq}\ndata: {payload}\n\n"
        │        last_seq = seq
        │    sleep(poll_interval)
        └─ SAFE: seq is monotonic; reconnect just passes Last-Event-ID
```

## Component Legend

| Symbol | Meaning in this feature |
|--------|------------------------|
| `db.py` | New SQLite layer; all schema + CRUD; connection cache with WAL |
| `eventlog.py` | Preserved API; delegates persistence to db.py; adds fallback guard |
| `pathly.db` | One SQLite file per feature dir; three tables; WAL journal |
| `fallback guard` | `if (feature_dir / "pathly.db").exists()` — SQLite wins; else legacy files |
| `since_seq` | Integer passed to `read_events()`; replaces file seek position |
