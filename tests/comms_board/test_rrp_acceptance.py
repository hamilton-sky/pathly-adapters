"""Identity and provenance end to end: spawn token, stamped board post, reviewer wall

role-read-policy ticket 10: the bar from the plan's map.md, driven through the real spawn path
(``supervisor/terminal.py``), the real Flask app and the real read policy. One fake broadcaster
stands in for the spawn host AND the agent: when ``TERMINAL_SPAWN`` goes out it posts with the
token from the payload, the way a fragment's ``curl`` sends the ``X-Pathly-Run-Token`` header
on ``POST /comms/post``. So the hosts' ``PATHLY_RUN_TOKEN`` export and the fragments' header are
not links this test drives; ``tests/runner_supervisor/test_pty_host.py``,
``studio/src/main/ipc/terminal/spawnEnv.test.ts`` and
``tests/consistency/test_fragments_run_token.py`` pin those. The read policy of tickets 01 and
02 is then evaluated over what the server stored.

The policy is NOT wired into any read path yet: no production code calls it, so it withholds
nothing from any agent. The last test pins that for ``GET /comms``, the one read path it
checks, and is the one a later plan changes when that route starts withholding.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest

from pathly_orchestrator.supervisor.registry import get_run
from pathly_orchestrator.supervisor.state import RunnerState
from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal

FEATURE = "feat-rrp"
BUILDER_RUN = f"{FEATURE}-1-100"
REVIEWER_RUN = f"{FEATURE}-2-200"
RUN_TOKEN_HEADER = "X-Pathly-Run-Token"


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    return app.test_client()


def _post(client, token: str | None, **fields) -> str:
    """One ``curl -X POST /comms/post``; the header is sent only when the agent has a token."""
    body = {
        "feature": FEATURE,
        "board": "feature",
        "scope": FEATURE,
        "from": "explorer",
        "type": "discovery",
        "text": "found something",
        **fields,
    }
    headers = {RUN_TOKEN_HEADER: token} if token else {}
    resp = client.post("/comms/post", json=body, headers=headers)
    assert resp.status_code == 200, resp.data
    return resp.get_json()["message_id"]


def _stamp(message_id: str) -> tuple:
    """(author_role, author_run_id, author_source) as the server stored them."""
    from pathly_orchestrator.db import get_db

    row = (
        get_db()
        .execute(
            "SELECT author_role, author_run_id, author_source"
            " FROM comms_messages WHERE id=?",
            (message_id,),
        )
        .fetchone()
    )
    return tuple(row)


@dataclass
class Spawn:
    """One stage run through the real spawn path."""

    run_id: str
    payload: dict  # the TERMINAL_SPAWN payload, as the spawn host receives it
    live: dict | None  # what its token resolved to while the spawn was running


def _spawn(
    tmp_path: Path, stage: str, run_id: str, agent: Callable[[str], None]
) -> Spawn:
    """Spawn FSM stage ``stage`` of the ``team`` flow.

    On ``TERMINAL_SPAWN`` the fake broadcaster (spawn host and agent in one) runs
    ``agent(token)`` with the token from the payload, where a real CLI process would read
    it from PATHLY_RUN_TOKEN. It then reports the process started and exited 0, so the
    spawn settles and revokes its token.
    """
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token

    storage = tmp_path / "pathly" / "features" / FEATURE
    storage.mkdir(parents=True, exist_ok=True)
    state = RunnerState(
        topic=FEATURE,
        flow="team",
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=60,
        run_id="parent-1",
        current_state=stage,
    )
    state.storage_path = str(storage)
    seen: dict = {}

    def broadcast(_topic, payload):
        if payload.get("type") != "TERMINAL_SPAWN":
            return
        seen["payload"] = payload
        seen["live"] = resolve_run_token(get_db(), payload.get("run_token"))
        agent(payload["run_token"])
        run = get_run(run_id)
        assert run is not None
        run.mark_started()
        run.mark_pty_result({"result": {}, "exit_code": 0})

    _run_stage_via_terminal(state, "do the work", "claude", "m", run_id, broadcast)
    return Spawn(run_id, seen["payload"], seen["live"])


@dataclass
class Scenario:
    project_root: str
    builder: Spawn
    reviewer: Spawn
    reviewer_identity: Any  # caller_identity() of the reviewer's own request
    reviewer_saw: set  # ids GET /comms returned to the reviewer, mid-spawn
    ids: dict  # label -> message id of every row the agents posted


@pytest.fixture()
def scenario(tmp_path: Path, client) -> Scenario:
    """A builder stage posts three rows, then a reviewer stage posts one and reads the board."""
    import flask

    from pathly_orchestrator.http_server import app
    from pathly_orchestrator.http_server.run_identity import caller_identity

    ids: dict = {}
    reviewer: dict = {}

    def builder_agent(token: str) -> None:
        # Steps 2 and 3. The builder labels its discovery "explorer" and puts the reviewer's
        # run id in the body; the server must not take the stamp from either. Its other
        # post lost the header.
        ids["discovery"] = _post(
            client, token, text="the builder's story", run_id=REVIEWER_RUN
        )
        ids["unverified"] = _post(client, None, text="posted without a header")
        ids["decision"] = _post(
            client, token, type="decision", text="we chose X", **{"from": "builder"}
        )

    def reviewer_agent(token: str) -> None:
        with app.test_request_context("/comms", headers={RUN_TOKEN_HEADER: token}):
            reviewer["identity"] = caller_identity(flask.request)
        # Labelled "builder", but the reviewer's token says what it is.
        ids["review"] = _post(
            client, token, text="the reviewer's own finding", **{"from": "builder"}
        )
        resp = client.get(
            "/comms",
            query_string={"feature": FEATURE, "limit": 100},
            headers={RUN_TOKEN_HEADER: token},
        )
        assert resp.status_code == 200, resp.data
        reviewer["saw"] = {m["id"] for m in resp.get_json()}

    built = _spawn(tmp_path, "BUILDING", BUILDER_RUN, builder_agent)
    reviewed = _spawn(tmp_path, "REVIEWING", REVIEWER_RUN, reviewer_agent)
    return Scenario(
        project_root=str(tmp_path),
        builder=built,
        reviewer=reviewed,
        reviewer_identity=reviewer["identity"],
        reviewer_saw=reviewer["saw"],
        ids=ids,
    )


# ── 1. the spawn payload carries a token that identifies the run ────────────────


def test_spawn_payload_token_resolves_to_the_stage_run_and_role(scenario):
    for spawn, role in ((scenario.builder, "builder"), (scenario.reviewer, "reviewer")):
        token = spawn.payload["run_token"]
        assert isinstance(token, str) and token
        live = spawn.live
        assert live is not None, "the token must resolve while the spawn is running"
        assert (live["run_id"], live["role"]) == (spawn.run_id, role)
        assert (live["feature"], live["board"], live["scope"]) == (
            FEATURE,
            "feature",
            FEATURE,
        )
        assert live["project_root"] == scenario.project_root


# ── 2. a post with the token is stamped from the token, not the body ────────────


def test_post_with_the_token_is_stamped_from_the_token_not_the_body(scenario):
    from pathly_orchestrator.db import get_db

    discovery = scenario.ids["discovery"]
    assert _stamp(discovery) == ("builder", BUILDER_RUN, "token")
    # The old body columns are still written as sent; the stamp does not come from them.
    cur = get_db().execute(
        "SELECT from_agent, run_id FROM comms_messages WHERE id=?", (discovery,)
    )
    assert tuple(cur.fetchone()) == ("explorer", REVIEWER_RUN)
    assert _stamp(scenario.ids["decision"]) == ("builder", BUILDER_RUN, "token")
    assert _stamp(scenario.ids["review"]) == ("reviewer", REVIEWER_RUN, "token")


# ── 3. a post with no header is unverified ──────────────────────────────────────


def test_post_with_no_header_is_stored_unverified(scenario):
    assert _stamp(scenario.ids["unverified"]) == (None, None, "none")


# ── 4. the reviewer wall: SQL predicate and pure twin agree ─────────────────────


def test_reviewer_wall_withholds_the_builder_row_and_the_unverified_row(scenario):
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.runner.read_policy import (
        policy_predicate,
        resolve_read_policy,
        row_allowed,
    )

    me = scenario.reviewer_identity
    assert (me.kind, me.role, me.run_id) == ("run", "reviewer", REVIEWER_RUN)
    conn = get_db()
    policy = resolve_read_policy(conn, me.role, me.feature, me.project_root)
    assert policy["exclude_authors"] == ["builder"]  # the built-in reviewer wall
    where, params = policy_predicate(policy, me.run_id)

    board = (me.board, me.scope)
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM comms_messages WHERE board=? AND scope=?", board
        )
    ]
    selected = {
        r[0]
        for r in conn.execute(
            "SELECT id FROM comms_messages WHERE board=? AND scope=? AND " + where,
            (*board, *params),
        )
    }
    kept = {r["id"] for r in rows if row_allowed(r, policy, me.run_id)}

    ids = scenario.ids
    assert ids["discovery"] not in selected  # stamped builder, labelled "explorer"
    assert ids["unverified"] not in selected  # no token, labelled "explorer"
    assert ids["decision"] in selected  # a builder decision is never withheld
    assert ids["review"] in selected  # the reviewer's own, labelled "builder"
    # The pure twin agrees with the SQL on every row of the board, and these two are
    # the only rows the wall withholds from the reviewer.
    assert kept == selected
    assert {r["id"] for r in rows} - selected == {ids["discovery"], ids["unverified"]}


# ── 5. the token dies with the spawn ────────────────────────────────────────────


def test_token_resolves_to_none_once_the_spawn_settles(scenario, client):
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token

    for spawn in (scenario.builder, scenario.reviewer):
        assert resolve_run_token(get_db(), spawn.payload["run_token"]) is None
    # A run that outlives its token still gets its post stored, but unverified.
    late = _post(client, scenario.builder.payload["run_token"], text="too late")
    assert _stamp(late) == (None, None, "none")


# ── what the stamps must survive ────────────────────────────────────────────────


def test_a_server_restart_keeps_the_stamps(scenario):
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.migrations_provenance import add_comms_provenance

    before = {label: _stamp(mid) for label, mid in scenario.ids.items()}
    add_comms_provenance(get_db())  # runs on every server start
    assert {label: _stamp(mid) for label, mid in scenario.ids.items()} == before
    assert before["unverified"] == (None, None, "none")  # not relabelled `legacy`


# ── what this plan does NOT do ──────────────────────────────────────────────────


def test_get_comms_still_returns_every_row_to_a_reviewer(scenario):
    """The policy exists but no production code calls it, so ``GET /comms`` with a
    reviewer's own live token returns every row, the two the wall would hide included.
    Only this read path is pinned.
    """
    assert set(scenario.ids.values()) <= scenario.reviewer_saw
