# Live Communication Board — Architecture & Implementation Spec

Status: DESIGN_SPEC for GAP 2 (resolve→FSM), GAP 4 (search / supersede / attach), GAP 3 (async question loop).
Audience: a builder who must execute without re-discovering anything. Every claim below is anchored to a `file:line` in the current code.

---

## 1. Architecture overview

### 1.1 The four loops

The board is a non-blocking advisory mirror layered on top of the FSM. It has four data/control flows. The first two already ship; this spec adds the last two.

```
                         COMMUNICATION BOARD — DATA / CONTROL FLOW
 ════════════════════════════════════════════════════════════════════════════

 WRITE PATH  (agent → board)                            [SHIPPED — Gap 1]
   agent (comms-post.md fragment)
        │  curl POST /comms/post  {feature,from,type,text,board,stage}
        ▼
   comms.py:45 comms_post ──► queries/comms.py:18 post_message
        │                          (INSERT comms_messages)
        ├─► _embed_async (hybrid-search index)           comms.py:134
        └─► _broadcast_comms(scope, COMMS_UPDATE)         comms.py:137

 READ PATH  (board → agent prompt)                       [SHIPPED]
   runner/comms_context.py  ──► assembled into agent_hint.instructions
        (every /next_action re-injects the board context)

 ──────────────────────────────────────────────────────────────────────────────

 HUMAN-ACTION PATH  (human → board → FSM)                [GAP 2 — THIS SPEC]
   CardBody resolve buttons (block│note│ignore)          CardBody.tsx:73-83
        │  onResolve(id, mode)
        ▼
   useCommsPanel.resolve ──► commsStore.resolve(id, mode) commsStore.ts:150
        │
        ├─(1)─► POST /comms/acknowledge {message_id, agent:'you'}   (mark handled)
        ├─(2)─► POST /comms/post type=decision   (ONLY when mode==='note')
        └─(3)─► POST /runner/decision {topic, decision}             (drive FSM)
                     decision = block→'block' · note/ignore→'continue'
                     topic    = useRunnerStore.getState().topic
                     guard    = only when status==='awaiting_decision'

 MANAGEMENT PATH  (human curates board)                  [GAP 4 — THIS SPEC]
   Search   SearchBar ─► store.search ─► POST /comms/search  → overlay list
   Supersede overflow menu ─► store.supersede ─► POST /comms/supersede
   Attach   CommsInput paperclip ─► store.attach ─► POST /comms/attach
                                       └─ backend: 501 STUB → REAL (this spec)

 ASYNC QUESTION LOOP  (agent ↔ human)                    [GAP 3 — THIS SPEC]
   Part A  agent posts type=question/options   (comms-post.md addition)
   Part A  human answers ─► store.answer ─► POST /comms/answer  [SHIPPED]
   Part B  answer → /runner/agent-answer       [STRETCH — out of scope]
```

### 1.2 Design principles (binding constraints for every change below)

1. **Advisory / non-blocking.** A board action never blocks the pipeline. Every network call is best-effort (`.catch(() => {})`) and the optimistic UI stands even if the POST fails. This mirrors the existing `resolve`/`answer`/`post` pattern at `commsStore.ts:128,147,170,202,212`.
2. **Single source of truth = the FSM, not the board.** The board records and *signals*; the FSM owns stage transitions. Gap 2 therefore must route the *real* transition through `POST /runner/decision` (`runner.py:263`), never simulate it by mutating `features[].stage` only. The current `resolve()` fakes the stage transition locally (`commsStore.ts:163-167`) — that local guess is replaced by the real FSM call plus optimistic UI.
3. **Optimistic UI + reconcile via SSE.** Mutate local state first, fire the POST, and let the `COMMS_UPDATE` SSE (`useCommsPanel.ts:39`) trigger `loadBoard()` to reconcile against authoritative rows. Server-authored fields (`superseded_by`, `artifact_*`, `acknowledged_by`) arrive on the next board reload — do not hand-roll them as permanent local truth.
4. **Role-gated writes already enforced server-side.** `_check_write_permission` (`comms.py:23-42`) governs project/global writes. The UI always posts as `from:'human'`, which is in both `_PROJECT_WRITERS` and `_GLOBAL_WRITERS` (`comms.py:16-20`), so human-driven posts (the `note` decision, attach metadata) are never 403'd. No new permission code is needed.

### 1.3 Obtaining the active run (the GAP 2 linchpin)

The FSM decision gate is keyed by **topic alone** — `run_id` is an internal orchestrator detail (`runner.py:263-303` validates `topic` + `decision`, never `run_id`). The board's feature → topic mapping is:

- `useRunnerStore.getState().topic` holds the active run's topic, set by `setRunnerConfig` (`runnerStore.ts:126`) on `RUN_STARTED`.
- A board feature is the *active run* only when `runnerStore.topic === <board feature id>` **and** the runner is `awaiting_decision`.
- To check liveness without guessing, `GET /runner/status?topic=<feature>` returns `public_dict()`; act only when `status === 'awaiting_decision'` and `pending_menu` is present.

This produces the central edge-case rule for Gap 2: **resolve always acknowledges + (optionally) posts the note decision; it only fires `/runner/decision` when the board's feature is the topic of an `awaiting_decision` run.** Otherwise the resolve is a pure board annotation (acknowledge + optimistic resolve), which is correct — a warning can be triaged after the gate has already passed.

