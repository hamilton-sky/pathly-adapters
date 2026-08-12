"""spawn-policy P0 — per-agent model + logging config (db/queries/app_settings).

The DB-backed keystone: ONE source of truth for "which company+model per agent" + "where
agents narrate", read by both the renderer gate and the Python resolver. Isolation is handled
by the _isolate_db autouse fixture in conftest.py.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.app_settings import (
    clear_agent_model,
    get_logging_config,
    get_model_policy,
    resolve_agent_model,
    set_agent_model,
    set_logging_board_enabled,
    set_setting,
)


def test_resolve_layers_role_over_default_over_none() -> None:
    conn = get_db()
    # Nothing configured → None (caller keeps its adapter, engine picks its own model).
    assert resolve_agent_model(conn, "builder") is None
    # Global default applies to every role.
    set_agent_model(conn, None, "claude", "claude-opus-4-1")
    assert resolve_agent_model(conn, "builder") == {
        "adapter": "claude",
        "model": "claude-opus-4-1",
    }
    # A per-role override wins over the default.
    set_agent_model(conn, "builder", "codex", "gpt-5-codex")
    assert resolve_agent_model(conn, "builder") == {
        "adapter": "codex",
        "model": "gpt-5-codex",
    }
    # A different role still resolves to the default.
    assert resolve_agent_model(conn, "scout") == {
        "adapter": "claude",
        "model": "claude-opus-4-1",
    }
    # Clearing the override falls back to the default.
    clear_agent_model(conn, "builder")
    assert resolve_agent_model(conn, "builder") == {
        "adapter": "claude",
        "model": "claude-opus-4-1",
    }


def test_empty_model_means_engine_default() -> None:
    conn = get_db()
    set_agent_model(
        conn, "analyze", "claude", ""
    )  # adapter chosen, model = engine default
    assert resolve_agent_model(conn, "analyze") == {"adapter": "claude", "model": ""}


def test_set_agent_model_rejects_blank_adapter() -> None:
    conn = get_db()
    with pytest.raises(ValueError):
        set_agent_model(conn, "builder", "   ", "gpt-5")


def test_get_model_policy_shape_for_the_ui() -> None:
    conn = get_db()
    set_agent_model(conn, None, "claude", "claude-opus-4-1")
    set_agent_model(conn, "scout", "claude", "claude-haiku-4")
    policy = get_model_policy(conn)
    assert policy["default"] == {"adapter": "claude", "model": "claude-opus-4-1"}
    assert policy["roles"]["scout"] == {"adapter": "claude", "model": "claude-haiku-4"}


def test_malformed_value_degrades_to_none() -> None:
    conn = get_db()
    set_setting(conn, "models:role:builder", "not json{{{")
    # Malformed override → falls through to the (absent) default → None. Never raises.
    assert resolve_agent_model(conn, "builder") is None


def test_logging_board_defaults_on_and_toggles() -> None:
    conn = get_db()
    cfg = get_logging_config(conn)
    assert cfg["board"] is True  # agent board-narration defaults ON
    assert (
        cfg["verbosity"] == "normal"
    )  # reuses the existing board:default_progress default
    set_logging_board_enabled(conn, False)
    assert get_logging_config(conn)["board"] is False


def test_logging_config_never_exposes_the_monitor_spine() -> None:
    # The invariant: the always-on cost/monitor spine must NEVER be a togglable key here.
    conn = get_db()
    cfg = get_logging_config(conn)
    assert set(cfg.keys()) == {"board", "verbosity"}
    assert "monitor" not in cfg and "cost" not in cfg


def test_effective_model_takes_effect_fail_safe() -> None:
    """P1b: the resolver that makes the model choice take effect at a board spawn."""
    from pathly_orchestrator.supervisor.spawn_policy import effective_model

    conn = get_db()
    set_agent_model(conn, "builder", "claude", "claude-opus-4-1")
    # An explicit model always wins (a per-run choice is never overridden).
    assert effective_model("builder", "claude", "claude-sonnet-5") == "claude-sonnet-5"
    # No explicit model + the run's company matches the config → the configured model applies.
    assert effective_model("builder", "claude", "") == "claude-opus-4-1"
    # Different company than configured → respect the run's company, don't override it.
    assert effective_model("builder", "codex", "") == ""
    # No agent, or an unconfigured role → unchanged (fail-safe: behaves exactly as before).
    assert effective_model("", "claude", "") == ""
    assert effective_model("scout", "claude", "") == ""
