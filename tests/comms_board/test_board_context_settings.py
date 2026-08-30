"""Board-context size is configured and measured, not hardcoded.

The Context channel used to be sized by two unjustified literals: ``CONTEXT_CHAR_BUDGET
= 2000`` in ``context_budget.py`` and the ``3``/``2``/``1`` k-ladder inline in
``comms_context.enabled_boards`` — neither with any recorded calibration, four lines
below cosine cutoffs that DO carry one. Both are now app_settings-backed
(``context_settings.py``, defaults 4000 and 5/3/2) and every prompt build records a
``BOARD_CONTEXT`` event (``context_record.py``) with what it actually rendered vs
dropped, so the next move on those numbers can be measured.

These tests pin three things: the defaults, that a bad setting can never reach the
renderer OR raise, and that the measurement is written (and that failing to write it
never costs the agent its context).
"""

from __future__ import annotations

import pytest

from pathly_orchestrator import eventlog
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.runner.context_budget import allocate_budget
from pathly_orchestrator.runner.context_settings import (
    DEFAULT_CHAR_BUDGET,
    DEFAULT_K,
    resolve_context_limits,
)

# --------------------------------------------------------------------------
# 1. Defaults + overrides
# --------------------------------------------------------------------------


def test_defaults_with_no_settings_rows():
    """A DB with no board_context.* rows yields the documented defaults."""
    assert resolve_context_limits() == {
        "char_budget": 4000,
        "k_feature": 5,
        "k_project": 3,
        "k_global": 2,
    }
    # The constants are the contract the docs and Studio quote — pin them too.
    assert DEFAULT_CHAR_BUDGET == 4000
    assert DEFAULT_K == {"feature": 5, "project": 3, "global": 2}


@pytest.mark.parametrize(
    "key,field,stored,expected",
    [
        ("board_context.char_budget", "char_budget", "6000", 6000),
        ("board_context.char_budget", "char_budget", "200", 200),  # floor is inclusive
        ("board_context.k_feature", "k_feature", "9", 9),
        ("board_context.k_project", "k_project", "1", 1),
        ("board_context.k_global", "k_global", "0", 0),  # 0 mutes a tier, legally
    ],
)
def test_stored_setting_overrides_its_default(key, field, stored, expected):
    set_setting(get_db(), key, stored)
    assert resolve_context_limits()[field] == expected


def test_each_key_is_independent():
    """Setting one key must not disturb the other three."""
    set_setting(get_db(), "board_context.k_project", "7")
    limits = resolve_context_limits()
    assert limits["k_project"] == 7
    assert limits["char_budget"] == DEFAULT_CHAR_BUDGET
    assert limits["k_feature"] == DEFAULT_K["feature"]
    assert limits["k_global"] == DEFAULT_K["global"]


# --------------------------------------------------------------------------
# 2. A bad value never reaches the renderer, and never raises
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stored",
    [
        "",  # blank row
        "   ",
        "abc",  # non-numeric
        "4e3",  # float syntax int() rejects
        "3.5",
        "-1",  # negative
        "-4000",
        "0",  # below the 200 floor: a "cap" that caps nothing
        "199",
        "400000",  # extra zero — would bury the task under board chatter
        "None",
        "[]",
    ],
)
def test_garbage_char_budget_falls_back_silently(stored):
    set_setting(get_db(), "board_context.char_budget", stored)
    assert resolve_context_limits()["char_budget"] == DEFAULT_CHAR_BUDGET


@pytest.mark.parametrize("stored", ["", "abc", "-1", "2.5", "26", "9999", "null"])
def test_garbage_k_falls_back_silently(stored):
    set_setting(get_db(), "board_context.k_feature", stored)
    assert resolve_context_limits()["k_feature"] == DEFAULT_K["feature"]


def test_unreachable_db_returns_defaults_and_does_not_raise(monkeypatch):
    """The whole point of the never-raises contract: config can't break a prompt."""
    import pathly_orchestrator.db.connection as conn_mod

    def _boom():
        raise RuntimeError("db gone")

    monkeypatch.setattr(conn_mod, "get_db", _boom)
    assert resolve_context_limits() == {
        "char_budget": DEFAULT_CHAR_BUDGET,
        "k_feature": DEFAULT_K["feature"],
        "k_project": DEFAULT_K["project"],
        "k_global": DEFAULT_K["global"],
    }


# --------------------------------------------------------------------------
# 3. The per-tier split still holds against the CONFIGURED total
# --------------------------------------------------------------------------


