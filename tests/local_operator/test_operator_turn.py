"""The operator turn POST /hq/prompt serves when actions are enabled
(local-operator tickets 01 and 03): only enabled ∩ available actions are
offered, the packet names goals and artifacts by id, never-offered requests are
refused before the model, and zero actions is the read-only copilot unchanged.
"""

from __future__ import annotations

import pytest
from _operator_env import (
    BOARD,
    client,  # noqa: F401  (fixture)
    make_all_available,
    seed_artifact,
    seed_goal,
)


def _turn(client, message: str, enabled: list[str]) -> dict:
    resp = client.post(
        "/hq/prompt",
        json={
            "message": message,
            "board": BOARD,
            "project_root": "/proj",
            "enabled_actions": enabled,
        },
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def test_zero_actions_is_the_read_only_copilot(client):  # noqa: F811
    from pathly_orchestrator.hq_prompt import HQ_READONLY_REDIRECT, HQ_SYSTEM_PROMPT

    turn = _turn(client, "what needs my attention?", [])
    assert turn["system_prompt"] == HQ_SYSTEM_PROMPT and turn["tools"] == []
    assert turn["manifest"]["actions"] == []
    assert _turn(client, "pause the builder", [])["redirect"] == HQ_READONLY_REDIRECT


def test_operator_turn_offers_only_enabled_and_available(client):  # noqa: F811
    from pathly_orchestrator.hq_operator import OPERATOR_SYSTEM_PROMPT

    # run_goal is in the catalog but not available by default: ticking it does nothing.
    turn = _turn(client, "pause the builder", ["pause_run", "run_goal", "post_note"])
    assert turn["redirect"] is None
    assert turn["system_prompt"] == OPERATOR_SYSTEM_PROMPT
    assert [t["name"] for t in turn["tools"]] == ["pause_run", "post_note"]
    assert turn["actions"] == ["pause_run", "post_note"]
    assert turn["manifest"]["actions"] == ["pause_run", "post_note"]
    tool = turn["tools"][0]
    assert tool["parameters"]["required"] == ["run_id"]
    # The offered definitions ride in the context the runtime allocates.
    plain = _turn(client, "hi", [])
    assert turn["context_tokens"] > plain["context_tokens"]


def test_more_than_eight_is_refused(client):  # noqa: F811
    resp = client.post(
        "/hq/prompt",
        json={
            "message": "hi",
            "board": BOARD,
            "enabled_actions": [f"x{i}" for i in range(9)],
        },
    )
    assert resp.status_code == 400


def test_packet_names_goals_and_artifacts_by_id_in_operator_mode(client):  # noqa: F811
    make_all_available(client)
    gid = seed_goal("Ship the gateway")
    aid = seed_artifact("design.md")
    op = _turn(client, "what can I run?", ["run_goal"])["prompt"]
    assert f"(id {gid[:8]})" in op and f"(id {aid[:8]})" in op
    plain = _turn(client, "what can I run?", [])["prompt"]
    assert "(id " not in plain  # the read-only packet is unchanged


@pytest.mark.parametrize(
    "message",
    [
        "answer the builder's question with yes",
        "please post a directive to use JWT",
        "change the settings to use opus",
        "can you delete the file PLAN.md",
        "run the shell command ls",
    ],
)
def test_never_offered_requests_are_refused_before_the_model(
    client, message
):  # noqa: F811
    turn = _turn(client, message, ["pause_run", "post_note"])
    assert turn["redirect"] and turn["tools"] == [] and turn["prompt"] is None


@pytest.mark.parametrize(
    "message",
    [
        "how many tokens did the last run use?",
        "which question is the builder asking?",
        "post a note that review starts at 3",
        "pause the builder",
    ],
)
def test_questions_and_offered_actions_reach_the_model(client, message):  # noqa: F811
    turn = _turn(client, message, ["pause_run", "post_note"])
    assert turn["redirect"] is None and turn["tools"]
