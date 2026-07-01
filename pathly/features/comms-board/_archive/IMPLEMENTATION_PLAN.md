---
name: Implementation Plan
---
# Comms Board (Phase 1 — Backend Core) — Implementation Plan

## Overview

Build the backend of the communication board: a sqlite-vec message store at three scopes,
an embedding worker, HTTP endpoints, SSE broadcast, and FSM prompt injection. The result —
a human posts a message to the board and the next agent reads it automatically in its
`## Communication Board` prompt block. No Studio changes; fully testable via curl.

## Layer Architecture

```
Plans (this file)            →  Orchestrator modules               →  Contracts / API
        ↓                               ↓                                     ↓
comms-board Phase 1          db/ + runner/ + http_server/          /comms/* + agent_hint
                                                                     ## Communication Board
```

```
db/migrations.py     comms_messages + comms_embeddings (vec0)        ← storage
db/queries/comms.py  post / get / search / acknowledge / trash       ← data access
runner/embeddings.py embed() + async worker + warm-up                ← semantics
http_server/         blueprints/comms.py + sse.py + streams.py       ← API + realtime
runner/comms_context retrieve_board_context() → markdown block       ← retrieval
fsm_ops.py           append block to agent_hint.instructions         ← injection
```

## Phases

### Phase 1: Dependencies   ← Conversation: 1
**File:** `pyproject.toml` — MODIFY: add `sqlite-vec==0.1.6` and `sentence-transformers>=2.7.0` to `[project].dependencies`
**Done when:** `pip install -e .` succeeds and `python -c "import sqlite_vec, sentence_transformers"` runs clean.
**Delivers stories:** S1.1, S1.2
**Depends on:** nothing
**Enables:** Phases 2–5
**Details:** Pin sqlite-vec exactly (`==0.1.6`) — the `FLOAT[384]` vec0 syntax is version-specific (CONSULTATION §1.2 Risk 4). sentence-transformers may use `>=`.
**Verify:** `python -c "import sqlite_vec, sentence_transformers; print('ok')"`

### Phase 2: Load sqlite-vec at connection time   ← Conversation: 1
**File:** `src/pathly_orchestrator/db/connection.py` — MODIFY: load the extension inside `get_db()` before `_run_migrations(conn)`
**Done when:** `get_db()` returns a connection on which `SELECT vec_version()` succeeds, and a missing extension degrades gracefully.
**Delivers stories:** S1.1
**Depends on:** Phase 1
**Enables:** Phase 3 (vec0 virtual table needs the extension loaded first)
**Details:** Sequence inside the `with _cache_lock` block, right after `PRAGMA` lines and **before** `_run_migrations(conn)`:
```python
try:
    conn.enable_load_extension(True)
    import sqlite_vec; sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    _VEC_AVAILABLE = True
except Exception:
    _VEC_AVAILABLE = False
    logging.warning("sqlite-vec unavailable — comms board uses recency-only retrieval")
```
Expose `_VEC_AVAILABLE` (module-level) so query helpers can branch. Critical ordering: extension load MUST precede migrations (CONSULTATION §1.2 Risk 1).
**Verify:** `python -c "from pathly_orchestrator.db.connection import get_db; print(get_db().execute('select vec_version()').fetchone())"`

### Phase 3: Comms tables migration   ← Conversation: 1
**File:** `src/pathly_orchestrator/db/migrations.py` — MODIFY: append `comms_messages` table + `comms_embeddings` vec0 virtual table
**Done when:** a fresh `get_db()` creates both tables; `SELECT` against each succeeds.
**Delivers stories:** S1.1
**Depends on:** Phase 2
**Enables:** Phase 4
**Details:** Use the exact schema in SPEC §21.1 (all lifecycle/artifact/task columns). Guard the vec0 `CREATE VIRTUAL TABLE` with `IF NOT EXISTS`; if `_VEC_AVAILABLE` is false, skip the virtual table creation (a plain fallback table is not needed — recency queries hit `comms_messages` directly). Bump the migration version counter if the file uses one.
**Verify:** `python -m pytest tests/ -q -k "migrat or comms"`

