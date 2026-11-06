"""chief-autopilot-round-two 03: the answer of a consult that changed the project is withheld.

A consult may write only under its board's ``feedback/`` folder and post board rows. The
supervisor does not trust that: ``supervisor/consult_window`` snapshots the git working tree and
``HEAD`` before and after the consult's spawn and blames each change that is not under the
feedback folder, not Pathly's own ``pathly/`` storage, and not inside the declared ``files`` of a
task ``in_progress`` at the window's start or posted before it and claimed during it by another
run. The window closes only once the consult's process exited. A blamed consult gets no answer
row: its route
is ``withheld``, its question goes to the person, and one escalation lists what changed. When git
cannot measure (not a repo top), the answer is delivered with an "answer not measured" status.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries import consult_routes as cr
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.db.queries.task_waits import park_task
from pathly_orchestrator.supervisor import consult_run, consult_window

BOARD, SCOPE = "feature", "feat-consult-read-only"
TASK_TEXT = "Build the export button. Files: export.py. Done when: it exports."
QUESTION_TEXT = "Should the export stream rows or buffer the whole file?"
ANSWER = "ANSWER: Stream the rows."


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def conn():
    return get_db()


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def plain(tmp_path: Path) -> Path:
    """A project that is not a git repository."""
    root = tmp_path / "plain"
    (root / "pathly" / "features" / SCOPE).mkdir(parents=True)
    return root


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A git-initialised project with a tracked ``app.py`` and one commit."""
    root = tmp_path / "repo"
    (root / "pathly" / "features" / SCOPE).mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _write(root, "app.py", "def add(a, b):\n    return a + b\n")
    _git(root, "add", "app.py")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _storage(project: Path) -> Path:
    return project / "pathly" / "features" / SCOPE


def _parked_question(conn, *, to: str = "architect"):
    """A task claimed by its loop run, a question from that run to ``to``, routed, the task
    parked on it. Returns ``(task_id, question_id)``."""
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
    return tid, qid


def _in_progress_task(
    conn, files: list[str], *, board: str = BOARD, scope: str = SCOPE
) -> str:
    tid = post_message(
        conn, board, scope, "planner", type="task", text="Other work.", files=files
    )
    assert claim_task(conn, tid, f"sched-{tid}#1")
    return tid


class EditingSpawn:
    """A spawn_fn that runs ``edit(project)`` (the consult's side effects), then writes the
    consult's own AGENT_DONE."""

    def __init__(self, project: Path, edit=None, summary: str | None = ANSWER):
        self.project = project
        self.edit = edit
        self.summary = summary
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.edit is not None:
            self.edit(self.project)
        if self.summary is None:  # the consult crashed after its edits
            raise RuntimeError("the consult crashed")
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


def _start(qid: str, project: Path, spawn) -> dict:
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


def _edit_app(project: Path) -> None:
    _write(project, "app.py", "def add(a, b):\n    return b + a\n")


def _assert_delivered(conn, qid: str, tid: str) -> None:
    assert [a["text"] for a in _replies(conn, qid, "answer")] == ["Stream the rows."]
    assert _route(conn, qid)["status"] == "answered"
    assert _replies(conn, qid, "escalation") == []
    assert _row(conn, tid)["task_status"] == "pending"


# ── withheld ─────────────────────────────────────────────────────────────────


def test_a_consult_that_edits_a_tracked_file_is_withheld(conn, repo):
    tid, qid = _parked_question(conn)

    result = _start(qid, repo, EditingSpawn(repo, _edit_app))

    assert result["status"] == "withheld"
    assert _replies(conn, qid, "answer") == []
    assert _replies(conn, qid, "decision") == []
    route = _route(conn, qid)
    assert route["status"] == "withheld"
    assert "app.py" in route["reason"]
    assert _row(conn, qid)["to_agent"] == "human"
    escalations = _replies(conn, qid, "escalation")
    assert len(escalations) == 1
    esc = escalations[0]
    assert esc["to_agent"] == "human"
    assert "M app.py" in esc["text"]
    assert "nothing was reverted" in esc["text"]
    assert esc["author_source"] == "system"
    assert esc["author_run_id"] is None
    statuses = _replies(conn, qid, "status")
    assert any(
        "the architect consult changed the project" in s["text"] for s in statuses
    )
    assert _row(conn, tid)["task_status"] == "blocked"


