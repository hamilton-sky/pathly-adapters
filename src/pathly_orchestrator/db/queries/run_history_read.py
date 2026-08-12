"""Unified run read-model: list top-level runs + per-run detail (unified-control-plane P0).

db/ layer — imports only db/connection-siblings (``fsm_events._norm``, ``run_log``). Read
only: every function takes a ``conn`` and never writes, never locks. Backs ``GET /runs`` and
``GET /runs/<run_id>`` (the new ``control`` blueprint).

The run-grain decision (ARCHITECTURE §1): list at the TOP-LEVEL run grain and fold FSM
stage spawns into RunDetail. A run's kind is inferred from its run_id SHAPE — how the system
actually mints identity, so no new plumbing — plus the ``run_history`` adapter, by
``_classify_kind``. Cost comes from ``agent_invocations`` (the same fact table the Monitor
RECENT cards read → figures reconcile, §1.1); status comes from ``run_history`` (so RUNNING
runs appear, which RECENT cannot show).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from .fsm_events import _norm
from .run_log import get_run_log

# Flow-style adapters: a bare-uuid run_history row whose adapter is one of these is a flow
# PARENT (its stages are separate per-stage rows, folded into detail). Any other bare-uuid
# run is a board ``single``.
FLOW_NAMES = {
    "team",
    "team-build",
    "consultation",
    "feature-consultation",
    "project-consultation",
}

# A per-stage (CHILD-of-a-flow) run_id: ``{topic}-{N}-{ts}`` with an optional retry suffix
# ``-q{n}`` / ``-fb{n}`` (orchestrator.py stage ids). Matched as a SUFFIX (no ^ anchor).
# Edge accepted per ARCHITECTURE §1/§1.1: a bare uuid whose last TWO groups are both
# all-numeric (e.g. ``...-4444-555566667777``) also matches — vanishingly rare for real
# hex uuids, and made exact in P1 by stamping the parent run_id onto stage rows.
_STAGE_RE = re.compile(r"-\d+-\d{10,}(-(?:q|fb)\d+)?$")

# run_log columns surfaced in a RunDetail "logs" entry (ARCHITECTURE §4.2).
_LOG_KEYS = ("stage", "prompt_sent", "board_context_injected", "stdin", "stdout", "ts")


def _now_iso() -> str:
    """UTC now as an ISO-8601 'T' string.

    Matches the stored ``started_at`` / ``ts`` format so a time-window ``BETWEEN`` over a
    still-running run compares chronologically. SQLite's ``datetime('now')`` emits a
    SPACE-separated string that sorts BEFORE any 'T' timestamp, so it must NOT be used as
    the open-ended upper bound here (that would silently drop every in-window row).
    """
    return datetime.now(timezone.utc).isoformat()


def _classify_kind(run_id: str, adapter: str | None) -> str:
    """Classify a run by run_id shape + adapter (ARCHITECTURE §1).

    Returns ``'loop'`` | ``'stage'`` | ``'flow'`` | ``'single'``. ``'stage'`` is a CHILD of a
    flow — excluded from ``list_runs`` and folded into the parent's RunDetail. ``'loop'`` covers
    BOTH a loop's per-task ``sched-*`` rows (children) AND its bare-uuid PARENT (adapter
    ``goal-loop``); the two are told apart by run_id shape (``_is_parent``), so the parent windows
    its ``sched-*`` tasks like a flow windows its stages.
    """
    rid = run_id or ""
    if rid.startswith("sched-"):
        return "loop"
    if _STAGE_RE.search(rid):
        return "stage"
    a = adapter or ""
    if a in FLOW_NAMES:
        return "flow"
    if (
        a == "goal-loop"
    ):  # goal `loop` executor PARENT (supervisor/goal_executor._run_loop)
        return "loop"
    return "single"


def _is_parent(run_id: str, adapter: str | None) -> bool:
    """A windowed PARENT run: its children are separate run_history rows folded into its detail
    and out of ``list_runs``, and its cost is summed over the child time-window (not its own
    run_id, which carries no invocations). True for flow/decompose and for a loop PARENT
    (``goal-loop`` adapter on a bare uuid — a loop TASK is ``sched-*`` and is a child, not a
    parent)."""
    kind = _classify_kind(run_id, adapter)
    if kind in ("flow", "decompose"):
        return True
    return kind == "loop" and not (run_id or "").startswith("sched-")


def _run_cost(
    conn: sqlite3.Connection, row: sqlite3.Row, kind: str
) -> tuple[float, int, int]:
    """``(cost_usd, tokens_total, invocations)`` for one top-level run, from
    ``agent_invocations`` — the SAME fact table the Monitor RECENT cards read, so the
    figures reconcile (§1.1).

    single / loop-task / stage → exact SUM over ``run_id``. PARENT runs (flow / decompose /
    loop parent, ``_is_parent``) → SUM over the child time-window (``project_root`` + ``feature``
    + ``board_scope``, ``started_at`` within the parent's lifespan) — the PO-sanctioned window
    join (approximate under back-to-back same-board runs; made exact in P1 by stamping the parent
    run_id onto child rows).
    """
    if _is_parent(row["run_id"], row["adapter"]):
        upper = row["finished_at"] or _now_iso()
        agg = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) c, "
            "COALESCE(SUM(COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0)), 0) t, "
            "COUNT(*) n FROM agent_invocations "
            "WHERE project_root=? AND feature=? AND COALESCE(board_scope, feature)=? "
            "AND started_at BETWEEN ? AND ?",
            (
                row["project_root"],
                row["feature"],
                row["board_scope"] or row["feature"],
                row["started_at"],
                upper,
            ),
        ).fetchone()
    else:
        agg = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) c, "
            "COALESCE(SUM(COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0)), 0) t, "
            "COUNT(*) n FROM agent_invocations WHERE run_id=?",
            (row["run_id"],),
        ).fetchone()
    return float(agg["c"] or 0.0), int(agg["t"] or 0), int(agg["n"] or 0)


def list_runs(
    conn: sqlite3.Connection, project_root: str, limit: int = 50
) -> list[dict]:
    """One row per TOP-LEVEL run for ``project_root`` (ARCHITECTURE §4.1).

    Stage rows are folded out; a loop's per-task ``sched-*`` rows fold under their loop parent
    (so a loop shows as ONE row, not parent + N tasks — a legacy parent-less loop still shows its
    tasks); running rows appear (status from ``run_history``). Newest first (by ``finished_at``
    else ``started_at``), capped at ``limit``. Each row: ``{run_id, kind, feature, board_scope,
    status, adapter, started_at, finished_at, stage_count, cost_usd, tokens_total}``.
    """
    pr = _norm(project_root or "")
    if not pr:
        return []
    rows = conn.execute(
        "SELECT * FROM run_history WHERE project_root=? "
        "ORDER BY COALESCE(finished_at, started_at) DESC",
        (pr,),
    ).fetchall()
    # Loop parents in this set — their sched-* task rows fold under them (like stages under a
    # flow). A parent-less (legacy) loop has nothing covering its tasks, so those still show.
    loop_parents = [
        r
        for r in rows
        if not (r["run_id"] or "").startswith("sched-")
        and _classify_kind(r["run_id"], r["adapter"]) == "loop"
    ]

    def _folded_loop_task(r: sqlite3.Row) -> bool:
        if not (r["run_id"] or "").startswith("sched-"):
            return False
        st = r["started_at"] or ""
        return any(
            p["feature"] == r["feature"]
            and (p["board_scope"] or p["feature"]) == (r["board_scope"] or r["feature"])
            and (p["started_at"] or "") <= st <= (p["finished_at"] or _now_iso())
            for p in loop_parents
        )

    out: list[dict] = []
    cap = max(1, limit)
    for r in rows:
        kind = _classify_kind(r["run_id"], r["adapter"])
        if kind == "stage" or _folded_loop_task(r):
            continue
        cost_usd, tokens_total = _run_cost(conn, r, kind)[:2]
        stage_count = r["stage_count"] or (1 if kind in ("single", "loop") else 0)
        out.append(
            {
                "run_id": r["run_id"],
                "kind": kind,
                "feature": r["feature"],
                "board_scope": r["board_scope"],
                "status": r["status"],
                "adapter": r["adapter"],
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "stage_count": stage_count,
                "cost_usd": cost_usd,
                "tokens_total": tokens_total,
            }
        )
        if len(out) >= cap:
            break
    return out


def _child_rows(conn: sqlite3.Connection, parent: sqlite3.Row) -> list[sqlite3.Row]:
    """Child ``run_history`` rows folded into a PARENT run's detail (§1.1 window join), within
    the parent's lifespan (``project_root`` + ``feature`` + ``board_scope`` + timespan), excluding
    the parent itself. For a flow/decompose parent the children are stage-shaped rows; for a loop
    parent they are the per-task ``sched-*`` rows. A back-to-back sibling PARENT (a bare uuid) is
    neither stage- nor sched-shaped → dropped."""
    upper = parent["finished_at"] or _now_iso()
    rows = conn.execute(
        "SELECT * FROM run_history "
        "WHERE project_root=? AND feature=? AND COALESCE(board_scope, feature)=? "
        "AND started_at BETWEEN ? AND ? ORDER BY started_at ASC",
        (
            parent["project_root"],
            parent["feature"],
            parent["board_scope"] or parent["feature"],
            parent["started_at"],
            upper,
        ),
    ).fetchall()
    is_loop = _classify_kind(parent["run_id"], parent["adapter"]) == "loop"
    out: list[sqlite3.Row] = []
    for r in rows:
        if r["run_id"] == parent["run_id"]:
            continue
        rid = r["run_id"] or ""
        if is_loop:
            if rid.startswith("sched-"):
                out.append(r)
        elif _classify_kind(rid, r["adapter"]) == "stage":
            out.append(r)
    return out


def _enrich_stage(conn: sqlite3.Connection, r: sqlite3.Row) -> dict:
    """A RunDetail stage entry: identity + status from ``run_history``, cost/tokens + the
    stage NAME from ``agent_invocations`` (``run_history`` has no stage-name column; fall
    back to ``run_log.stage`` when the run wrote no invocation)."""
    agg = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) c, "
        "COALESCE(SUM(COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0)), 0) t, "
        "MAX(stage) stg FROM agent_invocations WHERE run_id=?",
        (r["run_id"],),
    ).fetchone()
    stage_name = agg["stg"]
    if not stage_name:
        logs = get_run_log(conn, r["run_id"])
        stage_name = logs[0]["stage"] if logs else None
    return {
        "run_id": r["run_id"],
        "stage": stage_name,
        "adapter": r["adapter"],
        "status": r["status"],
        "started_at": r["started_at"],
        "finished_at": r["finished_at"],
        "cost_usd": float(agg["c"] or 0.0),
        "tokens": int(agg["t"] or 0),
    }


def _board_posts(
    conn: sqlite3.Connection,
    run_id: str,
    board_scope: str,
    started_at: str | None,
    finished_at: str | None,
) -> list[dict]:
    """Board posts correlated to this run: run_id-when-present, else the P0 time-window
    fallback over the run's board scope (ARCHITECTURE §4.3, PO constraint b4af4d17). Zero
    posts → ``[]`` (empty Board tab, never an error). Approximate under concurrent
    same-board runs (accepted for read-only P0; exact in P1 once posts are run_id-stamped).
    """
    upper = finished_at or _now_iso()
    rows = conn.execute(
        "SELECT id, from_agent, type, text, ts, run_id FROM comms_messages "
        "WHERE deleted_at IS NULL AND ("
        "  run_id=? OR (run_id IS NULL AND scope=? AND ts BETWEEN ? AND ?)) "
        "ORDER BY ts ASC",
        (run_id, board_scope, started_at, upper),
    ).fetchall()
    return [dict(r) for r in rows]


def _artifacts(
    conn: sqlite3.Connection,
    run_id: str,
    board_scope: str,
    started_at: str | None,
    finished_at: str | None,
) -> list[dict]:
    """Artifacts on posts correlated to this run — same run_id/window filter as the board
    posts. Metadata ONLY (``{path, type, title, summary}``); NO ``hydrate`` call, so a
    non-md artifact is listed by type/path and never mojibake (AC-4)."""
    upper = finished_at or _now_iso()
    rows = conn.execute(
        "SELECT a.path, a.type, a.title, a.summary FROM comms_artifacts a "
        "JOIN comms_messages m ON m.id = a.message_id "
        "WHERE m.deleted_at IS NULL AND ("
        "  m.run_id=? OR (m.run_id IS NULL AND m.scope=? AND m.ts BETWEEN ? AND ?)) "
        "ORDER BY a.created_at ASC",
        (run_id, board_scope, started_at, upper),
    ).fetchall()
    return [dict(r) for r in rows]


def get_run_detail(conn: sqlite3.Connection, run_id: str) -> dict:
    """Full RunDetail for one run (ARCHITECTURE §4.2): identity+lifecycle, stages, per-stage
    ``run_log`` logs, correlated board posts + artifacts, and cost. Unknown run_id →
    ``{"run": None, ...}`` (the route turns that into a 404)."""
    row = conn.execute("SELECT * FROM run_history WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return {
            "run": None,
            "stages": [],
            "logs": [],
            "board": [],
            "artifacts": [],
            "cost": {"cost_usd": 0.0, "tokens_total": 0, "invocations": 0},
        }

    kind = _classify_kind(row["run_id"], row["adapter"])
    if _is_parent(row["run_id"], row["adapter"]):
        stage_rows: list[sqlite3.Row] = _child_rows(conn, row)
    else:
        stage_rows = [row]
    stages = [_enrich_stage(conn, sr) for sr in stage_rows]

    logs: list[dict] = []
    for sr in stage_rows:
        for lr in get_run_log(conn, sr["run_id"]):
            logs.append({k: lr.get(k) for k in _LOG_KEYS})

    cost_usd, tokens_total, invocations = _run_cost(conn, row, kind)
    board_scope = row["board_scope"] or row["feature"]
    board = _board_posts(
        conn, row["run_id"], board_scope, row["started_at"], row["finished_at"]
    )
    artifacts = _artifacts(
        conn, row["run_id"], board_scope, row["started_at"], row["finished_at"]
    )

    run = dict(row)
    run.update({"kind": kind, "cost_usd": cost_usd, "tokens_total": tokens_total})
    return {
        "run": run,
        "stages": stages,
        "logs": logs,
        "board": board,
        "artifacts": artifacts,
        "cost": {
            "cost_usd": cost_usd,
            "tokens_total": tokens_total,
            "invocations": invocations,
        },
    }