### Phase 4: Comms query helpers   ← Conversation: 1
**File:** `src/pathly_orchestrator/db/queries/comms.py` — CREATE; also MODIFY `db/queries/__init__.py` to re-export
**Done when:** posting a message then searching for it by text returns the row.
**Delivers stories:** S1.1
**Depends on:** Phase 3
**Enables:** Phases 6, 9
**Details:** Implement `post_message`, `get_messages`, `search_by_embedding`, `get_pending_decisions`, `acknowledge_message`, `answer_question`, `store_embedding`, `get_trash`, `restore_messages`, `purge_expired_trash`, `get_promotable_messages` (SPEC §21.2). `search_by_embedding` branches on `_VEC_AVAILABLE`: vec0 `vec_distance_cosine` when present, else `ORDER BY ts DESC LIMIT k`. Respect the `_get_write_lock(conn)` pattern for all writes.
**Verify:** `python -m pytest tests/ -q -k comms`

### Phase 5: Embedding worker   ← Conversation: 1
**File:** `src/pathly_orchestrator/runner/embeddings.py` — CREATE
**Done when:** `embed("hello")` returns a 384-float vector and the model loads only once.
**Delivers stories:** S1.2
**Depends on:** Phase 1
**Enables:** Phase 6 (post triggers embedding), Phase 9 (retrieval embeds the task)
**Details:** Lazy-load `SentenceTransformer("all-MiniLM-L6-v2")` into a module global; `embed(text) -> list[float]`. Add `embed_async(message_id, text)` that runs `embed` in a daemon thread and calls `store_embedding`. Add `warm()` that triggers the one-time load (called at server startup in Conv 2). Guard empty text.
**Verify:** `python -c "from pathly_orchestrator.runner.embeddings import embed; print(len(embed('hi')))"`  → prints `384`

---

### Phase 6: Comms HTTP blueprint   ← Conversation: 2
**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py` — CREATE
**Done when:** all 8 routes respond and `POST /comms/post` then `GET /comms` round-trips a message.
**Delivers stories:** S1.3
**Depends on:** Phase 4, Phase 5
**Enables:** Phase 8
**Details:** Routes (SPEC §21.3): `POST /comms/post`, `GET /comms`, `POST /comms/search`, `POST /comms/acknowledge`, `POST /comms/answer`, `POST /comms/attach` (stub returning 501 is acceptable this phase — artifacts are Phase 4 of SPEC), `GET /comms/trash`, `POST /comms/restore`. On post: store, call `embed_async`, broadcast (Phase 8). Validate required fields; 400 on missing. Follow the existing blueprint style in `blueprints/runner.py`.
**Verify:** `python -m pytest tests/ -q -k comms_api`

### Phase 7: Register blueprint + model warm-up   ← Conversation: 2
**File:** `src/pathly_orchestrator/http_server/app.py` — MODIFY: register comms blueprint; start a daemon warm-up thread
**Done when:** the server starts, `/comms` is reachable, and the embedding model warms in the background without blocking startup.
**Delivers stories:** S1.3, S1.2
**Depends on:** Phase 6
**Enables:** Phase 8
**Details:** `app.register_blueprint(comms_bp)` alongside the others. After registration, `threading.Thread(target=warm, daemon=True).start()` so the first real post isn't blocked by the ~1–2s model load (CONSULTATION §1.2 Risk 3).
**Verify:** start `pathly-fsm-http`, then `curl http://127.0.0.1:8765/comms?feature=demo` returns `[]`

