"""build-proof 10: the diff base for the Review packet lives in STATE.

``next_action`` stamps a working-tree ``tree`` into ``build_baseline`` on entering BUILDING, and
``complete_stage`` copies ``{tree, started_at}`` into ``review_base`` on a transition out of
BUILDING (overwriting the last build's, never leaving a stale one). Setup is in
``review_packet_support``.
"""

from __future__ import annotations

import re

from review_packet_support import (
    FEATURE,
    _args,
    _build,
    _enter_building,
    _state,
    _storage,
    _write,
    flow,
    repo,
)

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms_tasks import complete_task
from pathly_orchestrator.proof import tree

# --- the base the diff starts from ----------------------------------------------------


def test_next_action_stamps_the_working_tree_into_build_baseline(repo, flow):
    _enter_building(repo, flow)

    baseline = _state(repo)["build_baseline"]

    assert re.fullmatch(r"[0-9a-f]{40,64}", baseline["tree"])
    assert baseline["started_at"]
    assert baseline["preexisting_dirty"] is not None
    # The tree is the project as it was before the builder started.
    assert tree.blob(repo, baseline["tree"], "src/app.py") == tree.blob(
        repo, tree.snapshot(str(repo)), "src/app.py"
    )


def test_a_project_outside_git_gets_no_tree_in_the_baseline(tmp_path, flow):
    plain = tmp_path / "plain"
    _write(plain, FEATURE + "/IMPLEMENTATION_PLAN.md", "# Plan\n")
    set_setting(get_db(), "code_context.backend", "off")
    eventlog.write_state(str(plain / FEATURE), {"current": "BUILDING"}, flow)

    fsm_ops.next_action({**_args(plain), "project_root": str(plain)})

    baseline = _state(plain)["build_baseline"]
    assert "tree" not in baseline
    assert baseline["started_at"]


def test_leaving_building_copies_the_base_into_review_base(repo, flow):
    _build(repo, flow)
    stamped = _state(repo)["build_baseline"]

    fsm_ops.complete_stage(_args(repo))

    state = _state(repo)
    assert state["current"] == "REVIEWING"
    assert state["review_base"] == {
        "tree": stamped["tree"],
        "started_at": stamped["started_at"],
    }
    assert "build_baseline" not in state


def test_a_later_build_overwrites_the_review_base(repo, flow):
    _enter_building(repo, flow)
    first = _state(repo)["build_baseline"]
    fsm_ops.complete_stage(_args(repo))
    assert _state(repo)["review_base"]["tree"] == first["tree"]

    # A failed review sends the run back to BUILDING; the new build has its own baseline.
    _write(repo, "src/app.py", "x = 3\ny = 2\n")
    state = _state(repo)
    eventlog.write_state(str(_storage(repo)), {**state, "current": "BUILDING"}, flow)
    fsm_ops.next_action(_args(repo))
    second = _state(repo)["build_baseline"]
    assert second["tree"] != first["tree"]
    fsm_ops.complete_stage(_args(repo))

    assert _state(repo)["review_base"] == {
        "tree": second["tree"],
        "started_at": second["started_at"],
    }


def test_leaving_another_state_keeps_the_review_base(repo, flow):
    task_id = _build(repo, flow)
    complete_task(get_db(), task_id)
    fsm_ops.complete_stage(_args(repo))
    kept = _state(repo)["review_base"]
    _write(repo, FEATURE + "/REVIEW.md", "RESULT: PASS\nReviewed: fine.\n")

    fsm_ops.complete_stage(_args(repo))

    state = _state(repo)
    assert state["current"] == "TESTING"
    assert state["review_base"] == kept


def test_a_build_without_a_tree_leaves_no_stale_review_base(repo, flow):
    _enter_building(repo, flow)
    state = _state(repo)
    state["review_base"] = {"tree": "a" * 40, "started_at": "2020-01-01T00:00:00+00:00"}
    state["build_baseline"] = {"started_at": state["build_baseline"]["started_at"]}
    eventlog.write_state(str(_storage(repo)), state, flow)

    fsm_ops.complete_stage(_args(repo))

    assert "review_base" not in _state(repo)
