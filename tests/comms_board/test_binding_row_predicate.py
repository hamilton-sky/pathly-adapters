"""One module says what "binding" means for a board row (``runner/comms_binding.py``).

The standing-orders query selects ``binding = 1``. The pending filter of ``comms_governance`` and
the Context filter of ``comms_context`` used to take any truthy value, so a row whose ``binding``
was ``2`` (no code writes one) was dropped from the pending list and read as no order anywhere
else. Both now ask ``is_binding_row``: such a row is an ordinary row everywhere.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from binding_support import (
    ROOT,
    governance_part,
    post,
    ranked_part,
    render,
    standing_part,
)


@pytest.fixture(autouse=True)
def _recency_path(monkeypatch):
    """No embedding model: the Context channel falls back to recency (and no download is tried)."""
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(emb, "embed_async", lambda *a, **k: None)
    monkeypatch.setattr(emb, "embed", lambda *a, **k: None)


@pytest.mark.parametrize(
    "row,expected",
    [
        ({"binding": 1}, True),
        ({"binding": 0}, False),
        ({"binding": None}, False),
        ({"binding": 2}, False),
        ({"binding": "1"}, False),
        ({}, False),
        ({"id": "x", "text": "no binding key"}, False),
    ],
)
def test_only_a_binding_of_one_is_binding(row, expected):
    from pathly_orchestrator.runner.comms_binding import is_binding_row

    assert is_binding_row(row) is expected


def test_the_mark_is_defined_once_and_the_three_modules_use_it():
    from pathly_orchestrator.runner import (
        comms_binding,
        comms_context,
        comms_formatters,
        comms_governance,
    )

    assert comms_binding.BINDING_MARK == "_binding"
    assert comms_governance.BINDING_MARK is comms_binding.BINDING_MARK
    assert comms_formatters.BINDING_MARK is comms_binding.BINDING_MARK
    assert comms_context.is_binding_row is comms_binding.is_binding_row
    assert comms_governance.is_binding_row is comms_binding.is_binding_row


def test_the_governance_module_imports_the_formatter_at_the_top_of_the_file():
    from pathly_orchestrator.runner import comms_governance

    top = ast.parse(inspect.getsource(comms_governance)).body
    names = [
        alias.name
        for node in top
        if isinstance(node, ast.ImportFrom) and node.module == "comms_formatters"
        for alias in node.names
    ]
    assert names == ["render_governance_lines"]


def test_a_pending_row_with_a_binding_of_two_stays_in_the_pending_half():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.runner.comms_governance import governance_decisions

    ordinary = post("An ordinary pending decision.", acked=False)
    odd = post("A pending decision whose binding is two.", binding=2, acked=False)
    order = post("A real standing order.", binding=1, acked=False)

    rows = governance_decisions(get_db(), ["project"], [ROOT], "builder", ROOT)

    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {ordinary, odd, order}
    assert "_binding" not in by_id[ordinary]
    assert "_binding" not in by_id[odd]
    assert by_id[order]["_binding"] is True
    assert (
        len(rows) == 3
    ), "the order is listed once, not once as pending and once as an order"


def test_a_binding_of_two_is_ranked_with_the_ordinary_decisions_and_not_a_standing_order():
    post("A pending decision whose binding is two.", binding=2, acked=False)
    post("A real standing order.", binding=1, acked=False)

    gov = governance_part(render("builder"))

    assert "A pending decision whose binding is two." in ranked_part(gov)
    assert "A pending decision whose binding is two." not in standing_part(gov)
    assert "A real standing order." in standing_part(gov)
    assert "A real standing order." not in ranked_part(gov)
