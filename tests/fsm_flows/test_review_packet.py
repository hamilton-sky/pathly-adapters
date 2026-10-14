"""build-proof 10: the REVIEWING prompt carries a Review packet, not the builder's summary.

The reviewer has no Bash, so ``team/review.md`` used to tell it to run a ``git diff`` it could not
run, and the prompt handed it the builder's own ``AGENT_DONE`` summaries. Now ``build_prompt`` puts
``fsm_compose_review.review_packet`` (the frozen task text, the diff of the last build, the
supervisor's notes) in place of the history block for the reviewer role. Every case runs a real
``git init`` project through the packaged ``team-build`` flow's ``next_action`` and
``complete_stage`` (setup in ``review_packet_support``).
"""

from __future__ import annotations

import re

from review_packet_support import (
    DIFF_LINE,
    FEATURE,
    SUMMARY,
    _args,
    _build,
    _claim,
    _enter_building,
    _packet,
    _section,
    _state,
    _storage,
    _write,
    _git,
    flow,
    repo,
)

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.db.queries.comms_messages import update_message_text
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.fsm_compose import build_prompt

LIMIT = 48 * 1024


# --- the REVIEWING prompt ----------------------------------------------------------------


def test_the_reviewing_prompt_has_the_packet_and_not_the_builders_summary(repo, flow):
    _build(repo, flow)

    done = fsm_ops.complete_stage(_args(repo))

    prompt = done["agent_hint"]["instructions"]
    assert done["next_state"] == "REVIEWING"
    assert "## Review packet" in prompt
    assert "FROZEN-TASK-TEXT" in prompt
    assert DIFF_LINE in prompt
    assert SUMMARY not in prompt
    assert "## Pipeline History" not in prompt
    # build_prompt gives the same answer when asked for REVIEWING directly.
    direct = build_prompt(flow, "REVIEWING", _storage(repo))
    assert "## Review packet" in direct and DIFF_LINE in direct
    assert SUMMARY not in direct


def test_the_building_prompt_keeps_the_history_block(repo, flow):
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))

    prompt = build_prompt(flow, "BUILDING", _storage(repo))

    assert "## Pipeline History" in prompt
    assert SUMMARY in prompt
    assert "## Review packet" not in prompt


def test_the_packet_shows_the_frozen_task_text_not_a_later_edit(repo, flow):
    task_id = _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    update_message_text(get_db(), task_id, "LATER-EDIT the builder rewrote its task")

    task = _section(_packet(repo), "The task")

    assert "FROZEN-TASK-TEXT" in task
    assert "LATER-EDIT" not in task


def test_the_packet_names_only_the_tasks_claimed_since_the_build_began(repo, flow):
    conn = get_db()
    old = post_message(
        conn, "feature", "demo", "planner", type="task", text="OLD-TASK-TEXT"
    )
    assert claim_task(conn, old, "build")
    conn.execute(
        "UPDATE comms_messages SET claimed_at=? WHERE id=?",
        ("2020-01-01T00:00:00+00:00", old),
    )
    conn.commit()
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    other = post_message(
        conn, "feature", "elsewhere", "planner", type="task", text="OTHER-SCOPE-TASK"
    )
    assert claim_task(conn, other, "build")

    task = _section(_packet(repo), "The task")

    assert "FROZEN-TASK-TEXT" in task
    assert "OLD-TASK-TEXT" not in task
    assert "OTHER-SCOPE-TASK" not in task


def test_the_diff_leaves_out_everything_under_pathly(repo, flow):
    _build(repo, flow)
    _write(repo, FEATURE + "/IMPLEMENTATION_PLAN.md", "# Plan\nPLAN-EDIT-LINE\n")
    _write(repo, "src/new_module.py", "NEW_MODULE_LINE = 1\n")
    fsm_ops.complete_stage(_args(repo))

    diff = _section(_packet(repo), "The diff")

    assert DIFF_LINE in diff
    assert "NEW_MODULE_LINE" in diff
    assert "PLAN-EDIT-LINE" not in diff
    assert "STATE.json" not in diff


def test_the_diff_carries_three_lines_of_context(repo, flow):
    _write(repo, "src/app.py", "a\nb\nc\nd\ne\nf\ng\nh\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "more lines")
    _enter_building(repo, flow)
    _claim()
    _write(repo, "src/app.py", "a\nb\nc\nd\nE-CHANGED\nf\ng\nh\n")
    fsm_ops.complete_stage(_args(repo))

    diff = _section(_packet(repo), "The diff")

    assert "-e\n+E-CHANGED\n" in diff
    assert " b\n c\n d\n-e" in diff
    assert " f\n g\n h\n" in diff


def test_a_markdown_fence_in_the_diff_cannot_close_the_packets_fence(repo, flow):
    _write(repo, "docs/guide.md", "intro\n```\ncode\n```\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "docs")
    _enter_building(repo, flow)
    _claim()
    _write(repo, "docs/guide.md", "intro\n```\ncode\nmore\n```\n")
    fsm_ops.complete_stage(_args(repo))

    diff = _section(_packet(repo), "The diff")

    opening = re.match(r"\s*(`{3,})diff\n", diff)
    assert opening, diff[:200]
    assert len(opening.group(1)) > 3
    assert diff.rstrip().endswith(opening.group(1))


def test_a_200_kib_diff_is_clipped_to_48_kib(repo, flow):
    _build(repo, flow)
    lines = "".join("value_%d = %d  # %s\n" % (i, i, "x" * 40) for i in range(4000))
    _write(repo, "src/big.py", lines)
    assert len(lines.encode("utf-8")) > 200 * 1024
    fsm_ops.complete_stage(_args(repo))

    diff = _section(_packet(repo), "The diff")

    assert len(diff.encode("utf-8")) <= LIMIT
    assert "value_0 = 0" in diff
    assert "value_3999 = 3999" in diff
    assert "value_2000 = 2000" not in diff
    assert "omitted" in diff


def test_a_diff_under_the_limit_is_not_clipped(repo, flow):
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))

    diff = _section(_packet(repo), "The diff")

    assert DIFF_LINE in diff
    assert "omitted" not in diff


def test_a_build_that_changed_nothing_says_so(repo, flow):
    _build(repo, flow, edit=False)
    fsm_ops.complete_stage(_args(repo))

    diff = _section(_packet(repo), "The diff")

    assert "nothing" in diff.lower()


def test_an_unreadable_diff_does_not_break_the_prompt(repo, flow):
    _build(repo, flow)
    state = _state(repo)
    state["review_base"] = {"tree": "0" * 40, "started_at": "2020-01-01T00:00:00+00:00"}
    eventlog.write_state(str(_storage(repo)), state, flow)

    packet = _packet(repo)

    assert "## Review packet" in packet
    assert "could not be read" in _section(packet, "The diff")


def test_without_a_review_base_the_packet_says_so_and_the_history_stays_out(repo, flow):
    _build(repo, flow)
    assert "review_base" not in _state(repo)

    prompt = build_prompt(flow, "REVIEWING", _storage(repo))

    assert "## Review packet" in prompt
    assert "No review packet" in prompt
    assert "git diff HEAD" in prompt
    assert SUMMARY not in prompt


def test_the_packet_says_the_builders_account_is_left_out(repo, flow):
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))

    packet = _packet(repo)

    assert packet.lstrip().startswith("## Review packet")
    assert "builder" in packet.split("### The task")[0].lower()
    assert SUMMARY not in packet
