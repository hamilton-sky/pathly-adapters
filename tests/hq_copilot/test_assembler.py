"""Tests for hq_context.assemble_packet (hq-copilot ticket 02).

The DB is auto-isolated per test by tests/conftest.py (Path.home is patched
so get_db() points at a fresh temp DB).
"""

from __future__ import annotations

import pytest

SCOPE = "hqtest"


@pytest.fixture()
def conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def _post(conn, **kw):
    from pathly_orchestrator.db.queries.comms import post_message

    base = dict(board="feature", scope=SCOPE, from_agent="builder")
    base.update(kw)
    return post_message(conn, **base)


def _seed_board(conn):
    gid = _post(
        conn,
        from_agent="planner",
        type="goal",
        text="Goal: ship it",
        executor="single",
    )
    _post(conn, from_agent="planner", type="task", text="write code", goal_id=gid)
    _post(conn, from_agent="planner", type="task", text="write tests", goal_id=gid)
    qid = _post(conn, type="question", text="Use JWT?", options=["yes", "no"])
    _post(conn, type="status", text="Build started")
    art_msg = _post(conn, type="status", text="Plan written")
    from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact

    insert_artifact(
        conn, art_msg, path="PLAN.md", type="plan_artifact", title="PLAN.md"
    )
    from pathly_orchestrator.db.queries.run_history import upsert_run

    upsert_run(
        conn,
        project_root="/proj",
        feature=SCOPE,
        run_id="run-live-1",
        status="running",
        adapter="claude",
        board_scope=SCOPE,
    )
    return gid, qid


def test_full_packet_has_all_sections(conn):
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    pkt = hq_context.assemble_packet(SCOPE, 6000, project_root="/proj")
    assert "<pathly-context>" in pkt.text
    assert "</pathly-context>" in pkt.text
    assert "Use JWT?" in pkt.text
    assert "run-live-1" in pkt.text
    assert "Goal: ship it" in pkt.text
    assert "0/2 tasks done" in pkt.text
    assert "PLAN.md" in pkt.text
    names = [s.name for s in pkt.sections if s.included]
    assert names == ["questions", "runs", "goals", "events", "artifacts"]
    assert pkt.tokens_est <= pkt.budget


def test_tight_budget_cuts_low_priority_first(conn):
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    pkt = hq_context.assemble_packet(SCOPE, 40, project_root="/proj")
    by_name = {s.name: s for s in pkt.sections}
    # Highest priority survives; the tail is cut and recorded.
    assert by_name["questions"].included
    assert not by_name["artifacts"].included
    assert by_name["artifacts"].cut_reason == "over budget"
    # Strict priority: included sections form a prefix of the order.
    order = ["questions", "runs", "goals", "events", "artifacts"]
    seen_cut = False
    for name in order:
        if not by_name[name].included:
            seen_cut = True
        elif seen_cut:
            pytest.fail(f"{name} included after a cut section")


def test_sections_report_their_token_size(conn):
    """Studio's token meter estimates the next question from these sizes."""
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    full = hq_context.assemble_packet(SCOPE, 6000, project_root="/proj")
    included = [s for s in full.sections if s.included]
    assert included and all(s.tokens > 0 for s in included)
    assert sum(s.tokens for s in included) <= full.tokens_est
    off = {s.name: s for s in full.sections}["summaries"]
    assert (off.cut_reason, off.tokens) == ("off", 0)

    # A section cut over budget still reports what it would have taken.
    tight = hq_context.assemble_packet(SCOPE, 40, project_root="/proj")
    cut = {s.name: s for s in tight.sections}["artifacts"]
    assert cut.cut_reason == "over budget" and cut.tokens > 0


def test_progress_order_puts_goals_first(conn, monkeypatch):
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    monkeypatch.setattr(hq_context, "_packet_order", lambda: "progress")
    pkt = hq_context.assemble_packet(SCOPE, 40, project_root="/proj")
    names = [s.name for s in pkt.sections if s.included]
    assert names[0] == "goals"


def test_empty_board_gives_valid_empty_packet(conn):
    from pathly_orchestrator import hq_context

    pkt = hq_context.assemble_packet("no-such-board", 6000, project_root="/proj")
    assert "<pathly-context>" in pkt.text
    assert "</pathly-context>" in pkt.text
    assert all(not s.included for s in pkt.sections)
    # summaries is opt-in, so it is "off" rather than "empty" by default.
    assert all(
        s.cut_reason == "empty"
        for s in pkt.sections
        if s.name not in ("runs", "summaries")
    )
    assert pkt.tokens_est <= pkt.budget


