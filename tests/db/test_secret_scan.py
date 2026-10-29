"""chief-autopilot 03: the run-token scanner and its redaction at the DB write chokepoints.

The server stores only sha256 of each run token, so ``db/secret_scan.py`` finds a token by
hashing every 43-character window of a URL-safe run and looking the hash up in ``run_tokens``,
plus whatever follows ``PATHLY_RUN_TOKEN=`` / ``PATHLY_RUN_TOKEN:``.
"""

from __future__ import annotations

import hashlib
import json
import secrets

import pytest

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, revoke_run_tokens
from pathly_orchestrator.db.secret_scan import (
    REDACTED,
    contains_secret_hash,
    find_run_tokens,
    redact_run_tokens,
)


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


def _mint(conn, run_id="run-scan"):
    return mint_run_token(conn, run_id, "builder", "feat", "C:/proj", "feature", "feat")


def test_live_token_alone_is_found() -> None:
    conn = get_db()
    token = _mint(conn)
    assert find_run_tokens(conn, f"the token is {token} ok") == [token]


def test_revoked_token_is_found() -> None:
    conn = get_db()
    token = _mint(conn, "run-revoked")
    revoke_run_tokens(conn, "run-revoked")
    assert find_run_tokens(conn, token) == [token]


def test_tokens_inside_a_longer_token_like_run_are_found() -> None:
    conn = get_db()
    live = _mint(conn, "run-live")
    revoked = _mint(conn, "run-gone")
    revoke_run_tokens(conn, "run-gone")
    text = f"x{live}abc-_Z and Q{revoked}_"
    assert sorted(find_run_tokens(conn, text)) == sorted([live, revoked])
    out = redact_run_tokens(conn, text)
    assert live not in out and revoked not in out
    assert out == f"x{REDACTED}abc-_Z and Q{REDACTED}_"


def test_random_43_character_string_is_not_found() -> None:
    conn = get_db()
    _mint(conn)
    stranger = secrets.token_urlsafe(32)
    assert len(stranger) == 43
    assert find_run_tokens(conn, stranger) == []
    assert redact_run_tokens(conn, stranger) == stranger


def test_text_without_a_long_run_is_untouched() -> None:
    conn = get_db()
    assert redact_run_tokens(conn, "short words only") == "short words only"
    assert redact_run_tokens(conn, "") == ""


def test_env_patterns_are_redacted_whatever_the_value() -> None:
    conn = get_db()
    assert find_run_tokens(conn, "PATHLY_RUN_TOKEN=abc123") == ["abc123"]
    assert find_run_tokens(conn, "PATHLY_RUN_TOKEN: xyz") == ["xyz"]
    assert (
        redact_run_tokens(conn, "env PATHLY_RUN_TOKEN=abc123 next")
        == f"env PATHLY_RUN_TOKEN={REDACTED} next"
    )
    assert (
        redact_run_tokens(conn, 'echo "PATHLY_RUN_TOKEN: xyz"')
        == f'echo "PATHLY_RUN_TOKEN: {REDACTED}"'
    )


def test_shell_references_are_left_alone() -> None:
    conn = get_db()
    for text in (
        'echo "PATHLY_RUN_TOKEN: $PATHLY_RUN_TOKEN"',
        'PATHLY_RUN_TOKEN="$PATHLY_RUN_TOKEN" pathly api GET /health',
        "curl -H 'X-Pathly-Run-Token: $PATHLY_RUN_TOKEN' http://x",
        'test -n "${PATHLY_RUN_TOKEN:-}"',
        "uses $PATHLY_RUN_TOKEN",
    ):
        assert find_run_tokens(conn, text) == [], text
        assert redact_run_tokens(conn, text) == text, text


def test_redaction_is_idempotent() -> None:
    conn = get_db()
    once = redact_run_tokens(conn, "PATHLY_RUN_TOKEN: abc")
    assert redact_run_tokens(conn, once) == once


def test_contains_secret_hash() -> None:
    secret = secrets.token_urlsafe(32)
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    assert contains_secret_hash(secret, digest)
    assert contains_secret_hash(f"x{secret}-y", digest)
    assert not contains_secret_hash(secrets.token_urlsafe(32), digest)
    assert not contains_secret_hash("short", digest)
    assert not contains_secret_hash("", digest)


