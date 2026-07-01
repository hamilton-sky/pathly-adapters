---
name: Architecture Proposal
---
# fsm-sqlite — Architecture Proposal

## Problem Statement

The Pathly orchestrator persists pipeline control state in three plain files per feature.
These files are written by multiple processes and threads without coordinated locking,
creating three concrete failure modes: partial STATE.json on crash, EVENTS.jsonl
corruption on Windows (no fcntl), and truncated RUNNER_STATE.json on supervisor crash.
The goal is to replace all three with a single SQLite database that provides atomicity
and concurrent-reader safety with zero new dependencies.

## Proposed Solution

Introduce `src/pathly_orchestrator/db.py` as a new module that owns the SQLite schema
and all CRUD helpers. Existing Python callers (`eventlog.py`, `supervisor.py`,
`http_server.py`, `runner.py`) are updated to call `db.py` instead of raw file I/O.
The public API of `eventlog.py` is preserved — only its internal persistence layer changes.
Markdown plan files and agent-written STATE.json stay on disk; only the Python
orchestrator's control plane moves to SQLite.

## Layer Breakdown

```
Callers (eventlog.py, supervisor.py, http_server.py, runner.py)
        │  call unchanged public API  (append_event, write_state, etc.)
        ▼
eventlog.py  (API preserved — internal persistence delegated to db.py)
        │  calls db.get_db() + db helpers
        ▼
db.py  (NEW — owns schema + CRUD, WAL mode, connection cache)
        │  opens
        ▼
pathly/plans/<feature>/pathly.db   (one SQLite DB per feature dir)
        │
        ├── fsm_events   (replaces EVENTS.jsonl)
        ├── fsm_state    (replaces STATE.json Python writes)
        └── runner_state (replaces RUNNER_STATE.json)
```

## Key Design Decisions

### Decision 1: One DB per feature, not one central DB
- **Options considered**:
  - A: One central `pathly/plans/pathly.db` with `feature` column in all tables
  - B: One `pathly.db` per feature folder
- **Chosen**: B
- **Rationale**: Preserves per-feature isolation (archive a feature = delete its folder); no cross-feature locking contention; matches existing dir-per-feature structure. Cross-feature queries are rare; iterating dirs is acceptable for the few cases that need it.

### Decision 2: WAL mode + NORMAL synchronous
- **Options considered**:
  - A: Default journal mode (DELETE) — only one writer/reader at a time
  - B: WAL mode + FULL sync — concurrent readers + OS-crash durable
  - C: WAL mode + NORMAL sync — concurrent readers + process-crash durable
- **Chosen**: C
- **Rationale**: WAL allows concurrent reads (SSE tail + status endpoint) while one writer commits. NORMAL sync is safe for this use case: a mid-transaction process crash rolls back cleanly; an OS crash could lose the last committed transaction but not corrupt the DB. FULL sync costs ~2x write latency for no practical benefit in a local dev tool.

### Decision 3: Preserve eventlog.py public API
- **Options considered**:
  - A: Replace all callers directly with db.py calls
  - B: Keep eventlog.py as the public API; db.py is its internal implementation
- **Chosen**: B
- **Rationale**: eventlog.py is imported by fsm.py, supervisor.py, http_server.py, runner.py, and tests. Changing all call sites in one step is high risk. Keeping the public API means each file can be updated independently; tests continue to work; no flag day.

### Decision 4: Backward compat via DB-exists guard
- **Options considered**:
  - A: Hard cutover — old plans break without migration
  - B: Dual-write — write both SQLite and files simultaneously during transition
  - C: Read fallback — if pathly.db exists use SQLite; else use legacy files
- **Chosen**: C
- **Rationale**: Lowest risk. Old plans continue to work unchanged. Migration script can be run at any time. No double-write overhead. Consistent: once pathly.db exists, it's authoritative; no split-brain.

### Decision 5: Agent-written STATE.json stays on disk
- **Options considered**:
  - A: Force agents to call an HTTP endpoint to update state (breaking change)
  - B: Keep STATE.json on disk; Python layer ignores it when pathly.db exists
- **Chosen**: B
- **Rationale**: Claude Code agents write STATE.json via the Write tool. Redirecting this to an HTTP call would require changing every agent prompt. For now, STATE.json written by agents is treated as a human-readable cache; the Python layer reads SQLite as authoritative. Future improvement: agents could be prompted to call a CLI command instead.

## Key Components

| Component | Type | Responsibility |
|---|---|---|
| `db.py` | New module | SQLite schema owner; all CRUD helpers; connection cache |
| `eventlog.py` | Modified | Delegates file I/O to db.py; keeps public API; adds fallback guard |
| `supervisor.py` | Modified | Removes direct .jsonl writes; RUNNER_STATE → db.write_runner_state |
| `http_server.py` | Modified | SSE tail → db.read_events(since_seq) |
| `runner.py` | Modified | read_last_agent_done → db.read_last_agent_done |
| `scripts/migrate_to_sqlite.py` | New script | One-shot import of legacy files into pathly.db |

## Interface Design

```python
# db.py public API
def get_db(feature_dir: Path) -> sqlite3.Connection
    """Open or return cached WAL connection for feature's pathly.db."""

def append_event(conn, feature: str, event_dict: dict) -> int
    """Insert event; return seq (auto-increment). Thread-safe."""

def read_events(conn, feature: str, since_seq: int = 0) -> list[dict]
    """Return events with seq > since_seq in ascending order."""

def read_last_agent_done(conn, feature: str) -> dict | None
    """Return the most recent AGENT_DONE event, or None."""

def write_state(conn, feature: str, state_dict: dict) -> None
    """Upsert FSM state row. Atomic INSERT OR REPLACE."""

def read_state(conn, feature: str) -> dict | None
    """Return current FSM state dict, or None if not set."""

def write_runner_state(conn, feature: str, runner_dict: dict) -> None
    """Upsert runner state row. Atomic INSERT OR REPLACE."""

def read_runner_state(conn, feature: str) -> dict | None
    """Return current runner state dict, or None if not set."""

def mark_stale_runners(conn) -> int
    """Set status='error' for all status='running' rows. Returns count updated."""
```

## Risks

- **sqlite3 connection cache thread-safety**: `check_same_thread=False` used; WAL handles concurrent access. Risk low — GIL + WAL prevents corruption; mitigated by `_cache_lock` protecting cache initialization.
- **Busy timeout on Windows**: On Windows, SQLite file locking can cause `SQLITE_BUSY` if two processes open the same DB simultaneously. Mitigated by `PRAGMA busy_timeout=5000` in `get_db()`.
- **Agent STATE.json drift**: If an agent writes STATE.json but pathly.db is present, the Python layer ignores STATE.json — agent cache becomes stale. Risk low: agents write state at conversation boundaries, not mid-run. Future PR can eliminate the dual-write.
- **Migration script idempotency on duplicate (ts, type)**: Two events with the same timestamp and type would conflict on the UNIQUE constraint. Mitigated by using `INSERT OR IGNORE`; duplicate events are dropped silently (acceptable for migration).
