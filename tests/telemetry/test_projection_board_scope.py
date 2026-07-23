"""run-identity: the invocation projection stamps board_scope from the event stream.

agent_invocations gains a nullable board_scope column; the projector copies it from
the AGENT_DONE payload (COALESCE — a superseding BILLING_UPDATE fills it only when
the anchor lacks one, never overwriting an agent-provided value). Legacy events
without the field stay NULL — the projector never guesses.
"""

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.fsm_events import append_event
from pathly_orchestrator.db.queries.invocation_projection import (
    backfill_invocations_from_events,
)

PR = "C:/proj"


def _rows(conn, feature):
    return conn.execute(
        "SELECT source_seq, board_scope, cost_usd, tokens_in, tokens_out "
        "FROM agent_invocations WHERE project_root=? AND feature=? ORDER BY id",
        (PR, feature),
    ).fetchall()


def _ad(agent="builder", conv=0, board_scope=None, run_id=None, cost=0.0):
    e = {
        "type": "AGENT_DONE",
        "agent": agent,
        "conversation": conv,
        "cost_usd": cost,
        "total_tokens": 100,
        "ts": "2026-07-22T12:00:00Z",
    }
    if board_scope is not None:
        e["board_scope"] = board_scope
    if run_id is not None:
        e["run_id"] = run_id
    return e


def _billing(agent="builder", conv=0, board_scope=None, run_id=None, cost=1.0):
    e = {
        "type": "BILLING_UPDATE",
        "agent": agent,
        "conversation": conv,
        "cost_usd": cost,
        "tokens_in": 80,
        "tokens_out": 20,
        "total_tokens": 100,
        "ts": "2026-07-22T12:01:00Z",
    }
    if board_scope is not None:
        e["board_scope"] = board_scope
    if run_id is not None:
        e["run_id"] = run_id
    return e


def test_projected_row_carries_board_scope_from_agent_done(tmp_path):
    conn = get_db()
    append_event(conn, PR, "g1-slug", _ad(board_scope="parent-feat"))
    rows = _rows(conn, "g1-slug")
    assert len(rows) == 1
    assert rows[0]["board_scope"] == "parent-feat"


def test_legacy_event_without_board_scope_stays_null(tmp_path):
    conn = get_db()
    append_event(conn, PR, "feat-legacy", _ad())
    rows = _rows(conn, "feat-legacy")
    assert len(rows) == 1
    assert rows[0]["board_scope"] is None


def test_billing_fills_board_scope_only_when_anchor_lacks_it(tmp_path):
    conn = get_db()
    # Anchor WITH board_scope: a different billing value must NOT overwrite it.
    append_event(conn, PR, "feat-a", _ad(board_scope="agent-chose", run_id="r1"))
    append_event(conn, PR, "feat-a", _billing(board_scope="gate-derived", run_id="r1"))
    rows = _rows(conn, "feat-a")
    assert len(rows) == 1
    assert rows[0]["board_scope"] == "agent-chose"
    assert float(rows[0]["cost_usd"]) == 1.0  # billing still folded for cost

    # Anchor WITHOUT board_scope: the billing's value fills it (COALESCE).
    append_event(conn, PR, "feat-b", _ad(run_id="r2"))
    append_event(conn, PR, "feat-b", _billing(board_scope="gate-derived", run_id="r2"))
    rows = _rows(conn, "feat-b")
    assert len(rows) == 1
    assert rows[0]["board_scope"] == "gate-derived"


def test_backfill_stamps_board_scope_and_is_idempotent(tmp_path):
    conn = get_db()
    append_event(conn, PR, "feat-c", _ad(board_scope="parent-feat", run_id="r3"))
    append_event(conn, PR, "feat-c", _ad())  # legacy shape, NULL
    append_event(conn, PR, "feat-c", _billing(board_scope="gate", run_id="r3"))

    backfill_invocations_from_events(conn, PR)
    first = [tuple(r) for r in _rows(conn, "feat-c")]
    backfill_invocations_from_events(conn, PR)
    second = [tuple(r) for r in _rows(conn, "feat-c")]

    assert first == second, "backfill must be idempotent"
    scopes = sorted((r[1] or "-") for r in second)
    assert scopes == ["-", "parent-feat"], scopes


def test_billing_folds_onto_anchor_across_features(tmp_path):
    """A mis-keyed run (AGENT_DONE under the parent feature, gate billing under the
    slug) must fold onto the anchor by run_id PROJECT-wide — one invocation row, the
    real cost, no orphan duplicate sharing the run_id (the Monitor's duplicate-key bug).
    """
    rid = "features/parent/goals/g1-slug-1-1784748338467"
    conn = get_db()
    # Live path: agent posts under the PARENT feature; the gate bills under the SLUG.
    append_event(conn, PR, "parent-feat", _ad(agent="builder", run_id=rid, cost=0.4))
    append_event(conn, PR, "g1-slug", _billing(agent=None, run_id=rid, cost=1.07))

    parent = _rows(conn, "parent-feat")
    slug = _rows(conn, "g1-slug")
    assert len(parent) == 1 and float(parent[0]["cost_usd"]) == 1.07
    assert (
        slug == []
    ), f"billing must not orphan into a duplicate row: {[tuple(r) for r in slug]}"

    # Backfill agrees (and cleans a stale orphan if one existed): same single row.
    backfill_invocations_from_events(conn, PR)
    parent = _rows(conn, "parent-feat")
    slug = _rows(conn, "g1-slug")
    assert len(parent) == 1 and float(parent[0]["cost_usd"]) == 1.07
    assert slug == []