---

## 2. File-by-file change spec

Work is partitioned into **two non-overlapping streams**. Stream A is pure Python (backend). Stream B is pure TypeScript (studio renderer). They share **no files**, so they can run fully in parallel. Within each stream, follow the stated ordering.

> Shared contract between streams (freeze this first): `POST /comms/attach` body is
> `{ message_id, artifact_path, artifact_type, artifact_url? }`, returns `{ ok: true, message_id }` on 200,
> `404` if message missing, `400` on bad input. Both streams code to this contract independently.

---

### STREAM A — Backend (Python)

Three files, in this order: (A1) DB query helper → (A2) HTTP handler → (A3) test. A2 imports A1, so A1 lands first.

#### A1 — `src/pathly_orchestrator/db/queries/comms.py`

Add a new update helper next to `acknowledge_message` (current def at `comms.py:251-270`). It follows the exact validate-then-write-locked-UPDATE shape used by `supersede_message` (`comms.py:212-228`).

```python
def attach_artifact_to_message(
    conn: sqlite3.Connection,
    message_id: str,
    artifact_path: str | None = None,
    artifact_type: str | None = None,
    artifact_url: str | None = None,
) -> str:
    """Set artifact_* fields on an existing message.

    Returns 'ok' | 'not_found'. Mirrors supersede_message()'s status-string
    contract (comms.py:212) so the route can map to 404 cleanly.
    Reuses the already-present artifact_path / artifact_type / artifact_url
    columns (migrations.py:237-239); never creates a new row.
    """
    row = conn.execute(
        "SELECT board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None:
        return "not_found"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages "
            "SET artifact_path=?, artifact_type=?, artifact_url=? WHERE id=?",
            (artifact_path, artifact_type, artifact_url, message_id),
        )
        conn.commit()
    return "ok"
```

Notes:
- `_get_write_lock` and `sqlite3` are already imported at the top of this file (`comms.py:5,11`).
- Return `board`/`scope` lookup is done so the route can broadcast to the correct scope (see A2). We only need the status string out of the function, but the SELECT confirms existence; the route does its own SELECT for scope OR we widen the return. To keep it simple, the route re-reads scope — see A2.

#### A2 — `src/pathly_orchestrator/http_server/blueprints/comms.py`

Replace the 501 stub at `comms.py:389-392` with a real handler. Model it on `comms_supersede` (`comms.py:445-476`) for status-string→HTTP mapping and on `comms_post` (`comms.py:137-144`) for the broadcast shape.

```python
@bp.route("/comms/attach", methods=["POST"])
def comms_attach():
    """Attach a file or URL artifact to an existing message.

    Required body fields: message_id, and at least one of artifact_path / artifact_url.
    Optional: artifact_type ('md'|'code'|'pdf'|'image'|'json'|'url'|'snippet').
    Returns 200 {ok, message_id} | 400 bad input | 404 message not found.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            attach_artifact_to_message as _attach,
        )

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return jsonify({"error": "Field 'message_id' must be a non-empty string"}), 400

        artifact_path = data.get("artifact_path")
        artifact_url = data.get("artifact_url")
        artifact_type = data.get("artifact_type")

        # Must supply at least one of path/url; both blank is a no-op error.
        has_path = isinstance(artifact_path, str) and artifact_path.strip()
        has_url = isinstance(artifact_url, str) and artifact_url.strip()
        if not has_path and not has_url:
            return jsonify({
                "error": "Provide at least one of 'artifact_path' or 'artifact_url'"
            }), 400
        if artifact_type is not None and not isinstance(artifact_type, str):
            return jsonify({"error": "Field 'artifact_type' must be a string or null"}), 400

        conn = _get_db()
        # Re-read board/scope for the broadcast (the row must exist for a valid attach).
        row = conn.execute(
            "SELECT board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        if row is None:
            return jsonify({"ok": False, "error": "Message not found"}), 404

        result = _attach(
            conn,
            message_id=message_id,
            artifact_path=artifact_path if has_path else None,
            artifact_type=artifact_type,
            artifact_url=artifact_url if has_url else None,
        )
        if result == "not_found":
            return jsonify({"ok": False, "error": "Message not found"}), 404

        _broadcast_comms(row["scope"], {
            "type": "COMMS_UPDATE",
            "message_id": message_id,
            "event": "artifact_attached",
            "board": row["board"],
            "scope": row["scope"],
            "artifact_type": artifact_type,
        })

        return jsonify({"ok": True, "message_id": message_id}), 200
    except Exception as exc:
        logging.exception("comms_attach error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
```

Design choices (and the trade-off):
- **No filesystem existence check.** The current-state map flagged "verify artifact exists on disk / HTTP HEAD" as a possible step. I deliberately omit it: attach is advisory metadata on a message; the renderer sends a path/URL the human picked, and a HEAD round-trip per attach is latency the non-blocking principle forbids. We validate *shape*, not *reachability*. If a future requirement needs reachability it belongs in a separate validator, not the hot path.
- `_broadcast_comms` is already imported at module top (`comms.py:8`) — no new import.
- The `row` re-read is intentional and cheap; it gives us the authoritative `scope` to broadcast to so subscribed panels reconcile (`useCommsPanel.ts:39` reloads on `COMMS_UPDATE`).

