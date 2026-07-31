# Unified Control Plane — Architecture (MVP: P0 + P1 + P2)

**Stage:** Architecture (interactive consultation, stage 2) · **Date:** 2026-07-24
· **Author:** architect (P0, §0–10). P1/P2 (§11–12) appended by the orchestrator after the
  extension stage stalled twice on transient API stream errors — same design intent, seams
  code-verified against live source.
· **Scope:** MVP = **P0 + P1 + P2** (human decision, 2026-07-24). P3 (unified control +
  server-side loop) remains the next milestone. §0–10 detail P0; §11 P1; §12 P2.
· **Inputs:** `SPEC.md`, `PO_NOTES.md`, feature board

> P0 is **pure-additive, zero-behavior-change**: one new table, one nullable column,
> two best-effort write points beside existing chokepoints (never into their spawn/billing
> logic), one read-model, one new blueprint domain, one read-only Studio pane. The four
> already-unified substrate chokepoints are **not touched**.

This document is a buildable design: file-by-file additions/changes, the exact schema,
the two write-point seams, the read-model queries, the Studio pane, and acceptance criteria.

---

## 0. Verified starting state (checked against live code, not assumed)

| Claim | Verified | Evidence |
|---|---|---|
| `db/queries/run_log.py`, `blueprints/control/`, `supervisor/dispatch.py`, `run_history.list_runs/get_run_detail` do **not** exist | ✅ greenfield | dir listings |
| `comms_messages` has no `run_id` (migrations.py:270) | ✅ | DDL read; not in `_add_additive_migrations` |
| `run_history` is the run-identity map, `UNIQUE(run_id)` | ✅ | migrations.py:222; run_history.py `upsert_run` |
| Spawn chokepoint receives the **merged** prompt as `instructions` (`run_id` in hand) | ✅ | terminal.py:401 `_run_stage_via_terminal(state, instructions, adapter, model, run_id, …)` |
| Result callback has `stdout_tail` + `run_id`, discards stdout after billing parse | ✅ | api_lifecycle.py:235 `runner_terminal_result` |
| `agent_invocations` is `run_id`-keyed (AGENT_DONE projection) | ✅ | invocation_projection.py; `/db/recent` reads it |

### 0.1 SPEC correction — the board block is NOT separately in hand at the chokepoint

SPEC §2 states `_run_stage_via_terminal` "already has the composed prompt + board block in
hand." **This is inaccurate.** `fsm_compose.build_prompt` (fsm_compose.py:458-503) composes
`board_block` as a discrete local, but returns only the **merged** string
`agent_text + context + history + board_block + code_block`. The supervisor and the spawn
chokepoint see only that merged `instructions`. Consequence for the schema: see §2.3 —
`board_context_injected` is a nullable column filled discretely in **P1**, not P0.

---

## 1. The run-grain decision (the single most load-bearing choice)

Verified id-minting reality:

| Run kind | `run_id` shape | `run_history` rows | Where cost lands (`agent_invocations`) |
|---|---|---|---|
| flow / team / consultation / decompose | flow: **bare uuid** (`start_run`, api.py:58); each stage: `{topic}-{N}-{ts}` (orchestrator.py:240) | **1 flow-parent row** (adapter = *flow name*, via `/runner/start`+`registry` finish) **+ N per-stage rows** (adapter = *CLI*, via `_record_spawn_identity`) | on the **per-stage** run_ids (completion-report threads the stage run_id) |
| board `single` | bare uuid per board run | 1 row (adapter = CLI) | on that run_id |
| `loop` task | `sched-{task_id}` (scheduler.py:257) | 1 row per task | on that run_id |

So **Monitor RECENT (`/db/recent`) shows one card per _spawn_** (per-stage), each tagged
`category` ∈ flow/single/loop. A 6-stage team run is 6 RECENT cards.

**Decision — list at the _top-level run_ grain; fold FSM stages into RunDetail.**
The supervisor's job-to-be-done is "show me everything about **run X**" — one team run, not
6 stage spawns. `list_runs` returns **one row per top-level run**:

- **flow/team/consultation/decompose** → the flow-parent row; its stages are reconstructed in
  RunDetail (§4.2).
- **board single / loop task** → one row each (a single spawn *is* the whole run) — byte-identical
  figures to its RECENT card.

