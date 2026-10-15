"""A reviewer stage opens a fresh CLI session instead of resuming the builder's.

A resumed claude session restores the whole conversation, tool calls included, so a reviewer
that resumed the builder's session would hold the builder's transcript whatever its prompt
leaves out. Other roles keep same-adapter continuity.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from pathly_orchestrator.supervisor import _lock, _registry, start_run
from pathly_orchestrator.supervisor.orchestrator_session import resolve_session
from pathly_orchestrator.supervisor.state import OpenSession, RunnerState

_NEXT_ACTION = "pathly_orchestrator.fsm_http_client.next_action"
_COMPLETE_STAGE = "pathly_orchestrator.fsm_http_client.complete_stage"
_RUN_STAGE = "pathly_orchestrator.supervisor._run_stage_via_terminal"


def _na(state: str, agent: str, adapter: str = "claude") -> dict:
    return {
        "current_state": state,
        "agent": agent,
        "instructions": "do stuff",
        "preferred_adapter": adapter,
    }


def _run(tmp_path, topic: str, stages: list[tuple[str, str, str, str]]):
    """Drive ``start_run`` through *stages*, each ``(state, agent, adapter, session returned)``.

    Returns ``(spawn sessions, SESSION events)``: what each spawn was called with as
    ``session=``, and every ``SESSION`` event the loop broadcast.
    """
    with _lock:
        _registry.pop(topic, None)

    spawn_sessions: list = []
    returned = iter(s[3] for s in stages)

    def fake_invoke(*_, **kwargs):
        spawn_sessions.append(kwargs.get("session"))
        return {"cost_usd": 0.01, "session_id": next(returned)}

    events: list[dict] = []

    def broadcast(_topic: str, payload: dict) -> None:
        events.append(payload)

    na_calls = [_na(state, agent, adapter) for state, agent, adapter, _ in stages]
    cs_calls = [{"next_state": "NEXT"} for _ in stages[:-1]] + [{"done": True}]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_RUN_STAGE, side_effect=fake_invoke),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
            broadcast_fn=broadcast,
        )
        deadline = time.monotonic() + 5.0
        while (
            state.status not in {"done", "error", "aborted"}
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)

    assert state.status == "done"
    with _lock:
        _registry.pop(topic, None)
    return spawn_sessions, [e for e in events if e.get("type") == "SESSION"]


def test_reviewer_opens_a_fresh_session_after_the_builder(tmp_path):
    sessions, events = _run(
        tmp_path,
        "fresh-review-after-build",
        [
            ("BUILDING", "team/build", "claude", "builder-sess"),
            ("REVIEWING", "team/review", "claude", "reviewer-sess"),
        ],
    )

    assert sessions == [None, None]
    assert [e["kind"] for e in events] == ["opened", "opened"]
    assert events[1]["independent"] is True
    assert events[1]["degraded"] is False
    assert not events[0].get("independent")


def test_stage_after_the_reviewer_continues_the_reviewers_session(tmp_path):
    sessions, events = _run(
        tmp_path,
        "fresh-test-after-review",
        [
            ("BUILDING", "team/build", "claude", "builder-sess"),
            ("REVIEWING", "team/review", "claude", "reviewer-sess"),
            ("TESTING", "team/test", "claude", "tester-sess"),
        ],
    )

    assert sessions == [None, None, "reviewer-sess"]
    assert [e["kind"] for e in events] == ["opened", "opened", "continued"]
    assert not events[2].get("independent")


def test_consecutive_builder_stages_still_share_a_session(tmp_path):
    sessions, events = _run(
        tmp_path,
        "fresh-build-build",
        [
            ("BUILDING", "team/build", "claude", "builder-sess"),
            ("BUILDING", "team/build", "claude", "builder-sess-2"),
        ],
    )

    assert sessions == [None, "builder-sess"]
    assert [e["kind"] for e in events] == ["opened", "continued"]


def test_agent_role_of_names_the_same_role_for_every_caller():
    from pathly_orchestrator.fsm_compose_tables import agent_role_of

    assert agent_role_of("team/review") == "reviewer"
    assert agent_role_of("quality/reviewer") == "reviewer"
    assert agent_role_of("builder") == "builder"
    assert agent_role_of("team/build") == "builder"
    assert agent_role_of("team/retro") == "planner"


def _state_with_open_session(adapter: str = "claude") -> RunnerState:
    state = RunnerState(
        topic="t", flow="team", project_root="/p", model="m", timeout=60
    )
    state.open_session = OpenSession(
        adapter=adapter, session_id="open-sess", resumable=True
    )
    return state


def test_resolve_session_without_a_stage_agent_continues_as_before():
    sent: list[dict] = []
    session_id, _, resumable = resolve_session(
        _state_with_open_session(), "t", "claude", sent.append
    )

    assert session_id == "open-sess"
    assert resumable is True
    assert sent[0]["kind"] == "continued"


def test_resolve_session_gives_an_independent_role_no_session():
    sent: list[dict] = []
    session_id, autonomy, resumable = resolve_session(
        _state_with_open_session(), "t", "claude", sent.append, "team/review"
    )

    assert session_id is None
    assert autonomy is True
    assert resumable is True
    assert sent[0]["kind"] == "opened"
    assert sent[0]["independent"] is True
    assert sent[0]["degraded"] is False


def test_resolve_session_keeps_degraded_for_an_adapter_that_cannot_resume():
    sent: list[dict] = []
    session_id, _, resumable = resolve_session(
        _state_with_open_session("copilot"),
        "t",
        "copilot",
        sent.append,
        "quality/reviewer",
    )

    assert session_id is None
    assert resumable is False
    assert sent[0]["independent"] is True
    assert sent[0]["degraded"] is True
