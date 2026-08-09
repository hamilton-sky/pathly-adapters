"""FSM-flow parent-row identity in the run read-model (unified-control-plane spawn-tracking).

Two gaps this locks down:
  GAP 1 — a completed FSM flow must stay ``kind='flow'`` with real (window-summed) cost. The
    bug: the terminal run_history write stamped the LAST STAGE's CLI adapter ("claude") over the
    flow name, so ``_classify_kind`` reclassified the parent uuid to ``single`` and its cost
    collapsed to $0 (no invocation carries the parent uuid). Fixed by writing ``state.flow`` as
    the parent adapter (``registry._record_run_history``).
  GAP 2 — the team executor + consultation/feature/project decomposes call ``start_run``
    directly (bypassing POST /runner/start), so nothing top-level appeared in GET /runs until the
    run finished. Fixed by an early ``running`` row in ``start_run`` (same helper).

Isolation via the _isolate_db autouse fixture (conftest.py).
"""

from __future__ import annotations

import sqlite3

import pytest

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_history import upsert_run
from pathly_orchestrator.db.queries.run_history_read import list_runs

PR = "C:/tmp/flowkindproj"
FEAT = "flowfeat"
PARENT = "ababcdef-1234-5678-9abc-def012345678"  # bare hex uuid (letter-tailed → not stage-shaped)
ST1 = "flowfeat-1-1784800000000"  # {topic}-{N}-{ts} -> stage-shaped
T0 = "2026-07-30T10:00:00+00:00"
S1 = "2026-07-30T10:00:05+00:00"
TF = "2026-07-30T10:05:00Z"

_AI = (
    "INSERT INTO agent_invocations "
    "(project_root,feature,run_id,stage,started_at,tokens_in,tokens_out,cost_usd,board_scope) "
    "VALUES (?,?,?,?,?,?,?,?,?)"
)


def _ins(conn: sqlite3.Connection, sql: str, args: tuple) -> None:
    conn.execute(sql, args)
    conn.commit()


def test_record_run_history_stamps_flow_name_not_cli_adapter() -> None:
    """GAP 1 (unit): the helper writes state.flow as the parent adapter, at both running and
    finish — even though state.current_adapter is a real CLI ("claude")."""
    from pathly_orchestrator.supervisor.registry import _record_run_history
    from pathly_orchestrator.supervisor.state import RunnerState

    conn = get_db()
    state = RunnerState(
        topic=FEAT,
        flow="team-build",
        project_root=PR,
        model="",
        timeout=600,
        run_id=PARENT,
        storage_path="/x/flowfeat",  # .name == FEAT (deterministic slug, no path probe)
        board_scope=FEAT,
        current_adapter="claude",  # the value the OLD code wrongly wrote
        iterations=3,
    )

    _record_run_history(state, "running")
    row = conn.execute(
        "SELECT adapter, status, feature, board_scope FROM run_history WHERE run_id=?",
        (PARENT,),
    ).fetchone()
    assert row["adapter"] == "team-build"  # flow name, NOT current_adapter ("claude")
    assert row["status"] == "running"
    assert row["feature"] == FEAT and row["board_scope"] == FEAT

    _record_run_history(state, "done", finished_at=TF)
    row2 = conn.execute(
        "SELECT adapter, status FROM run_history WHERE run_id=?", (PARENT,)
    ).fetchone()
    assert row2["adapter"] == "team-build"  # NOT clobbered to "claude" at finish
    assert row2["status"] == "done"


def test_flow_parent_visible_while_running_and_costed_after() -> None:
    """GAP 2 (visible while running) + GAP 1 (window cost after) through the read-model."""
    conn = get_db()
    # The early 'running' row start_run now writes (adapter = flow name).
    upsert_run(conn, PR, FEAT, PARENT, "running", started_at=T0,
               adapter="team-build", board_scope=FEAT)
    _ins(conn, _AI, (PR, FEAT, ST1, "BUILDING", S1, 1000, 2000, 1.25, FEAT))

    running = {r["run_id"]: r for r in list_runs(conn, PR)}
    assert PARENT in running  # GAP 2: visible WHILE running (was invisible until finish)
    assert running[PARENT]["kind"] == "flow" and running[PARENT]["status"] == "running"

    # Finish keeps the flow name → stays 'flow' with window-summed cost (not single/$0).
    upsert_run(conn, PR, FEAT, PARENT, "done", finished_at=TF,
               adapter="team-build", board_scope=FEAT)
    done = {r["run_id"]: r for r in list_runs(conn, PR)}
    assert done[PARENT]["kind"] == "flow"  # GAP 1: not reclassified to 'single'
    assert done[PARENT]["cost_usd"] == pytest.approx(1.25)  # window sum, NOT $0
    assert done[PARENT]["status"] == "done"


def test_finishing_with_cli_adapter_would_regress_to_single_zero() -> None:
    """Documents the exact bug the fix prevents: stamping the last stage's CLI adapter
    ("claude") on the parent row reclassifies it to single + $0."""
    conn = get_db()
    upsert_run(conn, PR, FEAT, PARENT, "running", started_at=T0,
               adapter="team-build", board_scope=FEAT)
    _ins(conn, _AI, (PR, FEAT, ST1, "BUILDING", S1, 1000, 2000, 1.25, FEAT))
    # The clobber (upsert_run adapter COALESCE is new-value-wins).
    upsert_run(conn, PR, FEAT, PARENT, "done", finished_at=TF,
               adapter="claude", board_scope=FEAT)

    done = {r["run_id"]: r for r in list_runs(conn, PR)}
    assert done[PARENT]["kind"] == "single"  # misclassified
    assert done[PARENT]["cost_usd"] == 0.0  # cost lost