#### A3 — `tests/test_comms_attach.py` (new file)

Mirror `test_comms_supersede.py` exactly (fixtures, the `_no_async_embed` autouse stub at `test_comms_supersede.py:13-21`, the `client` fixture at `:24-31`). Add:

```python
"""Tests for POST /comms/attach — real artifact attachment onto an existing
message row, reusing the artifact_* columns (migrations.py:237-239)."""
from __future__ import annotations

import json
import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod
    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_artifact_holder(client) -> str:
    r = client.post("/comms/post", json={
        "feature": "demo", "from": "human", "type": "artifact",
        "text": "DESIGN.md draft", "board": "feature", "scope": "demo",
    })
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


def test_attach_path_sets_columns_and_returns_ok(client):
    mid = _post_artifact_holder(client)
    r = client.post("/comms/attach", json={
        "message_id": mid,
        "artifact_path": "pathly/plans/demo/DESIGN.md",
        "artifact_type": "md",
    })
    assert r.status_code == 200
    body = json.loads(r.data)
    assert body["ok"] is True and body["message_id"] == mid

    # GET the board back; the row must now carry artifact_path/type.
    g = client.get("/comms?feature=demo&board=feature&scope=demo")
    rows = json.loads(g.data)
    row = next(x for x in rows if x["id"] == mid)
    assert row["artifact_path"] == "pathly/plans/demo/DESIGN.md"
    assert row["artifact_type"] == "md"


def test_attach_url_only_is_allowed(client):
    mid = _post_artifact_holder(client)
    r = client.post("/comms/attach", json={
        "message_id": mid, "artifact_url": "https://example.com/spec",
    })
    assert r.status_code == 200


def test_attach_missing_message_returns_404(client):
    r = client.post("/comms/attach", json={
        "message_id": "no-such-id", "artifact_path": "x.md",
    })
    assert r.status_code == 404
    assert json.loads(r.data)["ok"] is False


def test_attach_validation(client):
    assert client.post("/comms/attach", json={}).status_code == 400
    # message_id present but no path/url:
    mid = _post_artifact_holder(client)
    assert client.post("/comms/attach", json={"message_id": mid}).status_code == 400


def test_attach_helper_directly():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message, attach_artifact_to_message
    conn = get_db()
    mid = post_message(conn, board="feature", scope="t", from_agent="human",
                       type="artifact", text="x")
    assert attach_artifact_to_message(conn, mid, artifact_path="a.md", artifact_type="md") == "ok"
    assert attach_artifact_to_message(conn, "no-such", artifact_path="a.md") == "not_found"
```

> The `GET /comms` round-trip in `test_attach_path_sets_columns_and_returns_ok` confirms the columns are actually persisted and surfaced in the row shape the renderer consumes (`CommsRow` at `commsApi.ts:25-45` already declares `artifact_path/type/url`).

---

### STREAM B — Studio (TypeScript renderer)

Order within the stream: (B1) `commsApi.ts` adds the four HTTP helpers → (B2) `commsStore.ts` adds the store actions that call them → (B3..B6) components wire the UI to the store. B2 imports from B1; B3-B6 import from B2. Do B1→B2 first, then the four component files in any order.

#### B1 — `studio/src/renderer/src/store/commsApi.ts`

Append four helpers after `apiDelete` (current last export at `commsApi.ts:211-222`). All use `apiFetch` (`lib/config.ts:17`), matching the existing helper shape.

```typescript
// ── GAP 2: resolve → FSM decision gate ───────────────────────────────
// Drives the real FSM transition. topic is the active run's topic
// (runnerStore.topic). decision must be a key in the run's pending_menu.options
// — for warning/escalation gates that is 'block' | 'continue' (runner.py:263).
export async function apiRunnerDecision(topic: string, decision: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/runner/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, decision }),
    })
    return r.ok
  } catch {
    return false
  }
}

// Liveness probe: is <topic> a run currently awaiting a decision?
// Returns the decision-key set when so, else null. (runner.py:483 GET /runner/status)
export async function apiRunnerAwaitingDecision(topic: string): Promise<string[] | null> {
  try {
    const r = await apiFetch(`/runner/status?topic=${encodeURIComponent(topic)}`)
    if (!r.ok) return null
    const s = await r.json() as { status?: string; pending_menu?: { options?: Record<string, string> } }
    if (s.status !== 'awaiting_decision' || !s.pending_menu?.options) return null
    return Object.keys(s.pending_menu.options)
  } catch {
    return null
  }
}

// ── GAP 4(a): hybrid search ──────────────────────────────────────────
export async function apiSearch(
  query: string,
  feature: string,
  board: string,
  scope: string,
): Promise<Message[]> {
  try {
    const r = await apiFetch(`/comms/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, feature, board, scope, mode: 'hybrid' }),
    })
    if (!r.ok) return []
    const rows = await r.json() as CommsRow[]
    return rows.map(rowToMessage)
  } catch {
    return []
  }
}

