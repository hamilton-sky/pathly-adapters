"""chief-agent 20, B8 and B9: a close that lands while a chief is opening, and a tab that ended
before it ever started.

B8. ``open_chief`` writes the session row under its lock, then mints the token and sends the spawn
outside it, and ``POST /chief/close`` does not take that lock. A close between the row and the
mint closed the session, and the open then minted its token anyway and sent the spawn: a live
token on a closed session and a tab started for it. Once the token is minted ``open_chief`` now
reads the session again; if it is closed it revokes the token, sends no spawn and raises
``ChiefClosedWhileOpening`` (``POST /chief/open`` answers 409). A close that lands after that
re-read and before the broadcast still revokes the token, so the tab gets a dead one.

B9. The watcher used to wait up to 30 seconds for "started" and only then for the result, so a tab
whose process ended and whose result was posted without a "started" was noticed when the 30
seconds ran out. It now wakes on whichever comes first.
"""

from __future__ import annotations

import threading
import time

import pytest
from chief_open_support import (
    PROMPT,
    WATCHER_PREFIX,
    Host,
    _no_watcher_outlives_its_test,
    chief_root,
    open_with,
    project,
    wait,
)

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as chief_queries
from pathly_orchestrator.http_server import sse
from pathly_orchestrator.supervisor import chief_session
from pathly_orchestrator.supervisor.chief_session import close_chief
from pathly_orchestrator.supervisor.registry import TerminalRun, get_run

REASON = "closed mid-open"


def _live_tokens(run_id: str) -> int:
    row = get_db().execute(
        "SELECT COUNT(*) FROM run_tokens WHERE run_id = ? AND revoked_at IS NULL",
        (run_id,),
    )
    return row.fetchone()[0]


def _closing_mint(monkeypatch, *, after_minting: bool) -> list[str]:
    """Replace the mint with one that closes the session from inside it, before it returns the
    token (``after_minting`` False: the close lands before the token exists) or after the token
    exists. Returns the list the minted tokens are appended to."""
    real = chief_session.mint_run_token
    minted: list[str] = []

    def mint(conn, run_id, *args, **kwargs):
        if not after_minting:
            assert close_chief(run_id, REASON) is True
        token = real(conn, run_id, *args, **kwargs)
        minted.append(token)
        if after_minting:
            assert close_chief(run_id, REASON) is True
        return token

    monkeypatch.setattr(chief_session, "mint_run_token", mint)
    return minted


# --- B8 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("after_minting", [False, True], ids=["before", "after"])
def test_a_close_from_inside_the_mint_leaves_nothing_live_and_sends_no_spawn(
    project, chief_root, monkeypatch, after_minting
):
    minted = _closing_mint(monkeypatch, after_minting=after_minting)
    host = Host()

    with pytest.raises(chief_session.ChiefClosedWhileOpening) as raised:
        open_with(project, host)

    run_id = raised.value.run_id
    assert host.sent == []
    assert len(minted) == 1
    assert _live_tokens(run_id) == 0
    session = chief_queries.get_session(get_db(), run_id)
    assert session["closed_at"] is not None
    assert session["close_reason"] == REASON
    assert get_run(run_id) is None
    assert not (chief_root / run_id).exists()
    assert [t for t in threading.enumerate() if run_id in t.name] == []


def test_the_project_can_open_a_chief_again_after_a_close_that_landed_mid_open(
    project, chief_root, monkeypatch
):
    real = chief_session.mint_run_token
    _closing_mint(monkeypatch, after_minting=True)
    with pytest.raises(chief_session.ChiefClosedWhileOpening):
        open_with(project, Host())
    monkeypatch.setattr(chief_session, "mint_run_token", real)

    host = Host()
    second = open_with(project, host)

    assert len(host.sent) == 1
    assert _live_tokens(second["run_id"]) == 1


def test_an_open_nobody_closes_still_mints_one_token_and_sends_one_spawn(
    project, chief_root
):
    host = Host()

    run_id = open_with(project, host)["run_id"]

    assert len(host.sent) == 1
    assert _live_tokens(run_id) == 1
    assert chief_queries.get_session(get_db(), run_id)["closed_at"] is None


