# Trace — fsm-state-audit

## Files visited

| File | Lines | Finding |
|---|---|---|
| `src/pathly_orchestrator/fsm/engine.py` | 624–638 | `write_state(Path, str, dict)` — writes STATE.json only (atomic tmp→rename). Does NOT touch SQLite. |
| `src/pathly_orchestrator/fsm/__init__.py` | 3–15 | Re-exports `write_state` from `engine.py`. This is the version imported by `fsm_ops.py`. |
| `src/pathly_orchestrator/fsm_ops.py` | 14–22 | Imports `write_state` from `pathly_orchestrator.fsm` (i.e., engine.py — STATE.json only). |
| `src/pathly_orchestrator/fsm_ops.py` | 487, 510, 566, 643, 766 | Reads state via `eventlog.read_state()` (DB-only); writes via `write_state()` from fsm (STATE.json only). |
| `src/pathly_orchestrator/eventlog.py` | 45–48 | `_db_only()` — returns `True` by default (env `PATHLY_DB_ONLY` must be `"0"` to re-enable STATE.json writes). |
| `src/pathly_orchestrator/eventlog.py` | 113–136 | `_write_state_db()` — writes SQLite first, then skips STATE.json if `_db_only()` is True. |
| `src/pathly_orchestrator/eventlog.py` | 139–166 | `write_state(str, dict, flow)` — validates transitions, then calls `_write_state_db`. Both stores when `_db_only=False`; DB only when `_db_only=True`. |
| `src/pathly_orchestrator/eventlog.py` | 195–199 | `read_state(str)` — always reads from SQLite only. Never touches STATE.json. |
| `src/pathly_orchestrator/db/queries/fsm_state.py` | 11–26 | `write_state(conn, project_root, feature, dict)` — upserts JSON into `fsm_state` table. |
| `src/pathly_orchestrator/db/queries/fsm_state.py` | 29–39 | `read_state(conn, project_root, feature)` — reads from `fsm_state` table. |
| `src/pathly_orchestrator/db/connection.py` | 41–67 | `get_db()` always opens `~/.pathly/pathly.db`. `project_root` parameter is accepted but ignored. |
| `src/pathly_orchestrator/fsm/engine.py` | 180–188 | `on_state_counter` rule — reads via `eventlog.read_state()` (DB). Correct. |
| `src/pathly_orchestrator/fsm/engine.py` | 399–419 | `update_progress` transition action — reads via `eventlog.read_state()`, then writes via `eventlog.write_state()`. Both correct (writes DB + optional STATE.json via eventlog). |
| `src/pathly_orchestrator/fsm/engine.py` | 584–593 | `scope_gate` — reads `STATE.json` directly with `json.loads(state_file.read_text())`. Does NOT use DB. Split-brain read site. |
| `src/pathly_orchestrator/fsm/engine.py` | 26–85 | `recover_state(storage_path, flow, state_doc)` — if `state_doc` is provided, uses it (from DB). If not, falls back to STATE.json. |
| `src/pathly_orchestrator/http_server/blueprints/health.py` | 11, 83, 96 | Uses `from pathly_orchestrator.eventlog import read_state` — DB path. Correct. |
| `src/pathly_orchestrator/services/flow_service.py` | 12 | Uses `_db.read_state(conn, project_root, feature)` — DB path. Correct. |
| `src/pathly_orchestrator/supervisor/terminal.py` | 36, 51, 77, 86 | Uses `Path(project_root) / "pathly" / "plans" / topic` directly; passes `project_root` string to `_db.append_event`. |

---

## Code path

### Path A — `fsm_ops.complete_stage` write path (the split-brain path)

1. **`fsm_ops.complete_stage`** (`fsm_ops.py:622–794`) receives `{flow, topic, project_root}`.
2. Line 643: reads current state via `_eventlog.read_state(str(storage_path))` → this goes through `eventlog.read_state` → `db.read_state` → **SQLite** (`fsm_state` table). Returns `state_before`.
3. Line 646: calls `recover_state(storage_path, flow_config, state_doc=state_before)` with the DB doc pre-loaded, so STATE.json is skipped in recovery.
4. Lines 762–766: builds `prior_state = dict(state_before or {})`, pops baselines, then calls:
   ```python
   write_state(storage_path, next_state, prior_state)
   ```
   where `write_state` is imported from `pathly_orchestrator.fsm` (line 21) → `fsm/__init__.py` → `engine.write_state`.
5. `engine.write_state` (`engine.py:624–638`): **writes STATE.json only**. It does not call `_db.write_state` or `eventlog.write_state`. SQLite is not updated.

**Result:** After `complete_stage`, STATE.json reflects the new `current` state; SQLite `fsm_state` table still has the old state.

---

### Path B — `fsm_ops.next_action` write path (same split-brain)

