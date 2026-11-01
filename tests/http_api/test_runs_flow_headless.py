"""chief-autopilot 04: a flow a chief starts runs headless, and every packaged flow lists as
``flow`` in ``GET /runs``.

``POST /runs {"kind": "flow"}`` passes ``interactive=False`` to ``supervisor.api.start_run``
when the caller holds a chief token or the body says ``"interactive": false``; a tokenless call
with no field keeps ``start_run``'s own default (Studio's New-run button). ``interactive`` must be
a boolean, and a chief may not send it at all. ``start_run`` is a stub that records its keywords
(``flow_runs``); the gate and the route are real.
"""

from __future__ import annotations

import re
import uuid

import pytest
from chief_budget_support import flow_runs, shown, start_flow
from chief_gate_support import _chief, _gated, app, client, project

from tests._paths import SRC

NO_TOKEN = type("NoToken", (), {"headers": {}})()


def _packaged_flows() -> list[str]:
    """The ``flow:`` key of every packaged ``*.flow.yaml``."""
    names = []
    for path in sorted((SRC / "pathly_data" / "core" / "flows").glob("*.flow.yaml")):
        found = re.search(r"^flow:\s*(\S+)", path.read_text("utf-8"), re.MULTILINE)
        assert found, path
        names.append(found.group(1))
    return names


# --- headless on a chief token or an explicit false --------------------------------------------


def test_a_chief_started_flow_runs_headless(client, project, flow_runs):
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 200, shown(resp)
    assert [call.get("interactive") for call in flow_runs.calls] == [False]


def test_a_tokenless_start_with_no_field_keeps_the_default(client, project, flow_runs):
    resp = start_flow(client, NO_TOKEN, project)

    assert resp.status_code == 200, shown(resp)
    assert len(flow_runs.calls) == 1
    assert flow_runs.calls[0].get("interactive", True) is True


def test_a_tokenless_start_that_asks_for_headless_gets_it(client, project, flow_runs):
    resp = start_flow(client, NO_TOKEN, project, interactive=False)

    assert resp.status_code == 200, shown(resp)
    assert [call.get("interactive") for call in flow_runs.calls] == [False]


def test_a_tokenless_start_that_asks_for_interactive_gets_it(
    client, project, flow_runs
):
    resp = start_flow(client, NO_TOKEN, project, interactive=True)

    assert resp.status_code == 200, shown(resp)
    assert flow_runs.calls[0].get("interactive", True) is True


@pytest.mark.parametrize("value", ["false", 0, 1, None, [], {}])
def test_an_interactive_that_is_not_a_boolean_is_400(client, project, flow_runs, value):
    resp = start_flow(client, NO_TOKEN, project, interactive=value)

    assert resp.status_code == 400, shown(resp)
    assert "interactive" in resp.get_json()["error"]
    assert flow_runs.calls == []


@pytest.mark.parametrize("value", [True, False])
def test_a_chief_cannot_send_interactive(client, project, flow_runs, value):
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project, interactive=value)

    assert _gated(resp), shown(resp)
    assert "interactive" in resp.get_json()["error"]
    assert flow_runs.calls == []


# --- every packaged flow lists as `flow` ----------------------------------------------------


def test_every_packaged_flow_but_goal_loop_lists_as_flow(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_history import upsert_run

    flows = _packaged_flows()
    assert "goal-loop" in flows and "explore" in flows
    conn = get_db()
    root = str(project).replace("\\", "/")
    ids = {}
    for flow in flows:
        ids[flow] = str(uuid.uuid4())
        upsert_run(
            conn,
            root,
            "demo",
            ids[flow],
            "done",
            started_at="2026-07-30T10:00:00+00:00",
            finished_at="2026-07-30T10:05:00Z",
            adapter=flow,
            board_scope="demo",
        )

    resp = client.get(f"/runs?project_root={root}&limit=100")

    assert resp.status_code == 200, shown(resp)
    kinds = {row["run_id"]: row["kind"] for row in resp.get_json()}
    expected = {
        ids[flow]: ("loop" if flow == "goal-loop" else "flow") for flow in flows
    }
    assert {rid: kinds.get(rid) for rid in expected} == expected
