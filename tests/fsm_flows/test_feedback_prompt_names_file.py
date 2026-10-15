"""A feedback spawn's prompt names the feedback file it is handed and shows its text (build-proof 18).

``build_prompt_for_agent`` used to name the file and show its text only from ``retry_count > 0``
(the retry ladder, which a headless run never reaches) or in the Fix mode block of po, planner,
architect and designer. A builder, reviewer or tester sent back got its agent text, the
``## Current task`` context and, for a builder, a guide whose first step says "Read every failure
above" with nothing above it. Round 1 now carries a ``## Feedback to resolve`` block in the
position the ladder takes from round 2, and every other prompt is as it was.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.fsm_compose import build_prompt_for_agent

HEADING = "## Feedback to resolve"
GUIDE_HEADING = "## Root-cause debugging"


def _write(storage, name, text):
    folder = storage / "feedback"
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


def _path(storage, name):
    return "%s/feedback/%s" % (storage.as_posix().rstrip("/"), name)


def _block_of(prompt):
    """What follows the ``## Feedback to resolve`` heading."""
    return prompt.split(HEADING, 1)[1]


def test_a_builder_is_told_the_file_and_shown_its_text_before_the_guide(tmp_path):
    _write(
        tmp_path,
        "FLOOR_FAILURES.md",
        "floor: tests/test_app.py: a finding the gate quoted",
    )

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="FLOOR_FAILURES.md"
    )

    assert prompt.count(HEADING) == 1
    assert _path(tmp_path, "FLOOR_FAILURES.md") in _block_of(prompt)
    assert "floor: tests/test_app.py: a finding the gate quoted" in _block_of(prompt)
    # In the place the ladder takes: after the task context, before the guide.
    assert prompt.index("## Current task") < prompt.index(HEADING)
    assert prompt.index(HEADING) < prompt.index(GUIDE_HEADING)
    assert prompt.count("floor: tests/test_app.py: a finding the gate quoted") == 1


def test_the_block_says_what_the_file_is_and_to_fix_the_cause(tmp_path):
    _write(tmp_path, "FLOOR_FAILURES.md", "the failure")

    block = _block_of(
        build_prompt_for_agent("builder", tmp_path, feedback_file="FLOOR_FAILURES.md")
    )

    assert "gate or reviewer wrote" in block
    assert "cause" in block


@pytest.mark.parametrize(
    "role,name",
    [("reviewer", "REVIEW_INCOMPLETE.md"), ("tester", "TEST_FAILURES.md")],
)
def test_a_reviewer_and_a_tester_get_the_block_and_no_guide(tmp_path, role, name):
    _write(tmp_path, name, "the sent-back text")

    prompt = build_prompt_for_agent(role, tmp_path, feedback_file=name)

    assert prompt.count(HEADING) == 1
    assert _path(tmp_path, name) in _block_of(prompt)
    assert "the sent-back text" in _block_of(prompt)
    assert prompt.index("## Current task") < prompt.index(HEADING)
    assert GUIDE_HEADING not in prompt
    assert "Fix mode" not in prompt


def test_a_later_round_shows_the_text_once_in_the_ladder_and_has_no_block(tmp_path):
    _write(tmp_path, "FLOOR_FAILURES.md", "UNIQUE-FAILURE-TEXT")

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="FLOOR_FAILURES.md", retry_count=1
    )

    assert HEADING not in prompt
    assert "Retry attempt 2" in prompt
    assert prompt.count("UNIQUE-FAILURE-TEXT") == 1


@pytest.mark.parametrize("role", ["po", "planner", "architect", "designer"])
def test_a_root_cause_role_gets_fix_mode_and_no_new_block(tmp_path, role):
    _write(tmp_path, "ARCH_FEEDBACK.md", "the design decision was wrong")

    prompt = build_prompt_for_agent(role, tmp_path, feedback_file="ARCH_FEEDBACK.md")

    assert HEADING not in prompt
    assert "## Fix mode" in prompt
    # Fix mode follows the task context directly, as before.
    before_fix_mode = prompt.split("## Fix mode", 1)[0]
    assert before_fix_mode.endswith("Storage path: %s\n\n" % tmp_path)