def test_a_close_that_lands_during_the_broadcast_still_revokes_the_token(
    project, chief_root
):
    """The window ``open_chief`` cannot shut without holding a lock across the broadcast: the
    open succeeds, the tab gets a token that is already dead."""
    sent: list[dict] = []

    def broadcast(topic: str, payload: dict) -> None:
        sent.append(payload)
        assert close_chief(payload["run_id"], REASON) is True

    run_id = open_with(project, Host(), broadcast_fn=broadcast)["run_id"]

    assert len(sent) == 1
    assert _live_tokens(run_id) == 0
    assert chief_queries.get_session(get_db(), run_id)["close_reason"] == REASON


@pytest.fixture()
def client(monkeypatch):
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("after_minting", [False, True], ids=["before", "after"])
def test_the_open_route_answers_409_with_the_run_id_when_a_close_lands_mid_open(
    client, project, chief_root, monkeypatch, after_minting
):
    host = Host()
    monkeypatch.setattr(sse, "_broadcast_runner", host)
    _closing_mint(monkeypatch, after_minting=after_minting)

    answer = client.post(
        "/chief/open",
        json={
            "project_root": project,
            "engine": "claude",
            "preset": "operator",
            "prompt": PROMPT,
        },
    )

    assert answer.status_code == 409, answer.get_data(as_text=True)
    body = answer.get_json()
    assert set(body) == {"error", "run_id"}
    assert body["error"]
    session = chief_queries.get_session(get_db(), body["run_id"])
    assert session["closed_at"] is not None
    assert _live_tokens(body["run_id"]) == 0
    assert host.sent == []


# --- B9 ------------------------------------------------------------------------------------------


def _watcher(run_id: str) -> threading.Thread:
    (thread,) = [t for t in threading.enumerate() if t.name == WATCHER_PREFIX + run_id]
    return thread


def _reason(run_id: str) -> str | None:
    return chief_queries.get_session(get_db(), run_id)["close_reason"]


def test_a_result_posted_without_a_started_closes_the_session_at_once(
    project, chief_root
):
    host = Host()
    run_id = open_with(project, host)["run_id"]  # the watcher waits 30 seconds to start
    watcher = _watcher(run_id)

    get_run(run_id).mark_pty_result({"exit_code": 1})
    watcher.join(2)

    assert not watcher.is_alive()
    session = chief_queries.get_session(get_db(), run_id)
    assert session["closed_at"] is not None
    assert session["close_reason"] == "tab closed"
    assert _live_tokens(run_id) == 0


def test_started_and_then_a_result_closes_the_session_as_tab_closed(
    project, chief_root
):
    run_id = open_with(project, Host())["run_id"]
    run = get_run(run_id)
    watcher = _watcher(run_id)

    run.mark_started()
    time.sleep(0.05)
    assert chief_queries.get_session(get_db(), run_id)["closed_at"] is None
    run.mark_pty_result({"exit_code": 0})
    watcher.join(2)

    assert not watcher.is_alive()
    assert _reason(run_id) == "tab closed"


def test_neither_started_nor_a_result_within_the_timeout_closes_it_as_never_started(
    project, chief_root
):
    run_id = open_with(project, Host(), start_timeout=0.05)["run_id"]

    assert wait(lambda: _reason(run_id) is not None)

    assert _reason(run_id) == "never started"


def test_the_wait_for_started_or_a_result_wakes_on_whichever_comes_first():
    for mark in ("mark_started", "mark_pty_result"):
        run = TerminalRun(run_id="r")
        assert run.wait_started_or_result(0.01) is False
        if mark == "mark_started":
            run.mark_started()
        else:
            run.mark_pty_result({"exit_code": 0})
        assert run.wait_started_or_result(0.01) is True

    late = TerminalRun(run_id="r")
    threading.Timer(0.05, late.mark_pty_result, args=({"closed": "x"},)).start()
    began = time.monotonic()
    assert late.wait_started_or_result(30) is True
    assert time.monotonic() - began < 2

    started = TerminalRun(run_id="r")
    threading.Timer(0.05, started.mark_started).start()
    assert started.wait_started_or_result(30) is True