1. Line 487: reads `_db_state = _eventlog_pre.read_state(str(storage_path))` → SQLite.
2. Line 490: `recover_state(..., state_doc=_db_state)` — uses DB doc.
3. Line 510: reads `prior_state = _eventlog.read_state(str(storage_path)) or {}` → SQLite again.
4. Line 566 (conditional): `write_state(storage_path, state_info["current_state"], stamped_state)` → same `fsm` import → `engine.write_state` → **STATE.json only**.

**Result:** `next_action` updates STATE.json with stamped fields (conv_start_sha, build_baseline, convs_total) but SQLite is not updated. On the next call, `read_state` (DB) returns the old unstamped version.

---

### Path C — `eventlog.write_state` (the correct dual-write path)

Used by:
- `update_progress` transition action in `engine.py` line 418.
- Any caller that imports `write_state` directly from `pathly_orchestrator.eventlog`.

Flow:
1. `eventlog.write_state(str, dict, flow)` validates the state transition against `VALID_STATES` and `TRANSITIONS`.
2. Calls `_write_state_db(feature_dir, feature_dir.name, state)`.
3. `_write_state_db` calls `_db.write_state(conn, project_root, feature, state)` → SQLite updated.
4. If `_db_only()` is False → also writes STATE.json atomically. If True (default) → STATE.json skipped.

---

### Path D — `scope_gate` reads STATE.json directly

In `engine.run_gates` (`engine.py:584–593`), the `scope_gate` type reads `build_baseline` from STATE.json with a raw `json.loads(state_file.read_text())`. It does not use `eventlog.read_state` or `_db.read_state`. Since `next_action` writes `build_baseline` only to STATE.json (Path B above, via `engine.write_state`), this gate works as long as STATE.json was written. But because `engine.write_state` only writes STATE.json and `_db_only=True` suppresses STATE.json writes from the eventlog path, there is a risk that STATE.json is missing or stale on a fresh DB-only deployment.

---

### Path E — `project_root` key derivation (Windows path normalization)

In `eventlog.py`, `project_root` is derived as:
```python
feature_dir = _resolve_path(storage_path).resolve()
project_root = str(feature_dir.parent.parent.parent)
```
`Path.resolve()` on Windows returns a path with **backslashes** (e.g., `C:\Users\Yafit\pathly-adapters`).
`str()` on a Windows `Path` also uses backslashes.

In `fsm_ops.py`, `project_root` arrives from the HTTP POST body as a string. On Windows this is typically `C:/Users/Yafit/pathly-adapters` (forward slashes, as sent by Electron/JS) or `C:\Users\Yafit\pathly-adapters` (backslashes).

In `supervisor/terminal.py`, `project_root = str(feature_dir.parent.parent.parent)` produces backslashes on Windows.

**The DB key is `(project_root, feature)`.** If one call path stores `C:\Users\Yafit\pathly-adapters` and another stores `C:/Users/Yafit/pathly-adapters`, SQLite will see them as two different rows. `read_state` will return `None` when the key doesn't match, causing `next_action` to treat the feature as brand new.

This normalization gap is latent on Windows whenever `project_root` crosses a JS↔Python boundary without normalization.

---

## Summary table — every read/write call site

| Function | File:line | Store written/read | Called by |
|---|---|---|---|
| `engine.write_state(Path, str, dict)` | `fsm/engine.py:624` | STATE.json only | `fsm_ops.next_action` (line 566), `fsm_ops.complete_stage` (line 766) via `fsm` import |
| `eventlog.write_state(str, dict, flow)` | `eventlog.py:139` | DB always; STATE.json only if `PATHLY_DB_ONLY=0` | `update_progress` action (engine.py:418); any direct `eventlog` caller |
| `eventlog._write_state_db(Path, str, dict)` | `eventlog.py:113` | DB always; STATE.json if `_db_only()=False` | Called only by `eventlog.write_state` |
| `db.write_state(conn, root, feat, dict)` | `db/queries/fsm_state.py:11` | DB only | Called only by `eventlog._write_state_db` |
| `eventlog.read_state(str)` | `eventlog.py:195` | Reads DB only | `fsm_ops.next_action` (lines 487, 510), `fsm_ops.complete_stage` (line 643), `engine.on_state_counter` (line 182), `engine.update_progress` (line 411), `fsm_ops._count_planned_convs` (line 443), `health.py:83,96` |
| `db.read_state(conn, root, feat)` | `db/queries/fsm_state.py:29` | Reads DB only | Called by `eventlog.read_state`, `flow_service.get_feature_list` |
| `engine.recover_state(path, flow, state_doc)` | `fsm/engine.py:26` | Reads STATE.json (fallback only; skipped if `state_doc` is provided) | `fsm_ops.next_action` (line 490), `fsm_ops.complete_stage` (line 646) — both pass `state_doc` from DB |
| `scope_gate` read | `fsm/engine.py:586–593` | Reads STATE.json directly (no DB) | `engine.run_gates` via `fsm_ops.complete_stage` |
| `fsm_ops.write_state` (imported symbol) | `fsm_ops.py:21` | Resolves to `engine.write_state` → STATE.json only | `next_action` line 566, `complete_stage` line 766 |