def test_split_sums_to_the_configured_total():
    """The invariant is 'the split spends the whole budget' — at any budget."""
    set_setting(get_db(), "board_context.char_budget", "6000")
    total = resolve_context_limits()["char_budget"]
    assert total == 6000
    three = allocate_budget(["feature", "project", "global"], total)
    assert sum(three.values()) == total
    assert three["feature"] > three["project"] > three["global"]


def test_feature_only_run_keeps_the_whole_configured_budget():
    """A disabled tier's share is redistributed, never lost — at any budget."""
    set_setting(get_db(), "board_context.char_budget", "6000")
    total = resolve_context_limits()["char_budget"]
    assert allocate_budget(["feature"], total) == {"feature": total}
    two = allocate_budget(["feature", "project"], total)
    assert sum(two.values()) == total


# --------------------------------------------------------------------------
# 4. k actually drives the search depth
# --------------------------------------------------------------------------


def _stub_board(monkeypatch, rows_by_board: dict):
    import pathly_orchestrator.db.queries.comms as cq
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(cq, "get_pending_decisions", lambda *a, **k: [])
    monkeypatch.setattr(cq, "get_active_escalations", lambda *a, **k: [])
    monkeypatch.setattr(emb, "embed", lambda t: [0.0] * 384)
    monkeypatch.setattr(
        cq,
        "search_by_hybrid",
        lambda conn, q, e, boards, scopes, k, **kw: rows_by_board.get(boards[0], []),
    )


def _row(mid: str, text: str) -> dict:
    return {
        "id": mid,
        "text": text,
        "from_agent": "a",
        "to_agent": "*",
        "_distance": 0.2,
    }


def test_configured_k_caps_the_kept_rows(monkeypatch):
    import pathly_orchestrator.runner.comms_context as cc

    set_setting(get_db(), "board_context.k_feature", "2")
    _stub_board(
        monkeypatch, {"feature": [_row(f"f{i}", f"NOTE-{i}") for i in range(6)]}
    )

    block = cc.retrieve_board_context(
        "feat", "C:/p", "q", board_scope={"feature": True}
    )
    kept = [i for i in range(6) if f"NOTE-{i}" in block]
    assert kept == [0, 1], "k_feature=2 must cap the tier at two rows"


def test_k_zero_mutes_a_tier_without_disabling_it(monkeypatch):
    """k=0 is a legal floor: the tier still exists (governance, catalog), pulls nothing.

    Guards the off-by-one in the search loop — `if kept >= k` only fires AFTER a row is
    appended, so k=0 would otherwise still keep one.
    """
    import pathly_orchestrator.runner.comms_context as cc

    set_setting(get_db(), "board_context.k_global", "0")
    _stub_board(
        monkeypatch,
        {
            "feature": [_row("f1", "FEATURE-NOTE")],
            "global": [_row("g1", "GLOBAL-NOTE")],
        },
    )

    block = cc.retrieve_board_context(
        "feat", "C:/p", "q", board_scope={"feature": True, "global": True}
    )
    assert "FEATURE-NOTE" in block
    assert "GLOBAL-NOTE" not in block


# --------------------------------------------------------------------------
# 5. The measurement: one BOARD_CONTEXT event per prompt build
# --------------------------------------------------------------------------


def _feature_dir(tmp_path):
    d = tmp_path / "proj" / "pathly" / "features" / "demo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _board_context_events(storage) -> list[dict]:
    return [
        e
        for e in eventlog.read_events(str(storage))
        if e.get("type") == "BOARD_CONTEXT"
    ]


def test_board_context_event_carries_counts_and_settings(tmp_path, monkeypatch):
    import pathly_orchestrator.runner.comms_context as cc

    storage = _feature_dir(tmp_path)
    _stub_board(monkeypatch, {"feature": [_row("f1", "KEEP-ME")]})

    counts: dict[str, int] = {}
    block = cc.retrieve_board_context(
        "demo",
        str(tmp_path / "proj"),
        "q",
        board_scope={"feature": True},
        counts=counts,
        storage_path=str(storage),
    )
    assert "KEEP-ME" in block

    events = _board_context_events(storage)
    assert len(events) == 1, "exactly one record per prompt build"
    ev = events[0]
    # channel counts …
    assert ev["semantic"] == 1
    assert ev["governance"] == 0
    # … the budget + k in force for THIS call …
    assert ev["char_budget"] == DEFAULT_CHAR_BUDGET
    assert ev["k_feature"] == DEFAULT_K["feature"]
    assert ev["k_project"] == DEFAULT_K["project"]
    assert ev["k_global"] == DEFAULT_K["global"]
    # … and the volume actually rendered vs dropped.
    assert ev["rendered_entries"] == 1
    assert ev["rendered_chars"] > 0
    assert ev["rendered_chars_feature"] == ev["rendered_chars"]
    assert ev["omitted_entries"] == 0
    assert ev["omitted_chars"] == 0
    # The caller's counts dict sees the same numbers (the preview endpoint's view).
    assert counts["rendered_entries"] == 1
    assert counts["char_budget"] == DEFAULT_CHAR_BUDGET


