"""parse_result must capture the adapter's per-model usage breakdown (`modelUsage`).

A single agent run spans multiple models (e.g. haiku for cheap sub-work + sonnet for the
task). Capturing the per-model split enables accurate cost attribution, and — when the
adapter reports ONLY a per-model breakdown and no lump total — lets parse_result derive
the correct total instead of returning 0.
"""

import json

from pathly_orchestrator.runner.output import parse_result


def test_extracts_normalized_model_usage():
    payload = json.dumps(
        {
            "total_cost_usd": 0.2297,
            "modelUsage": {
                "claude-haiku-4-5": {
                    "inputTokens": 5490,
                    "outputTokens": 19,
                    "costUSD": 0.0056,
                },
                "claude-sonnet-4-6": {
                    "inputTokens": 7,
                    "outputTokens": 1630,
                    "cacheReadInputTokens": 226337,
                    "costUSD": 0.2241,
                },
            },
        }
    )
    r = parse_result("claude", payload)
    mu = r["model_usage"]
    assert set(mu) == {"claude-haiku-4-5", "claude-sonnet-4-6"}
    assert mu["claude-haiku-4-5"]["cost_usd"] == 0.0056
    assert mu["claude-sonnet-4-6"]["tokens_out"] == 1630
    # tokens_in folds cache tokens in, matching the lump tokens_in convention.
    assert mu["claude-sonnet-4-6"]["tokens_in"] == 7 + 226337


def test_derives_total_cost_from_model_usage_when_lump_absent():
    payload = json.dumps(
        {
            "modelUsage": {
                "claude-haiku-4-5": {
                    "inputTokens": 100,
                    "outputTokens": 10,
                    "costUSD": 0.01,
                },
                "claude-sonnet-4-6": {
                    "inputTokens": 50,
                    "outputTokens": 200,
                    "costUSD": 0.20,
                },
            },
        }
    )
    r = parse_result("claude", payload)
    assert abs(r["cost_usd"] - 0.21) < 1e-6  # summed from per-model
    assert r["tokens_out"] == 10 + 200  # summed from per-model


def test_lump_cost_wins_when_present():
    payload = json.dumps(
        {
            "total_cost_usd": 0.99,
            "modelUsage": {
                "claude-sonnet-4-6": {
                    "inputTokens": 1,
                    "outputTokens": 1,
                    "costUSD": 0.01,
                }
            },
        }
    )
    r = parse_result("claude", payload)
    assert r["cost_usd"] == 0.99  # do NOT override a reported lump total


def test_no_model_usage_yields_empty_map():
    r = parse_result("claude", json.dumps({"total_cost_usd": 0.5}))
    assert r["model_usage"] == {}


def test_surfaces_cli_error_signal_for_failure_guards():
    """A claude run that fails but exits 0 sets is_error=true (subtype may still read a
    success-ish value). parse_result must surface is_error/api_error_status so
    scheduler._outcome_is_failure and /comms/tasks/run — which branch on exactly these keys —
    can fail the run instead of marking clean-exit-over-failed-work as done (silent-failure
    guard #2). Before the fix these keys were dropped from the return dict, so the guards'
    branches were unreachable."""
    from pathly_orchestrator.supervisor.scheduler import _outcome_is_failure

    payload = json.dumps(
        {
            "is_error": True,
            "subtype": "error_during_execution",
            "api_error_status": 404,
            "total_cost_usd": 0.0,
            "result": "model not found",
        }
    )
    r = parse_result("claude", payload)
    assert r["is_error"] is True
    assert r["api_error_status"] == 404
    assert r["subtype"] == "error_during_execution"
    # The whole point of the fix: the guard can now actually see the failure.
    assert _outcome_is_failure(r) is True


def test_clean_success_is_not_flagged_as_failure():
    """A normal success (is_error=false) must NOT trip the failure guard — surfacing the field
    on every result is inert for the success path."""
    from pathly_orchestrator.supervisor.scheduler import _outcome_is_failure

    r = parse_result(
        "claude",
        json.dumps({"is_error": False, "subtype": "success", "total_cost_usd": 0.1}),
    )
    assert r["is_error"] is False
    assert _outcome_is_failure(r) is False