### Phase 8: SSE comms channel   ← Conversation: 2
**File:** `src/pathly_orchestrator/http_server/sse.py` — MODIFY: add `_comms_clients` + `_broadcast_comms()`; **and** `blueprints/streams.py` — MODIFY: add `GET /events/comms`
**Done when:** a curl SSE client on `/events/comms?scope=demo` receives a `COMMS_UPDATE` when a message is posted to `demo`.
**Delivers stories:** S1.4
**Depends on:** Phase 6
**Enables:** Phase 2 of the Studio plan (future)
**Details:** Mirror `_runner_clients` / `_broadcast_runner`. `_comms_clients: dict[str, list]` keyed by scope; `_broadcast_comms(scope, event)` pushes to subscribers and never raises. `GET /events/comms` uses the same generator pattern as `/events/runner`. Wire `_broadcast_comms` into `POST /comms/post`.
**Verify:** terminal A: `curl -N http://127.0.0.1:8765/events/comms?scope=demo` ; terminal B posts a message → A prints a `COMMS_UPDATE` line

---

### Phase 9: Board retrieval + FSM injection   ← Conversation: 3
**File:** `src/pathly_orchestrator/runner/comms_context.py` — CREATE; also MODIFY `fsm_ops.py` to call it
**Done when:** posting a message to a feature board then calling `/next_action` yields a `## Communication Board` block containing that message in `agent_hint.instructions`.
**Delivers stories:** S2.1
**Depends on:** Phase 4, Phase 5, Phase 10 (board_scope)
**Enables:** the core value of Phase 1
**Details:** `retrieve_board_context(topic, project_root, task_description, board_scope) -> str`. Embed the task; query feature(k=3)/project(k=2)/global(k=1) for enabled boards only; always union pending decisions + escalations; format the markdown block per SPEC §11. In `fsm_ops.py build_prompt()` (after the `## Pipeline History` block, ~lines 195–199), append the returned block when non-empty. Keep it additive — empty board ⇒ unchanged prompt.
**Verify:** post via curl, run `pathly-fsm-call next-action --flow team --topic demo --project-root <root>`, assert output contains `## Communication Board`

### Phase 10: board_scope storage + filtering   ← Conversation: 3
**File:** `src/pathly_orchestrator/db/queries/app_settings.py` — MODIFY: add `get_board_scope` / `set_board_scope`
**Done when:** setting `{project:false}` for a feature removes project-board messages from its next injection.
**Delivers stories:** S2.2
**Depends on:** Phase 9
**Enables:** per-feature steering
**Details:** Store under `app_settings` key `board_scope:{project_root}:{feature}` as JSON. `get_board_scope` defaults to `{feature:true, project:true, global:true}` when absent. **Do not** store in STATE.json — `write_state()` does a full `INSERT OR REPLACE` and would drop the key (CONSULTATION §1.2 Risk 2). `retrieve_board_context()` reads board_scope and filters which boards it queries.
**Verify:** `python -m pytest tests/ -q -k board_scope`

## Prerequisites
- Python 3.10+ environment with the package installed editable (`pip install -e .`)
- `~/.pathly/pathly.db` writable (created on first `get_db()`)
- Platform SQLite built with `enable_load_extension` (else recency fallback path is exercised)

## Key Decisions
- **sqlite-vec over a separate vector service** — no new process; fits the existing single-DB model (SPEC §6.1).
- **board_scope in `app_settings`, not STATE.json** — avoids the `write_state()` full-replace merge bug (CONSULTATION §1.2 Risk 2).
- **Extension load before migrations** — the vec0 virtual table cannot be created otherwise (CONSULTATION §1.2 Risk 1).
- **Graceful degradation** — missing sqlite-vec ⇒ recency-only retrieval, never a hard failure (CONSULTATION §1.3).
- **Agents write to their own feature board only** — project/global writes need human confirmation; keeps high-scope boards high-signal (CONSULTATION §1.4 Q1). Enforced as a convention in Phase 1; hard-enforced in Phase 1.5 (Phase 13).
- **Embedding async + warm at startup** — `/comms/post` never blocks on the model (CONSULTATION §1.2 Risk 3).
- **`embed()` returns `list[float] | None`** — callers must check for `None` and fall back to recency retrieval.
- **Additive columns go in `_add_additive_migrations()`** — add new `(table, col, ctype)` tuples there, not standalone `ALTER TABLE` statements. The function guards with `try/except OperationalError` so re-runs are safe.
- **No `@require_secret` in comms blueprint** — authentication is applied at middleware level; the blueprint routes are not individually decorated.

