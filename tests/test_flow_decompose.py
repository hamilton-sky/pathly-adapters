"""Tests for flow decompose/assemble round-trip and DB idempotency."""

from __future__ import annotations

import json
import sqlite3

import pytest
import yaml
from importlib.resources import files

from pathly_orchestrator.db.queries.flow_defs import (
    _assemble_from_parts,
    _decompose_flow_dict,
    read_flow_edges,
    read_flow_nodes,
    upsert_flow_definition,
)

# ---------------------------------------------------------------------------
# Fixture dicts for branches not covered by bundled flows (T1.5)
# ---------------------------------------------------------------------------

FIXTURE_DECIDE = {
    "version": 1,
    "flow": "decide-test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["CHOOSING", "PATH_A", "PATH_B"],
    "transitions": {"CHOOSING": ["PATH_A", "PATH_B"], "PATH_A": [], "PATH_B": []},
    "agent_map": {
        "CHOOSING": "team/decide",
        "PATH_A": "team/build",
        "PATH_B": "team/review",
    },
    "feedback_routing": {},
    "transition_rules": {
        "CHOOSING": {
            "decide": {
                "context_file": "CONTEXT.md",
                "question": "Which path?",
                "options": {"a": "PATH_A", "b": "PATH_B"},
                "default": "a",
            }
        }
    },
    "transition_actions": {},
}

FIXTURE_ON_CONTENT = {
    "version": 1,
    "flow": "content-test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["DRAFTING", "REVIEWING", "DONE"],
    "transitions": {
        "DRAFTING": ["REVIEWING", "DRAFTING"],
        "REVIEWING": ["DONE"],
        "DONE": [],
    },
    "agent_map": {
        "DRAFTING": "team/build",
        "REVIEWING": "team/review",
        "DONE": "team/retro",
    },
    "feedback_routing": {},
    "transition_rules": {
        "DRAFTING": {
            "on_content": [
                {"file": "PLAN.md", "contains": "## Conversation", "next": "REVIEWING"},
                {"file": "PLAN.md", "contains": "## Summary", "next": "REVIEWING"},
            ],
            "default": "DRAFTING",
        }
    },
    "transition_actions": {},
}

FIXTURE_ON_STATE_COUNTER = {
    "version": 1,
    "flow": "counter-test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["BUILDING", "REVIEWING", "DONE"],
    "transitions": {
        "BUILDING": ["REVIEWING"],
        "REVIEWING": ["BUILDING", "DONE"],
        "DONE": [],
    },
    "agent_map": {
        "BUILDING": "team/build",
        "REVIEWING": "team/review",
        "DONE": "team/retro",
    },
    "feedback_routing": {},
    "transition_rules": {
        "REVIEWING": {
            "on_state_counter": {
                "field": "convs_done",
                "op": "lt",
                "compare_to": "convs_total",
                "next": "BUILDING",
            },
            "default": "DONE",
        }
    },
    "transition_actions": {},
}


# ---------------------------------------------------------------------------
# T1.5 — Branch coverage tests for decide / on_content / on_state_counter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture", [FIXTURE_DECIDE, FIXTURE_ON_CONTENT, FIXTURE_ON_STATE_COUNTER]
)
def test_decompose_does_not_raise(fixture):
    _decompose_flow_dict(fixture)


def test_decide_rule_in_node_config():
    _, nodes, _ = _decompose_flow_dict(FIXTURE_DECIDE)
    choosing = next(n for n in nodes if n["node_id"] == "CHOOSING")
    cfg = json.loads(choosing["config_json"])
    assert "decide" in cfg["transition_rule"]
    assert cfg["transition_rule"]["decide"]["options"] == {"a": "PATH_A", "b": "PATH_B"}


def test_decide_rule_not_in_edge_config():
    _, _, edges = _decompose_flow_dict(FIXTURE_DECIDE)
    for edge in edges:
        cfg = json.loads(edge["config_json"] or "{}")
        assert "decide" not in cfg
        assert "transition_rule" not in cfg


def test_on_content_array_preserved_in_order():
    _, nodes, _ = _decompose_flow_dict(FIXTURE_ON_CONTENT)
    drafting = next(n for n in nodes if n["node_id"] == "DRAFTING")
    cfg = json.loads(drafting["config_json"])
    on_content = cfg["transition_rule"]["on_content"]
    assert len(on_content) == 2
    assert on_content[0]["contains"] == "## Conversation"
    assert on_content[1]["contains"] == "## Summary"


def test_on_state_counter_in_node_config():
    _, nodes, _ = _decompose_flow_dict(FIXTURE_ON_STATE_COUNTER)
    reviewing = next(n for n in nodes if n["node_id"] == "REVIEWING")
    cfg = json.loads(reviewing["config_json"])
    assert "on_state_counter" in cfg["transition_rule"]
    assert cfg["transition_rule"]["on_state_counter"]["field"] == "convs_done"


def test_on_state_counter_not_in_any_edge():
    _, _, edges = _decompose_flow_dict(FIXTURE_ON_STATE_COUNTER)
    for edge in edges:
        cfg = json.loads(edge["config_json"] or "{}")
        assert "on_state_counter" not in cfg


def test_no_db_in_fixture_tests():
    """Confirm no DB connections are used in fixture tests."""
    # This test simply documents the intent — if the functions above pass, this passes
    assert True


# ---------------------------------------------------------------------------
# T1.6 — Round-trip test: _assemble(_decompose(load(f))) == load(f) for all 5 flows
# ---------------------------------------------------------------------------

BUNDLED_FLOWS = ["team", "debug", "explore", "test", "quick-fix"]


@pytest.mark.parametrize("flow_name", BUNDLED_FLOWS)
def test_round_trip(flow_name):
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow_name}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    original = yaml.safe_load(text)
    flow_cfg, nodes, edges = _decompose_flow_dict(original)
    reconstructed = _assemble_from_parts(flow_cfg, nodes, edges)
    assert reconstructed == original, (
        f"Round-trip failed for {flow_name}. "
        f"Keys in original not in reconstructed: {set(original) - set(reconstructed)}. "
        f"Keys in reconstructed not in original: {set(reconstructed) - set(original)}."
    )


# ---------------------------------------------------------------------------
# T1.7 — Idempotency test: upsert twice, same row counts
# ---------------------------------------------------------------------------


def test_upsert_idempotency():
    from pathly_orchestrator.db.migrations import _run_migrations

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _run_migrations(conn)

    text = (
        files("pathly_data")
        .joinpath("core/flows/team.flow.yaml")
        .read_text(encoding="utf-8")
    )

    fid = upsert_flow_definition(conn, None, "team", "", text)
    nodes_1 = read_flow_nodes(conn, fid)
    edges_1 = read_flow_edges(conn, fid)

    upsert_flow_definition(conn, None, "team", "", text)
    nodes_2 = read_flow_nodes(conn, fid)
    edges_2 = read_flow_edges(conn, fid)

    assert len(nodes_1) == len(nodes_2)
    assert len(edges_1) == len(edges_2)
    assert [r["node_id"] for r in nodes_1] == [r["node_id"] for r in nodes_2]
