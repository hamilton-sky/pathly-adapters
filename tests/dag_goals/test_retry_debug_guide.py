"""A second attempt carries the root-cause debugging guide (build-proof 11).

``fragments/root-cause-debug.md`` is read at runtime (it is not in ``composition.yaml``, so no
golden snapshot moves) and appended in two places:

* ``task_retry.build_retry_context``, after the failure block, which exists only from a DAG
  task's second attempt on, so a first attempt's prompt stays byte-identical;
* ``fsm_compose.build_prompt_for_agent`` for a ``builder`` given a ``feedback_file``: every
  builder feedback prompt is a second attempt at the stage, and a headless run never climbs
  the FSM ``retry_count`` (build-proof spec, "When the debug guide is added").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.fsm_compose import build_prompt_for_agent
from pathly_orchestrator.supervisor.task_retry import build_retry_context

GUIDE = "## Root-cause debugging"


def _feedback(storage: Path, name: str = "REVIEW_FAILURES.md") -> None:
    fb = storage / "feedback"
    fb.mkdir(exist_ok=True)
    (fb / name).write_text("the build broke", encoding="utf-8")


# ── build_retry_context ──────────────────────────────────────────────────────


def test_a_first_attempt_adds_nothing():
    assert build_retry_context({"attempts": 0, "fail_reason": "boom"}) == ""
    assert build_retry_context({"attempts": 0}) == ""


def test_a_second_attempt_without_a_reason_adds_nothing():
    assert build_retry_context({"attempts": 1}) == ""


def test_a_second_attempt_carries_the_guide_after_the_failure():
    block = build_retry_context({"attempts": 1, "fail_reason": "FAILED test_x"})

    assert "Retry attempt 2" in block
    assert "FAILED test_x" in block
    assert GUIDE in block
    assert block.index("FAILED test_x") < block.index(GUIDE)


def test_the_guide_never_says_retry_attempt():
    """tests/fsm_flows/test_retry_ladder.py looks for those words to tell attempts apart."""
    from pathly_orchestrator.skills.compose_resources import root_cause_guide

    assert "Retry attempt" not in root_cause_guide()


def test_a_missing_fragment_costs_the_failure_block_nothing(monkeypatch):
    """A broken install must not kill the scheduler worker thread that builds the prompt."""
    from pathly_orchestrator.skills import compose_resources

    def _gone(fragments_dir: str, name: str) -> str:
        raise FileNotFoundError(name)

    monkeypatch.setattr(compose_resources, "_read_fragment", _gone)

    block = build_retry_context({"attempts": 1, "fail_reason": "FAILED test_x"})

    assert "FAILED test_x" in block
    assert GUIDE not in block


def test_a_retried_dag_task_prompt_carries_the_guide_and_a_first_attempt_does_not():
    from pathly_orchestrator.supervisor.task_prompt import build_task_prompt

    class _State:
        project_root = ""
        storage_path = ""
        topic = "guide-feature"
        goal_id = ""

    def prompt(attempts: int) -> str:
        task = {
            "id": "t1",
            "text": "do the thing",
            "attempts": attempts,
            "fail_reason": "FAILED test_x" if attempts else None,
        }
        return build_task_prompt(
            task,
            _State(),
            "feature",
            "guide-feature",
            adapter="claude",
            task_id="t1",
        )

    assert GUIDE not in prompt(0)
    assert GUIDE in prompt(1)


# ── build_prompt_for_agent ───────────────────────────────────────────────────


def test_a_builder_feedback_prompt_carries_the_guide(tmp_path):
    _feedback(tmp_path)

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md"
    )

    assert GUIDE in prompt


def test_a_builder_feedback_prompt_carries_the_guide_once_on_a_later_round(tmp_path):
    _feedback(tmp_path)

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )

    assert prompt.count(GUIDE) == 1
    assert "Retry attempt 2" in prompt


@pytest.mark.parametrize("role", ["planner", "architect", "po", "designer", "reviewer"])
def test_other_roles_do_not_get_the_guide(tmp_path, role):
    _feedback(tmp_path)

    prompt = build_prompt_for_agent(role, tmp_path, feedback_file="REVIEW_FAILURES.md")

    assert GUIDE not in prompt


def test_a_builder_without_a_feedback_file_does_not_get_the_guide(tmp_path):
    assert GUIDE not in build_prompt_for_agent("builder", tmp_path)
    assert GUIDE not in build_prompt_for_agent("builder", tmp_path, retry_count=2)


def test_a_builder_without_a_feedback_file_keeps_its_prompt_byte_identical(tmp_path):
    prompt = build_prompt_for_agent("builder", tmp_path)

    assert prompt.endswith(f"Storage path: {tmp_path}\n")


# ── the fragment itself ──────────────────────────────────────────────────────


def _guide() -> str:
    from pathly_orchestrator.skills.compose_resources import root_cause_guide

    return root_cause_guide()


def test_the_guide_has_its_heading_and_five_steps():
    guide = _guide()

    assert guide.lstrip().startswith(GUIDE)
    for step in ("1.", "2.", "3.", "4.", "5."):
        assert f"\n{step} " in guide, step
    for word in ("Read", "Reproduce", "Isolate", "Fix", "Prove"):
        assert word.lower() in guide.lower(), word


def test_the_guide_forbids_weakening_a_check_and_names_the_floor_guard():
    guide = _guide()

    for banned in (
        "skipped or deleted tests",
        "loosened expectations",
        "silenced linters",
        "lint, test or CI config",
    ):
        assert banned in guide, banned
    assert "floor guard" in guide


def test_the_guide_stops_after_two_failed_fixes():
    guide = _guide()

    assert "two failed fixes of the same error" in guide
    assert "report what was tried" in guide


def test_the_guide_is_not_a_composed_fragment():
    """Not in composition.yaml: it is read at runtime, so no golden snapshot moves."""
    from pathly_orchestrator.skills.compose_resources import _skills_root

    manifest = _skills_root().joinpath("composition.yaml").read_text(encoding="utf-8")

    assert "root-cause-debug" not in manifest