def test_direct_fsm_events_append_is_redacted() -> None:
    from pathly_orchestrator.db.queries.fsm_events import append_event

    conn = get_db()
    token = _mint(conn, "run-ev")
    seq = append_event(
        conn,
        "C:/proj",
        "feat",
        {
            "type": "AGENT_DONE",
            "summary": f"printed {token}",
            "error": f"PATHLY_RUN_TOKEN: {token}",
            "nested": {"result": [f"a{token}"]},
            "total_tokens": 5,
        },
    )
    payload = conn.execute(
        "SELECT payload FROM fsm_events WHERE seq=?", (seq,)
    ).fetchone()[0]
    assert token not in payload
    event = json.loads(payload)
    assert event["summary"] == f"printed {REDACTED}"
    assert event["error"] == f"PATHLY_RUN_TOKEN: {REDACTED}"
    assert event["nested"]["result"] == [f"a{REDACTED}"]
    assert event["total_tokens"] == 5


def test_artifact_row_is_redacted() -> None:
    from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact
    from pathly_orchestrator.db.queries.comms_messages import post_message

    conn = get_db()
    token = _mint(conn, "run-art")
    mid = post_message(conn, "feature", "feat", "builder", type="artifact", text="a")
    aid = insert_artifact(
        conn, mid, "pathly/x.md", title=f"t {token}", summary=f"s {token}"
    )
    row = conn.execute(
        "SELECT title, summary FROM comms_artifacts WHERE id=?", (aid,)
    ).fetchone()
    assert tuple(row) == (f"t {REDACTED}", f"s {REDACTED}")


def test_post_and_edited_post_are_redacted() -> None:
    from pathly_orchestrator.db.queries.comms_messages import (
        post_message,
        update_message_text,
    )

    conn = get_db()
    token = _mint(conn, "run-post")
    mid = post_message(
        conn,
        "feature",
        "feat",
        "builder",
        type="question",
        text=f"my token {token}",
        options=[{"id": "a", "label": token}],
        context_refs=[{"path": f"p/{token}"}],
        files=[f"f{token}"],
    )
    row = conn.execute(
        "SELECT text, options, context_refs, files FROM comms_messages WHERE id=?",
        (mid,),
    ).fetchone()
    assert all(token not in (v or "") for v in tuple(row))
    assert row[0] == f"my token {REDACTED}"
    assert json.loads(row[1]) == [{"id": "a", "label": REDACTED}]
    assert update_message_text(conn, mid, f"edited {token}") == "updated"
    text = conn.execute("SELECT text FROM comms_messages WHERE id=?", (mid,)).fetchone()
    assert text[0] == f"edited {REDACTED}"


def test_run_log_writes_are_redacted() -> None:
    from pathly_orchestrator.db.queries.run_log import (
        get_run_log,
        update_run_log_stdout,
        write_run_log_spawn,
    )

    conn = get_db()
    token = _mint(conn, "run-log")
    write_run_log_spawn(
        conn,
        "run-log",
        "BUILDING",
        'echo "PATHLY_RUN_TOKEN: $PATHLY_RUN_TOKEN"',
        board_context_injected=f"ctx {token}",
        stdin=None,
    )
    update_run_log_stdout(conn, "run-log", f"PATHLY_RUN_TOKEN: {token}\n")
    (row,) = get_run_log(conn, "run-log")
    assert row["prompt_sent"] == 'echo "PATHLY_RUN_TOKEN: $PATHLY_RUN_TOKEN"'
    assert row["board_context_injected"] == f"ctx {REDACTED}"
    assert row["stdin"] is None
    assert row["stdout"] == f"PATHLY_RUN_TOKEN: {REDACTED}\n"


def _task(conn, scope: str) -> str:
    from pathly_orchestrator.db.queries.comms_messages import post_message

    mid = post_message(conn, "feature", scope, "planner", type="task", text="do it")
    conn.execute(
        "UPDATE comms_messages SET task_status='in_progress' WHERE id=?", (mid,)
    )
    conn.commit()
    return mid


