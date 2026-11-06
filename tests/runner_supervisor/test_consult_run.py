"""chief-autopilot-round-two 02: a consult run answers a routed question and its answer is posted.

``supervisor/consult_run.start_consult`` spawns one headless agent of the question's role
(``consult-<hex>`` run, ``planning/consult-answer`` skill), reads the summary of its own
``AGENT_DONE`` and delivers it: ``ANSWER: <text>`` becomes an ``answer`` row (which frees a task
parked on the question), ``DECISION:`` from architect, po or designer a non-binding ``decision``
row, ``ANSWER: USER <why>`` hands the question to the person, and anything else (no ``ANSWER:``
line, a spawn that raised) hands it to the person with the route ``failed``. The consult runs on
the asking run's adapter (when it has a headless mode), else on claude.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries import consult_routes as cr
from pathly_orchestrator.db.queries.app_settings import set_agent_model
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.db.queries.task_waits import park_task
from pathly_orchestrator.supervisor import consult_run

BOARD, SCOPE = "feature", "feat-consult-run"
TASK_TEXT = "Build the export button. Files: export.py. Done when: it exports."
QUESTION_TEXT = "Should the export stream rows or buffer the whole file?"


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def conn():
    return get_db()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "pathly" / "features" / SCOPE).mkdir(parents=True)
    return tmp_path


def _storage(project: Path) -> Path:
    return project / "pathly" / "features" / SCOPE


def _parked_question(conn, *, to: str = "architect", park: bool = True):
    """A task claimed by its loop run, a question from that run to ``to``, routed, the task
    parked on it. Returns ``(task_id, question_id)``."""
    tid = post_message(conn, BOARD, SCOPE, "planner", type="task", text=TASK_TEXT)
    run_id = f"sched-{tid}#1"
    assert claim_task(conn, tid, run_id)
    qid = _question(conn, run_id, to=to)
    if park:
        assert park_task(conn, tid, [qid])
    return tid, qid


def _question(conn, run_id: str, *, to: str = "architect") -> str:
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
    return qid


class FakeSpawn:
    """A spawn_fn that records its call and writes the consult's own AGENT_DONE."""

    def __init__(self, project: Path, summary: str | None = None, error=None):
        self.project = project
        self.summary = summary
        self.error = error
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.summary is not None:
            from pathly_orchestrator.eventlog import append_event

            append_event(
                str(_storage(self.project)),
                {
                    "type": "AGENT_DONE",
                    "agent": kwargs["agent"],
                    "run_id": kwargs["run_id"],
                    "outcome": "success",
                    "error": "",
                    "summary": self.summary,
                },
            )
        return {"exit_code": 0}


def _start(qid: str, project: Path, spawn: FakeSpawn) -> dict:
    return consult_run.start_consult(
        qid,
        project_root=str(project),
        broadcast_fn=None,
        spawn_fn=spawn,
        block=True,
    )


def _replies(conn, qid: str, type_: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM comms_messages WHERE reply_to=? AND type=? AND deleted_at IS NULL",
        (qid, type_),
    ).fetchall()
    return [dict(r) for r in rows]


def _row(conn, mid: str) -> dict:
    return dict(
        conn.execute("SELECT * FROM comms_messages WHERE id=?", (mid,)).fetchone()
    )


def _route(conn, qid: str) -> dict:
    return cr.routes_for_questions(conn, [qid])[0]


# ── delivery ─────────────────────────────────────────────────────────────────


def test_an_answer_is_posted_and_frees_the_parked_task(conn, project):
    tid, qid = _parked_question(conn)
    spawn = FakeSpawn(
        project, "ANSWER: Stream the rows; buffering breaks on big exports."
    )

    result = _start(qid, project, spawn)

    run_id = spawn.calls[0]["run_id"]
    assert run_id.startswith("consult-") and len(run_id) == len("consult-") + 12
    assert result["run_id"] == run_id
    answers = _replies(conn, qid, "answer")
    assert len(answers) == 1
    answer = answers[0]
    assert answer["from_agent"] == "architect"
    assert answer["to_agent"] == "builder"
    assert answer["text"] == "Stream the rows; buffering breaks on big exports."
    assert answer["author_role"] == "architect"
    assert answer["author_run_id"] == run_id
    assert answer["author_source"] == "token"
    assert _row(conn, tid)["task_status"] == "pending"
    route = _route(conn, qid)
    assert route["status"] == "answered"
    assert route["consult_run_id"] == run_id
    assert route["ended_at"] is not None
    assert _replies(conn, qid, "decision") == []


def test_a_decision_line_from_the_architect_adds_a_non_binding_decision(conn, project):
    _, qid = _parked_question(conn)
    spawn = FakeSpawn(
        project,
        "ANSWER: Stream the rows.\nDECISION: stream rows — exports can be larger than memory",
    )

    _start(qid, project, spawn)

    run_id = spawn.calls[0]["run_id"]
    answers = _replies(conn, qid, "answer")
    assert [a["text"] for a in answers] == ["Stream the rows."]
    decisions = _replies(conn, qid, "decision")
    assert len(decisions) == 1
    d = decisions[0]
    assert d["text"] == "stream rows — exports can be larger than memory"
    assert d["binding"] == 0
    assert d["from_agent"] == "architect"
    assert d["author_role"] == "architect"
    assert d["author_run_id"] == run_id
    assert d["author_source"] == "token"