def test_a_decision_line_of_a_withheld_consult_is_not_posted(conn, repo):
    _, qid = _parked_question(conn)
    spawn = EditingSpawn(repo, _edit_app, summary=f"{ANSWER}\nDECISION: stream — why")

    _start(qid, repo, spawn)

    assert _replies(conn, qid, "answer") == []
    assert _replies(conn, qid, "decision") == []
    assert _route(conn, qid)["status"] == "withheld"


def test_a_consult_that_commits_is_withheld_with_head_moved(conn, repo):
    tid, qid = _parked_question(conn)
    notes = _storage(repo).relative_to(repo) / "feedback" / "NOTES.md"

    def commit_notes(project: Path) -> None:
        _write(project, str(notes), "notes\n")
        _git(project, "add", str(notes))
        _git(project, "commit", "-q", "-m", "consult notes")

    _start(qid, repo, EditingSpawn(repo, commit_notes))

    assert _replies(conn, qid, "answer") == []
    route = _route(conn, qid)
    assert route["status"] == "withheld"
    assert "HEAD moved" in route["reason"]
    escalations = _replies(conn, qid, "escalation")
    assert len(escalations) == 1
    assert "HEAD moved from" in escalations[0]["text"]
    assert _row(conn, tid)["task_status"] == "blocked"


def test_the_escalation_lists_at_most_twenty_findings(conn, repo):
    _, qid = _parked_question(conn)

    def many(project: Path) -> None:
        for i in range(25):
            _write(project, f"junk/f{i:02d}.txt", "x\n")

    _start(qid, repo, EditingSpawn(repo, many))

    text = _replies(conn, qid, "escalation")[0]["text"]
    assert text.count("- A junk/") == 20
    assert "- ... and 5 more" in text


@pytest.mark.parametrize(
    "summary", ["I changed app.py instead.", None], ids=["no-answer-line", "raised"]
)
def test_a_consult_that_edits_and_then_fails_is_still_withheld(conn, repo, summary):
    tid, qid = _parked_question(conn)

    result = _start(qid, repo, EditingSpawn(repo, _edit_app, summary=summary))

    assert result["status"] == "withheld"
    assert _replies(conn, qid, "answer") == []
    assert _route(conn, qid)["status"] == "withheld"
    assert _row(conn, qid)["to_agent"] == "human"
    escalations = _replies(conn, qid, "escalation")
    assert len(escalations) == 1
    assert "M app.py" in escalations[0]["text"]
    assert _row(conn, tid)["task_status"] == "blocked"


@pytest.mark.parametrize("board", ["feature", "project"])
def test_another_projects_in_progress_files_do_not_exempt_a_change(
    conn, repo, tmp_path, board
):
    """A task on another project's board declaring ``app.py`` does not exempt this
    project's ``app.py``: only the project board and its own feature boards count."""
    _, qid = _parked_question(conn)
    other = tmp_path / "other"
    (other / "pathly" / "features" / "feat-elsewhere").mkdir(parents=True)
    scope = "feat-elsewhere" if board == "feature" else str(other)
    _in_progress_task(conn, ["app.py"], board=board, scope=scope)

    _start(qid, repo, EditingSpawn(repo, _edit_app))

    route = _route(conn, qid)
    assert route["status"] == "withheld"
    assert "app.py" in route["reason"]


@pytest.mark.parametrize("scope", ["../..", "project"])
def test_a_feature_scope_that_is_not_a_plain_folder_name_exempts_nothing(
    conn, repo, scope
):
    """``pathly/features/../..`` names the project root itself, and ``project`` is reserved:
    neither is a feature board of this project."""
    (repo / "pathly" / "features" / "project").mkdir()
    _, qid = _parked_question(conn)
    _in_progress_task(conn, ["app.py"], board="feature", scope=scope)

    _start(qid, repo, EditingSpawn(repo, _edit_app))

    assert _route(conn, qid)["status"] == "withheld"


def test_an_in_progress_task_on_the_project_board_exempts_its_files(conn, repo):
    tid, qid = _parked_question(conn)
    _in_progress_task(conn, ["app.py"], board="project", scope=str(repo))

    _start(qid, repo, EditingSpawn(repo, _edit_app))

    _assert_delivered(conn, qid, tid)


