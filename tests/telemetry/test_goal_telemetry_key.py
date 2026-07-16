"""Goal-run telemetry-key unification.

A GOAL team run nests on disk at ``pathly/features/<feature>/goals/<slug>``. The FSM,
every ``eventlog.append_event(<path>)`` write, and the DB-explorer goal panel all key
events by the run SLUG (the storage-dir basename). But board writes must target the
parent BOARD scope (the feature) so artifacts don't orphan onto a throwaway slug board.

The prompt therefore carries two distinct placeholders:
  - ``<feature>``     → board scope   (e.g. ``planner-hierarchy``) — board posts
  - ``<fsm_feature>`` → run slug      (e.g. ``g3-…``)              — telemetry / AGENT_DONE

Regression guard: the completion-report AGENT_DONE must POST under ``<fsm_feature>`` so
its cost lands where the goal panel + billing reconciliation look. Before the fix it
posted under ``<feature>`` (board scope), so the goal showed $0 while the cost hid under
the feature.
"""

from pathlib import Path

from pathly_orchestrator.compose import compose_skill
from pathly_orchestrator.fsm_compose import _inject_prompt_vars

_GOAL_STORAGE = Path(
    "C:/proj/pathly/features/planner-hierarchy/goals/g3-modernize-bmad-prd-9f77f795"
)
_SLUG = "g3-modernize-bmad-prd-9f77f795"
_BOARD_SCOPE = "planner-hierarchy"


def test_goal_run_splits_board_scope_from_fsm_key():
    """For a goal run, <feature> resolves to the board scope, <fsm_feature> to the slug."""
    out = _inject_prompt_vars(
        "board=<feature> log=<fsm_feature>",
        feature=_BOARD_SCOPE,  # board_scope is what build_prompt passes as `feature`
        project_root="C:/proj",
        agent_role="builder",
        storage_path=_GOAL_STORAGE,
    )
    assert out == f"board={_BOARD_SCOPE} log={_SLUG}"


def test_plain_feature_run_keys_are_identical():
    """For a plain feature run the two placeholders resolve to the SAME value (no-op)."""
    storage = Path("C:/proj/pathly/features/myfeature")
    out = _inject_prompt_vars(
        "<feature>|<fsm_feature>",
        feature="myfeature",
        project_root="C:/proj",
        agent_role="builder",
        storage_path=storage,
    )
    assert out == "myfeature|myfeature"


def test_fsm_feature_falls_back_to_feature_without_storage_path():
    """No storage_path (defensive) → <fsm_feature> falls back to <feature>, never leaks literally."""
    out = _inject_prompt_vars(
        "<fsm_feature>",
        feature="somefeat",
        project_root="C:/proj",
        agent_role="builder",
        storage_path=None,
    )
    assert out == "somefeat"
    assert "<fsm_feature>" not in out


def test_completion_report_posts_agent_done_under_fsm_feature():
    """The composed completion-report must key its AGENT_DONE POST by <fsm_feature>, not <feature>.

    team/build composes completion-report; its /runner/event POST body carries the feature
    key. It must be <fsm_feature> (the slug) so the goal panel + reconciliation find the event.
    """
    out = compose_skill("team/build", "claude")
    assert (
        "'feature': '<fsm_feature>'" in out
    ), "AGENT_DONE POST must key by <fsm_feature>"
    assert (
        "'feature': '<feature>'" not in out
    ), "AGENT_DONE POST must NOT key by board scope"


def test_completion_report_fragment_source_uses_fsm_feature():
    """Guard the fragment source itself so a future edit can't silently revert to <feature>."""
    from importlib.resources import files

    frag = (
        files("pathly_data")
        .joinpath("core/skills/fragments/completion-report.md")
        .read_text(encoding="utf-8")
    )
    assert "'feature': '<fsm_feature>'" in frag
    assert "'feature': '<feature>'" not in frag