---

## Phase 1.4 — Retrieval Correctness (PRs 1–4)

> **Ship BEFORE Phase 1.5.** These fix correctness bugs in the already-deployed Phase 1 retrieval.
> Adding new features (hybrid search, DAG) on top of broken retrieval makes things worse, not better.
> All four phases are independent — Phase 1.4d should be bundled with Phase 1.4a since both touch migrations.
>
> Full descriptions of each PR in `docs/BOARD_RETRIEVAL_IMPROVEMENTS.md`.

---

### Phase 1.4a: PR1 — `superseded_by` column + supersede route   ← Conversation: 4

**File:** `src/pathly_orchestrator/db/migrations.py` — MODIFY: add `("comms_messages", "superseded_by", "TEXT")` to `_add_additive_migrations()`  
**File:** `src/pathly_orchestrator/db/queries/comms.py` — MODIFY: `get_pending_decisions()` + add `supersede_message()`  
**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py` — MODIFY: add `POST /comms/supersede` route  
**Done when:** a decision marked `superseded_by=<new_id>` no longer appears in the `## Communication Board` block at `/next_action`.  
**Delivers stories:** S1.4a  
**Depends on:** Phase 10 (board already deployed)  
**Enables:** Phase 1.4c (escalation fetcher can also filter on `superseded_by IS NULL`)

**Details:**

Migration — add to `_add_additive_migrations()` in `migrations.py` (the existing list of `(table, col, ctype)` tuples):
```python
("comms_messages", "superseded_by", "TEXT"),
```
No separate `ALTER TABLE` statement needed — the helper handles the try/except OperationalError guard already.

`get_pending_decisions()` update — add one clause to the WHERE:
```python
# BEFORE (line ~129 in comms.py)
"AND type='decision' AND status='pending' AND deleted_at IS NULL "

# AFTER
"AND type='decision' AND status='pending' AND deleted_at IS NULL "
"AND (superseded_by IS NULL OR superseded_by = '') "
```

New helper `supersede_message(conn, old_id, new_id)`:
```python
def supersede_message(conn, old_id: str, new_id: str) -> str:
    """Mark old_id as superseded by new_id. Returns 'ok'|'not_found'|'already_superseded'."""
    row = conn.execute(
        "SELECT superseded_by FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (old_id,)
    ).fetchone()
    if row is None:
        return "not_found"
    if row["superseded_by"]:
        return "already_superseded"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET superseded_by=? WHERE id=?",
            (new_id, old_id)
        )
        conn.commit()
    return "ok"
```

New route `POST /comms/supersede` in `blueprints/comms.py`:
```python
@bp.route("/comms/supersede", methods=["POST"])
def comms_supersede():
    """Mark a decision as superseded by a newer one.
    Required body: {old_id: str, new_id: str}
    Returns 200 {ok:true} | 404 not found | 409 already superseded
    """
```

**Verify:**
```bash
# Post old decision, post new decision, supersede old
curl -X POST http://127.0.0.1:8765/comms/supersede \
  -d '{"old_id":"<old>","new_id":"<new>"}'
# Then call /next_action — old decision should NOT appear in ## Communication Board
python -m pytest tests/ -q -k comms_supersede
```

---

### Phase 1.4b: PR2 — write-time curation filter   ← Conversation: 4

**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py` — MODIFY: add `_EMBED_TYPES` frozenset; wrap `_embed_async` call  
**Done when:** posting a `status` message produces NO embedding row in `comms_embeddings`; posting a `decision` message DOES.  
**Delivers stories:** S1.4b  
**Depends on:** Phase 1.4a (share the same conversation)  
**Enables:** Phase 11 (hybrid search over a cleaner embedding pool)

**Details:**

Add module-level constant in `blueprints/comms.py`:
```python
_EMBED_TYPES: frozenset[str] = frozenset({
    "decision", "discovery", "constraint", "warning", "escalation", "artifact"
})
```

In `comms_post()`, change line 82 from:
```python
_embed_async(message_id, text)
```
to:
```python
if msg_type in _EMBED_TYPES:
    _embed_async(message_id, text)
