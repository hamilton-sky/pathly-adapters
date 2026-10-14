"""A DAG task's prompt carries what the tasks it depends on produced (build-proof 11).

``supervisor/task_prompt.build_task_prompt`` handed a task agent its own text and nothing from
the tasks it depends on, so a dependent task redid or guessed at work an earlier task had
already reported. The result is the newest ``AGENT_DONE`` ``summary`` of the dependency's
``sched-<id>#<n>`` runs, read by ``db/queries/task_results.latest_task_summaries``: no
migration and no new write path.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.supervisor.task_prompt import build_task_prompt

HEADING = "## Results of the tasks this one depends on"
SCOPE = "dep-results-feature"


class _State:
    """The attributes ``build_task_prompt`` reads from a RunnerState."""

    project_root = ""
    storage_path = ""
    topic = SCOPE
    goal_id = ""


@pytest.fixture
def conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def _task(conn, text: str, depends_on: list[str] | None = None) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="builder",
        type="task",
        text=text,
        depends_on=depends_on,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


def _done(conn, task_id: str, attempt: int, summary: str | None) -> None:
    """Append the AGENT_DONE a task agent writes (its run id is sched-<id>#<attempt>)."""
    from pathly_orchestrator.db.queries.fsm_events import append_event

    event = {
        "type": "AGENT_DONE",
        "ts": "2026-01-01T00:00:00Z",
        "run_id": f"sched-{task_id}#{attempt}",
        "outcome": "success",
    }
    if summary is not None:
        event["summary"] = summary
    append_event(conn, "/tmp/dep-results-project", SCOPE, event)


def _prompt(conn, task_id: str) -> str:
    row = dict(
        conn.execute("SELECT * FROM comms_messages WHERE id=?", (task_id,)).fetchone()
    )
    return build_task_prompt(
        row, _State(), "feature", SCOPE, adapter="claude", task_id=task_id
    )


def _block(prompt: str) -> str:
    """The dependency-results block: from its heading to the runner contract after it."""
    from pathly_orchestrator.fsm_compose import RUNNER_CONTRACT_BLOCK

    start = prompt.index(HEADING)
    return prompt[start : prompt.index(RUNNER_CONTRACT_BLOCK, start)].rstrip()


def test_a_dependent_prompt_carries_its_dependencys_summary(conn):
    a = _task(conn, "Build the parser module\nwith tokens")
    b = _task(conn, "Wire the parser into the CLI", depends_on=[a])
    _done(conn, a, 1, "A-RESULT-MARKER")

    prompt = _prompt(conn, b)

    assert HEADING in prompt
    block = _block(prompt)
    assert "### Build the parser module" in block
    assert "with tokens" not in block, "the heading is the first text line only"
    assert "A-RESULT-MARKER" in block


def test_the_block_sits_after_the_task_and_before_the_runner_contract(conn):
    from pathly_orchestrator.fsm_compose import RUNNER_CONTRACT_BLOCK

    a = _task(conn, "Build A")
    b = _task(conn, "Build B on top of A", depends_on=[a])
    _done(conn, a, 1, "A-RESULT-MARKER")

    prompt = _prompt(conn, b)

    assert (
        prompt.index("Build B on top of A")
        < prompt.index(HEADING)
        < prompt.index(RUNNER_CONTRACT_BLOCK)
    )


def test_a_later_attempts_summary_wins(conn):
    a = _task(conn, "Build A")
    b = _task(conn, "Build B", depends_on=[a])
    _done(conn, a, 1, "FIRST-ATTEMPT-SUMMARY")
    _done(conn, a, 2, "A-RESULT-MARKER")

    block = _block(_prompt(conn, b))

    assert "A-RESULT-MARKER" in block
    assert "FIRST-ATTEMPT-SUMMARY" not in block


def test_a_task_without_dependencies_has_no_block(conn):
    a = _task(conn, "Build A")
    _done(conn, a, 1, "A-RESULT-MARKER")

    assert HEADING not in _prompt(conn, a)


def test_an_empty_dependency_list_has_no_block(conn):
    a = _task(conn, "Build A", depends_on=[])

    assert HEADING not in _prompt(conn, a)


def test_a_dependency_with_no_event_shows_no_result_recorded(conn):
    a = _task(conn, "Build A")
    b = _task(conn, "Build B", depends_on=[a])

    block = _block(_prompt(conn, b))

    assert "### Build A" in block
    assert "(no result recorded)" in block


def test_a_dependency_whose_event_has_no_summary_shows_no_result_recorded(conn):
    a = _task(conn, "Build A")
    b = _task(conn, "Build B", depends_on=[a])
    _done(conn, a, 1, None)

    assert "(no result recorded)" in _block(_prompt(conn, b))


def test_only_direct_dependencies_are_listed(conn):
    a = _task(conn, "Build A")
    b = _task(conn, "Build B", depends_on=[a])
    c = _task(conn, "Build C", depends_on=[b])
    _done(conn, a, 1, "A-RESULT-MARKER")
    _done(conn, b, 1, "B-RESULT-MARKER")

    block = _block(_prompt(conn, c))

    assert "B-RESULT-MARKER" in block
    assert "A-RESULT-MARKER" not in block
    assert "### Build A" not in block


def test_each_dependency_gets_its_own_heading_in_depends_on_order(conn):
    a = _task(conn, "Build A")
    b = _task(conn, "Build B")
    c = _task(conn, "Build C", depends_on=[b, a])
    _done(conn, a, 1, "A-RESULT-MARKER")
    _done(conn, b, 1, "B-RESULT-MARKER")

    block = _block(_prompt(conn, c))

    assert block.count("\n### ") == 2
    assert block.index("### Build B") < block.index("B-RESULT-MARKER")
    assert block.index("B-RESULT-MARKER") < block.index("### Build A")
    assert block.index("### Build A") < block.index("A-RESULT-MARKER")


def test_a_summary_is_clipped_to_2000_characters(conn):
    a = _task(conn, "Build A")
    b = _task(conn, "Build B", depends_on=[a])
    _done(conn, a, 1, "x" * 5000)

    block = _block(_prompt(conn, b))

    assert 1900 <= block.count("x") <= 2000
    assert "x" * 2001 not in block


def test_the_whole_block_is_clipped_to_8000_characters(conn):
    deps = []
    for n in range(8):
        dep = _task(conn, f"Build dependency {n}")
        _done(conn, dep, 1, f"{n}" * 2000)
        deps.append(dep)
    b = _task(conn, "Build B", depends_on=deps)

    block = _block(_prompt(conn, b))

    assert len(block) <= 8000
    assert len(block) > 7000, "eight 2000-character summaries fill the block"


def test_an_unreadable_depends_on_leaves_the_prompt_without_a_block(conn):
    a = _task(conn, "Build A")
    conn.execute("UPDATE comms_messages SET depends_on='not json' WHERE id=?", (a,))
    conn.commit()

    assert HEADING not in _prompt(conn, a)


# ── latest_task_summaries ────────────────────────────────────────────────────


def test_latest_task_summaries_returns_the_newest_summary_per_id(conn):
    from pathly_orchestrator.db.queries.task_results import latest_task_summaries

    a = _task(conn, "Build A")
    b = _task(conn, "Build B")
    c = _task(conn, "Build C")
    _done(conn, a, 1, "A-OLD")
    _done(conn, a, 2, "A-NEW")
    _done(conn, b, 1, "B-ONLY")

    assert latest_task_summaries(conn, [a, b, c]) == {a: "A-NEW", b: "B-ONLY"}


def test_latest_task_summaries_reads_only_agent_done_events(conn):
    from pathly_orchestrator.db.queries.fsm_events import append_event
    from pathly_orchestrator.db.queries.task_results import latest_task_summaries

    a = _task(conn, "Build A")
    _done(conn, a, 1, "A-RESULT-MARKER")
    append_event(
        conn,
        "/tmp/dep-results-project",
        SCOPE,
        {
            "type": "BILLING_UPDATE",
            "ts": "2026-01-01T00:00:01Z",
            "run_id": f"sched-{a}#1",
            "summary": "NOT-AN-AGENT-DONE",
        },
    )

    assert latest_task_summaries(conn, [a]) == {a: "A-RESULT-MARKER"}


def test_latest_task_summaries_ignores_other_runs(conn):
    from pathly_orchestrator.db.queries.fsm_events import append_event
    from pathly_orchestrator.db.queries.task_results import latest_task_summaries

    a = _task(conn, "Build A")
    append_event(
        conn,
        "/tmp/dep-results-project",
        SCOPE,
        {
            "type": "AGENT_DONE",
            "ts": "2026-01-01T00:00:00Z",
            "run_id": f"{SCOPE}-1-20260101",
            "summary": "A-STAGE-RUN",
        },
    )

    assert latest_task_summaries(conn, [a]) == {}


def test_latest_task_summaries_of_nothing_is_empty(conn):
    from pathly_orchestrator.db.queries.task_results import latest_task_summaries

    assert latest_task_summaries(conn, []) == {}


# ── the skill asks for a summary a dependent can use ─────────────────────────


def test_execute_task_asks_for_a_summary_that_dependents_read():
    from pathly_orchestrator.skills.compose import compose_skill

    text = compose_skill("development/execute-task", "claude")

    assert "what was built" in text
    assert "which files changed" in text
    assert "shortcut" in text
    assert "later task" in text
    assert "dependent tasks read" in text