@pytest.mark.parametrize("role", ["builder", "reviewer", "tester", "architect"])
def test_no_feedback_file_leaves_the_prompt_as_it_was(tmp_path, role):
    _write(tmp_path, "FLOOR_FAILURES.md", "left on disk, not handed over")

    prompt = build_prompt_for_agent(role, tmp_path)

    assert HEADING not in prompt
    assert prompt.endswith("Storage path: %s\n" % tmp_path)


def test_a_file_that_does_not_exist_is_named_and_reported_unreadable(tmp_path):
    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="FLOOR_FAILURES.md"
    )

    assert prompt.count(HEADING) == 1
    block = _block_of(prompt)
    assert _path(tmp_path, "FLOOR_FAILURES.md") in block
    assert "could not be read" in block
    assert "```" not in block  # no empty fence


def test_an_empty_file_is_reported_like_an_unreadable_one(tmp_path):
    _write(tmp_path, "FLOOR_FAILURES.md", "  \n\n")

    block = _block_of(
        build_prompt_for_agent("builder", tmp_path, feedback_file="FLOOR_FAILURES.md")
    )

    assert "could not be read" in block
    assert "```" not in block


def test_a_file_that_is_not_text_is_reported_unreadable(tmp_path):
    (tmp_path / "feedback").mkdir()
    (tmp_path / "feedback" / "FLOOR_FAILURES.md").write_bytes(b"\xff\xfe\x00bad")

    block = _block_of(
        build_prompt_for_agent("builder", tmp_path, feedback_file="FLOOR_FAILURES.md")
    )

    assert "could not be read" in block


def test_a_long_file_is_clipped_to_4000_characters(tmp_path):
    marker = ""
    _write(tmp_path, "FLOOR_FAILURES.md", marker * 6000)

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="FLOOR_FAILURES.md"
    )

    assert prompt.count(marker) == 4000


def test_a_file_holding_a_triple_backtick_is_fenced_with_four(tmp_path):
    text = "output:\n```\nboom\n```\nend"
    _write(tmp_path, "FLOOR_FAILURES.md", text)

    block = _block_of(
        build_prompt_for_agent("builder", tmp_path, feedback_file="FLOOR_FAILURES.md")
    )

    assert "\n````\n%s\n````\n" % text in block


def test_the_fence_is_one_backtick_longer_than_any_run_in_the_text(tmp_path):
    text = "a ```` run, and a ` one"
    _write(tmp_path, "FLOOR_FAILURES.md", text)

    block = _block_of(
        build_prompt_for_agent("builder", tmp_path, feedback_file="FLOOR_FAILURES.md")
    )

    assert "\n`````\n%s\n`````\n" % text in block


def test_a_text_without_backticks_is_fenced_with_three(tmp_path):
    _write(tmp_path, "FLOOR_FAILURES.md", "plain text")

    block = _block_of(
        build_prompt_for_agent("builder", tmp_path, feedback_file="FLOOR_FAILURES.md")
    )

    assert "\n```\nplain text\n```\n" in block


# ── the two functions the prompt and the ladder share ─────────────────────────


def test_read_feedback_strips_and_clips(tmp_path):
    from pathly_orchestrator.fsm_compose_feedback import read_feedback

    _write(tmp_path, "A.md", "\n  text  \n")
    _write(tmp_path, "B.md", "y" * 5000)

    assert read_feedback(tmp_path, "A.md") == "text"
    assert read_feedback(tmp_path, "B.md") == "y" * 4000


def test_read_feedback_is_empty_when_the_file_cannot_be_read(tmp_path):
    from pathly_orchestrator.fsm_compose_feedback import read_feedback

    assert read_feedback(tmp_path, "MISSING.md") == ""


def test_feedback_block_is_the_same_text_the_prompt_carries(tmp_path):
    from pathly_orchestrator.fsm_compose_feedback import feedback_block

    _write(tmp_path, "FLOOR_FAILURES.md", "the failure")

    prompt = build_prompt_for_agent(
        "reviewer", tmp_path, feedback_file="FLOOR_FAILURES.md"
    )

    assert feedback_block(tmp_path, "FLOOR_FAILURES.md") in prompt
