"""chief-agent 16: every writer that can take a binding directive out of ``get_binding_decisions``.

The query returns a ``binding = 1`` decision that is not deleted and not superseded, so only a
write to ``deleted_at`` or ``superseded_by`` can retire one (``binding``, ``type``, ``board``,
``scope`` and ``to_agent`` are written once, by ``post_message`` and ``post_directive``). This
file pins the writers: a new one, or a new caller of the two functions that write them, fails
here until its author has decided whether a caller other than the chief can reach a directive
through it. ``test_binding_directive_guard.py`` holds the behaviour of each door.
"""

from __future__ import annotations

import ast
import re

from _paths import SRC

from pathly_orchestrator.db.queries.comms import _DEDUP_PROTECTED_TYPES

PACKAGE = SRC / "pathly_orchestrator"
UPDATE = re.compile(
    r"UPDATE\s+comms_messages\s+SET\s+(?P<set>.*?)(?:\s+WHERE\b|$)", re.I | re.S
)
RETIRING = re.compile(r"\b(deleted_at|superseded_by)\s*=")
DELETE = re.compile(r"DELETE\s+FROM\s+comms_messages\b", re.I)
REPLACE = re.compile(r"REPLACE\s+INTO\s+comms_messages\b", re.I)


def _sources():
    for path in PACKAGE.rglob("*.py"):
        yield path.relative_to(PACKAGE).as_posix(), path.read_text(encoding="utf-8")


def _statements(pattern):
    """(file, match) for every string literal in ``src`` that ``pattern`` finds a hit in."""
    for rel, source in _sources():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for hit in pattern.finditer(node.value):
                    yield rel, hit


def _users(name):
    """Files that import or call ``name``, bar its home and the re-export shim."""
    found = set()
    for rel, source in _sources():
        for node in ast.walk(ast.parse(source)):
            imported = isinstance(node, ast.ImportFrom) and any(
                alias.name == name for alias in node.names
            )
            called = (
                isinstance(node, ast.Call)
                and (getattr(node.func, "id", None) or getattr(node.func, "attr", None))
                == name
            )
            if imported or called:
                found.add(rel)
    return found - {"db/queries/comms_messages.py", "db/queries/comms.py"}


def test_only_two_statements_write_the_columns_that_retire_a_row():
    found = {
        (rel, column)
        for rel, hit in _statements(UPDATE)
        for column in RETIRING.findall(hit.group("set"))
    }

    # soft_delete_message (deleted_at), supersede_message (superseded_by) and
    # restore_messages (deleted_at = NULL, which brings a row back and retires nothing).
    assert found == {
        ("db/queries/comms_messages.py", "deleted_at"),
        ("db/queries/comms_messages.py", "superseded_by"),
    }


def test_no_statement_deletes_or_replaces_a_message_row_but_the_trash_purge():
    """``purge_expired_trash`` removes rows that are already trashed, and a binding row never
    is; a ``REPLACE`` would overwrite ``binding``, ``deleted_at`` and ``superseded_by`` at once.
    """
    deleting = {rel for rel, _ in _statements(DELETE)}
    replacing = {rel for rel, _ in _statements(REPLACE)}

    assert deleting == {"db/queries/comms_messages.py"}
    assert replacing == set()


def test_soft_delete_message_has_one_user_and_it_is_the_route():
    assert _users("soft_delete_message") == {
        "http_server/blueprints/comms/messages_crud.py"
    }


def test_supersede_message_is_used_by_the_route_the_post_and_the_dedup_pass():
    assert _users("supersede_message") == {
        "http_server/blueprints/comms/messages_crud.py",  # behind refuse_agent_supersede
        "http_server/blueprints/comms/_supersede_on_post.py",  # apply_supersedes
        "db/queries/comms_embeddings.py",  # dedupe_board, which skips decisions
    }


def test_the_dedup_pass_never_touches_a_decision():
    """``/comms/consolidate`` supersedes near-duplicate notes; a directive is a decision."""
    assert "decision" in _DEDUP_PROTECTED_TYPES