```

One conditional. Zero schema changes. The recency fallback path in `search_by_embedding` is unaffected — it queries `comms_messages` directly, not `comms_embeddings`.

**Verify:**
```bash
python -m pytest tests/ -q -k comms_embed_curation
# Manual: post a 'status' message, then query comms_embeddings for its id — expect no row
```

---

### Phase 1.4c: PR3 — labeled governance/semantic channels   ← Conversation: 4

**File:** `src/pathly_orchestrator/db/queries/comms.py` — MODIFY: add `get_active_escalations()`  
**File:** `src/pathly_orchestrator/runner/comms_context.py` — MODIFY: restructure `## Communication Board` block into two labeled channels  
**Done when:** `/next_action` response contains a `🔒 Governance` section (decisions + escalations) and a `💡 Context` section (semantic matches), each with distinct labels and advisory caveats.  
**Delivers stories:** S1.4c  
**Depends on:** Phase 1.4a (`superseded_by IS NULL` filter needed in both decision + escalation queries)  
**Enables:** Phase 11 (cleaner retrieval is most visible with labeled channels)

**Details:**

New helper `get_active_escalations(conn, boards, scopes)` in `comms.py`:
```python
def get_active_escalations(conn, boards, scopes):
    """Return all unresolved escalation messages for the given boards/scopes."""
    if not boards or not scopes:
        return []
    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT * FROM comms_messages "
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        "AND type='escalation' AND status='pending' AND deleted_at IS NULL "
        "AND (superseded_by IS NULL OR superseded_by = '') "
        "ORDER BY ts ASC"
    )
    return [dict(r) for r in conn.execute(sql, list(boards) + list(scopes)).fetchall()]
```

`comms_context.py` — replace the current markdown block builder with two labeled sections:
```
🔒 Governance (always applies — do not override)
  Active decisions and open escalations injected unconditionally.

  Decisions:
    • <text>  [feature · 2d ago]

  Open escalations (human input required):
    • <text>  [feature · 1h ago]

---

💡 Context (possibly relevant — verify before acting)
  Semantic matches for this task. Inform but do not override governance above.

  • <text>  [builder → *, BUILDING, 3h ago]
```

The restructuring spans two logical blocks in `comms_context.py` (lines ~192–240):
- **Partition block (lines ~192–208):** Splits retrieved messages into `decisions / context_msgs / questions`. Must be extended to also call `get_active_escalations()` and partition escalations into a separate list.
- **Markdown builder (lines ~214–240):** Renders `### 📌 Decisions`, `### 💬 Recent context`, `### ❓ Open questions`. Replace entirely with the two-channel structure.
Both blocks must change — replacing only the markdown builder (lines 222–240) will leave the escalation partitioning logic untouched and escalations will still fall through to the semantic pool.

**Verify:**
```bash
# Post a decision and an escalation, run /next_action
# Confirm: decision appears under 🔒 Governance
# Confirm: a soft context message appears under 💡 Context with "verify before acting" label
python -m pytest tests/ -q -k comms_context_channels
```

---

### Phase 1.4d: PR4 — remove dead promotion code   ← Conversation: 4 (bundle with 1.4a)

**File:** `src/pathly_orchestrator/db/queries/comms.py` — MODIFY: delete `get_promotable_messages()`  
**File:** `src/pathly_orchestrator/db/migrations.py` — MODIFY: add comment to `promoted_to/promoted_from/original_scope` columns marking them reserved  
**Done when:** `get_promotable_messages` no longer exists in the module.  
**Delivers stories:** S1.4d  
**Depends on:** Phase 1.4a (open migration is already being touched)

**Details:**

Delete lines 257–269 in `comms.py` (the `get_promotable_messages` function). The `promoted_to`, `promoted_from`, and `original_scope` columns in `comms_messages` stay in the schema (dropping SQLite columns is a table-rebuild, not worth the risk) — add a comment in the CREATE TABLE statement noting they are "reserved for future promotion feature."

