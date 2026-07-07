"""Board message count aggregates — decompose-gate counters.

Small read-only ``COUNT(*)`` helpers used by the FSM decompose exit gates
(``fsm/engine_transitions.py``). Split out of ``comms_messages.py`` to keep that
file under the 400-line limit and to co-locate the two mirror counters:

  - ``count_goals_for_feature``   → feature-consultation PLANNING gate (>= 2 goals)
  - ``count_features_for_project`` → project-consultation PLANNING gate (>= 2 features)

``comms.py`` (the canonical re-export shim) re-exports both, so existing
``from ...comms import count_goals_for_feature`` imports keep working; the FSM
gate and tests import them directly from this module.
"""

from __future__ import annotations

import sqlite3


def count_goals_for_feature(conn: sqlite3.Connection, feature_scope: str) -> int:
    """Count non-deleted goal rows belonging to a feature scope (any status)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_messages "
        "WHERE scope=? AND type='goal' AND deleted_at IS NULL",
        (feature_scope,),
    ).fetchone()
    return int(row["n"]) if row else 0


def count_features_for_project(conn: sqlite3.Connection, project_scope: str) -> int:
    """Count non-deleted feature rows on the project board for a project scope (any status)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_messages "
        "WHERE scope=? AND type='feature' AND board='project' AND deleted_at IS NULL",
        (project_scope,),
    ).fetchone()
    return int(row["n"]) if row else 0