# ── delivered ────────────────────────────────────────────────────────────────


def test_a_consult_that_writes_only_its_feedback_folder_is_delivered(conn, repo):
    """The feedback folder sits under ``pathly/``, so this covers both the feedback rule
    and the own-storage rule (``_is_own_storage``): either one alone lets it through."""
    tid, qid = _parked_question(conn)
    notes = _storage(repo).relative_to(repo) / "feedback" / "NOTES.md"

    _start(qid, repo, EditingSpawn(repo, lambda p: _write(p, str(notes), "notes\n")))

    _assert_delivered(conn, qid, tid)
    assert not any("not measured" in s["text"] for s in _replies(conn, qid, "status"))


def test_a_consult_that_changes_nothing_is_delivered(conn, repo):
    tid, qid = _parked_question(conn)

    _start(qid, repo, EditingSpawn(repo))

    _assert_delivered(conn, qid, tid)


@pytest.mark.parametrize("when", ["at-start", "during-the-window"])
def test_a_change_inside_an_in_progress_tasks_files_is_left_out(conn, repo, when):
    tid, qid = _parked_question(conn)
    if when == "at-start":
        _in_progress_task(conn, ["app.py"])
    else:  # posted before the window, claimed during it by another run
        pending = post_message(
            conn, BOARD, SCOPE, "planner", type="task", text="Junk.", files=["junk/"]
        )

    def builder_edits(project: Path) -> None:
        if when == "at-start":
            _edit_app(project)
        else:  # a builder claims the task declaring a folder and writes inside it
            assert claim_task(get_db(), pending, f"sched-{pending}#1")
            _write(project, "junk/new.py", "x = 1\n")

    _start(qid, repo, EditingSpawn(repo, builder_edits))

    _assert_delivered(conn, qid, tid)


@pytest.mark.parametrize("claimer", ["the-consult", "another-run"])
def test_a_consult_cannot_exempt_its_own_edit_with_a_task_it_posts(conn, repo, claimer):
    """A task posted during the window (by the consult) and claimed, whoever the claim names,
    does not exempt its files: the consult could post and claim one itself."""
    tid, qid = _parked_question(conn)
    spawn = EditingSpawn(repo)

    def post_claim_and_edit(project: Path) -> None:
        db = get_db()
        own = post_message(
            db, BOARD, SCOPE, "architect", type="task", text="Mine.", files=["app.py"]
        )
        run_id = spawn.calls[-1]["run_id"] if claimer == "the-consult" else "sched-x#1"
        assert claim_task(db, own, run_id)
        _edit_app(project)

    spawn.edit = post_claim_and_edit
    _start(qid, repo, spawn)

    assert _replies(conn, qid, "answer") == []
    route = _route(conn, qid)
    assert route["status"] == "withheld"
    assert "app.py" in route["reason"]
    assert _row(conn, tid)["task_status"] == "blocked"


def test_a_pending_task_the_consult_claims_does_not_exempt_its_files(conn, repo):
    """A task posted before the window but claimed during it by the consult itself."""
    tid, qid = _parked_question(conn)
    pending = post_message(
        conn, BOARD, SCOPE, "planner", type="task", text="Old.", files=["app.py"]
    )
    spawn = EditingSpawn(repo)

    def claim_and_edit(project: Path) -> None:
        assert claim_task(get_db(), pending, spawn.calls[-1]["run_id"])
        _edit_app(project)

    spawn.edit = claim_and_edit
    _start(qid, repo, spawn)

    assert _route(conn, qid)["status"] == "withheld"


def test_a_change_outside_the_in_progress_files_is_still_blamed(conn, repo):
    _, qid = _parked_question(conn)
    _in_progress_task(conn, ["other.py"])

    _start(qid, repo, EditingSpawn(repo, _edit_app))

    assert _route(conn, qid)["status"] == "withheld"


def test_outside_a_git_repo_the_answer_is_delivered_unmeasured(conn, plain):
    tid, qid = _parked_question(conn)

    _start(qid, plain, EditingSpawn(plain, _edit_app))

    _assert_delivered(conn, qid, tid)
    statuses = [s for s in _replies(conn, qid, "status") if "not measured" in s["text"]]
    assert len(statuses) == 1
    assert statuses[0]["text"] == (
        f"answer not measured: {plain} is not a git repository top"
    )
    assert statuses[0]["author_source"] == "system"


