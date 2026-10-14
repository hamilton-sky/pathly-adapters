"""build-proof 10: the REVIEWING prompt carries a Review packet, not the builder's summary.

The reviewer has no Bash, so ``team/review.md`` used to tell it to run a ``git diff`` it could not
run, and the prompt handed it the builder's own ``AGENT_DONE`` summaries. Now ``next_action``
stamps a working-tree ``tree`` into ``build_baseline``, leaving BUILDING copies it into
``review_base``, and ``build_prompt`` puts ``fsm_compose_review.review_packet`` (the frozen task
text, the diff of the last build, the supervisor's notes) in place of the history block for the
reviewer role. Every case runs a real ``git init`` project through the packaged ``team-build``
flow's ``next_action`` and ``complete_stage``.
"""

from __future__ import annotations

import re
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest
import yaml
from _paths import SRC

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.db.queries.comms_messages import update_message_text
from pathly_orchestrator.db.queries.comms_tasks import claim_task, complete_task
from pathly_orchestrator.fsm_compose import RUNNER_CONTRACT_BLOCK, build_prompt
from pathly_orchestrator.proof import tree

FEATURE = "pathly/features/demo"
FROZEN = "Make x two. FROZEN-TASK-TEXT\n"
SUMMARY = "BUILDER-SAYS-ALL-GOOD"
DIFF_LINE = "x = 2  # LINE-FROM-THE-DIFF"
NO_CHECK = "no check block: review its acceptance by reading the code"
LIMIT = 48 * 1024
SKILLS = SRC / "pathly_data" / "core" / "skills"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _write(root, "src/app.py", "x = 1\ny = 2\n")
    _write(root, FEATURE + "/IMPLEMENTATION_PLAN.md", "# Plan\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    # build_prompt would otherwise start a code-intel tool through the `auto` backend.
    set_setting(get_db(), "code_context.backend", "off")
    return root


@pytest.fixture
def flow() -> dict:
    text = (
        files("pathly_data")
        .joinpath("core/flows/team-build.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _storage(repo: Path) -> Path:
    return repo / FEATURE


def _args(repo: Path) -> dict:
    return {
        "flow": "team-build",
        "topic": "demo",
        "project_root": str(repo),
        "scope": "demo",
    }


def _state(repo: Path) -> dict:
    return eventlog.read_state(str(_storage(repo))) or {}


def _enter_building(repo: Path, flow: dict) -> None:
    """Put the feature in BUILDING and let ``next_action`` stamp ``build_baseline``."""
    eventlog.write_state(str(_storage(repo)), {"current": "BUILDING"}, flow)
    fsm_ops.next_action(_args(repo))


def _claim(text: str = FROZEN) -> str:
    conn = get_db()
    task_id = post_message(
        conn,
        board="feature",
        scope="demo",
        from_agent="planner",
        type="task",
        text=text,
    )
    assert claim_task(conn, task_id, "build")
    return task_id


def _build(repo: Path, flow: dict, edit: bool = True) -> str:
    """A BUILDING stage: baseline stamped, a task claimed, the builder edits and reports."""
    _enter_building(repo, flow)
    task_id = _claim()
    if edit:
        _write(repo, "src/app.py", "%s\ny = 2\n" % DIFF_LINE)
    eventlog.append_event(
        str(_storage(repo)),
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 1,
            "summary": SUMMARY,
            "outcome": "success",
        },
        flow=flow,
    )
    return task_id


def _packet(repo: Path) -> str:
    from pathly_orchestrator.fsm_compose_review import review_packet

    return review_packet(_storage(repo), str(repo), "feature", "demo", "")


def _section(packet: str, heading: str) -> str:
    found = re.search(
        r"^### %s\n(.*?)(?=^### |\Z)" % re.escape(heading), packet, re.S | re.M
    )
    assert found, "no '### %s' section in:\n%s" % (heading, packet[:2000])
    return found.group(1)


def _task_proof(repo: Path, task_id: str, checks: str, ts: str | None = None) -> None:
    event = {
        "type": "TASK_PROOF",
        "task_id": task_id,
        "claimed_at": "x",
        "run_id": "build",
        "checks": checks,
        "floor": "n/a",
        "warnings": [],
    }
    if ts is not None:
        event["ts"] = ts
    eventlog.append_event(str(_storage(repo)), event)


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

    diff = _section(_packet(repo), "The diff")

    assert len(diff.encode("utf-8")) <= LIMIT
    assert "value_0 = 0" in diff
    assert "value_3999 = 3999" in diff
    assert "value_2000 = 2000" not in diff
    assert "omitted" in diff


def test_a_diff_under_the_limit_is_not_clipped(repo, flow):
    _build(repo, flow)

    diff = _section(_packet(repo), "The diff")

    assert DIFF_LINE in diff
    assert "omitted" not in diff


def test_a_build_that_changed_nothing_says_so(repo, flow):
    _build(repo, flow, edit=False)

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


# --- supervisor notes --------------------------------------------------------------------


def test_the_notes_say_none_recorded_when_nothing_was_recorded(repo, flow):
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))

    notes = _section(_packet(repo), "Supervisor notes")

    assert "none recorded" in notes


