# REVIEW_FAILURES — comms-board Conv 5 (Phases 11–13)

Reviewer: adversarial review pass
Files reviewed: db/connection.py, db/migrations.py, db/queries/comms.py,
db/queries/app_settings.py, http_server/blueprints/comms.py,
runner/comms_context.py, tests/test_comms_hybrid.py,
tests/test_comms_search_mode.py, tests/test_comms_write_perm.py
Spec refs: SPEC.md §26, §27; IMPLEMENTATION_PLAN.md Phases 11–13

---

## BLOCKER

### B1 — `comms_post()` ignores project-level write-permission overrides (SPEC §27.4)

**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py:77–83`
**Rule violated:** SPEC §27.4 — "Project-level overrides are stored in `app_settings` under the key `write_permissions:{project_root}`. This lets a project grant `builder` write access to project scope."

`_check_write_permission` is hardcoded against the module-level frozensets `_PROJECT_WRITERS` / `_GLOBAL_WRITERS` and never consults the database. The override system (`get_write_permissions` / `set_write_permissions` in `app_settings.py`) is correctly implemented and correctly exposed at `GET /comms/permissions`, but `POST /comms/post` never calls `get_write_permissions`. As a result, any project-level override stored via `set_write_permissions` silently has no effect on actual enforcement.

Concrete breakage: `test_comms_write_perm_set_and_get_overrides` stores `{"global": ["director", "human", "tester"]}` and reads it back correctly, but if a tester then calls `POST /comms/post` with `board="global"` the request is still rejected with 403 because the live check ignores the DB.

`comms_post()` must retrieve the project's write-permission table (using `project_root` from the request body, or a default) and pass it into a revised `_check_write_permission` instead of using the hardcoded frozensets for the override tiers.

---

## MAJOR

### M1 — Unguarded FTS5 MATCH expression causes HTTP 500 on malformed query (SPEC §26, security/robustness)

**File:** `src/pathly_orchestrator/db/queries/comms.py:137–141`
**Rule violated:** SPEC §26 robustness — the spec shows the query_text reaching `comms_fts MATCH ?` as a parameterized bind; it does not address FTS5 parse errors. The parameter prevents SQL injection but does not prevent FTS5 from raising `sqlite3.OperationalError` on syntactically invalid FTS5 query expressions (unmatched double quotes, lone `OR`/`AND`/`NOT` operators, unbalanced parentheses, bare `*` prefix, etc.).

`search_by_keyword` does not catch `sqlite3.OperationalError` internally. The exception propagates through `search_by_hybrid` → `comms_search()` where it is caught by the outermost `except Exception` and returned as HTTP 500 with `{"error": "...", "type": "OperationalError"}`. Any caller (including an agent) can trigger a 500 by sending a query such as `"OR setup"`, `"setup*"`, `"setup AND"`, or a lone `"`.

Fix: wrap the FTS5 `conn.execute(sql, ...)` in `search_by_keyword` with `except sqlite3.OperationalError: return []` so a bad query string degrades to an empty result rather than a 500. This also keeps `search_by_hybrid` correct — it will simply see `bm25_rows=[]` and fall through to the semantic path.

---

## MINOR

### N1 — `POST /comms/search` mode='hybrid' has no recency fallback when both FTS and vec are absent (SPEC §26.7)

**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py:218–219`
**Rule violated:** SPEC §26.7 — "Both absent → recency `ORDER BY ts DESC`"

When `sqlite-vec` is unavailable AND FTS5 returns empty (or is unavailable), `search_by_hybrid` returns `[]`. The `comms_search()` handler for `mode='hybrid'` returns that empty list directly without a recency fallback. By contrast, `retrieve_board_context()` in `comms_context.py:204–207` correctly falls back to `get_messages()` when rows are empty and `task_embedding is None`. The HTTP endpoint is inconsistent with the spec's degradation table and with the retrieval path.

This only fires when `task_description` produces an empty keyword result AND embedding is None — an edge case — but it is a spec deviation.

---

## Pass (checked and clean)

- **Layer/dependency:** `db/queries/comms.py` and `db/queries/app_settings.py` import only from `db/connection` (same layer). `runner/comms_context.py` imports from `db/` (allowed). `http_server/blueprints/comms.py` does all `db/` and `runner/` imports lazily inside route handlers (allowed per layer rules). No upward imports.
- **Write-lock discipline:** All mutating operations in `db/queries/comms.py` and `db/queries/app_settings.py` are wrapped with `with _get_write_lock(conn)`. No writes bypass the lock.
- **RRF formula:** `1.0 / (_RRF_K + rank)` with `_RRF_K = 60` matches SPEC §26.4 exactly. Sentinel rank 9999 for missing-from-one-list is correct. Sorting `reverse=True` is correct.
- **_FTS_AVAILABLE flag:** Set correctly after migrations complete (connection.py:121–124). Probed via `SELECT * FROM comms_fts LIMIT 0`. `search_by_keyword` guards on `_connection_module._FTS_AVAILABLE` before touching FTS5.
- **FTS5 trigger forms:** `comms_fts_ai` (after insert), `comms_fts_au` (delete + reinsert on update), `comms_fts_ad` (delete form) all use the correct FTS5 content-table trigger patterns. The `'delete'` command form is correct.
- **Trigger rowid mapping:** `comms_messages` has a TEXT primary key (`id`) but retains an implicit SQLite rowid. Triggers use `NEW.rowid`/`OLD.rowid` (implicit rowid), and `search_by_keyword` JOINs on `comms_fts.rowid = m.rowid`. Mapping is consistent.
- **`_PROJECT_WRITERS` / `_GLOBAL_WRITERS`:** Match SPEC §27.3 exactly (same 8-element and 2-element frozensets).
- **403 body shape:** `{"error": ..., "allowed_roles": [...]}` matches SPEC §27 requirement. `allowed_roles` is `sorted(...)` giving a deterministic list.
- **Default-deny for unknown roles on project/global:** `_check_write_permission` returns `False` for any role not in the relevant frozenset. Consistent with SPEC §27.2 row "`*` / unknown → Project ❌, Global ❌".
- **mode='semantic' regression:** The `mode='semantic'` branch in `comms_search()` still routes directly to `search_by_embedding`, unchanged from pre-Phase-12. No regression.
- **mode validation:** Invalid `mode` silently falls back to `'hybrid'` — consistent with IMPLEMENTATION_PLAN.md and test expectations.
- **No hardcoded credentials or secrets.**
- **No raw string interpolation in SQL** (all board/scope lists use `",".join("?" * len(...))` parameterization).
- **Duplicate-permission-table disconnect:** `_DEFAULT_WRITE_PERMISSIONS` in `app_settings.py` with `feature: ["*"]` and the live enforcement in `_check_write_permission` (always returns True for feature) are consistent in effect, even though they are not directly coupled.