def test_a_decision_line_from_a_tester_adds_none(conn, project):
    _, qid = _parked_question(conn, to="tester")
    spawn = FakeSpawn(
        project, "ANSWER: Test it with 10k rows.\nDECISION: big fixture — why"
    )

    _start(qid, project, spawn)

    assert len(_replies(conn, qid, "answer")) == 1
    assert _replies(conn, qid, "decision") == []
    assert _route(conn, qid)["status"] == "answered"


def test_answer_user_hands_the_question_to_the_person(conn, project):
    tid, qid = _parked_question(conn)
    spawn = FakeSpawn(project, "ANSWER: USER only the person knows the export budget")

    _start(qid, project, spawn)

    assert _replies(conn, qid, "answer") == []
    assert _row(conn, qid)["to_agent"] == "human"
    statuses = _replies(conn, qid, "status")
    assert len(statuses) == 1
    assert "only the person knows the export budget" in statuses[0]["text"]
    assert _route(conn, qid)["status"] == "to_person"
    assert _row(conn, tid)["task_status"] == "blocked"


def test_answer_user_without_a_reason_says_so(conn, project):
    _, qid = _parked_question(conn)

    _start(qid, project, FakeSpawn(project, "ANSWER: USER"))

    assert _replies(conn, qid, "answer") == []
    assert "no reason given" in _replies(conn, qid, "status")[0]["text"]


@pytest.mark.parametrize(
    "spawn_kwargs",
    [
        {"summary": "I looked at the code and it is fine."},
        {"summary": None},
        {"error": RuntimeError("terminal_spawn_timeout: no PTY")},
    ],
    ids=["no-answer-line", "no-agent-done", "spawn-raised"],
)
def test_no_answer_hands_the_question_to_the_person_and_fails_the_route(
    conn, project, spawn_kwargs
):
    tid, qid = _parked_question(conn)

    _start(qid, project, FakeSpawn(project, **spawn_kwargs))

    assert _replies(conn, qid, "answer") == []
    assert _row(conn, qid)["to_agent"] == "human"
    statuses = _replies(conn, qid, "status")
    assert len(statuses) == 1
    assert "the architect consult did not answer" in statuses[0]["text"]
    route = _route(conn, qid)
    assert route["status"] == "failed"
    assert route["consult_run_id"].startswith("consult-")
    assert _row(conn, tid)["task_status"] == "blocked"


# ── the prompt ───────────────────────────────────────────────────────────────


def test_the_prompt_holds_the_question_the_task_and_the_feedback_folder(conn, project):
    _, qid = _parked_question(conn)
    spawn = FakeSpawn(project, "ANSWER: yes")

    _start(qid, project, spawn)

    call = spawn.calls[0]
    prompt = call["prompt"]
    assert QUESTION_TEXT in prompt
    assert qid in prompt
    assert TASK_TEXT in prompt
    assert str(_storage(project) / "feedback") in prompt
    assert "<run_category>" not in prompt
    assert "ANSWER: USER" in prompt  # the consult-answer skill body
    assert not prompt.lstrip().startswith("---")
    assert call["agent"] == "architect"
    assert call["scope"] == SCOPE and call["board"] == BOARD


# ── engine and model ─────────────────────────────────────────────────────────


def _asking_run(conn, run_id: str, adapter: str) -> None:
    conn.execute(
        "INSERT INTO run_history (project_root, feature, run_id, status, adapter) "
        "VALUES (?, ?, ?, 'running', ?)",
        ("/tmp/p", SCOPE, run_id, adapter),
    )
    conn.commit()


def _question_from_run(conn, run_id: str, adapter: str | None) -> str:
    if adapter is not None:
        _asking_run(conn, run_id, adapter)
    return _question(conn, run_id)


def test_a_codex_asking_run_spawns_the_consult_on_codex_with_the_roles_model(
    conn, project
):
    set_agent_model(conn, "architect", "codex", "gpt-5-codex")
    qid = _question_from_run(conn, "goal-a-single", "codex")
    spawn = FakeSpawn(project, "ANSWER: yes")

    _start(qid, project, spawn)

    assert spawn.calls[0]["adapter"] == "codex"
    assert spawn.calls[0]["model"] == "gpt-5-codex"


def test_a_codex_asking_run_with_no_configured_model_uses_the_engine_default(
    conn, project
):
    qid = _question_from_run(conn, "goal-b-single", "codex")
    spawn = FakeSpawn(project, "ANSWER: yes")

    _start(qid, project, spawn)

    assert spawn.calls[0]["adapter"] == "codex"
    assert spawn.calls[0]["model"] == ""


@pytest.mark.parametrize("adapter", [None, "copilot"], ids=["no-row", "no-headless"])
def test_otherwise_the_consult_runs_on_claude_sonnet(conn, project, adapter):
    qid = _question_from_run(conn, "goal-c-single", adapter)
    spawn = FakeSpawn(project, "ANSWER: yes")

    _start(qid, project, spawn)

    assert spawn.calls[0]["adapter"] == "claude"
    assert spawn.calls[0]["model"] == "claude-sonnet-4-6"
