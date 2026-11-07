"""chief-autopilot-round-two 16: a consult run is billed and categorised as ``consult``.

``supervisor/consult_run.start_consult`` spawns with ``flow="consult"``. Driven here through the
real ``_run_stage_via_terminal`` (the fake ``spawn_fn`` wraps ``consult_run._default_spawn`` with a
broadcast that acts as the spawn host): the ``TERMINAL_SPAWN`` payload's ``category`` is
``consult``; a consult whose agent writes its ``AGENT_DONE`` (``category: consult``) and one that
writes none (the supervisor's synthetic one) both leave exactly one ``agent_invocations`` row with
category ``consult`` and the ``BILLING_UPDATE``'s cost folded in; the run token minted for the
consult names the asked role. ``fsm_compose_vars.spawn_category`` maps the other flows as before.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries import consult_routes as cr
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.db.queries.run_tokens import lookup_run_token
from pathly_orchestrator.db.queries.task_waits import park_task
from pathly_orchestrator.supervisor import consult_run
from pathly_orchestrator.supervisor.registry import get_run

BOARD, SCOPE = "feature", "feat-consult-billing"
TASK_TEXT = "Build the export button. Files: export.py. Done when: it exports."
QUESTION_TEXT = "Should the export stream rows or buffer the whole file?"
COST = 0.42


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _slow_path(monkeypatch):
    """The spawn returns on the PTY result (no early-advance watcher or billing thread), so the
    synthetic AGENT_DONE and the BILLING_UPDATE are written before ``start_consult`` returns.
    """
    monkeypatch.setenv("PATHLY_RUNNER_EARLY_ADVANCE", "0")


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "pathly" / "features" / SCOPE).mkdir(parents=True)
    return tmp_path


def _parked_question(conn, to: str = "architect") -> str:
    tid = post_message(conn, BOARD, SCOPE, "planner", type="task", text=TASK_TEXT)
    run_id = f"sched-{tid}#1"
    assert claim_task(conn, tid, run_id)
    qid = post_message(
        conn,
        BOARD,
        SCOPE,
        "builder",
        to_agent=to,
        type="question",
        text=QUESTION_TEXT,
        author_role="builder",
        author_run_id=run_id,
        author_source="token",
    )
    decision = cr.route_decision(conn, qid)
    assert decision.kind == "route", decision
    assert cr.record_route(conn, decision, qid)
    assert park_task(conn, tid, [qid])
    return qid


class HostSpawn:
    """A spawn_fn that runs the consult's real spawn path with a broadcast acting as the spawn
    host: it records the TERMINAL_SPAWN payload and the run token's row, optionally writes the
    agent's own AGENT_DONE, then reports the PTY start and its billed result."""

    def __init__(self, project: Path, write_agent_done: bool):
        self.project = project
        self.write_agent_done = write_agent_done
        self.spawns: list[dict] = []
        self.tokens: list[dict | None] = []

    def __call__(self, **kwargs) -> dict:
        def host(_topic, payload):
            if payload.get("type") != "TERMINAL_SPAWN":
                return
            self.spawns.append(payload)
            self.tokens.append(lookup_run_token(get_db(), payload.get("run_token")))
            run_id = payload["run_id"]
            if self.write_agent_done:
                from pathly_orchestrator.eventlog import append_event

                append_event(
                    str(self.project / "pathly" / "features" / SCOPE),
                    {
                        "type": "AGENT_DONE",
                        "agent": kwargs["agent"],
                        "run_id": run_id,
                        "category": "consult",
                        "outcome": "success",
                        "summary": "ANSWER: Stream the rows.",
                        "cost_usd": 0.0,
                    },
                )
            run = get_run(run_id)
            assert run is not None
            run.mark_started()
            run.mark_pty_result(
                {
                    "result": {"cost_usd": COST, "tokens_in": 1200, "tokens_out": 300},
                    "exit_code": 0,
                }
            )

        kwargs["broadcast_fn"] = host
        return consult_run._default_spawn(**kwargs)


def _start(qid: str, project: Path, spawn: HostSpawn) -> dict:
    return consult_run.start_consult(
        qid, project_root=str(project), broadcast_fn=None, spawn_fn=spawn, block=True
    )


def _invocations(run_id: str) -> list[dict]:
    rows = (
        get_db()
        .execute(
            "SELECT agent_role, category, cost_usd FROM agent_invocations WHERE run_id=?",
            (run_id,),
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


@pytest.mark.parametrize(
    "write_agent_done", [True, False], ids=["agent-done", "no-agent-done"]
)
def test_a_consult_is_spawned_billed_and_categorised_as_consult(
    project, write_agent_done
):
    conn = get_db()
    qid = _parked_question(conn)
    spawn = HostSpawn(project, write_agent_done)

    result = _start(qid, project, spawn)

    run_id = result["run_id"]
    assert run_id.startswith("consult-")
    assert len(spawn.spawns) == 1
    assert spawn.spawns[0]["category"] == "consult"
    rows = _invocations(run_id)
    assert len(rows) == 1, rows
    assert rows[0]["category"] == "consult"
    assert rows[0]["cost_usd"] == pytest.approx(COST)
    if write_agent_done:
        assert result["status"] == "answered"


def test_the_consults_run_token_names_the_asked_role(project):
    conn = get_db()
    qid = _parked_question(conn, to="tester")
    spawn = HostSpawn(project, write_agent_done=True)

    result = _start(qid, project, spawn)

    token = spawn.tokens[0]
    assert token is not None
    assert token["run_id"] == result["run_id"]
    assert token["role"] == "tester"


@pytest.mark.parametrize(
    "flow, category",
    [("consult", "consult"), ("board-run", "single"), ("team-build", "flow")],
)
def test_spawn_category(flow, category):
    from pathly_orchestrator.fsm_compose_vars import spawn_category

    assert spawn_category(flow) == category