// ── GAP 4(b): supersede ──────────────────────────────────────────────
export async function apiSupersede(oldId: string, newId: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/supersede`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_id: oldId, new_id: newId }),
    })
    return r.ok
  } catch {
    return false
  }
}

// ── GAP 4(c): attach ─────────────────────────────────────────────────
export async function apiAttach(
  messageId: string,
  artifactPath: string,
  artifactType?: Message['atype'],
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/attach`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message_id: messageId,
        artifact_path: artifactPath,
        artifact_type: artifactType ?? null,
      }),
    })
    return r.ok
  } catch {
    return false
  }
}
```

Note: `rowToMessage`, `CommsRow`, `Message`, `apiFetch` are all already in this file's scope (`commsApi.ts:1,4,25,87`). The exact body keys (`old_id/new_id` for supersede `comms.py:460-461`; `query/feature/board/scope/mode` for search `comms.py:212-229`; `message_id/artifact_path/artifact_type` for attach per Stream A) match the backend contracts verbatim.

#### B2 — `studio/src/renderer/src/store/commsStore.ts`

Three changes.

**(i)** Import the new helpers (extend the import block at `commsStore.ts:3-15`):

```typescript
import {
  fetchBoard, apiPost, apiAnswer, apiAcknowledge, apiToggleScope, apiDelete,
  scopeToParams, buildFeature, fetchFeatureState, featureBlocked, fetchLastSummary,
  // NEW:
  apiRunnerDecision, apiRunnerAwaitingDecision, apiSearch, apiSupersede, apiAttach,
} from './commsApi'
```

**(ii)** Extend the `CommsState` interface (`commsStore.ts:30-48`). Replace the `resolve` signature so it becomes async (it now awaits the liveness probe) and add four actions plus a search-results slot:

```typescript
  // GAP 2 — resolve now reaches the FSM. Returns a promise so callers may await,
  // but the UI never blocks on it (handlers fire-and-forget).
  resolve: (key: string, messageId: string, mode: 'block' | 'note' | 'ignore') => Promise<void>

  // GAP 4 — management actions + transient search overlay state.
  searchResults: Message[] | null
  searchTerm: string
  runSearch: (key: string, query: string) => Promise<void>
  clearSearch: () => void
  supersede: (key: string, oldId: string, newId: string) => void
  attach: (key: string, messageId: string, path: string, atype?: Message['atype']) => void
```

> The `resolve` signature gains `key` as the first arg. Today `resolve(mid, mode)` re-derives the board key by scanning every board for the id (`commsStore.ts:155`). The panel already knows its `key` (`useCommsPanel.ts:15`), so passing it in is cleaner and removes the scan. Update the `useCommsPanel.resolve` callback accordingly (B3).

**(iii)** Replace the `resolve` implementation (`commsStore.ts:150-171`) and append the four new actions inside the store body:

```typescript
  resolve: async (key, mid, mode) => {
    // 1. Optimistic board annotation (unchanged shape from the old impl).
    set((s) => {
      const resolution =
        mode === 'block' ? 'blocked → builder retry'
        : mode === 'note' ? 'noted as future work'
        : 'ignored'
      const arr = (s.boards[key] || []).map((m) =>
        m.id === mid ? { ...m, status: 'resolved' as const, resolution } : m)
      return { boards: { ...s.boards, [key]: arr } }
    })

    // 2. Mark handled on the board (best-effort).
    void apiAcknowledge(mid, 'you')

    // 3. mode==='note' → record the choice as a durable decision on the board.
    if (mode === 'note') {
      const params = scopeToParams('feature', key)
      const stage = get().features.find((f) => f.id === key)?.stage ?? null
      void apiPost(key, params.board, params.scope, 'decision',
        'Noted as future work (deferred from a warning).', stage)
    }

    // 4. Drive the FSM ONLY when this feature is the active awaiting-decision run.
    //    decision keys for a warning/escalation gate: block→'block', else 'continue'.
    const { topic } = useRunnerStore.getState()
    if (topic && topic === key) {
      const options = await apiRunnerAwaitingDecision(topic)
      if (options) {
        const wanted = mode === 'block' ? 'block' : 'continue'
        const decision = options.includes(wanted)
          ? wanted
          : (options.includes('continue') ? 'continue' : options[0])
        void apiRunnerDecision(topic, decision)
      }
    }
  },

  searchResults: null,
  searchTerm: '',

  runSearch: async (key, query) => {
    const q = query.trim()
    if (!q) { set({ searchResults: null, searchTerm: '' }); return }
    set({ searchTerm: q })
    const isFeature = key !== 'project' && key !== 'global'
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    const params = scopeToParams(scope, key)
    // GET /comms search requires a non-empty feature param (comms.py:216).
    const feature = isFeature ? key : (scope === 'global' ? 'global' : key)
    const results = await apiSearch(q, feature, params.board, params.scope)
    set({ searchResults: results })
  },

  clearSearch: () => set({ searchResults: null, searchTerm: '' }),

  supersede: (key, oldId, newId) => {
    // Optimistic: mark the old card superseded; reconciled by COMMS_UPDATE reload.
    set((s) => {
      const arr = (s.boards[key] || []).map((m) =>
        m.id === oldId ? { ...m, supersededBy: newId } : m)
      return { boards: { ...s.boards, [key]: arr } }
    })
    void apiSupersede(oldId, newId)
  },

  attach: (key, messageId, path, atype) => {
    // Optimistic artifact badge; server persists + broadcasts (Stream A).
    set((s) => {
      const arr = (s.boards[key] || []).map((m) =>
        m.id === messageId ? { ...m, artifact: path.split(/[/\\]/).pop(), atype } : m)
      return { boards: { ...s.boards, [key]: arr } }
    })
    void apiAttach(messageId, path, atype)
  },