**Classifier** (`db/queries/run_history_read.py::_classify_kind(run_id, adapter)`), by id shape
(shape is how the system actually mints identity — robust, no new plumbing):

```
run_id startswith "sched-"                          -> "loop"      (top-level)
run_id matches r"-\d+-\d{10,}(-(q|fb)\d+)?$"          -> "stage"     (CHILD of a flow — excluded from list)
else (bare uuid): adapter in FLOW_NAMES              -> "flow"      (top-level)
                  else                               -> "single"    (top-level)
FLOW_NAMES = {team, team-build, consultation, feature-consultation, project-consultation}
```

### 1.1 Parity definition (make the AC precise, avoid over-promising)

- **single / loop**: the pane's per-run cost/status is **identical** to its RECENT card
  (same `agent_invocations` row).
- **flow / decompose**: the pane's one flow-row cost = **SUM of that flow's stage
  `agent_invocations`** = exactly the sum of its RECENT cards. "Parity" = *figures reconcile*,
  not *same number of rows*. Stated in AC-1.

Flow→stage linkage in P0 uses **feature-slug + board_scope + time-window** (stage `started_at`
BETWEEN parent `started_at` and `COALESCE(finished_at, now)`) — the **same window-join pattern**
the PO already sanctioned for board posts. Approximate only under back-to-back same-feature flow
runs; made exact in P1 by stamping the parent run_id onto stage rows.

---

## 2. Schema — one table + one column

### 2.1 `run_log` table (NEW) — in `db/migrations.py` executescript

Add alongside the other `CREATE TABLE IF NOT EXISTS` blocks (the SEED DDL home; ALTERs go in
`migrations_incremental.py`):

```sql
CREATE TABLE IF NOT EXISTS run_log (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                 TEXT NOT NULL,
    stage                  TEXT,
    prompt_sent            TEXT,   -- the full composed prompt (`instructions`) sent to the CLI
    board_context_injected TEXT,   -- discrete board block; NULL in P0 (embedded in prompt_sent) — see §2.3
    stdin                  TEXT,   -- stdin fed to the CLI (usually NULL: prompt goes via argv, not stdin)
    stdout                 TEXT,   -- full PTY stdout tail at result time, untruncated (§2.4)
    ts                     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_log_run_id ON run_log(run_id);
```

`run_id` is effectively unique per spawn (retries mint `-q{n}`/`-fb{n}` variants), so one
`run_log` row per spawn. Not enforced UNIQUE (keeps the write path INSERT-only + a WHERE-run_id
UPDATE; a stray duplicate degrades to "newest wins", never an error).

### 2.2 `comms_messages.run_id` (NEW column) — in `db/migrations_incremental.py`

Append one line to the `_add_additive_migrations` list (idempotent ALTER, skips if exists):

```python
# unified-control-plane P0: correlate a board post to the run that made it. Nullable +
# un-backfilled — legacy/human/non-poster posts legitimately carry NULL. RunDetail's Board
# tab joins run_id-when-present, time-window-when-NULL (P1 threads it into make_board_posters).
("comms_messages", "run_id", "TEXT"),
```