---

## The exact split-brain flow (event-phase-summary scenario)

The specific scenario where split-brain was observed during event-phase-summary:

1. **Agent writes AGENT_DONE event** to DB via `eventlog.append_event` → SQLite `fsm_events` table updated. SQLite `fsm_state` has previous state (e.g., `current: "BUILDING"`).

2. **`complete_stage` is called.** It reads `state_before` from SQLite (`current: "BUILDING"`). Evaluates transition → `next_state = "REVIEWING"`.

3. **`engine.write_state(storage_path, "REVIEWING", prior_state)`** is called (line 766). This writes STATE.json with `current: "REVIEWING"`. SQLite `fsm_state` is NOT updated — it still has `current: "BUILDING"`.

4. **`append_event` writes `STATE_TRANSITION`** event to SQLite `fsm_events`. SQLite `fsm_state` still says `"BUILDING"`.

5. **Next call to `next_action`:** reads `_db_state` via `eventlog.read_state` → SQLite returns `current: "BUILDING"` (stale). `recover_state` uses this `state_doc` parameter and also sees `"BUILDING"`. The agent prompt is built for `BUILDING` again, even though STATE.json says `"REVIEWING"`. The FSM appears to loop.

6. **If `recover_state` fell back to STATE.json** (e.g., if `state_doc=None`), it would see `"REVIEWING"` and advance correctly — but `next_action` always pre-loads `_db_state` and passes it in, so the fallback never fires.

---

## Windows path normalization gaps

| Location | Gap | Confidence |
|---|---|---|
| `eventlog._write_state_db` line 120: `project_root = str(feature_dir.parent.parent.parent)` | On Windows, `Path.resolve()` produces backslashes. DB key is stored with backslashes. | HIGH |
| `fsm_ops.next_action` / `complete_stage` lines 481, 625: `project_root = args["project_root"]` | Value comes from HTTP POST body. Electron/JS typically sends forward slashes. DB lookup uses this string directly. | HIGH |
| `supervisor/terminal.py` line 77: `project_root = str(feature_dir.parent.parent.parent)` | Backslashes on Windows (same as eventlog). Consistent with eventlog if both paths are fully resolved. | MEDIUM |
| `runner.py` line 69: `project_root=data["project_root"]` | Passes the raw JSON string from Studio to `supervisor.start_run`. No normalization. | HIGH |
| `health.py` line 90: `plans_dir.glob("*/STATE.json")` | Uses filesystem glob, not DB. Does not depend on project_root key. Independent of this gap. | HIGH (no gap here) |

**The critical gap:** If Studio sends `project_root: "C:/Users/Yafit/pathly-adapters"` (forward slashes) and `eventlog` derives `project_root` as `C:\Users\Yafit\pathly-adapters` (backslashes), they are different SQLite keys. A write via one path is invisible to a read via the other. This would manifest as `read_state` returning `None` on every call from the HTTP-path, triggering repeated re-initialization of `convs_total`, `conv_start_sha`, etc.

---

## Gaps (paths not traced)

- The MCP server path (non-HTTP) was not traced — it may pass `project_root` differently.
- `pathly-ff` / `pathly-back` CLI shortcuts were not traced — they may bypass the `fsm_ops` layer.
- The `EVENTS.jsonl` flat file (legacy) was not traced — it is no longer written by current code (DB-only for events).

---

## Confidence levels

| Finding | Confidence |
|---|---|
| `fsm_ops.complete_stage` and `next_action` import `engine.write_state` (STATE.json only) | HIGH — confirmed by direct import at `fsm_ops.py:21` and function body at `engine.py:624–638` |
| After `complete_stage`, SQLite `fsm_state` is stale (old state) while STATE.json has new state | HIGH — no call to `eventlog.write_state` or `db.write_state` in either `complete_stage` or `next_action` write paths |
| `eventlog.read_state` reads DB only, never falls back to STATE.json | HIGH — confirmed at `eventlog.py:195–199` |
| `_db_only()` returns True by default (suppresses STATE.json writes from eventlog path) | HIGH — confirmed at `eventlog.py:45–48` |
| `scope_gate` reads STATE.json directly, not DB | HIGH — confirmed at `engine.py:586–593` |
| Windows backslash vs forward-slash DB key mismatch risk | HIGH (code confirmed) / MEDIUM (actual runtime behavior depends on what Studio sends — not tested) |
| `update_progress` transition action correctly uses `eventlog.write_state` (dual-write) | HIGH — confirmed at `engine.py:418` |
| `recover_state` fallback to STATE.json is effectively dead code in normal flow | HIGH — both callers pre-load `state_doc` from DB and pass it in |