```

> `useRunnerStore` must be imported at the top of `commsStore.ts` (it currently is not):
> `import { useRunnerStore } from './runnerStore'`. Using `.getState()` (not the hook) is correct inside a store action — matches the established cross-store read pattern at `runnerStore.ts:163-167`.

**(iv)** Add two optional fields to the `Message` interface (`components/CommandCenter/types.ts:25-43`) so the optimistic supersede/search renders type-safely:

```typescript
  /** Set when this message has been superseded by a newer one (maps to
   *  comms_messages.superseded_by; surfaced as a struck-through card). */
  supersededBy?: string
```

> `artifact` / `atype` already exist on `Message` (`types.ts:38-39`) — attach reuses them, no new field. Also extend `rowToMessage` (`commsApi.ts:87-114`) to map the backend `superseded_by` column onto `supersededBy` if present, and add `superseded_by` to the `CommsRow` interface (`commsApi.ts:25-45`) so SSE reloads reflect server truth:
> ```typescript
> // CommsRow: add
> superseded_by?: string | null
> // rowToMessage: after the options block (~commsApi.ts:106)
> if (row.superseded_by) m.supersededBy = row.superseded_by
> ```

#### B3 — `studio/src/renderer/src/components/HQ/CommsPanel/hooks/useCommsPanel.ts`

Expose search state and adapt the `resolve`/`supersede`/`attach` callbacks. Current return at `useCommsPanel.ts:84`.

```typescript
  // resolve now takes the panel key explicitly (commsStore.resolve signature change).
  const resolve = useCallback(
    (mid: string, mode: 'block' | 'note' | 'ignore') => { void store.resolve(key, mid, mode) },
    [store, key],
  )

  const supersede = useCallback(
    (oldId: string, newId: string) => store.supersede(key, oldId, newId),
    [store, key],
  )

  const attach = useCallback(
    (mid: string, path: string, atype?: Message['atype']) => store.attach(key, mid, path, atype),
    [store, key],
  )

  // Search overlay — store-owned transient state.
  const searchResults = store.searchResults
  const searchTerm = store.searchTerm
  const runSearch = useCallback((q: string) => { void store.runSearch(key, q) }, [store, key])
  const clearSearch = useCallback(() => store.clearSearch(), [store])

  return {
    messages, feature, pendingCount, flashId, post, answer, resolve,
    toggleScope, del, supersede, attach,
    searchResults, searchTerm, runSearch, clearSearch,
  }
```

> Import `Message` type at the top if not already present (it is referenced in the new callbacks): the file currently imports only `BoardScope, MessageType` (`useCommsPanel.ts:2`) — add `Message`.

#### B4 — `studio/src/renderer/src/components/HQ/CommsPanel/CommsPanel.tsx`

Add the search bar above the list and route the search overlay. Current structure at `CommsPanel.tsx:44-84`. Pull the new values from the hook (`CommsPanel.tsx:25`):

```tsx
const {
  messages, feature, flashId, post, answer, resolve, toggleScope, del,
  supersede, attach, searchResults, searchTerm, runSearch, clearSearch,
} = useCommsPanel(scope, mainFeature)
```

Render a `SearchBar` (new sub-component, see below) before `CommsMsgList`, and feed the overlay through:

```tsx
return (
  <>
    <SearchBar value={searchTerm} onSearch={runSearch} onClear={clearSearch} />
    <CommsMsgList
      scope={scope}
      messages={messages}
      searchResults={searchResults}   {/* when non-null, list renders the overlay */}
      searchTerm={searchTerm}
      flashId={flashId}
      onAnswer={answer}
      onResolve={resolve}
      onDelete={del}
      onSupersede={supersede}          {/* GAP 4(b) — passed through to cards */}
    />

    <div className={s.foot}>
      {/* scopeRow unchanged (CommsPanel.tsx:56-74) */}
      <CommsInput
        scope={scope}
        mainFeature={mainFeature}
        type={type}
        onTypeChange={setType}
        onSend={(text) => post(type, text)}
        onAttachPath={(path, atype) => {
          // Attach to the most recent message authored by 'you' in this board,
          // or no-op if none exists (see Risks §4 — attach on an unsent message).
          const mine = [...messages].reverse().find((m) => m.from === 'you')
          if (mine) attach(mine.id, path, atype)
        }}
      />
    </div>
  </>
)
```

New file `CommsPanel/SearchBar/SearchBar.tsx` (+ `SearchBar.module.css`) — single responsibility, ≤150 lines (studio/CLAUDE.md size rule):

```tsx
import React, { useState } from 'react'
import { Search, X } from 'lucide-react'
import s from './SearchBar.module.css'