`db/queries/__init__.py` — remove the re-export of `get_promotable_messages` if present.
(In the current codebase `__init__.py` does `from . import comms` at module level, not a named
re-export — so this step is likely a no-op. Check anyway with `grep get_promotable_messages db/queries/__init__.py`.)

**Verify:**
```bash
python -c "from pathly_orchestrator.db.queries.comms import get_promotable_messages"
# Should raise ImportError
```

---

## Phase 1.5 — Retrieval Quality, Permissions, DAG Tasks

> Ship after Phase 1.4 (retrieval correctness) and before Phase 2 (Studio UI).
> Phase 14 (DAG tasks) is deferred — it requires Phase 3 skill integration to be useful.
> Phases 11–13 are each independently deployable.

---

### Phase 11: FTS5 virtual table + hybrid search helpers   ← Conversation: 5

**File:** `src/pathly_orchestrator/db/migrations.py` — MODIFY: add FTS5 virtual table creation in `_run_migrations()` (guarded like `comms_embeddings`); add `_FTS_AVAILABLE` flag in `connection.py`  
**File:** `src/pathly_orchestrator/db/queries/comms.py` — MODIFY: add `search_by_keyword()` and `search_by_hybrid()`  
**Done when:** `search_by_hybrid(conn, "setupWebGL crash", embedding, ["feature"], ["demo"], k=3)` returns a row whose text contains "setupWebGL".  
**Delivers stories:** S3.1  
**Depends on:** Phase 1.4b (write-time curation ensures only high-value messages are in the embedding pool)  
**Enables:** Phase 12

**Details:**

`connection.py` — add `_FTS_AVAILABLE` flag alongside `_VEC_AVAILABLE` (mirror the same pattern):
```python
# After _run_migrations(conn) — comms_fts is created there, so the probe MUST run
# AFTER migrations, NOT after the sqlite-vec load block (comms_fts doesn't exist yet there).
try:
    conn.execute("SELECT * FROM comms_fts LIMIT 0")
    _FTS_AVAILABLE = True
except Exception:
    _FTS_AVAILABLE = False
```

`migrations.py` — in `_run_migrations()`, after the `comms_embeddings` vec0 block, add:
```python
if True:   # FTS5 is bundled with SQLite on all platforms — no flag needed at creation time
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS comms_fts "
            "USING fts5(text, content=comms_messages, content_rowid=rowid, tokenize='porter ascii')"
        )
        conn.commit()
    except Exception:
        pass
```

`comms.py` — import `_FTS_AVAILABLE` from connection (add alongside `_VEC_AVAILABLE`). Add:

`search_by_keyword(conn, query_text, boards, scopes, k)` — follows existing `search_by_embedding` signature pattern:
```python
def search_by_keyword(conn, query_text: str, boards: list[str], scopes: list[str], k: int = 6):
    if not _FTS_AVAILABLE or not boards or not scopes:
        return []
    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT m.* FROM comms_messages m "
        "JOIN comms_fts ON comms_fts.rowid = m.rowid "
        f"WHERE comms_fts MATCH ? AND m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
        "AND m.deleted_at IS NULL "
        "ORDER BY rank LIMIT ?"   # FTS5 rank is BM25; lower is better
    )
    rows = conn.execute(sql, [query_text] + list(boards) + list(scopes) + [k]).fetchall()
    return [dict(r) for r in rows]
```

