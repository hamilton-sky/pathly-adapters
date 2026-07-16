"""Tests for supervisor/slug.py — _slugify and ensure_goal_slug."""

from __future__ import annotations

import sqlite3
import threading

import pytest

from pathly_orchestrator.db.migrations import _run_migrations
from pathly_orchestrator.supervisor.slug import _slugify, ensure_goal_slug


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    _run_migrations(c)
    yield c
    c.close()


def _insert_goal(conn, goal_id: str, text: str) -> None:
    conn.execute(
        "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts) "
        "VALUES (?, 'feature', 'test', 'agent', 'goal', ?, '2026-01-01T00:00:00Z')",
        (goal_id, text),
    )
    conn.commit()


def test_slugify_normal():
    assert _slugify("My Feature Plan!") == "my-feature-plan"


def test_slugify_caps_length():
    # Readable slugs cap at ~32 chars (first few meaningful words), even for one long word.
    long_text = "a" * 60
    assert len(_slugify(long_text)) <= 32


def test_slugify_empty_returns_goal():
    assert _slugify("") == "goal"
    assert _slugify("!!! ###") == "goal"


def test_ensure_goal_slug_format(conn):
    goal_id = "abc12345-1234-5678-90ab-cdef01234567"
    _insert_goal(conn, goal_id, "Build the login page")
    slug = ensure_goal_slug(conn, goal_id)
    # "the" is a dropped stopword in the readable slug -> "build-login-page-<id>"
    assert slug.startswith("build-login-page-")
    assert slug.endswith(goal_id[:8])


def test_ensure_goal_slug_idempotent(conn):
    goal_id = "abc12345-1234-5678-90ab-cdef01234567"
    _insert_goal(conn, goal_id, "My goal")
    slug1 = ensure_goal_slug(conn, goal_id)
    slug2 = ensure_goal_slug(conn, goal_id)
    assert slug1 == slug2
    # Verify only one write happened (slug is set in DB)
    row = conn.execute(
        "SELECT slug FROM comms_messages WHERE id=?", (goal_id,)
    ).fetchone()
    assert row["slug"] == slug1


def test_ensure_goal_slug_empty_text(conn):
    goal_id = "empty0000-1234-5678-90ab-cdef01234567"
    _insert_goal(conn, goal_id, "")
    slug = ensure_goal_slug(conn, goal_id)
    assert slug.startswith("goal-")


def test_ensure_goal_slug_concurrent(conn):
    """Two threads racing on the same goal_id must converge on ONE slug."""
    goal_id = "race0000-1234-5678-90ab-cdef01234567"
    _insert_goal(conn, goal_id, "Race condition test")
    results = []
    errors = []

    def worker():
        try:
            results.append(ensure_goal_slug(conn, goal_id))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors: {errors}"
    # All threads must return the same slug
    assert len(set(results)) == 1
