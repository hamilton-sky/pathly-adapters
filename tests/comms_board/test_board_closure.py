"""Board closure — the write paths that let a resolution actually land.

Three defects shared one shape: an agent RESOLVES something and the board never records it.
Decisions accumulated forever because nothing called supersede; task resolutions lived only
as prose in a markdown file; and a terminal FSM state could not say which flow's DONE it was.

* Proposal A — POST /comms/post accepts `supersedes`, retiring the decisions it replaces.
* Proposal B — POST /comms/tasks/status write-backs a batch of task resolutions in one call.
* Proposal D — write_state stamps the flow name, and delivery flows gate ->DONE on tasks done.

See docs/BOARD_LIFECYCLE_FINDINGS.md.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(client, **fields):
    body = {"feature": "closure-demo", "board": "feature", "scope": "closure-demo"}
    body.update(fields)
    r = client.post("/comms/post", json=body)
    assert r.status_code == 200, r.data
    return json.loads(r.data)


def _decision(client, text, **extra):
    return _post(
        client, **{"from": "architect", "type": "decision", "text": text, **extra}
    )


def _agent_headers(role="evaluator", board="feature", scope="closure-demo"):
    """A live run token for an agent on *board*/*scope* — /comms/tasks/status needs one."""
    import uuid

    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    token = mint_run_token(
        get_db(),
        f"run-{uuid.uuid4().hex[:8]}",
        role,
        scope,
        "/tmp/closure",
        board,
        scope,
    )
    return {"X-Pathly-Run-Token": token}


def _superseded_by(message_id):
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute("SELECT superseded_by FROM comms_messages WHERE id=?", (message_id,))
        .fetchone()
    )
    return row["superseded_by"] if row else None


# ── Proposal A — supersession write path ─────────────────────────────────────


def test_post_with_supersedes_retires_the_named_decision(client):
    old = _decision(client, "ARCH_QUESTION 2 remains a hard human gate before P1 BUILD")
    new = _decision(
        client, "Adopt Option B. Phase 1 unblocked.", supersedes=[old["message_id"]]
    )
    assert new["superseded"] == [old["message_id"]]
    assert _superseded_by(old["message_id"]) == new["message_id"]


def test_superseded_decision_leaves_the_governance_block(client):
    """The point of the write path: a retired decision stops being injected as live truth."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_pending_decisions

    old = _decision(client, "GATE: do not build until the human answers")
    new = _decision(
        client, "Gate resolved by the human.", supersedes=[old["message_id"]]
    )

    live = get_pending_decisions(get_db(), boards=["feature"], scopes=["closure-demo"])
    live_ids = {m["id"] for m in live}
    assert old["message_id"] not in live_ids
    assert new["message_id"] in live_ids


def test_supersedes_reports_per_id_verdicts_without_failing_the_post(client):
    """A stale id must not lose the decision post — it degrades to a skipped entry."""
    first = _decision(client, "first")
    _decision(client, "retires first", supersedes=[first["message_id"]])

    resp = _decision(
        client,
        "names one already-superseded id and one that does not exist",
        supersedes=[first["message_id"], "no-such-id"],
    )
    assert resp["ok"] is True
    assert resp["superseded"] == []
    reasons = {s["id"]: s["reason"] for s in resp["supersede_skipped"]}
    assert reasons[first["message_id"]] == "already_superseded"
    assert reasons["no-such-id"] == "not_found"


def test_a_message_cannot_supersede_itself(client):
    """Self-supersession would retire the very post being made — get_pending_decisions
    filters on superseded_by IS NULL."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_pending_decisions

    posted = _decision(client, "self-referential decision")
    # The id isn't knowable before the post, so exercise the guard directly.
    from pathly_orchestrator.http_server.blueprints.comms._supersede_on_post import (
        apply_supersedes,
    )

    out = apply_supersedes(get_db(), [posted["message_id"]], posted["message_id"])
    assert out["superseded"] == []
    assert out["skipped"] == [{"id": posted["message_id"], "reason": "self_reference"}]
    live_ids = {
        m["id"]
        for m in get_pending_decisions(
            get_db(), boards=["feature"], scopes=["closure-demo"]
        )
    }
    assert posted["message_id"] in live_ids


def test_supersede_refuses_an_escalation(client):
    """A human-addressed escalation is a gate only a human closes; superseding it would
    retire the gate silently (get_active_escalations filters superseded rows)."""
    esc = _post(
        client,
        **{
            "from": "architect",
            "type": "escalation",
            "to": "human",
            "text": "needs a human",
        },
    )
    resp = _decision(client, "unblocked, start now", supersedes=[esc["message_id"]])
    assert resp["superseded"] == []
    assert resp["supersede_skipped"] == [
        {"id": esc["message_id"], "reason": "not_a_decision"}
    ]
    assert _superseded_by(esc["message_id"]) is None


def test_supersede_refuses_a_decision_on_another_board(client):
    """The feature board takes a post from any role, so a cross-board supersede would let it
    retire a decision it could never have written."""
    other = _post(
        client,
        **{
            "feature": "other-board",
            "scope": "other-board",
            "from": "architect",
            "type": "decision",
            "text": "a decision on another board",
        },
    )
    resp = _decision(client, "tries to retire it", supersedes=[other["message_id"]])
    assert resp["supersede_skipped"][0]["reason"] == "other_board"
    assert _superseded_by(other["message_id"]) is None


def test_supersedes_on_a_non_decision_post_is_rejected(client):
    old = _decision(client, "a live decision")
    r = client.post(
        "/comms/post",
        json={
            "feature": "closure-demo",
            "board": "feature",
            "scope": "closure-demo",
            "from": "builder",
            "type": "status",
            "text": "a status line",
            "supersedes": [old["message_id"]],
        },
    )
    assert r.status_code == 400
    assert _superseded_by(old["message_id"]) is None


@pytest.mark.parametrize("bad", ["not-a-list", [1, 2], [{"id": "x"}]])
def test_malformed_supersedes_is_rejected_before_anything_is_written(client, bad):
    r = client.post(
        "/comms/post",
        json={
            "feature": "closure-demo",
            "board": "feature",
            "scope": "closure-demo",
            "from": "architect",
            "type": "decision",
            "text": "bad supersedes",
            "supersedes": bad,
        },
    )
    assert r.status_code == 400
    assert "supersedes" in json.loads(r.data)["error"]


def test_supersedes_is_capped(client):
    from pathly_orchestrator.http_server.blueprints.comms._supersede_on_post import (
        MAX_SUPERSEDES,
        validate_supersedes,
    )

    ids, err = validate_supersedes([f"id-{i}" for i in range(MAX_SUPERSEDES + 1)])
    assert ids is None and "at most" in err


def test_supersedes_is_deduplicated_and_absent_field_stays_none():
    from pathly_orchestrator.http_server.blueprints.comms._supersede_on_post import (
        validate_supersedes,
    )

    assert validate_supersedes(None) == (None, None)
    ids, err = validate_supersedes(["a", "a", " b ", ""])
    assert err is None and ids == ["a", "b"]


# ── Proposal B — task state write-back ───────────────────────────────────────


def _task(client, text, **extra):
    return _post(
        client,
        **{"from": "planner", "type": "task", "text": text, "no_refs": "test", **extra},
    )


def _task_status(message_id):
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute("SELECT task_status FROM comms_messages WHERE id=?", (message_id,))
        .fetchone()
    )
    return row["task_status"] if row else None


def test_status_marks_a_batch_of_tasks_done_in_one_call(client):
    """The evaluator's "Mark tasks A, B, C as COMPLETE" becomes a call, not a sentence."""
    ids = [_task(client, f"task {i}")["message_id"] for i in range(3)]
    r = client.post(
        "/comms/tasks/status",
        headers=_agent_headers(),
        json={
            "task_ids": ids,
            "status": "done",
            "from": "evaluator",
            "reason": "resolved by ADR-007",
        },
    )
    assert r.status_code == 200, r.data
    assert set(json.loads(r.data)["updated"]) == set(ids)
    assert all(_task_status(i) == "done" for i in ids)


def test_completing_a_dependency_reports_newly_ready_dependents(client):
    dep = _task(client, "the blocker")
    blocked = _task(client, "waits on the blocker", depends_on=[dep["message_id"]])
    r = client.post(
        "/comms/tasks/status",
        headers=_agent_headers(),
        json={"task_ids": [dep["message_id"]], "status": "done"},
    )
    assert blocked["message_id"] in json.loads(r.data)["newly_ready"]


def test_failing_a_task_cascades_to_its_dependents(client):
    dep = _task(client, "will fail")
    downstream = _task(
        client, "downstream of the failure", depends_on=[dep["message_id"]]
    )
    r = client.post(
        "/comms/tasks/status",
        headers=_agent_headers(),
        json={
            "task_ids": [dep["message_id"]],
            "status": "failed",
            "reason": "unbuildable",
        },
    )
    assert _task_status(dep["message_id"]) == "failed"
    assert downstream["message_id"] in json.loads(r.data)["blocked"]


def test_unknown_ids_are_reported_not_silently_dropped(client):
    real = _task(client, "real task")
    r = client.post(
        "/comms/tasks/status",
        headers=_agent_headers(),
        json={"task_ids": [real["message_id"], "ghost-id"], "status": "done"},
    )
    body = json.loads(r.data)
    assert body["updated"] == [real["message_id"]]
    assert body["unknown"] == ["ghost-id"]


def test_status_is_idempotent(client):
    tid = _task(client, "done twice")["message_id"]
    for _ in range(2):
        r = client.post(
            "/comms/tasks/status",
            headers=_agent_headers(),
            json={"task_ids": [tid], "status": "done"},
        )
        assert json.loads(r.data)["updated"] == [tid]
    assert _task_status(tid) == "done"


def test_reopening_a_task_is_refused(client):
    """An agent that can reopen its own failures can loop without anything closing."""
    tid = _task(client, "no reopening")["message_id"]
    r = client.post(
        "/comms/tasks/status",
        headers=_agent_headers(),
        json={"task_ids": [tid], "status": "pending"},
    )
    assert r.status_code == 400
    assert "supervisory" in json.loads(r.data)["note"]


@pytest.mark.parametrize(
    "body",
    [
        {"status": "done"},  # no ids
        {"task_ids": ["x"]},  # no status
        {"task_ids": [], "status": "done"},  # empty ids
        {"task_ids": ["x"], "status": "banana"},  # unknown status
    ],
)
def test_status_rejects_malformed_requests(client, body):
    assert (
        client.post(
            "/comms/tasks/status", headers=_agent_headers(), json=body
        ).status_code
        == 400
    )


def test_status_without_a_run_token_is_refused(client):
    """Without a caller identity any process could mark every task done and walk a run
    through the ->DONE: require_tasks_done gate."""
    tid = _task(client, "needs an agent")["message_id"]
    r = client.post("/comms/tasks/status", json={"task_ids": [tid], "status": "done"})
    assert r.status_code == 403
    assert _task_status(tid) != "done"


def test_status_refuses_a_task_on_another_board(client):
    tid = _task(client, "belongs to closure-demo")["message_id"]
    r = client.post(
        "/comms/tasks/status",
        headers=_agent_headers(scope="some-other-feature"),
        json={"task_ids": [tid], "status": "done"},
    )
    body = json.loads(r.data)
    assert body["updated"] == []
    assert body["refused"] == [tid]
    assert _task_status(tid) != "done"


def test_status_line_is_stamped_as_the_calling_run(client):
    from pathly_orchestrator.db.connection import get_db

    tid = _task(client, "stamped settle")["message_id"]
    client.post(
        "/comms/tasks/status",
        headers=_agent_headers(role="evaluator"),
        json={"task_ids": [tid], "status": "done", "reason": "covered by ADR-7"},
    )
    row = (
        get_db()
        .execute(
            "SELECT author_role, author_source FROM comms_messages "
            "WHERE type='status' AND text LIKE 'Done: stamped settle%'"
        )
        .fetchone()
    )
    assert (row["author_role"], row["author_source"]) == ("evaluator", "token")


def test_an_agent_cannot_close_a_human_escalation(client):
    """Acknowledging or deleting the row is how a human gate closes; an agent run (live
    token) may do neither, whatever `agent` it names in the body."""
    esc = _post(
        client,
        **{
            "from": "architect",
            "type": "escalation",
            "to": "human",
            "text": "human call",
        },
    )
    mid = esc["message_id"]
    headers = _agent_headers(role="builder")
    ack = client.post(
        "/comms/acknowledge",
        headers=headers,
        json={"message_id": mid, "agent": "human"},
    )
    assert ack.status_code == 403
    gone = client.post(
        "/comms/delete", headers=headers, json={"message_id": mid, "force": True}
    )
    assert gone.status_code == 403
    # A caller without a run token (a human in Studio, until the UI token) still can.
    ok = client.post("/comms/acknowledge", json={"message_id": mid, "agent": "human"})
    assert ok.status_code == 200


def test_an_agent_cannot_answer_a_human_escalation_away(client):
    """`/comms/answer` flips the row to `answered`, and the gate only reads pending rows."""
    esc = _post(
        client,
        **{"from": "architect", "type": "escalation", "to": "human", "text": "h?"},
    )
    r = client.post(
        "/comms/answer",
        headers=_agent_headers(role="builder"),
        json={"question_id": esc["message_id"], "answer": "yes, go"},
    )
    assert r.status_code == 403


def test_the_direct_supersede_route_holds_an_agent_to_the_same_rules(client):
    """POST /comms/supersede checked neither type nor board, so an agent could retire a
    human escalation through it even after /comms/post refused to."""
    esc = _post(
        client,
        **{"from": "architect", "type": "escalation", "to": "human", "text": "gate"},
    )
    new = _decision(client, "the replacement")
    headers = _agent_headers(role="builder")
    r = client.post(
        "/comms/supersede",
        headers=headers,
        json={"old_id": esc["message_id"], "new_id": new["message_id"]},
    )
    assert r.status_code == 403
    assert _superseded_by(esc["message_id"]) is None
    other = _post(
        client,
        **{
            "feature": "elsewhere",
            "scope": "elsewhere",
            "from": "architect",
            "type": "decision",
            "text": "a decision on another board",
        },
    )
    r = client.post(
        "/comms/supersede",
        headers=headers,
        json={"old_id": other["message_id"], "new_id": new["message_id"]},
    )
    assert r.status_code == 403
    # Studio's supersede menu sends no run token and still works.
    old = _decision(client, "superseded from the UI")
    r = client.post(
        "/comms/supersede",
        json={"old_id": old["message_id"], "new_id": new["message_id"]},
    )
    assert r.status_code == 200


def test_supersedes_on_post_is_bound_to_the_agents_token_board(client):
    """The post's board/scope come from the body; an agent cannot claim another board's
    scope on its decision and retire a decision there."""
    other = _post(
        client,
        **{
            "feature": "board-b",
            "scope": "board-b",
            "from": "architect",
            "type": "decision",
            "text": "board B's decision",
        },
    )
    r = client.post(
        "/comms/post",
        headers=_agent_headers(role="builder", scope="closure-demo"),
        json={
            "feature": "board-b",
            "board": "feature",
            "scope": "board-b",
            "from": "builder",
            "type": "decision",
            "text": "claims board B's scope",
            "supersedes": [other["message_id"]],
        },
    )
    body = json.loads(r.data)
    assert body["supersede_skipped"][0]["reason"] == "other_board"
    assert _superseded_by(other["message_id"]) is None


def test_single_task_id_form_is_accepted(client):
    tid = _task(client, "singular form")["message_id"]
    r = client.post(
        "/comms/tasks/status",
        headers=_agent_headers(),
        json={"task_id": tid, "status": "done"},
    )
    assert json.loads(r.data)["updated"] == [tid]


# ── Proposal D — a terminal state that says which terminal ───────────────────


def test_write_state_stamps_the_flow_name(tmp_path, monkeypatch):
    """ "DONE" alone cannot distinguish consultation's DONE (decomposed, nothing built)
    from team's DONE (shipped)."""
    from pathly_orchestrator import eventlog

    feature_dir = tmp_path / "pathly" / "features" / "stamp-demo"
    feature_dir.mkdir(parents=True)
    captured: dict = {}
    monkeypatch.setattr(
        eventlog, "_write_state_db", lambda d, n, state: captured.update(state)
    )

    flow = {
        "flow": "consultation",
        "states": ["PLANNING", "DONE"],
        "transitions": {"PLANNING": ["DONE"], "DONE": []},
    }
    eventlog.write_state(str(feature_dir), {"current": "DONE"}, flow)
    assert captured["current"] == "DONE"
    assert captured["flow"] == "consultation"


def test_write_state_without_a_flow_does_not_erase_the_stamp(tmp_path, monkeypatch):
    from pathly_orchestrator import eventlog

    feature_dir = tmp_path / "pathly" / "features" / "stamp-demo-2"
    feature_dir.mkdir(parents=True)
    captured: dict = {}
    monkeypatch.setattr(
        eventlog, "_write_state_db", lambda d, n, state: captured.update(state)
    )
    eventlog.write_state(str(feature_dir), {"current": "DONE", "flow": "team"}, None)
    assert captured["flow"] == "team"


def test_delivery_flows_gate_done_on_tasks_done():
    """team/team-build DONE claims the feature shipped, so it must not be reachable with
    unfinished tasks. Consultation flows END at decomposition — pending tasks are their
    correct output, so they must NOT carry this gate."""
    import yaml

    from tests._paths import SRC

    def gates_for(flow):
        with open(SRC / "pathly_data" / "core" / "flows" / f"{flow}.flow.yaml") as fh:
            return yaml.safe_load(fh).get("gates") or {}

    for delivery in ("team", "team-build"):
        done_gates = gates_for(delivery).get("->DONE", [])
        assert any(g["type"] == "require_tasks_done" for g in done_gates), delivery

    for decomposer in ("consultation", "feature-consultation", "project-consultation"):
        assert "->DONE" not in gates_for(decomposer), decomposer


def test_wildcard_gates_survive_the_db_round_trip():
    """run_gates honours "->TARGET", but gates are persisted per-EDGE — a wildcard matches no
    edge row and was dropped on the way into the DB. Flows load DB-first, so the gate would
    silently not fire."""
    from pathly_orchestrator.db.queries.flow_graph_ops import (
        _assemble_from_parts,
        _decompose_flow_dict,
    )

    original = {
        "version": 1,
        "flow": "wildcard-demo",
        "states": ["A", "DONE"],
        "transitions": {"A": ["DONE"], "DONE": []},
        "agent_map": {"A": "team/builder"},
        "gates": {
            "->DONE": [{"type": "require_tasks_done", "on_fail": "INCOMPLETE_TASKS.md"}]
        },
    }
    flow_cfg, nodes, edges = _decompose_flow_dict(original)
    assembled = _assemble_from_parts(flow_cfg, nodes, edges)
    assert assembled["gates"]["->DONE"] == original["gates"]["->DONE"]