def test_task_failure_reason_is_stored_redacted() -> None:
    from pathly_orchestrator.supervisor.task_retry import resolve_task_failure

    conn = get_db()
    token = _mint(conn, "run-task")
    reason = f"failed after printing PATHLY_RUN_TOKEN: {token}"
    kwargs = dict(board="feature", goal_id=None, text="do it", lane="default")

    retried = _task(conn, "feat-retry")
    decision, _ = resolve_task_failure(
        conn, retried, 1, reason, scope="feat-retry", max_attempts=3, **kwargs
    )
    assert decision == "retried"
    stored = conn.execute(
        "SELECT fail_reason FROM comms_messages WHERE id=?", (retried,)
    ).fetchone()[0]
    assert token not in stored and REDACTED in stored

    failed = _task(conn, "feat-fail")
    statuses: list[str] = []
    decision, _ = resolve_task_failure(
        conn,
        failed,
        3,
        reason,
        scope="feat-fail",
        max_attempts=3,
        post_status=statuses.append,
        **kwargs,
    )
    assert decision == "escalated"
    stored = conn.execute(
        "SELECT fail_reason FROM comms_messages WHERE id=?", (failed,)
    ).fetchone()[0]
    assert token not in stored and REDACTED in stored
    assert all(token not in s for s in statuses)
    rows = conn.execute(
        "SELECT text, fail_reason FROM comms_messages WHERE scope='feat-fail'"
    ).fetchall()
    assert any(r[0] and "Task failed after" in r[0] for r in rows)
    assert all(token not in (r[0] or "") + (r[1] or "") for r in rows)


def test_fail_task_redacts_the_reason_before_its_length_cap() -> None:
    from pathly_orchestrator.db.queries.comms import fail_task

    conn = get_db()
    token = _mint(conn, "run-fail-cap")
    mid = _task(conn, "feat-fail-cap")
    # The token straddles fail_task's 4000-character cap.
    fail_task(conn, mid, reason="word " * 798 + token)
    stored = conn.execute(
        "SELECT fail_reason FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()[0]
    assert token[:10] not in stored
    assert stored.startswith("word ") and stored.endswith(REDACTED[:10])


def test_update_artifact_summary_stores_the_summary_redacted() -> None:
    from pathly_orchestrator.db.queries.comms_artifacts import (
        insert_artifact,
        update_artifact_summary,
    )
    from pathly_orchestrator.db.queries.comms_messages import post_message

    conn = get_db()
    token = _mint(conn, "run-summary")
    mid = post_message(conn, "feature", "feat-sum", "builder", text="artifact")
    art_id = insert_artifact(conn, mid, "pathly/y.md", title="y", summary="old")
    for count in (None, 7):
        update_artifact_summary(conn, art_id, f"s {token} e", token_count=count)
        stored = conn.execute(
            "SELECT summary FROM comms_artifacts WHERE id=?", (art_id,)
        ).fetchone()[0]
        assert stored == f"s {REDACTED} e"


def test_post_message_redacts_before_taking_the_write_lock(monkeypatch) -> None:
    import threading

    from pathly_orchestrator.db import connection
    from pathly_orchestrator.db.queries import comms_messages

    held: list[bool] = []
    real = comms_messages.redact_run_tokens

    def _probe(conn, text):
        result: list[bool] = []

        def _try() -> None:
            got = connection._global_write_lock.acquire(blocking=False)
            if got:
                connection._global_write_lock.release()
            result.append(not got)

        t = threading.Thread(target=_try)
        t.start()
        t.join()
        held.append(result[0])
        return real(conn, text)

    monkeypatch.setattr(comms_messages, "redact_run_tokens", _probe)
    conn = get_db()
    token = _mint(conn, "run-lock")
    mid = comms_messages.post_message(
        conn, "feature", "feat-lock", "builder", text=f"t {token}", stage="s"
    )
    assert held and not any(held)
    text = conn.execute(
        "SELECT text FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()[0]
    assert text == f"t {REDACTED}"
