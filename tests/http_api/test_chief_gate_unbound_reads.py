"""chief-agent 08: the reads that are fleet-wide say so, and no more.

``/telemetry/trends`` without a feature must name the project; a named feature, and the
global counts of ``/db/stats``, are stated rather than hidden; an ``unbound`` entry lists
only a field the gate really leaves to the caller.
"""

from __future__ import annotations

import pytest

from chief_gate_support import (
    TIERS,
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)

# `/telemetry/trends` with a feature sums that feature across every project; without one it sums
# every project's cost unless `project_root` narrows it.


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("feature", ["", "   "])
def test_trends_without_a_feature_must_name_the_project(
    client, project, other_project, tier, feature
):
    chief = _chief(tier, project)

    unnamed = client.get(
        "/telemetry/trends", query_string={"feature": feature}, headers=chief.headers
    )
    other = client.get(
        "/telemetry/trends",
        query_string={"feature": feature, "project_root": str(other_project)},
        headers=chief.headers,
    )
    own = client.get(
        "/telemetry/trends",
        query_string={"feature": feature, "project_root": str(project)},
        headers=chief.headers,
    )

    assert _gated(unnamed), (unnamed.status_code, unnamed.get_data(as_text=True)[:200])
    assert "project_root" in unnamed.get_json()["error"]
    assert _gated(other)
    assert _passed(own), (own.status_code, own.get_data(as_text=True)[:200])


def test_trends_of_a_named_feature_stay_fleet_wide_and_say_so(client, project):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    chief = _chief("status", project)

    resp = client.get(
        "/telemetry/trends", query_string={"feature": "demo"}, headers=chief.headers
    )

    assert _passed(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    entry = ROUTE_FIELDS[("/telemetry/trends", "GET")]
    assert "feature" in entry.unbound
    assert "every project" in entry.note


def test_db_stats_says_its_counts_are_global():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    note = ROUTE_FIELDS[("/db/stats", "GET")].note

    for word in ("features", "events", "invocations", "global"):
        assert word in note, note


# The `unbound` entries list what the gate really leaves to the caller. A feature that a query
# filters by `project_root` as well is bound by the root the gate checks.

FEATURE_UNDER_THE_ROOT = [
    "/db/features/<feature>/agents",
    "/db/features/<feature>/events",
    "/db/features/<feature>/otel",
    "/db/features/<feature>/runs",
    "/api/features/<feature>/artifacts",
    "/api/features/<feature>/events",
    "/api/features/<feature>/invocations",
    "/api/features/<feature>/metrics",
    "/api/traces",
    "/flows/stage-config",
    "/comms/scope",
    "/db/rollup",
]


@pytest.mark.parametrize("rule", FEATURE_UNDER_THE_ROOT)
def test_a_feature_filtered_by_the_root_as_well_is_not_listed_unbound(rule):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    entry = ROUTE_FIELDS[(rule, "GET")]

    assert "feature" not in entry.unbound
    assert "project_root" in entry.roots