`search_by_hybrid(conn, query_text, query_embedding, boards, scopes, k)` — RRF merge:
```python
_RRF_K = 60

def search_by_hybrid(conn, query_text: str, query_embedding: list[float] | None,
                     boards: list[str], scopes: list[str], k: int = 6):
    """BM25 + cosine merged via Reciprocal Rank Fusion. Falls back to semantic or recency."""
    bm25_rows = search_by_keyword(conn, query_text, boards, scopes, k * 2) if query_text else []
    sem_rows  = search_by_embedding(conn, query_embedding, boards, scopes, k * 2) \
                if query_embedding is not None else []

    if not bm25_rows and not sem_rows:
        return []

    scores: dict[str, dict] = {}
    for rank, row in enumerate(bm25_rows):
        mid = row["id"]
        scores.setdefault(mid, {"row": row, "bm25": 9999, "sem": 9999})
        scores[mid]["bm25"] = rank
    for rank, row in enumerate(sem_rows):
        mid = row["id"]
        scores.setdefault(mid, {"row": row, "bm25": 9999, "sem": 9999})
        scores[mid]["sem"] = rank

    ranked = sorted(
        scores.values(),
        key=lambda x: 1.0/(_RRF_K + x["bm25"]) + 1.0/(_RRF_K + x["sem"]),
        reverse=True,
    )
    return [r["row"] for r in ranked[:k]]
```

**Verify:**
```bash
python -m pytest tests/ -q -k comms_hybrid
# Manual: post a message with 'setupWebGL' in text, run search_by_hybrid with
# query_text='setupWebGL', assert that message ranks first
```

---

### Phase 12: Switch API and retrieval to hybrid mode   ← Conversation: 5

**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py` — MODIFY: add `mode` param to `comms_search()`  
**File:** `src/pathly_orchestrator/runner/comms_context.py` — MODIFY: call `search_by_hybrid` instead of `search_by_embedding`  
**Done when:** `POST /comms/search {"mode":"keyword","query":"setupWebGL",...}` returns keyword-ranked results; default mode returns hybrid results.  
**Delivers stories:** S3.1  
**Depends on:** Phase 11  
**Enables:** Phase 13

**Details:**

`comms_search()` in `blueprints/comms.py` — add `mode` field (default `'hybrid'`) to the request body parse:
```python
mode = data.get("mode", "hybrid")
if mode not in ("hybrid", "semantic", "keyword"):
    mode = "hybrid"
```
Replace the current `_search(conn, embedding=embedding, ...)` call with a branch:
```python
if mode == "keyword":
    results = search_by_keyword(conn, query, [board], [scope], k)
elif mode == "semantic":
    results = _search(conn, embedding, [board], [scope], k) if embedding else get_messages(...)
else:  # hybrid
    results = search_by_hybrid(conn, query, embedding, [board], [scope], k)
```
Note: `embed()` returns `None` when model is unavailable — the hybrid function handles `None` gracefully.

`retrieve_board_context()` in `comms_context.py` — change the per-board retrieval loop (lines ~154–169) to call `search_by_hybrid` instead of `search_by_embedding`.

Add `search_by_hybrid` to the **lazy import block inside the function** (lines ~131–134), alongside the existing `get_pending_decisions` and `search_by_embedding` imports — NOT inside the for-loop body:
```python
# Inside retrieve_board_context(), in the existing lazy import try-block (lines ~131-134)
from pathly_orchestrator.db.queries.comms import (
    get_pending_decisions,
    search_by_embedding,
    search_by_hybrid,   # ← add this
)
```
Then in the per-board loop, replace the `search_by_embedding` call:
```python
rows = search_by_hybrid(conn, task_description, task_embedding, [board_type], [scope_val], k)
```
`task_description` is already the function parameter; `task_embedding` is already computed above the loop. `query_embedding=None` is handled gracefully inside `search_by_hybrid` (falls back to keyword-only).

**Verify:**
```bash
python -m pytest tests/ -q -k comms_search_mode
```

---

### Phase 13: Role-based write permissions   ← Conversation: 5

**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py` — MODIFY: add `_PROJECT_WRITERS`/`_GLOBAL_WRITERS` + check in `comms_post()`; add `GET /comms/permissions`  
**File:** `src/pathly_orchestrator/db/queries/app_settings.py` — MODIFY: add `get_write_permissions()` / `set_write_permissions()`  
**Done when:** `POST /comms/post` with `from='builder'` and `board='global'` returns **403**; with `board='feature'` returns **200**.  
**Delivers stories:** S3.2  
**Depends on:** Phase 12  
**Enables:** Phase 14 (deferred — see note below)

