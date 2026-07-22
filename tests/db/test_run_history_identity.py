"""run-identity: run_history as the identity map run_id -> (project_root, slug, board_scope).

New rows key `feature` by the run SLUG (storage-dir basename) and carry the spawn-issued
board_scope. Legacy rows (full topic paths like features/<f>/goals/<slug>) are never
rewritten — the read helpers resolve them via a basename-normalization shim.
"""

from __future__ import annotations

from pathlib import Path

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_history import (
    latest_project_root_for_feature,
    read_run_history,
    upsert_run,
)

PR = "C:/proj"


def test_run_history_board_scope_column_and_persist(tmp_path: Path) -> None:
    conn = get_db()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(run_history)").fetchall()}
    assert "board_scope" in cols
    upsert_run(conn, PR, "g1-slug", "run-1", "running", board_scope="parent-feat")
    rows = read_run_history(conn, PR, "g1-slug")
    assert len(rows) == 1
    assert rows[0]["board_scope"] == "parent-feat"
    assert rows[0]["feature"] == "g1-slug"


def test_upsert_board_scope_is_issue_once(tmp_path: Path) -> None:
    """The spawn-issued board_scope survives later upserts (existing wins; NULL is filled)."""
    conn = get_db()
    upsert_run(conn, PR, "g1-slug", "run-2", "running", board_scope="parent-feat")
    # a later finish-upsert without board_scope must not erase it
    upsert_run(conn, PR, "g1-slug", "run-2", "done")
    rows = read_run_history(conn, PR, "g1-slug")
    assert rows[0]["board_scope"] == "parent-feat"
    assert rows[0]["status"] == "done"
    # ... and a later DIFFERENT value must not overwrite the issued one
    upsert_run(conn, PR, "g1-slug", "run-2", "done", board_scope="other")
    assert read_run_history(conn, PR, "g1-slug")[0]["board_scope"] == "parent-feat"
    # ... but a NULL one gets filled by the first non-NULL writer
    upsert_run(conn, PR, "g1-slug", "run-3", "running")
    upsert_run(conn, PR, "g1-slug", "run-3", "done", board_scope="late-fill")
    by_run = {r["run_id"]: r for r in read_run_history(conn, PR, "g1-slug")}
    assert by_run["run-3"]["board_scope"] == "late-fill"


def test_legacy_full_path_rows_resolve_by_slug(tmp_path: Path) -> None:
    """A legacy row keyed by the full topic path still resolves by its slug."""
    conn = get_db()
    legacy = "features/parent-feat/goals/g9-legacy-slug"
    upsert_run(conn, PR, legacy, "run-legacy", "done")

    rows = read_run_history(conn, PR, "g9-legacy-slug")
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-legacy"

    assert latest_project_root_for_feature(conn, "g9-legacy-slug") == PR


def test_plain_slug_rows_unaffected_by_shim(tmp_path: Path) -> None:
    conn = get_db()
    upsert_run(conn, PR, "plain-feat", "run-p1", "done")
    rows = read_run_history(conn, PR, "plain-feat")
    assert len(rows) == 1
    # the shim must not over-match: a different slug finds nothing
    assert read_run_history(conn, PR, "feat") == []
    assert latest_project_root_for_feature(conn, "plain-feat") == PR


def test_registry_finish_upsert_keys_by_slug(tmp_path: Path) -> None:
    """The supervisor's terminal-status upsert keys feature by the run SLUG, not the
    nested topic path (the retired keying-by-full-topic-path residual)."""
    from pathly_orchestrator.supervisor.registry import _set_status
    from pathly_orchestrator.supervisor.state import RunnerState

    storage = tmp_path / "pathly" / "features" / "parent-feat" / "goals" / "g1-slug"
    storage.mkdir(parents=True, exist_ok=True)
    state = RunnerState(
        topic="features/parent-feat/goals/g1-slug",
        flow="team-build",
        project_root=str(tmp_path),
        model="m",
        timeout=60,
        run_id="run-reg-1",
        board_scope="parent-feat",
    )
    state.storage_path = str(storage)
    _set_status(state, "done", None)

    conn = get_db()
    row = conn.execute(
        "SELECT feature, board_scope FROM run_history WHERE run_id='run-reg-1'"
    ).fetchone()
    assert row is not None, "finish upsert wrote no run_history row"
    assert row["feature"] == "g1-slug"
    assert row["board_scope"] == "parent-feat"


def test_spawn_identity_row_written_at_chokepoint(tmp_path: Path) -> None:
    """Every spawn (runner/board/goal) issues an identity row up front — the
    _record_spawn_identity helper _run_stage_via_terminal calls."""
    from pathly_orchestrator.supervisor.state import RunnerState
    from pathly_orchestrator.supervisor.terminal import _record_spawn_identity

    storage = tmp_path / "pathly" / "features" / "feat-x"
    storage.mkdir(parents=True, exist_ok=True)
    state = RunnerState(
        topic="feat-x",
        flow="goal-loop",
        project_root=str(tmp_path),
        model="m",
        timeout=60,
        run_id="loop-run",
        board_scope="parent-feat",
    )
    state.storage_path = str(storage)
    _record_spawn_identity(state, "sched-task-1", "claude")

    conn = get_db()
    row = conn.execute(
        "SELECT project_root, feature, board_scope, status, adapter "
        "FROM run_history WHERE run_id='sched-task-1'"
    ).fetchone()
    assert row is not None
    assert row["feature"] == "feat-x"
    assert row["board_scope"] == "parent-feat"
    assert row["status"] == "running"
    assert row["adapter"] == "claude"