export function SearchBar(
  { value, onSearch, onClear }: { value: string; onSearch: (q: string) => void; onClear: () => void },
) {
  const [text, setText] = useState('')
  const submit = (): void => { if (text.trim()) onSearch(text) }
  const clear = (): void => { setText(''); onClear() }
  return (
    <div className={s.bar}>
      <Search size={12} className={s.ico} />
      <input
        className={s.input}
        placeholder="Search this board…"
        value={text}
        onChange={(e) => setText(e.currentTarget.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') clear() }}
      />
      {value && (
        <button type="button" className={s.clear} aria-label="Clear search" onClick={clear}>
          <X size={12} />
        </button>
      )}
    </div>
  )
}
```

CSS must obey the responsiveness rules (`studio/CLAUDE.md`): `.bar { display:flex; align-items:center; min-width:0 }`, `.input { flex:1; min-width:0 }`, colours from `tokens.css` vars. No inline styles.

#### B5 — `studio/src/renderer/src/components/HQ/CommsPanel/CommsMsgList.tsx`

Render the search overlay when `searchResults` is non-null; otherwise the normal thread. Pass `onSupersede` through to cards. (Current props/skeleton per the components map: `.thread` container with pins + `thread.map(... CommsMsgCard)`.)

```tsx
export interface CommsMsgListProps {
  scope: BoardScope
  messages: Message[]
  searchResults?: Message[] | null
  searchTerm?: string
  flashId: string | null
  onAnswer?: (id: string, opt: string) => void
  onResolve?: (id: string, mode: 'block' | 'note' | 'ignore') => void
  onDelete?: (id: string) => void
  onSupersede?: (oldId: string, newId: string) => void
}

// Inside the component, before the existing .thread block:
if (searchResults) {
  return (
    <div className={s.thread}>
      <div className={s.searchHead}>
        {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for “{searchTerm}”
      </div>
      {searchResults.map((m) => (
        <CommsMsgCard key={m.id} message={m} flash={false}
          onAnswer={onAnswer} onResolve={onResolve} onDelete={onDelete} onSupersede={onSupersede} />
      ))}
    </div>
  )
}
// else: existing pins + thread render (unchanged), with onSupersede added to each
// <CommsMsgCard .../> in the thread.map.
```

#### B6 — `studio/src/renderer/src/components/HQ/CommsPanel/CommsMsgCard.tsx` + `CardBody.tsx`

**Card meta — overflow menu (supersede + struck-through rendering).** Current meta row at `CommsMsgCard.tsx:23-46`. Add `onSupersede` to props (`CommsMsgCardProps` at `:10-16`), an overflow button after the delete button (`:45`), and a struck-through style when `m.supersededBy` is set.

```tsx
export interface CommsMsgCardProps {
  message: Message
  flash?: boolean
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void   // NEW
}

// Class on the outer card carries the superseded state (data-attr pattern, studio/CLAUDE.md):
<div className={`${s.msg}${flash ? ` ${s.flash}` : ''}`} data-msg={m.id}
     {...(m.supersededBy ? { 'data-superseded': '' } : {})}>

// After the delete button (CommsMsgCard.tsx:45), an overflow menu:
{onSupersede && !m.supersededBy && (
  <SupersedeMenu message={m} onSupersede={onSupersede} />
)}
```

`data-superseded` drives CSS: `.msg[data-superseded] .msgCard { text-decoration: line-through; opacity:.55 }`, plus a small "superseded" link badge in `CardBody` (below).

New sub-component `CommsMsgCard/SupersedeMenu/SupersedeMenu.tsx` (own folder + CSS module, ≤150 lines). It owns its open/close `useState` (ephemeral UI state stays local, never Zustand — studio/CLAUDE.md hover/state rule) and presents a picker of *newer* messages on the same board:

```tsx
import React, { useState } from 'react'
import { MoreVertical } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { useCommsPanel } from '../hooks/useCommsPanel'  // for the candidate list, OR pass candidates as a prop
import s from './SupersedeMenu.module.css'

export function SupersedeMenu(
  { message, candidates, onSupersede }:
  { message: Message; candidates: Message[]; onSupersede: (oldId: string, newId: string) => void },
) {
  const [open, setOpen] = useState(false)
  // Only messages newer than this one are valid supersessors.
  const newer = candidates.filter((c) => c.id !== message.id && c.type === message.type)
  return (
    <div className={s.wrap}>
      <button type="button" className={s.btn} aria-label="Message actions"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={() => setOpen((o) => !o)}>
        <MoreVertical size={12} />
      </button>
      {open && (
        <div className={s.menu} role="menu">
          <div className={s.menuHead}>Supersede with…</div>
          {newer.length === 0 && <div className={s.empty}>No newer message</div>}
          {newer.map((c) => (
            <button key={c.id} type="button" role="menuitem" className={s.item}
              onClick={() => { onSupersede(message.id, c.id); setOpen(false) }}>
              {c.text.slice(0, 60)}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

> Decision: pass `candidates` (the panel's `messages`) as a prop from `CommsMsgCard` → `SupersedeMenu` rather than re-reading the store inside the leaf — keeps the leaf pure and avoids a second `useCommsPanel` subscription. So `CommsMsgCard` must also receive the board's `messages` (add a `siblings: Message[]` prop fed from `CommsMsgList`, which already has the array).

**CardBody — superseded link badge.** Add to `CardBody.tsx` (after the type branches, before the default return at `:89`) a small struck-through indicator with a jump-to-link when `m.supersededBy` is set:

```tsx
// Near the top of CardBody, render a banner above the body when superseded:
{m.supersededBy && (
  <div className={s.supersededNote}>
    superseded — see newer message
  </div>
)}
```

(Place this inside each branch's fragment or wrap the whole body; simplest is to render it once at the start of the returned fragment for the `decision`/default branches, which is where superseded messages live.)

**CommsInput — enable the paperclip (GAP 4c).** Current disabled button at `CommsInput.tsx:59-67`. Add a hidden file input + `onAttachPath` prop, and enable the button.

```tsx
export interface CommsInputProps {
  scope: BoardScope
  mainFeature: string
  type: MessageType
  onTypeChange: (t: MessageType) => void
  onSend: (text: string) => void
  onAttachPath?: (path: string, atype?: 'md' | 'code' | 'pdf' | 'image' | 'json' | 'url' | 'snippet') => void  // NEW
}

// add a ref (CommsInput.tsx:26 region):
const fileRef = useRef<HTMLInputElement>(null)

const ATYPE: Record<string, CommsInputProps['onAttachPath'] extends undefined ? never : 'md'|'code'|'pdf'|'image'|'json'> = {} // (helper below instead)

function inferAtype(name: string): 'md' | 'code' | 'pdf' | 'image' | 'json' {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'md') return 'md'
  if (ext === 'pdf') return 'pdf'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return 'image'
  if (ext === 'json') return 'json'
  return 'code'
}

// replace the disabled button (CommsInput.tsx:59-67) with:
<input
  ref={fileRef}
  type="file"
  className={s.hiddenFile}        /* CSS: display:none — not an inline style */
  onChange={(e) => {
    const f = e.currentTarget.files?.[0]
    if (f && onAttachPath) onAttachPath(f.name, inferAtype(f.name))
    e.currentTarget.value = ''
  }}
/>
<button
  type="button"
  className={s.toolbarBtn}
  title="Attach artifact"
  aria-label="Attach artifact"
  onClick={() => fileRef.current?.click()}
>
  <Paperclip size={12} />
</button>
```

> `style={{ display:'none' }}` is forbidden by the no-inline-styles rule (studio/CLAUDE.md) — use a `.hiddenFile { display: none }` class in `CommsInput.module.css`. Browser `File.name` gives a base name only (no full path); for the v1 wiring we attach by file name. If a real disk path is needed later, route through an Electron `dialog.showOpenDialog` IPC channel — noted as a follow-up, not in this spec's scope.

---

## 3. Verification plan

### Backend (Stream A)

```bash
# From repo root. Run the new suite plus the sibling comms suites it mirrors.
python -m pytest tests/test_comms_attach.py -q
python -m pytest tests/test_comms_supersede.py tests/test_comms_search_mode.py -q
# Full comms regression:
python -m pytest tests/ -q -k comms
```

A reviewer checks: (1) `attach_artifact_to_message` returns `'ok'`/`'not_found'` and only ever UPDATEs existing rows (never INSERTs); (2) the route maps `not_found`→404 and missing-path-and-url→400; (3) the broadcast targets the message's own `scope` (so the right panel reloads); (4) no filesystem/network reachability check sneaks into the hot path (advisory principle).

### Studio (Stream B)

```bash
# From repo root (studio/CLAUDE.md: typecheck runs from root, not studio/).
node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
# equivalently:
npm run typecheck
```

A reviewer checks: (1) no inline `style={{...}}` (only the documented exceptions); every new `<button>` has `type="button"`; new ARIA uses the spread pattern; (2) every network call is best-effort `.catch`/`void` — nothing awaits in a way that blocks a click handler; (3) `resolve` fires `/runner/decision` **only** when `runnerStore.topic === key` and the run is `awaiting_decision`; (4) `SearchBar`, `SupersedeMenu` each live in their own folder with a CSS module and stay ≤150 lines; (5) optimistic mutations are reconciled by the existing `COMMS_UPDATE` → `loadBoard` path (`useCommsPanel.ts:39`), not treated as permanent truth.

End-to-end smoke (manual, optional): start a run, let it hit a review warning gate, click **Block stage** on the card → confirm the pipeline retries BUILDING (FSM moved, not just the card); click **Note as future work** → confirm a `decision` message appears and the run continues; type in the search bar → overlay replaces the list, clear restores it; pick **Supersede with…** → old card renders struck-through; click the paperclip → pick a file → an artifact badge appears on your latest message.

---

## 4. Risks & non-goals

### Explicit non-goals (out of scope)

- **GAP 3 Part B (answer → runner loop) is STRETCH and NOT in this spec's build.** Part A is the only required Gap 3 deliverable — see §5. Closing the loop would POST `/runner/agent-answer` (`runner.py`, listed in CLAUDE.md runner endpoints) when a board `question` posted by an agent mid-run is answered. It requires correlating a board `question` message with the run's pending `agentQuestion` (`runnerStore.ts:71`), which has no current linkage (no `run_id`/`question_id` bridge on the board row). Left as a follow-up; do not build it now.
- **Artifact reachability validation** (disk-exists / HTTP HEAD) is intentionally omitted from `/comms/attach` (advisory-metadata principle). Not a gap — a deliberate boundary.
- **Real disk paths for attach** beyond `File.name` (Electron file-dialog IPC) — follow-up.
- **Auto-binding `mainFeature` to `activeTopic`** — the known gap where a user can view one feature while running another (studio store map §4) is unchanged here; the Gap 2 guard (`topic === key`) makes the mismatch safe rather than fixing it.

### Race / edge cases (and how the design handles each)

1. **Resolve when no active run.** `runnerStore.topic` is `null` or `≠ key`. The guard in `resolve` skips `/runner/decision` entirely; the action degrades to acknowledge (+ note decision). Correct: a warning can be triaged after the gate has passed. No 409 spam, because we never POST `/runner/decision` unless `apiRunnerAwaitingDecision` confirmed the gate is open.
2. **Resolve when the run moved on between probe and POST.** `apiRunnerAwaitingDecision` returns the options, but the run advances before `apiRunnerDecision` lands → backend returns 409 (`runner.py:272-293`). `apiRunnerDecision` swallows non-`ok` (`.ok` false → returns false, no throw). Harmless; the optimistic card stays resolved.
3. **`decision` key not in `pending_menu.options`.** For warning/escalation gates the keys are typically `block`/`continue`/`escalate`. We pick `'block'` for block-mode else `'continue'`, falling back to `options[0]` if neither is present (`commsStore.resolve` step 4). This prevents the 400 "invalid decision" path (`runner.py`).
4. **Attach on an "unsent" / no-eligible message.** The paperclip attaches to the latest `from:'you'` message in the board (`CommsPanel.onAttachPath`). If the board has none, it is a no-op (no crash, no orphan attach) — attach targets an existing message row by design (`/comms/attach` 404s on a missing id anyway). A future "compose-with-attachment" flow would post first, then attach; out of scope.
5. **Superseding the active decision.** If the superseded message is the very `decision` currently gating the run, the supersede only flips `superseded_by` on the board row (`comms.py:445`) — it does **not** call `/runner/decision`. The gate stays open until a human resolves it. This is intentional: supersede is board curation, not an FSM action. Documented so a reviewer does not expect supersede to advance the pipeline.
6. **Optimistic vs. server truth drift.** Every optimistic mutation (resolve/supersede/attach) is overwritten on the next `COMMS_UPDATE` → `loadBoard` (`useCommsPanel.ts:39`). If a POST silently fails, the next SSE reload reverts the card to server truth — the board self-heals rather than lying permanently.
7. **Search overlay staleness.** `searchResults` is transient store state; a new `COMMS_UPDATE` does not refresh it (search is a point-in-time query). `clearSearch` restores the live thread. Acceptable — searches are explicit, momentary actions.

---

## 5. GAP 3 — Async question loop

### Part A (REQUIRED) — "post a question" section for `comms-post.md`

Append a section to `src/pathly_data/core/skills/fragments/comms-post.md` (current file ends at `:64`). It teaches agents to ask a non-blocking question on the board, mirroring the existing post recipe (`comms-post.md:26-37`) but with `type:question` + `options`.

```markdown
### Asking a question (non-blocking)

When you need a human decision but must **not** block, post a `question` with 2–4 options.
You continue working on the assumption stated in `text`; if a human answers, the answer is
injected at the next `/next_action`. Never wait in a loop for the reply.

​```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "<your-role>",
    "type": "question",
    "text": "<the question + the assumption you are proceeding with if unanswered>",
    "options": [
      {"id": "a", "label": "<option A>", "description": "<short consequence>"},
      {"id": "b", "label": "<option B>", "description": "<short consequence>"}
    ],
    "board": "feature",
    "stage": "<CURRENT_STATE>"
  }'
​```

Rules:
- Always state your fallback assumption in `text` — the question is advisory, not a gate.
- 2–4 options, each with a one-line `description` of its consequence.
- One question per genuinely-open decision; do not turn routine work into questions.
- The human answer arrives via `/comms/answer`; you read it from the injected board context
  on your next turn. Do not poll.
```

> **Adapter sync (CRITICAL, per src/pathly_data/CLAUDE.md):** `comms-post.md` is a core fragment shared
> across agents. After editing it, propagate:
> ```bash
> pathly-setup claude --apply --repair   # overwrite installed fragment
> python -m build                          # rebuild codex/copilot/antigravity adapters
> ```
> Skipping `--repair` leaves the installed fragment stale and agents never see the new section.

### Part B (STRETCH — do not build now)

Close the loop: when a human answers a board `question` that an agent posted mid-run, forward the
answer to the waiting run via `POST /runner/agent-answer` so the run resumes with the human's choice
instead of only surfacing it at the next `/next_action`. Blocked on a missing board↔run correlation
(no `question_id`/`run_id` bridge on the comms row). Explicitly deferred; see Risks §4.

---

## 6. Stream summary (build order)

```
STREAM A (Python, parallel-safe with B)        STREAM B (TypeScript, parallel-safe with A)
  A1 queries/comms.py  attach_artifact_to_msg     B1 commsApi.ts   +5 helpers
  A2 comms.py          real /comms/attach         B2 commsStore.ts +actions, Message.supersededBy
  A3 test_comms_attach.py (new)                    B3 useCommsPanel.ts  expose new actions/state
                                                   B4 CommsPanel.tsx + SearchBar/ (new)
GAP 3 Part A (independent, any time)               B5 CommsMsgList.tsx  search overlay + onSupersede
  comms-post.md  + "Asking a question" section     B6 CommsMsgCard/CardBody/CommsInput
  then: pathly-setup claude --apply --repair          + SupersedeMenu/ (new)
        python -m build
```

Within Stream A: A1 → A2 → A3. Within Stream B: B1 → B2 → (B3..B6 any order). The two streams share only the frozen `/comms/attach` JSON contract in §2 and never touch the same file.
