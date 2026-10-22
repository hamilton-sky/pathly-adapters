"""What hydration stores for every kind of stamp a ``BOARD.json`` row can carry.

A snapshot is a file, so nothing in it is verified (``comms_hydrate._unverified``). A review once
changed that function so ``binding`` was reset only for a row that claimed the ``token`` source,
and the tests that existed still passed: none of them sent a ``binding`` of 1 with every source and
every role. Here each source (absent, ``none``, ``legacy``, ``system``, ``token``) meets each role
(absent, ``chief``, ``builder``), always with ``binding`` 1, through ``insert_message_row`` and
through ``hydrate_board``:

* ``binding`` is stored as 0 every time;
* ``none`` stays ``none`` (the read wall withholds it; ``legacy`` would show it);
* ``legacy``, ``system`` and ``token`` are stored as ``legacy``;
* an absent source is stored as NULL by the insert alone and as ``legacy`` once ``hydrate_board``
  has run its backfill;
* the role and the run id are stored as the file names them, which is documented, so pinned. The
  one exception is a row with no source after ``hydrate_board``: the backfill labels it ``legacy``
  and takes its role from ``from_agent`` (``add_comms_provenance`` says so), and keeps the run id.
"""

from __future__ import annotations

import pytest
from binding_guard_support import _no_embedding_threads, message, row, write_board

from pathly_orchestrator.board_mirror import hydrate_board
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import insert_message_row

ABSENT = "(absent)"
SOURCES = [ABSENT, "none", "legacy", "system", "token"]
ROLES = [None, "chief", "builder"]
STORED_BY_INSERT = {
    ABSENT: None,
    "none": "none",
    "legacy": "legacy",
    "system": "legacy",
    "token": "legacy",
}
STORED_BY_HYDRATE = {**STORED_BY_INSERT, ABSENT: "legacy"}
FROM_AGENT = "human"  # what ``binding_guard_support.message`` writes as ``from_agent``


def _claim(mid: str, source: str, role: str | None) -> dict:
    """A snapshot row of the feature board ``feat`` that claims to be a standing order."""
    claim = {
        "to_agent": "builder",
        "status": "active",
        "binding": 1,
        "author_role": role,
        "author_run_id": None if role is None else f"run-of-{role}",
    }
    if source != ABSENT:
        claim["author_source"] = source
    return message(mid, "feature", "feat", **claim)


def _id(source: str, role: str | None) -> str:
    return f"m-{source}-{role}".replace("(", "").replace(")", "")


@pytest.mark.parametrize("role", ROLES, ids=str)
@pytest.mark.parametrize("source", SOURCES)
def test_insert_message_row_stores_no_order_and_no_verified_stamp(source, role):
    mid = _id(source, role)

    insert_message_row(get_db(), _claim(mid, source, role))

    stored = row(mid)
    assert stored is not None
    assert stored["binding"] == 0
    assert stored["author_source"] == STORED_BY_INSERT[source]
    assert stored["author_role"] == role
    assert stored["author_run_id"] == (None if role is None else f"run-of-{role}")


@pytest.mark.parametrize("role", ROLES, ids=str)
@pytest.mark.parametrize("source", SOURCES)
def test_hydrate_board_stores_no_order_and_no_verified_stamp(tmp_path, source, role):
    mid = _id(source, role)
    path = write_board(
        tmp_path / "BOARD.json", "feature", "feat", [_claim(mid, source, role)]
    )

    assert hydrate_board(get_db(), "feature", "feat", path) is True

    stored = row(mid)
    assert stored["binding"] == 0
    assert stored["author_source"] == STORED_BY_HYDRATE[source]
    assert stored["author_role"] == (FROM_AGENT if source == ABSENT else role)
    assert stored["author_run_id"] == (None if role is None else f"run-of-{role}")


def test_every_claim_of_one_file_is_stored_without_an_order(tmp_path):
    """The same rows in one file: the first row's stamp does not decide the others'."""
    claims = [_claim(_id(s, r), s, r) for s in SOURCES for r in ROLES]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat", claims)

    assert hydrate_board(get_db(), "feature", "feat", path) is True

    stored = get_db().execute(
        "SELECT binding, author_source FROM comms_messages WHERE board='feature'"
    )
    pairs = {(r["binding"], r["author_source"]) for r in stored.fetchall()}
    assert pairs == {(0, "legacy"), (0, "none")}
    assert (
        get_db()
        .execute("SELECT COUNT(*) FROM comms_messages WHERE binding != 0")
        .fetchone()[0]
        == 0
    )