No index needed in P0 (RunDetail queries one run's board_scope over a bounded window). Add
`idx_comms_messages_run_id` in P1 when posts are always run_id-stamped.

### 2.3 `board_context_injected` — nullable in P0, discrete in P1 (SPEC §0.1 correction)

The chokepoint has only merged `instructions`. Capturing the board block **discretely** without a
substrate rewrite requires threading `build_prompt`'s local `board_block` out via an additive
`agent_hint.board_context` field — that touches the hot compose+next_action path and is **out of
P0's single-seam "beside `_run_stage_via_terminal`" scope**. So:

- **P0:** `prompt_sent = instructions` (the injected board context **is** visible inside it —
  `retrieve_board_context` emits its own delimiter header, so the pane can show it in-context).
  `board_context_injected = NULL`. AC-2 is met (the transcript shows the injected context) and the
  Board tab shows the *actual correlated posts* (the more useful artifact).
- **P1:** add optional `capture: dict|None=None` to `build_prompt` (non-breaking; existing callers
  pass nothing) → `capture['board_block']=board_block`; `next_action` returns
  `agent_hint.board_context`; supervisor threads it as a new optional kwarg to
  `_run_stage_via_terminal`; the spawn write fills the column. Purely additive, deferred.

### 2.4 stdout — persist the full tail untruncated (human board answer, 2026-07-24)

The human answered the open PO question `full`: *"Persist full stdout untruncated. Keep it
simple."* So the stdout write stores `data.get("stdout_tail","")` **verbatim** — no head+tail cap,
no truncation marker of our own. Caveat carried forward from PO_NOTES risk #2 and stated in AC:
this tail is the runner's rolling ~500-chunk PTY buffer, so "full untruncated" means *we do not
further truncate it*, **not** *a guaranteed-complete transcript* (the capture point is unchanged).
The `run_log` is a debug/display sink; billing stays authoritative in `agent_invocations`.

---

## 3. Write points — two best-effort seams (never raise into spawn/billing)

### 3.1 `db/queries/run_log.py` (NEW, db/ layer — no upward imports)

```python
"""run_log store: per-spawn prompt / board-context / stdin / stdout (unified-control-plane P0)."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from ..connection import _get_write_lock

def write_run_log_spawn(conn, run_id, stage, prompt_sent,
                        board_context_injected=None, stdin=None) -> None:
    """INSERT the spawn-time half (prompt + board context + stdin). Best-effort caller."""
    ts = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO run_log (run_id, stage, prompt_sent, board_context_injected, stdin, stdout, ts) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?)",
            (run_id, stage, prompt_sent, board_context_injected, stdin, ts))
        conn.commit()

def update_run_log_stdout(conn, run_id, stdout) -> None:
    """Fill the result-time half (stdout) for the newest row of run_id. No-op if no spawn row."""
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE run_log SET stdout=? WHERE id=("
            "  SELECT id FROM run_log WHERE run_id=? ORDER BY id DESC LIMIT 1)",
            (stdout, run_id))
        conn.commit()

def get_run_log(conn, run_id) -> list[dict]:
    """All run_log rows for run_id (positional-safe via dict(row))."""
    rows = conn.execute("SELECT * FROM run_log WHERE run_id=? ORDER BY id ASC", (run_id,)).fetchall()
    return [dict(r) for r in rows]
```

### 3.2 Write point A — spawn (prompt + board context + stdin)

**Site:** `supervisor/terminal.py::_run_stage_via_terminal`, immediately after
`_spawn_identity = _record_spawn_identity(state, run_id, adapter)` (line 429). It reuses that
existing best-effort pattern verbatim.

```python
# unified-control-plane P0: persist this spawn's prompt for the Complete Run Record.
# Best-effort — MUST NOT raise into the spawn path (PO risk #1: this is what keeps the
# "pure-additive, zero-behavior-change" claim true). Board context is embedded in
# `instructions` in P0 (board_context_injected discrete in P1 — see ARCHITECTURE §2.3).
try:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_log import write_run_log_spawn
    write_run_log_spawn(
        get_db(), run_id,
        stage=state.current_state or state.status or "stage",
        prompt_sent=instructions,
        board_context_injected=None,   # P1: discrete via agent_hint.board_context
        stdin=None,                    # prompt is delivered via argv, not stdin
    )
except Exception:
    logger.debug("run_log spawn write skipped", exc_info=True)
```

Does **not** touch argv build, billing, identity, or early-advance. Pure add.

### 3.3 Write point B — result (stdout, before it is discarded)

**Site:** `http_server/blueprints/runner/api_lifecycle.py::runner_terminal_result` — a NEW
best-effort block, placed **after** the existing billing `_patch_last_agent_done` block and
**before** the function returns (where stdout is otherwise dropped). It reads only
`data["stdout_tail"]` + `run_id`; it does **not** alter the billing path.

```python
# unified-control-plane P0: persist the PTY stdout tail (full, untruncated — human answer
# 2026-07-24). Best-effort; the billing parse above is unchanged. Do NOT gate the result
# callback on this.
try:
    from pathly_orchestrator.db.connection import get_db as _rl_db
    from pathly_orchestrator.db.queries.run_log import update_run_log_stdout
    update_run_log_stdout(_rl_db(), run_id, data.get("stdout_tail", ""))
except Exception:
    logging.getLogger("pathly.http").debug("run_log stdout write skipped", exc_info=True)
```

> Note: the result callback is keyed by the **flow-topic** run in `_registry`, but `run_id` in
> the body is the **spawn's** run_id (matches the spawn write). Both writes therefore key the
> same `run_log` row. Board runs/loop tasks that POST no `/runner/terminal/result` simply keep a
> NULL stdout (the spawn-half row still exists — a silent run still gets a record, mirroring the
> telemetry "every run gets a row" lesson).

---

## 4. Read-model — `db/queries/run_history_read.py` (NEW)

New file (mirrors the `goals_read.py` split precedent) so `run_history.py` stays the write/identity
map and neither file nears 400 lines.

### 4.1 `list_runs(conn, project_root, limit=50) -> list[dict]`

One row per **top-level** run (§1). Algorithm:

1. `SELECT * FROM run_history WHERE project_root=? ORDER BY COALESCE(finished_at, started_at) DESC`.
2. Compute `kind = _classify_kind(run_id, adapter)`; **drop `kind == "stage"`** (folded into detail).
3. For each kept row attach cost/tokens:
   - single/loop → `SELECT SUM(cost_usd), SUM(tokens_in+tokens_out) FROM agent_invocations WHERE run_id=?`.
   - flow/decompose → sum over the stage window: `WHERE project_root=? AND feature=? AND
     COALESCE(board_scope,feature)=? AND started_at BETWEEN ? AND COALESCE(?, datetime('now'))`.
4. Return `{run_id, kind, feature, board_scope, status, adapter, started_at, finished_at,
   stage_count, cost_usd, tokens_total}`, capped to `limit`.

Status comes from `run_history` (so **running** runs appear — RECENT can't show them). Cost comes
from `agent_invocations` (the same fact table as RECENT → parity by construction, §1.1).

### 4.2 `get_run_detail(conn, run_id) -> dict`

```
{ run: {…identity+lifecycle from run_history…, kind, cost_usd, tokens_total},
  stages: [ {run_id, stage, adapter, status, started_at, finished_at, cost_usd, tokens} … ],
  logs:   [ {stage, prompt_sent, board_context_injected, stdin, stdout, ts} … ],  # from run_log
  board:  [ {id, from_agent, type, text, ts, run_id} … ],   # §4.3 join
  artifacts: [ {path, type, title, summary} … ],            # §4.3 window join
  cost:   {cost_usd, tokens_total, invocations} }
```

- **stages:** for `kind in (flow, decompose)` → the child stage rows via the §1.1 window join
  (each enriched with its own `agent_invocations` cost + `run_log`). For single/loop → one stage
  (itself). `run_log` fetched per stage run_id via `get_run_log`.
- **cost:** reuse the §4.1 aggregate (keeps `/runs/<id>` and the list identical).

### 4.3 Board posts + artifacts join (PO constraint honored)

Board posts: **run_id-when-present, time-window-when-NULL** (PO constraint b4af4d17):

```sql
SELECT * FROM comms_messages
WHERE deleted_at IS NULL AND (
    run_id = :run_id                                   -- exact (P1-populated rows)
    OR (run_id IS NULL AND scope = :board_scope        -- P0 window fallback
        AND ts BETWEEN :started_at AND COALESCE(:finished_at, datetime('now'))))
ORDER BY ts ASC
```

Zero posts → empty list → empty-state tab (AC-3), never error. Window join is approximate under
concurrent same-board runs (PO-accepted for read-only P0; exact in P1).

Artifacts: `comms_artifacts` JOIN `comms_messages` on `message_id`, same `scope`+window filter.
Return `{path, type, title, summary}` only — **no hydrate call** here, so a non-md artifact is
listed by type/path and never mojibake (AC-4).

### 4.4 `supervisor/dispatch.py` (NEW, supervisor/ layer) — `overlay_live_status`

```python
"""Live-status + capability overlay for the unified run read-model (unified-control-plane P0)."""
def overlay_live_status(runs: list[dict]) -> list[dict]:
    """Upgrade a persisted 'running' row to the live registry status, and attach a per-kind
    capabilities set. DB-on-mount is the invariant (SPEC risk 5); this is a thin overlay,
    never the source. Imports only sibling supervisor modules (layer-safe)."""
    from .registry import _lock, _registry
    CAPS = {"flow": ["abort"], "single": ["abort"], "loop": ["abort"], "decompose": ["abort"]}
    with _lock:
        live = {s.run_id: s.status for s in _registry.values()}
    for r in runs:
        if r.get("status") == "running" and r["run_id"] in live:
            r["status"] = live[r["run_id"]]
        r["capabilities"] = CAPS.get(r.get("kind"), [])   # P0 read-only: display-only hint
    return runs
```

P0 caps are display-only (the pane is read-only; controls are P3). Included now so the read-model
shape is stable for later phases. Layer-safe: `supervisor` → `registry` only.

---

## 5. HTTP — `http_server/blueprints/control/` (NEW domain)

New blueprint domain per the CLAUDE.md blueprint map (do **not** grow `runner/api.py`). P0 adds
**only** `runs_read.py`; `runs_control.py`/`run_streams.py`/`_lifecycle.py` are P1-P3 stubs (not
created in P0).

```
http_server/blueprints/control/
  __init__.py       # all_blueprints = [runs_read_bp]  (mirrors comms/__init__.py)
  runs_read.py      # GET /runs, GET /runs/<run_id>
```

`runs_read.py` (~90 lines, lazy imports inside handlers per the layer rule):

```python
bp = Blueprint("control_runs_read", __name__)

@bp.route("/runs", methods=["GET"])
def list_runs_route():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_history_read import list_runs
    from pathly_orchestrator.supervisor.dispatch import overlay_live_status
    pr = (request.args.get("project_root") or "").strip()
    limit = min(int(request.args.get("limit", 50)), 200)
    runs = list_runs(get_db(), pr, limit) if pr else []
    return jsonify(overlay_live_status(runs)), 200

@bp.route("/runs/<run_id>", methods=["GET"])
def get_run_route(run_id):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_history_read import get_run_detail
    detail = get_run_detail(get_db(), run_id)
    if not detail.get("run"):
        return jsonify({"error": "unknown run_id"}), 404
    return jsonify(detail), 200
```

Register in `app.py`: `from .blueprints.control import all_blueprints as control_blueprints`
then `for _bp in control_blueprints: app.register_blueprint(_bp)` (mirrors the comms registration
at app.py:58). Both handlers wrap in try/except → `jsonify({"error":…}), 500` (house pattern).

> **Path note:** `GET /runs` sits at the server root (no `/runner` prefix) — a *new* namespace,
> so it cannot collide with the existing `runner/` routes.

---

## 6. Studio — read-only `components/Pipelines/` pane

Reuses the existing primitives (no new run engine). Follows the 150-line-per-component +
own-subfolder + `.module.css` rules.

```
components/Pipelines/
  Pipelines.tsx                 # panel shell: RunList | RunDetail (selection state)
  hooks/
    useRuns.ts                  # GET /runs?project_root=… (DB on mount + 8s poll; invariant: DB-on-mount)
    useRunDetail.ts             # GET /runs/<id> on selection
  RunList/RunList.tsx           # rows: kind badge · feature · status · cost · when
  RunList/RunRow.tsx
  RunDetail/RunDetail.tsx       # tab shell: Stages · Logs · Board · Cost   (Artifacts folded into Logs/Board in P0)
  RunDetail/StagesTab.tsx       # reuse deriveFlowSteps + FlowStepper (flowSteps.ts)
  RunDetail/LogsTab.tsx         # prompt_sent / board_context_injected / stdin / stdout, per stage
  RunDetail/BoardTab.tsx        # correlated posts; empty-state when none (AC-3)
  RunDetail/CostTab.tsx         # reuse RunCostBadge shape (cost_usd / tokens / invocations)
```

- **Reuse:** `deriveFlowSteps(pipelineStates, stageRoles, fsmState, events)` → `FlowStepper` for
  the Stages tab (renders any flow's phases); `RunCostBadge`'s readout shape for Cost;
  `useRecentEngines`' `adapterFromProvider` + the `timestamp.ts` utils for badges.
- **Data source:** the new `/runs` endpoints only — **never** the live SSE stores (P0 is read-only;
  live overlay is P1). This satisfies "DB on mount, SSE overlay" as the reload invariant (SPEC risk
  5 / AC-5): a renderer reload re-fetches `/runs` and repopulates — no orphan blank.
- **Panel wiring:** add a `BottomNav`/`IconStrip` PANELS entry (id e.g. `pipelines`) exactly like
  the other six panels. **Do not** modify Monitor / CliMonitorBar / CommsPanel / FlowControlBar
  (AC-7, zero behavior change).
- **Non-md artifact:** BoardTab/LogsTab list `{title, type, path}`; md → inline preview allowed,
  anything else → "preview unavailable for `<type>`" (AC-4). No hydrate fetch.

---

## 7. Layer + file-size compliance (checked for every new/changed file)

| File | Layer | Imports | Size after |
|---|---|---|---|
| `db/queries/run_log.py` (NEW) | db/ | `db/connection` only | ~45 |
| `db/queries/run_history_read.py` (NEW) | db/ | `db/connection`, sibling `db/queries` | ~180 |
| `db/migrations.py` (+table) | db/ | — | +12 |
| `db/migrations_incremental.py` (+1 col) | db/ | — | +1 |
| `supervisor/dispatch.py` (NEW) | supervisor/ | `supervisor/registry` only | ~40 |
| `supervisor/terminal.py` (+spawn write) | supervisor/ | lazy db import (existing pattern) | +10 (→~820; pre-existing 810 over-limit, in grandfather allowlist — not made worse structurally) |
| `http_server/blueprints/control/runs_read.py` (NEW) | http_server/ | lazy (db, supervisor) inside handlers | ~90 |
| `http_server/blueprints/control/__init__.py` (NEW) | http_server/ | local bp | ~6 |
| `http_server/app.py` (+register) | http_server/ | — | +2 |
| `http_server/blueprints/runner/api_lifecycle.py` (+stdout write) | http_server/ | lazy db import | +8 |

All new-file imports obey `db → (nothing internal)`, `supervisor → db, runner`,
`http_server → all (lazy in handlers)`. No upward imports introduced. Every new file is well under
400 lines. `terminal.py` is already over 400 (grandfathered); the +10 best-effort block does not
add a new structural concern (P-1's 400-line CI gate uses a grandfather allowlist).

---

## 8. Acceptance criteria (P0)

1. **AC-1 (list + parity):** `GET /runs?project_root=…` lists every top-level run kind
   (flow/team/consultation/single/loop/decompose) with status + cost. For single/loop the figure
   is **identical** to that run's Monitor RECENT card; for flow/decompose the run-row cost equals
   the **sum** of its stage RECENT cards (§1.1). Running runs appear (status from `run_history`).
2. **AC-2 (detail):** selecting a run shows Stages · Logs · Board · Cost from the DB — including
   the composed `prompt_sent` (with the injected board context visible inside it), stdout, correlated
   board posts, and cost.
3. **AC-3 (empty board):** a run with zero board posts → empty Board tab (empty state), never an
   error or spinner.
4. **AC-4 (non-md artifact):** listed with type + path; **no inline hydrate**, no mojibake.
5. **AC-5 (reload):** renderer reload → pane repopulates from `GET /runs` (DB on mount); no orphan
   blank. Boundary: a *still-running* flow's **continuation** is renderer-driven until P3 — P0
   guarantees the *pane* survives, **not** the *run*.
6. **AC-6 (best-effort invariant):** a `run_log` write failure (spawn or result) never fails the
   run — both writes are try/except that only `logger.debug`. Verified by a fault-injection unit
   test (patch `write_run_log_spawn`/`update_run_log_stdout` to raise; assert the spawn/result path
   still completes).
7. **AC-7 (zero behavior change):** Monitor / CommsPanel / FlowControlBar untouched; existing test
   suite (105/105) still green; the two new columns/table are additive and nullable.

### 8.1 Test plan (new tests)
- `tests/db/test_run_log.py` — spawn INSERT + stdout UPDATE + `get_run_log`; missing-spawn-row
  UPDATE is a no-op; full untruncated stdout round-trips.
- `tests/db/test_run_history_read.py` — `_classify_kind` table; `list_runs` folds stages, includes
  running rows, cost parity vs `agent_invocations`; `get_run_detail` window joins (board posts
  run_id-vs-NULL, zero-post empty list, non-md artifact listed-not-hydrated).
- `tests/migrations/test_run_log_migration.py` — idempotent re-run; `comms_messages.run_id` added
  nullable; existing rows preserved.
- `tests/http/test_runs_read.py` — `GET /runs` shape + `project_root` scope; `GET /runs/<id>` 200 +
  404; overlay upgrades a live running row.
- AC-6 fault-injection test (above).

---

## 9. Risks + mitigations (P0-specific)

| Risk | Mitigation |
|---|---|
| Spawn write raises into the hot chokepoint | try/except → `logger.debug` only; mirrors `_record_spawn_identity`; AC-6 test |
| Flow→stage window join cross-attributes under back-to-back same-feature runs | accepted for read-only P0 (PO-sanctioned); exact in P1 via parent-run_id stamp |
| Board-post window join cross-attributes concurrent same-board posts | PO constraint b4af4d17; run_id-when-present already wins; exact in P1 |
| stdout tail is not a complete transcript | AC + UI copy state "tail (may be truncated by the PTY buffer)"; run_log is a display sink, not billing authority |
| `run_history` has both flow-parent and stage rows | `_classify_kind` drops `stage` from the list; deterministic by id shape |
| Non-md artifact mojibake | read-model returns metadata only; no `hydrate` call anywhere in the P0 path |

---

## 10. Out of P0 (built in later MVP phases / deferred)
**Now in MVP (designed below):** P1 unified event feed — §11; P2 launcher — §12.
**Deferred (post-MVP):** P3 control (`control_run`/`resolve_run`, `RunControls`, surface merge,
**server-side loop** — the real reload-resilience fix); Pillar 3 artifact type-model; Pillar 4
context-depth toggles; P-1 halt-vs-warn.

---

## 11. P1 — Unified run_id-keyed live feed (make the pane LIVE + exact correlation)

P1 turns the read-only pane live and retires P0's window-join by stamping `run_id` onto board
posts. Additive to P0; the four substrate chokepoints stay untouched.

### 11.1 `sse.py::_broadcast_run_event` — the 4th sink
Add `_run_clients: list[Queue]` + `_broadcast_run_event(payload)` (firehose; optional server-side
`run_id` filter), mirroring the existing `_broadcast_spawn`/`_clients` shape. Feed it from the three
existing broadcast helpers — **one added line each**, the proven `_SPAWN_EVENT_TYPES` mirror
precedent (sse.py:70) — stamping `{channel, run_id, board_scope}`:

| Helper | Added emission |
|---|---|
| `_broadcast_runner(topic, payload)` | `_broadcast_run_event({channel:'runner', run_id: payload.get('run_id'), board_scope: topic, **payload})` |
| `_broadcast_comms(scope, payload)` | `_broadcast_run_event({channel:'comms', run_id: payload.get('run_id'), board_scope: scope, **payload})` |
| `_broadcast_spawn(payload)` | `_broadcast_run_event({channel:'terminal', run_id: payload.get('run_id'), **payload})` |

Net new emission: ~3 lines. The existing 4 channels stay (their consumers unchanged).

### 11.2 `GET /events/runs` — `blueprints/control/run_streams.py` (NEW)
Mirror `/events/spawn`'s topic-independent SSE generator: one always-on subscriber draining
`_run_clients`; filter server-side on `?run_id=` when supplied, else the client filters. Register in
`control/__init__.py` next to `runs_read`. ~70 lines.

### 11.3 Single board-posting path — `blueprints/control/_lifecycle.py::make_board_posters` (NEW)
Extract the three near-identical `_board_post`/`_on_start`/`_on_done` poster closures duplicated in
`comms/runs.py`, `goals.py`, `tasks.py` into one `make_board_posters(board, scope, event, run_id=…)`.
Every post it makes now carries `run_id`, filling the P0 `comms_messages.run_id` column. Then:
- `get_run_detail` §4.3 flips to **prefer `run_id = :run_id` exactly**; the NULL/time-window branch
  survives only for legacy + human + non-poster posts.
- add the deferred `idx_comms_messages_run_id` index.

This is the SOLID de-duplication the SPEC's third seam calls for — three copies → one.

### 11.4 Discrete `board_context_injected` (resolves the P0 §0.1/§2.3 correction)
- `fsm_compose.build_prompt(..., capture: dict|None=None)` → when passed, `capture['board_block'] =
  board_block` (non-breaking; every existing caller passes nothing and is unaffected).
- `next_action` surfaces it as `agent_hint.board_context`; the supervisor threads it as a new
  **optional** kwarg to `_run_stage_via_terminal`; Write-point A (§3.2) fills
  `board_context_injected` instead of NULL. Purely additive to the compose/next_action path.

### 11.5 Studio — live RunDetail
`useRunDetail` opens a `GET /events/runs?run_id=<id>` EventSource on selection; `LogsTab` appends
live stdout + status, `BoardTab` appends new posts — layered **onto** the DB-on-mount baseline. The
"DB on mount, SSE overlay" invariant (AC-5) holds: a reload re-baselines from `GET /runs`, then
re-subscribes.

### 11.6 Acceptance criteria (P1)
- **AC-P1-1:** selecting a *running* run streams its stdout + new board posts + status live from
  **one** `/events/runs?run_id=` subscription.
- **AC-P1-2:** board posts render **run_id-exact** (no window approximation) for runs started after
  P1; legacy NULL posts still resolve via the window fallback.
- **AC-P1-3:** `board_context_injected` is populated discretely (no longer NULL) for new runs.
- **AC-P1-4:** the three former poster closures are gone — one `make_board_posters` covers
  runs/goals/tasks (grep shows no duplicate closure).

---

## 12. P2 — Dispatch facade + unified launcher (START any run kind from one place)

P2 puts one front door — `POST /runs` — over the six entry facades, and one Studio launcher over
the four board buttons. It reimplements no run logic; it routes to the existing `start_*` functions.

### 12.1 `supervisor/dispatch.py::RunSpec` + `dispatch_run` (extends the P0 `dispatch.py`)
`RunSpec` (dataclass) normalizes what varies across the six facades:
```python
@dataclass
class RunSpec:
    kind: str            # flow|board|goal|decompose|task|feature|project
    project_root: str
    topic: str = "";  flow: str = ""                  # flow
    board: str = "feature";  scope: str = ""           # board / evaluate
    goal_id: str = "";  message_id: str = ""           # goal / task
    mode: str = "";  executor_override: str = ""        # decompose mode / executor
    adapter: str = "claude";  model: str = "";  interactive: bool = False
    agent: str = "";  skill: str = "";  instructions: str = ""
    stage_overrides: dict | None = None;  prompt_override: str = "";  ability_ids: list | None = None

def dispatch_run(spec, *, broadcast_fn, on_start, on_done) -> dict:
    # thin switch spec.kind -> the EXISTING start_* fn; returns {ok, run_id, kind, board_scope, status, reason?}
```
Routing: `flow→start_run`, `board/evaluate→start_board_run`, `goal→start_goal_run`,
`decompose→start_goal_decompose`, `task→` the tasks.py claim/complete wrapper, `feature/project→`
the decompose routes. Existing functions + their locks/storage/telemetry are untouched. Layer-safe:
imports only sibling `supervisor/` modules (api, board_run, goal_executor, goal_decomposer).

### 12.2 `POST /runs` — `blueprints/control/runs_control.py` (NEW)
Validate the `RunSpec` JSON body → `dispatch_run(...)` → the uniform envelope. Lifecycle board posts
go through `make_board_posters` (§11.3), so a `/runs`-started run is `run_id`-correlated from birth.
Register in `control/__init__.py`. ~110 lines (validation + the dispatch call).

### 12.3 Studio — `NewRunButton` unified launcher
A target picker (flow / goal / board / task / feature / project) → `POST /runs`, reusing the existing
`FlowGatePreview` gate for `stage_overrides`. Add a `[+ New Run]` control atop the Pipelines
`RunList`. The board's existing launchers (`SingleAgentButton`, `GoalRunButton`,
`EvaluateBoardButton`, `TaskCard` Run) become **thin openers** of `NewRunButton` (they call the one
endpoint); the legacy `/comms/*` and `/runner/start` routes keep working (back-compat).

### 12.4 Acceptance criteria (P2)
- **AC-P2-1:** every run kind (flow/board/goal/decompose/task/feature/project) starts from the one
  launcher via `POST /runs`.
- **AC-P2-2:** a run started via `POST /runs` is **indistinguishable downstream** from one started
  via its legacy route — same `run_id` identity, same telemetry, appears in `GET /runs` and streams
  on `/events/runs`.
- **AC-P2-3:** the old board buttons still function (thin openers); no `/comms/*` or `/runner/start`
  route is removed in the MVP.

### 12.5 What P2 deliberately does NOT do (P3)
No `control_run`/`resolve_run` (drive: pause/resume/advance/reroute/retry), no capability-gated
`RunControls`, no surface merge/retirement of the Monitor/CommsPanel launchers, no server-side run
loop. The launcher *starts* runs; **driving** a run stays on the legacy `FlowControlBar` until P3.