def test_section_failure_raises_never_partial(conn, monkeypatch):
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(hq_context, "_read_goals", _boom)
    with pytest.raises(hq_context.HQContextUnavailable):
        hq_context.assemble_packet(SCOPE, 6000, project_root="/proj")


def test_no_project_root_skips_runs_section(conn):
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    pkt = hq_context.assemble_packet(SCOPE, 6000)
    by_name = {s.name: s for s in pkt.sections}
    assert not by_name["runs"].included
    assert "project_root" in (by_name["runs"].cut_reason or "")
    assert "run-live-1" not in pkt.text


def test_large_board_finishes_within_timeout(conn):
    from pathly_orchestrator.db.queries.comms import post_message

    for i in range(10_000):
        post_message(
            conn,
            board="feature",
            scope=SCOPE,
            from_agent="b",
            type="status",
            text=f"event {i}",
        )
    from pathly_orchestrator import hq_context

    # Returns (rather than raising HQContextUnavailable) == finished in time.
    pkt = hq_context.assemble_packet(SCOPE, 6000, project_root="/proj")
    assert pkt.text
    assert pkt.tokens_est <= pkt.budget


def test_runs_name_their_board_and_prefer_this_one(conn):
    """Runs are project-wide, so each line names its board; with nothing
    live, this board's own recent runs are shown, not another board's."""
    from pathly_orchestrator import hq_context
    from pathly_orchestrator.db.queries.run_history import upsert_run

    _post(conn, type="status", text="known board")
    upsert_run(
        conn,
        project_root="/proj",
        feature="other-board",
        run_id="run-other",
        status="done",
        adapter="claude",
        board_scope="other-board",
        started_at="2026-10-14T10:00:00",
        finished_at="2026-10-14T10:05:00",
    )
    upsert_run(
        conn,
        project_root="/proj",
        feature=SCOPE,
        run_id="run-mine",
        status="done",
        adapter="claude",
        board_scope=SCOPE,
        started_at="2026-10-14T09:00:00",
        finished_at="2026-10-14T09:05:00",
    )
    pkt = hq_context.assemble_packet(SCOPE, 6000, project_root="/proj")
    assert "run-mine (single/claude, this board): done" in pkt.text
    assert "run-other" not in pkt.text

    upsert_run(
        conn,
        project_root="/proj",
        feature="other-board",
        run_id="run-live",
        status="running",
        adapter="codex",
        board_scope="other-board",
    )
    pkt = hq_context.assemble_packet(SCOPE, 6000, project_root="/proj")
    assert "## Live runs across the project (1)" in pkt.text
    assert "run-live (single/codex, board other-board): running" in pkt.text


def test_sections_choice_turns_sections_off(conn):
    """Only the chosen sections are read; the rest are recorded as "off"."""
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    pkt = hq_context.assemble_packet(
        SCOPE, 6000, project_root="/proj", sections=["goals", "nonsense"]
    )
    status = {s.name: s for s in pkt.sections}
    assert status["goals"].included
    for name in ("questions", "runs", "events", "artifacts", "summaries"):
        assert (status[name].included, status[name].cut_reason) == (False, "off")
    assert "Goal: ship it" in pkt.text
    assert "Use JWT?" not in pkt.text


def test_no_sections_selected_says_so(conn):
    _seed_board(conn)
    from pathly_orchestrator import hq_context

    pkt = hq_context.assemble_packet(SCOPE, 6000, project_root="/proj", sections=[])
    assert "no board sections selected" in pkt.text
    assert all(s.cut_reason == "off" for s in pkt.sections)


def test_summaries_section_is_opt_in(conn):
    _seed_board(conn)
    from pathly_orchestrator import hq_context
    from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact

    msg = _post(conn, type="status", text="design done")
    insert_artifact(
        conn,
        msg,
        path="DESIGN.md",
        type="plan_artifact",
        title="DESIGN.md",
        summary="Picks SQLite over Postgres for the local store.",
    )
    assert "Picks SQLite" not in hq_context.assemble_packet(SCOPE, 6000).text
    pkt = hq_context.assemble_packet(
        SCOPE, 6000, sections=hq_context.SECTION_DEFAULTS + ("summaries",)
    )
    assert "## Artifact summaries (1)" in pkt.text
    assert "- DESIGN.md: Picks SQLite over Postgres for the local store." in pkt.text
