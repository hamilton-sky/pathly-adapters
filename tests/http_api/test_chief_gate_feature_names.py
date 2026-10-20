"""chief-agent 08 (round 8): a feature name is one name, not a pattern.

A feature board is keyed by its name alone, so the board mirror places its ``BOARD.json`` in the
project ``run_history`` last mapped that name to. The lookup matched a legacy row (one whose
``feature`` is a full topic path) with ``LIKE '%/' || name``, so a ``%`` or ``_`` in the name
was a wildcard and a planner chief on project A could name a feature board ``%``, which the
mirror then wrote into project B (``<B>/pathly/features/%/BOARD.json``) without the chief
knowing any name of B's. ``%`` is a legal feature name for the gate (one folder name), so the
lookup has to treat it literally.
"""

from __future__ import annotations

import pytest
from chief_audit_sandbox import drain_the_mirrors

from chief_gate_support import (
    _chief,
    _count,
    _msg,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)


@pytest.fixture()
def legacy_run_of_b(other_project):
    """Project B ran a feature ``demo`` before run_history keyed rows by slug, so its row holds
    the full topic path.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_history import upsert_run

    upsert_run(get_db(), str(other_project), "features/demo", "run-old", "done")


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("scope", ["%", "_", "d%", "%o", "d_mo", "_emo", "dem_", "%%"])
def test_a_wildcard_scope_plants_no_board_file_in_another_project(
    client, project, other_project, legacy_run_of_b, tier, scope
):
    chief = _chief(tier, project)

    resp = client.post(
        "/comms/post",
        json=_msg("note", board="feature", scope=scope),
        headers=chief.headers,
    )
    drain_the_mirrors()

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE scope = ?", scope) == 1
    assert not (other_project / "pathly").exists()
    assert list(other_project.rglob("BOARD.json")) == []


def test_the_mirror_places_no_wildcard_board_anywhere(
    client, project, other_project, legacy_run_of_b
):
    from pathly_orchestrator.board_mirror import resolve_project_root
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()

    assert resolve_project_root(conn, "feature", "%") is None
    assert resolve_project_root(conn, "feature", "de_o") is None
    assert resolve_project_root(conn, "feature", "demo") == str(other_project)