def test_board_context_event_records_what_the_budget_dropped(tmp_path, monkeypatch):
    import pathly_orchestrator.runner.comms_context as cc

    storage = _feature_dir(tmp_path)
    set_setting(get_db(), "board_context.char_budget", "1000")
    _stub_board(
        monkeypatch,
        {"feature": [_row(f"f{i}", "x" * 900) for i in range(4)]},
    )

    cc.retrieve_board_context(
        "demo",
        str(tmp_path / "proj"),
        "q",
        board_scope={"feature": True},
        storage_path=str(storage),
    )

    ev = _board_context_events(storage)[0]
    assert ev["char_budget"] == 1000
    assert ev["omitted_entries"] > 0, "a 1000-char budget must drop 900-char lines"
    assert ev["omitted_chars"] > 0
    assert ev["rendered_entries"] + ev["omitted_entries"] == 4


def test_empty_board_still_records(tmp_path, monkeypatch):
    """'The agent got nothing' must be distinguishable from 'no prompt was built'."""
    import pathly_orchestrator.runner.comms_context as cc

    storage = _feature_dir(tmp_path)
    _stub_board(monkeypatch, {})

    assert (
        cc.retrieve_board_context(
            "demo",
            str(tmp_path / "proj"),
            "q",
            board_scope={"feature": True},
            storage_path=str(storage),
        )
        == ""
    )
    ev = _board_context_events(storage)[0]
    assert ev["semantic"] == 0
    assert ev["char_budget"] == DEFAULT_CHAR_BUDGET


def test_no_storage_path_writes_nothing(tmp_path, monkeypatch):
    """The /comms/agent-context/preview contract: render, but no DB writes."""
    import pathly_orchestrator.runner.comms_context as cc

    storage = _feature_dir(tmp_path)
    _stub_board(monkeypatch, {"feature": [_row("f1", "KEEP-ME")]})

    cc.retrieve_board_context(
        "demo", str(tmp_path / "proj"), "q", board_scope={"feature": True}
    )
    assert _board_context_events(storage) == []


def test_failing_event_write_never_costs_the_agent_its_context(tmp_path, monkeypatch):
    """Telemetry is best-effort — exactly like the invocation-projection hook."""
    import pathly_orchestrator.runner.comms_context as cc

    storage = _feature_dir(tmp_path)
    _stub_board(monkeypatch, {"feature": [_row("f1", "KEEP-ME")]})

    def _boom(*a, **k):
        raise RuntimeError("event log on fire")

    monkeypatch.setattr(eventlog, "append_event", _boom)

    block = cc.retrieve_board_context(
        "demo",
        str(tmp_path / "proj"),
        "q",
        board_scope={"feature": True},
        storage_path=str(storage),
    )
    assert "KEEP-ME" in block, "a telemetry failure must not empty the board block"


def test_fsm_prompt_build_records_one_row_per_stage(tmp_path, monkeypatch):
    """End-to-end wiring: an FSM stage's prompt build lands exactly one record.

    Keyed by the RUN's storage dir, not the board scope — for a goal/nested run those
    differ, and the run is the identity every other fsm_events row uses.
    """
    import pathly_orchestrator.fsm_compose as fsm_compose

    monkeypatch.setattr(fsm_compose, "_load_agent_text", lambda *_: "base agent text")
    _stub_board(monkeypatch, {"feature": [_row("f1", "KEEP-ME")]})

    storage = tmp_path / "pathly" / "features" / "demo"
    storage.mkdir(parents=True, exist_ok=True)
    prompt = fsm_compose.build_prompt(
        {"agent_map": {"BUILDING": "quick"}, "composition": {}}, "BUILDING", storage
    )

    assert "KEEP-ME" in prompt, "the board block must still reach the prompt"
    events = _board_context_events(storage)
    assert len(events) == 1
    assert events[0]["rendered_entries"] == 1
    assert events[0]["char_budget"] == DEFAULT_CHAR_BUDGET
