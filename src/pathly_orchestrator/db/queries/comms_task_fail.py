"""Task failure: ``fail_task`` (moved out of comms_tasks.py, at its 400-line ratchet baseline).

Re-exported from ``comms_tasks`` and ``comms``, so ``from ...comms import fail_task`` keeps
working. It is the one writer of ``comms_messages.fail_reason`` for every caller (the
``/comms/tasks/fail`` and ``/comms/tasks/status`` routes, ``supervisor/task_retry.py``), so the
reason is stored with run tokens redacted (``db/secret_scan.py``), before the 4000-character
cap: a token cut by the cap would leave a fragment the window scan no longer matches.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock
from ..secret_scan import redact_run_tokens


def fail_task(conn: sqlite3.Connection, message_id: str, reason: str = "") -> list[str]:
    """Mark a task failed and BFS-cascade transitive dependents to 'blocked'.

    Returns the list of blocked dependent IDs. Idempotent.
    """
    row = conn.execute(
        "SELECT board, scope, task_status FROM comms_messages "
        "WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None or row["task_status"] == "failed":
        return []
    board, scope = row["board"], row["scope"]
    reason = redact_run_tokens(conn, reason)
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET task_status='failed', failed_at=?, fail_reason=? "
            "WHERE id=?",
            (now, reason[:4000], message_id),
        )
        conn.commit()

    all_pending = conn.execute(
        "SELECT id, depends_on FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' "
        "AND task_status IN ('pending','in_progress') AND deleted_at IS NULL",
        (board, scope),
    ).fetchall()
    dep_index = {r["id"]: json.loads(r["depends_on"] or "[]") for r in all_pending}
    blocked: list[str] = []
    frontier: set[str] = {message_id}
    with _get_write_lock(conn):
        changed = True
        while changed:
            changed = False
            for tid, deps in list(dep_index.items()):
                if tid in blocked:
                    continue
                if frontier & set(deps):
                    conn.execute(
                        "UPDATE comms_messages SET task_status='blocked' WHERE id=?",
                        (tid,),
                    )
                    blocked.append(tid)
                    frontier.add(tid)
                    changed = True
        conn.commit()
    return blocked
