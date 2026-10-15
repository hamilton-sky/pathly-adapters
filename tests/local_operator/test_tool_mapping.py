"""Every HQ operator action maps onto a real endpoint and runs through it
(local-operator ticket 02): the route exists, accepts the settled args, and its
refusals (a busy board, a stale run) reach the card instead of being retried.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from _operator_env import (
    BOARD,
    check,
    client,  # noqa: F401  (fixture)
    db,
    make_all_available,
    registry_run,
    run_card,
    seed_artifact,
    seed_goal,
)

SERVER_RUN = (
    "pause_run",
    "resume_run",
    "retry_run",
    "stop_run",
    "run_goal",
    "plan_goal",
    "post_note",
)


@pytest.mark.parametrize("name", SERVER_RUN)
def test_each_server_action_targets_a_registered_route(name):
    from pathly_orchestrator.http_server import app
    from pathly_orchestrator.http_server.blueprints.hq._action_exec import route_for

    args = {
        "run_id": "r1",
        "flow": "team",
        "project_root": "/p",
        "goal_id": "g1",
        "text": "hi",
    }
    method, path, _body = route_for(name, args, BOARD, "/p")
    endpoint, _ = app.url_map.bind("localhost").match(path, method=method)
    assert endpoint  # a real, registered route — no new spawn path


def test_catalog_never_offers_forbidden_actions():
    from pathly_orchestrator.hq_actions import CATALOG, NEVER_OFFERED

    assert not {a.name for a in CATALOG} & NEVER_OFFERED
    assert {a.name for a in CATALOG} >= set(SERVER_RUN)


def test_pause_runs_through_the_run_control_route(client):  # noqa: F811
    with registry_run("run-pause-1", "running") as state:
        card = check(
            client, [{"name": "pause_run", "args": {"run_id": "run-pause-1"}}]
        )["cards"][0]
        assert card["status"] == "proposed"
        assert card["title"].startswith("Pause run run-pause-1")
        out = run_card(client, card)
        assert out["status"] == "done", out
        assert state._pause_flag or state.status == "paused"


def test_stop_and_resume(client):  # noqa: F811
    with registry_run("run-stop-1", "running") as state:
        card = check(client, [{"name": "stop_run", "args": {"run_id": "run-stop-1"}}])[
            "cards"
        ][0]
        assert run_card(client, card)["status"] == "done"
        assert state._abort_flag is True
    with registry_run("run-resume-1", "paused"):
        card = check(
            client, [{"name": "resume_run", "args": {"run_id": "run-resume-1"}}]
        )["cards"][0]
        assert card["status"] == "proposed"
        assert run_card(client, card)["status"] == "done"


def test_retry_restarts_a_finished_flow_run(client, monkeypatch):  # noqa: F811
    import pathly_orchestrator.supervisor.api as api

    calls = []

    def fake_start_run(**kw):
        calls.append(kw)
        return SimpleNamespace(run_id="run-new-123456")

    monkeypatch.setattr(api, "start_run", fake_start_run)
    with registry_run("run-done-1", "error", flow="team-build"):
        card = check(client, [{"name": "retry_run", "args": {"run_id": "run-done-1"}}])[
            "cards"
        ][0]
        assert card["status"] == "proposed"
        out = run_card(client, card)
    assert out["status"] == "done" and "run-new-1234" in out["summary"]
    assert len(calls) == 1 and calls[0]["flow"] == "team-build"


def test_run_goal_and_plan_goal_use_the_goal_routes(client, monkeypatch):  # noqa: F811
    import pathly_orchestrator.supervisor.goal_run as goal_run

    started, planned = [], []
    monkeypatch.setattr(
        goal_run,
        "start_goal_run",
        lambda gid, **kw: started.append(gid) or {"ok": True},
    )
    monkeypatch.setattr(
        goal_run,
        "start_goal_decompose",
        lambda gid, **kw: planned.append((gid, kw["mode"])) or {"ok": True},
    )
    make_all_available(client)
    gid = seed_goal("Ship the gateway")
    cards = check(
        client,
        [
            {"name": "run_goal", "args": {"goal": gid[:8]}},
            {"name": "plan_goal", "args": {"goal": "ship the gateway"}},
        ],
    )["cards"]
    assert [c["status"] for c in cards] == ["proposed", "proposed"]
    assert cards[0]["args"] == {"goal": gid[:8]}
    assert [run_card(client, c)["status"] for c in cards] == ["done", "done"]
    assert started == [gid] and planned == [(gid, "planner")]


def test_a_spawn_refusal_reaches_the_card(client, monkeypatch):  # noqa: F811
    """A busy board / cost ceiling is the route's own refusal — relayed, not retried."""
    import pathly_orchestrator.supervisor.goal_run as goal_run

    calls = []
    monkeypatch.setattr(
        goal_run,
        "start_goal_run",
        lambda gid, **kw: calls.append(gid) or {"ok": False, "reason": "board_busy"},
    )
    make_all_available(client)
    gid = seed_goal()
    card = check(client, [{"name": "run_goal", "args": {"goal": gid}}])["cards"][0]
    out = run_card(client, card)
    assert out["status"] == "failed" and "board busy" in out["summary"]
    assert len(calls) == 1  # one attempt, no retry loop


