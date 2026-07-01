# EDGE_CASES.md — studio-backend

---

## Migration: existing per-feature pathly.db files after upgrade

**Situation:** A developer has been using Pathly with the old per-feature DB layout.
Each feature has a `pathly/plans/<feature>/pathly.db`. After upgrading to the
studio-backend build, they call `get_db()` for the first time.

**Behavior:** The old per-feature DBs are NOT automatically migrated. They remain
on disk at their original paths and are not read by `get_db()`. Historical event
data from old runs will not appear in Studio's DB Explorer.

**Rationale:** Automatic migration across an unknown number of project directories
is risky and out of scope. Old data is not deleted — it remains accessible via the
legacy file path.

**Mitigation:** If the user needs old data in Studio, a future migration script
(not part of this feature) could read each legacy DB and INSERT its events into
the centralized DB. This is documented as a future TODO, not an acceptance criteria
for studio-backend.

---

## Concurrent writes: two runner processes writing to the same DB

**Situation:** Two pipeline runs are active at the same time (e.g., two separate
features being built in parallel, each with their own PTY). Both call `get_db()`
and write events simultaneously.

**Behavior:** SQLite WAL (Write-Ahead Log) mode allows concurrent readers and one
writer. The second writer will wait (up to the connection timeout) if the first has
an active write transaction. For short write bursts (appending events), contention
is negligible.

**Recovery path:** If a runner crashes mid-write, `mark_stale_runners(conn)` is
the recovery mechanism. It performs a global sweep to mark runner records as stale
based on timeout, regardless of `project_root`. The server calls this at startup.

**Rule:** `mark_stale_runners` intentionally takes no `project_root` argument — it
is a global sweep by design.

---

## Seed idempotency: calling get_db() twice in the same process

**Situation:** Application code or tests call `get_db()` more than once.

**Behavior:** `_seed_if_empty` checks `SELECT COUNT(*) FROM flow_definitions` first.
If count > 0, it returns immediately without any INSERTs. Even if count were 0,
all seed inserts use `INSERT OR IGNORE` (via upsert helpers) — duplicates are silently
discarded.

**Result:** Calling `get_db()` N times produces the same DB state as calling it once.
Tests that call `get_db()` in multiple test functions will not accumulate duplicate rows.

---

## Missing pathly_data files: seed source not found

**Situation:** `src/pathly_data/` is not present at the expected path (e.g., package
installed from PyPI without source tree, or repo layout differs).

**Behavior:**
- `_seed_if_empty` walks up the directory tree from `db.py`'s location to find
  `pathly_data/core/`. If not found after checking 3 levels up, it logs a `WARNING`
  and returns. `get_db()` continues normally and returns a valid (empty) connection.
- Individual malformed files (bad YAML, unreadable, encoding errors) are caught
  per-file with `try/except`. A WARNING is logged, the file is skipped, and seeding
  continues with remaining files.
- `get_db()` never raises an exception due to seed failures.

**Impact:** The DB will be empty — Studio will show empty flow selector, empty
skill catalog. This is acceptable for deployed environments where pathly_data is
not co-located. A future `pathly seed` CLI command can re-run seeding manually.

---

## project_root as None: global skills and agents

**Situation:** Some skills and agents are global (not tied to any project). These
are the seeded catalog entries. Their `project_root` column is NULL.

**Behavior:**
- `read_skill_definitions(conn, project_root=None)` returns only rows where
  `project_root IS NULL`.
- `read_skill_definitions(conn, project_root='/home/dev/my-app')` returns only
  rows where `project_root = '/home/dev/my-app'`.
- `resolve_skill` implements local-first: project-level rows sort before NULL rows
  via `ORDER BY project_root IS NULL` (NULL sorts last in SQLite with this expression).
- UNIQUE constraints use `COALESCE(project_root, '')` to treat NULL as a single
  global namespace — two global skills with the same name are rejected.

---

## HTTP route: project_root not provided in query string

**Situation:** Studio calls `GET /api/features` without a `project_root` query parameter.

**Behavior:** The route returns an empty JSON array `[]` with HTTP 200. It does NOT
return 400. Studio is expected to always send `project_root`, but an absent value is
not an error — it just means no features are scoped.

**Rationale:** A 400 would cause Studio to show an error dialog for what is logically
a "nothing selected yet" state. Empty list is the correct semantic response.

---

## DB path collision: two users on the same machine

**Situation:** Two OS users both run Pathly on the same machine.

**Behavior:** `get_db()` uses `Path.home()` which resolves to each user's own home
directory. Each user gets their own `~/.pathly/pathly.db`. There is no cross-user
DB access.

---

## WAL file left open after crash

**Situation:** The server crashes while a WAL write is in progress, leaving a
`pathly.db-wal` file on disk.

**Behavior:** SQLite's WAL mechanism handles this automatically. On next open,
SQLite will either checkpoint the WAL into the main DB or discard uncommitted
transactions. No manual recovery is needed. The `-wal` and `-shm` files can be
left in place — they are managed by SQLite.