def test_when_git_fails_inside_a_repo_the_status_says_so(conn, repo, monkeypatch):
    tid, qid = _parked_question(conn)
    monkeypatch.setattr(consult_window.tree, "snapshot", lambda root: None)

    _start(qid, repo, EditingSpawn(repo, _edit_app))

    _assert_delivered(conn, qid, tid)
    statuses = [s for s in _replies(conn, qid, "status") if "not measured" in s["text"]]
    assert [s["text"] for s in statuses] == [
        f"answer not measured: git could not snapshot {repo}"
    ]


def test_blamed_without_a_window_cannot_measure():
    assert consult_window.blamed(None) is None


def test_open_window_outside_a_repo_is_none(plain):
    assert consult_window.open_window(str(plain)) is None


# ── measured only once the consult's process stopped ────────────────────────


class EarlyAdvanceTerminal:
    """Stands in for ``terminal._run_stage_via_terminal`` with early advance on: it writes the
    consult's AGENT_DONE and returns while the PTY still runs. ``after`` runs on a thread once it
    returned (the consult keeps working), then the PTY reports its exit, unless ``exits`` is
    False (the process is never confirmed stopped)."""

    def __init__(self, project: Path, after=None, *, exits: bool = True):
        self.project = project
        self.after = after
        self.exits = exits
        self.threads: list = []

    def __call__(self, state, prompt, adapter, model, run_id, broadcast_fn) -> dict:
        import threading
        import time

        from pathly_orchestrator.eventlog import append_event
        from pathly_orchestrator.supervisor.registry import create_run, drop_run

        run = create_run(run_id)
        append_event(
            str(_storage(self.project)),
            {
                "type": "AGENT_DONE",
                "agent": state.current_state,
                "run_id": run_id,
                "outcome": "success",
                "error": "",
                "summary": ANSWER,
            },
        )

        def still_running() -> None:
            time.sleep(0.3)
            if self.after is not None:
                self.after(self.project)
            if self.exits:
                run.mark_pty_result({"exit_code": 0, "result": {}})
                drop_run(run_id)

        t = threading.Thread(target=still_running, daemon=True)
        t.start()
        self.threads.append(t)
        return {"result": ANSWER}


def _start_default(qid: str, project: Path, terminal, monkeypatch) -> dict:
    from pathly_orchestrator.supervisor import terminal as terminal_mod

    monkeypatch.setattr(terminal_mod, "_run_stage_via_terminal", terminal)
    try:
        return _start(qid, project, None)
    finally:
        for t in terminal.threads:
            t.join(timeout=5)


def test_an_edit_after_an_early_agent_done_is_still_withheld(conn, repo, monkeypatch):
    tid, qid = _parked_question(conn)

    result = _start_default(
        qid, repo, EarlyAdvanceTerminal(repo, _edit_app), monkeypatch
    )

    assert result["status"] == "withheld"
    assert _replies(conn, qid, "answer") == []
    assert "M app.py" in _replies(conn, qid, "escalation")[0]["text"]
    assert _row(conn, tid)["task_status"] == "blocked"


def test_a_consult_that_stops_cleanly_after_an_early_agent_done_is_delivered(
    conn, repo, monkeypatch
):
    tid, qid = _parked_question(conn)

    _start_default(qid, repo, EarlyAdvanceTerminal(repo), monkeypatch)

    _assert_delivered(conn, qid, tid)


def test_a_consult_whose_exit_is_not_confirmed_is_not_delivered(
    conn, repo, monkeypatch
):
    tid, qid = _parked_question(conn)
    monkeypatch.setattr(consult_window, "EXIT_WAIT", 0.5)

    result = _start_default(
        qid, repo, EarlyAdvanceTerminal(repo, exits=False), monkeypatch
    )

    assert result["status"] == "failed"
    assert _replies(conn, qid, "answer") == []
    route = _route(conn, qid)
    assert "not confirmed stopped" in route["reason"]
    assert _row(conn, qid)["to_agent"] == "human"
    assert _row(conn, tid)["task_status"] == "blocked"