**Details:**

Add module-level constants in `blueprints/comms.py` (no `@require_secret` decorator — auth is middleware-level):
```python
_PROJECT_WRITERS: frozenset[str] = frozenset({
    "tester", "reviewer", "explorer", "architect",
    "planner", "designer", "director", "human",
})
_GLOBAL_WRITERS: frozenset[str] = frozenset({"director", "human"})

def _check_write_permission(from_agent: str, board: str) -> bool:
    if board == "feature":
        return True
    if board == "project":
        return from_agent in _PROJECT_WRITERS
    if board == "global":
        return from_agent in _GLOBAL_WRITERS
    return False
```

In `comms_post()`, add after the `board` and `from_agent` variables are resolved (~line 60):
```python
if not _check_write_permission(from_agent, board):
    allowed = sorted(_GLOBAL_WRITERS if board == "global" else _PROJECT_WRITERS)
    return jsonify({
        "error": f"Role '{from_agent}' cannot write to '{board}' scope",
        "allowed_roles": allowed,
    }), 403
```

`app_settings.py` — add `get_write_permissions(conn, project_root)` and `set_write_permissions(conn, project_root, overrides)` storing under key `write_permissions:{project_root}`. `get_write_permissions` returns the default table merged with any project override.

`GET /comms/permissions?project_root=<root>` — new route returning the resolved permission table.

**Verify:**
```bash
# feature scope — always allowed
curl -X POST http://127.0.0.1:8765/comms/post \
  -H 'Content-Type: application/json' \
  -d '{"feature":"demo","from":"builder","type":"status","text":"hello"}'
# → 200

# global scope — builder blocked
curl -X POST http://127.0.0.1:8765/comms/post \
  -H 'Content-Type: application/json' \
  -d '{"board":"global","scope":"global","from":"builder","type":"decision","text":"bad"}'
# → 403 {"error":"Role 'builder' cannot write to 'global' scope","allowed_roles":["director","human"]}

python -m pytest tests/ -q -k comms_write_perm
```

---

---

## ══════════════ BACKEND COMPLETE ══════════════

> All source code work for this plan ends at Phase 13.
> Conv 6 (below) contains no code changes — it is the handoff and RETRO only.
>
> **What the backend delivers (curl-testable, zero Studio changes):**
> - Full comms board HTTP API (post, search, acknowledge, trash, restore, SSE)
> - Semantic embedding + retrieval injected into every `/next_action` call
> - Retrieval correctness: stale decisions suppressed, noise not embedded, labeled channels
> - Hybrid BM25 + semantic search (FTS5 + cosine via RRF)
> - Role-based write permissions (feature unrestricted; project/global gated)
>
> **What comes next (separate plan folders, frontend gated on design):**
> - `comms-board-skills` → Phase 3: builder/planner skill updates + DAG Phase 14
> - `comms-board-studio` → Phase 2: Studio UI (PENDING design consultation)
> - `board-storm` → Phase 5: Board-Storm consultation mode
> - `comms-board-command-center` → Phase 4: Command Center canvas

---

### Phase 14: DAG task `depends_on` + ready endpoint   ← DEFERRED

> **⚠️ Deferred to Phase 3 skill integration.** Phase 14 is complete infrastructure but no agent
> calls it until the builder skill is updated to use `GET /comms/tasks?ready=true` instead of
> reading from `CONVERSATION_PROMPTS.md`. Shipping this endpoint before Phase 3 skill updates
> creates infrastructure with no consumer. Bundle Phase 14 with the Phase 3 builder skill update.
>
> Full design: SPEC §28. Stories: S3.3.

**Files to touch (when deferred work begins):**
- `db/migrations.py` — add `("comms_messages", "depends_on", "TEXT DEFAULT '[]'")` to `_add_additive_migrations()`
- `db/queries/comms.py` — add `get_ready_tasks(conn, board, scope)` (see SPEC §28.6)
- `http_server/blueprints/comms.py` — add `GET /comms/tasks` and `POST /comms/tasks/complete`