def test_post_note_posts_as_the_human(client):  # noqa: F811
    card = check(
        client, [{"name": "post_note", "args": {"text": "Pause after review"}}]
    )["cards"][0]
    assert run_card(client, card)["status"] == "done"
    row = (
        db()
        .execute(
            "SELECT from_agent, type FROM comms_messages WHERE scope=? AND text=?",
            (BOARD, "Pause after review"),
        )
        .fetchone()
    )
    assert (row["from_agent"], row["type"]) == ("human", "note")


def test_diagram_actions_are_approved_for_studio(client, tmp_path):  # noqa: F811
    make_all_available(client)
    doc = tmp_path / "design.md"
    doc.write_text("# Gateway\n")
    art_id = seed_artifact(str(doc))
    card = check(
        client,
        [{"name": "diagram_artifact", "args": {"artifact": art_id, "style": None}}],
    )["cards"][0]
    assert card["runs_on"] == "studio" and card["status"] == "proposed"
    out = run_card(client, card)
    assert out["status"] == "approved"
    assert out["target"]["path"] == str(doc) and out["target"]["style"] is None

    # No diagram yet → add-to-board can't be proposed; once one exists it can.
    add = {"name": "add_diagram_to_board", "args": {"artifact": "Gateway design"}}
    diagrams = ["diagram_artifact", "add_diagram_to_board"]
    assert check(client, [add], diagrams)["cards"][0]["status"] == "invalid"
    (tmp_path / "design.md.diagrams.json").write_text(
        '{"version": 1, "source": "design.md", "diagrams": [{"id": "dg_1", "title": "Flow"}]}'
    )
    card = check(client, [add], diagrams)["cards"][0]
    assert card["status"] == "proposed" and card["fingerprint"] == "dg_1"
    assert run_card(client, card)["target"]["diagram_id"] == "dg_1"


def test_stale_card_runs_nothing(client):  # noqa: F811
    with registry_run("run-stale-1", "running") as state:
        card = check(
            client, [{"name": "pause_run", "args": {"run_id": "run-stale-1"}}]
        )["cards"][0]
        state.status = "paused"  # the board changed after the card was shown
        out = run_card(client, card)
        assert out["status"] == "stale" and "not running" in out["summary"]
        assert state._pause_flag is False


def test_check_drops_actions_not_enabled_and_caps_enabled(client):  # noqa: F811
    out = check(
        client,
        [
            {"name": "post_note", "args": {"text": "x"}},
            {"name": "answer_question", "args": {}},
        ],
        enabled=["pause_run"],
    )
    assert out["cards"] == []
    assert {d["name"] for d in out["dropped"]} == {"post_note", "answer_question"}

    too_many = client.post(
        "/hq/actions/check",
        json={
            "board": BOARD,
            "enabled_actions": [f"a{i}" for i in range(9)],
            "proposals": [],
        },
    )
    assert too_many.status_code == 400


def test_bad_args_make_an_invalid_card_not_a_call(client):  # noqa: F811
    card = check(client, [{"name": "stop_run", "args": {"nope": 1}}])["cards"][0]
    assert card["status"] == "invalid" and "run_id" in card["summary"]


def test_settings_turn_an_action_off(client):  # noqa: F811
    resp = client.put("/hq/actions/available", json={"actions": ["pause_run"]})
    assert resp.status_code == 200
    names = {a["name"]: a["available"] for a in resp.get_json()["actions"]}
    assert names["pause_run"] and not names["post_note"]
    # post_note is no longer usable even though the composer still ticks it.
    assert check(client, [{"name": "post_note", "args": {"text": "x"}}])["cards"] == []
    out = client.post(
        "/hq/actions/run",
        json={
            "board": BOARD,
            "name": "post_note",
            "args": {"text": "x"},
            "fingerprint": "",
        },
    ).get_json()
    assert out["status"] == "unavailable"
    bad = client.put("/hq/actions/available", json={"actions": ["answer_question"]})
    assert bad.status_code == 400


def test_default_availability_is_run_control_and_note(client):  # noqa: F811
    actions = client.get("/hq/actions").get_json()["actions"]
    on = [a["name"] for a in actions if a["available"]]
    assert on == ["pause_run", "resume_run", "retry_run", "stop_run", "post_note"]
