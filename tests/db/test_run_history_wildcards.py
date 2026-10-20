"""chief-agent 08 (round 8): a feature name is matched literally against legacy run_history rows.

Rows written before the slug keying fix hold a full topic path in ``feature``; the readers match
them by the last segment (``feature LIKE '%/' || ?``). That used to treat a ``%`` or ``_`` in the
name as a wildcard, so the name ``%`` was "the last project to run a feature" whatever its name,
and the board mirror (which places a feature board's ``BOARD.json`` by that lookup) wrote
``<that project>/pathly/features/%/BOARD.json``. The name is escaped now (``%``, ``_`` and the
escape character itself), so only a row whose last segment IS the name matches.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_history import (
    latest_project_root_for_feature,
    latest_running_run_id_for_feature,
    read_run_history,
    upsert_run,
)

OTHER = "C:/proj-b"


def _legacy(path: str, run_id: str, status: str = "running") -> None:
    upsert_run(get_db(), OTHER, path, run_id, status)


@pytest.mark.parametrize("name", ["%", "_", "de%", "%mo", "d_mo", "_emo", "de_o", "\\"])
def test_a_wildcard_in_a_name_matches_no_legacy_row(name: str) -> None:
    _legacy("features/demo", "run-old")
    conn = get_db()

    assert latest_project_root_for_feature(conn, name) is None
    assert latest_running_run_id_for_feature(conn, name) is None
    assert read_run_history(conn, OTHER, name) == []


@pytest.mark.parametrize(
    "stored, name",
    [
        ("features/100%", "100%"),
        ("features/my_feature", "my_feature"),
        ("features/back\\slash", "back\\slash"),
        ("features/demo", "demo"),
        ("features/parent/goals/g1-slug", "g1-slug"),
    ],
)
def test_a_name_that_holds_a_wildcard_character_still_matches_itself(
    stored: str, name: str
) -> None:
    _legacy(stored, "run-old")
    conn = get_db()

    assert latest_project_root_for_feature(conn, name) == OTHER
    assert latest_running_run_id_for_feature(conn, name) == "run-old"
    assert [r["run_id"] for r in read_run_history(conn, OTHER, name)] == ["run-old"]


@pytest.mark.parametrize(
    "stored, name",
    [
        ("features/1000", "100%"),
        ("features/myXfeature", "my_feature"),
        ("features/xdemo", "demo"),
    ],
)
def test_a_name_with_a_wildcard_character_matches_no_other_row(
    stored: str, name: str
) -> None:
    _legacy(stored, "run-old")
    conn = get_db()

    assert latest_project_root_for_feature(conn, name) is None
    assert read_run_history(conn, OTHER, name) == []