@pytest.mark.parametrize(
    "checks, wanted",
    [
        ("passed", "checks passed"),
        ("failed", "checks failed"),
        ("none", NO_CHECK),
    ],
)
def test_the_notes_report_each_tasks_latest_check_result(repo, flow, checks, wanted):
    task_id = _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    _task_proof(repo, task_id, checks)

    notes = _section(_packet(repo), "Supervisor notes")

    assert task_id[:8] in notes
    assert wanted in notes
    assert "none recorded" not in notes


def test_the_notes_use_the_latest_task_proof_of_a_task(repo, flow):
    task_id = _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    _task_proof(repo, task_id, "failed")
    _task_proof(repo, task_id, "passed")

    notes = _section(_packet(repo), "Supervisor notes")

    assert "checks passed" in notes
    assert "checks failed" not in notes


def test_the_notes_ignore_a_task_proof_from_before_the_build(repo, flow):
    task_id = _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    _task_proof(repo, task_id, "failed", ts="2020-01-01T00:00:00Z")

    notes = _section(_packet(repo), "Supervisor notes")

    assert "checks failed" not in notes
    assert "none recorded" in notes


def test_the_notes_carry_the_warnings_of_the_latest_floor_check(repo, flow):
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    eventlog.append_event(
        str(_storage(repo)),
        {"type": "FLOOR_CHECKED", "warnings": ["OLDER-WARNING"]},
    )
    eventlog.append_event(
        str(_storage(repo)),
        {"type": "FLOOR_CHECKED", "warnings": ["fewer assertions in tests/test_a.py"]},
    )

    notes = _section(_packet(repo), "Supervisor notes")

    assert "fewer assertions in tests/test_a.py" in notes
    assert "OLDER-WARNING" not in notes
    assert "none recorded" not in notes


# --- the runner contract and the skills --------------------------------------------------


def test_the_runner_contract_forbids_spawning_a_role_for_a_feedback_file():
    assert "{" not in RUNNER_CONTRACT_BLOCK and "}" not in RUNNER_CONTRACT_BLOCK
    for part in (
        "never spawn another Pathly role",
        "planner, architect, po, designer, builder",
        "to resolve a feedback file",
        "write the feedback file and stop",
        "the supervisor routes it",
    ):
        assert part in RUNNER_CONTRACT_BLOCK, part


@pytest.mark.parametrize("skill", ["team/build", "team/review"])
def test_the_team_skills_leave_feedback_spawns_to_interactive_runs(skill):
    text = (SKILLS / (skill + ".md")).read_text(encoding="utf-8")

    assert "Interactive `/pathly` only" in text
    assert "feedback file" in text.split("Interactive `/pathly` only")[1][:600]


def test_team_review_pastes_the_packet_and_never_asks_the_reviewer_to_run_anything():
    text = (SKILLS / "team/review.md").read_text(encoding="utf-8")

    assert "git diff HEAD~1 HEAD" not in text
    assert "git diff --staged" not in text
    assert "### The task" in text and "### The diff" in text
    assert "VERIFY.md" in text  # named only to say it is never passed on
    assert "Never pass" in text
