"""Shared constants and helpers of the binding-directive tests (chief-agent 11).

``post`` writes a message through ``post_message`` and sets ``binding`` (and, when given, ``ts``)
directly: the route that sets ``binding`` is a later ticket, and an explicit ``ts`` keeps an
ordering assertion off the wall clock. ``render`` renders the board context for a role;
``governance_part``, ``standing_part`` and ``ranked_part`` cut the governance section and its two
lists out of it. Imported by bare name: with no ``__init__.py`` pytest puts the test file's own
directory (``tests/comms_board``, where this file sits) on ``sys.path``; ``tests/conftest.py``
adds only ``tests/`` itself.
"""

from __future__ import annotations

TOPIC = "demo"
ROOT = "C:/proj"
ALL = {"feature": True, "project": True, "global": True}
NO_PROJECT = {"feature": True, "project": False, "global": False}
NONE = {"feature": False, "project": False, "global": False}
STANDING = "**Standing orders (binding"
RANKED = "**Decisions (higher tier first"
FLOW = {
    "agent_map": {
        "BUILDING": "team/build",
        "REVIEWING": "team/review",
        "TESTING": "team/test",
    },
    "composition": {},
}
NO_DEPS = "Never add a dependency without asking the human first."
ONLY_BUILDER = "Run the formatter before every commit."
RETIRE = {
    "superseded_by": "UPDATE comms_messages SET superseded_by='x' WHERE id=?",
    "deleted_at": "UPDATE comms_messages SET deleted_at='x' WHERE id=?",
}


def at(second):
    """An explicit, strictly ordered ``ts`` for ``post(..., ts=at(n))``."""
    return f"2026-08-10T10:00:{second:02d}+00:00"


def post(
    text,
    *,
    to_agent="*",
    board="project",
    scope=ROOT,
    binding=0,
    acked=True,
    kind="decision",
    ts=None,
):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import acknowledge_message, post_message

    conn = get_db()
    mid = post_message(
        conn,
        board=board,
        scope=scope,
        from_agent="chief",
        to_agent=to_agent,
        type=kind,
        text=text,
    )
    if binding:
        conn.execute("UPDATE comms_messages SET binding=? WHERE id=?", (binding, mid))
        conn.commit()
    if ts:
        conn.execute("UPDATE comms_messages SET ts=? WHERE id=?", (ts, mid))
        conn.commit()
    if acked:
        acknowledge_message(conn, mid, "builder")
    return mid


def directive(text, **kw):
    return post(text, binding=1, **kw)


def retire(mid, column):
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    conn.execute(RETIRE[column], (mid,))
    conn.commit()


def render(role, board_scope=ALL, counts=None, root=ROOT):
    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    return retrieve_board_context(
        TOPIC, root, "do the work", board_scope=board_scope, counts=counts, role=role
    )


def governance_part(block):
    if "### Governance" not in block:
        return ""
    return block.split("### Governance", 1)[1].split("\n---\n", 1)[0]


def standing_part(gov):
    return gov.split(STANDING, 1)[1].split(RANKED, 1)[0] if STANDING in gov else ""


def ranked_part(gov):
    return gov.split(RANKED, 1)[1] if RANKED in gov else ""
