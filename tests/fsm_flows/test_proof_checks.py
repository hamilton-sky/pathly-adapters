"""Task check blocks (``proof/checks.py``) and the shared command runner (``proof/command.py``).

Real subprocesses (``sys.executable -c …``), for the same reason as test_command_gate.py: a
check whose whole value is "it actually ran the command" is not worth testing against a mock.
"""

from __future__ import annotations

import json
import sys

import pytest

from pathly_orchestrator.proof.checks import Check, ParseError, checks_in, run_checks
from pathly_orchestrator.proof.command import run_command, to_argv

pytestmark = pytest.mark.no_pathly_autouse

FENCE = "```"


def _py(code: str) -> str:
    """A shell-free command string that runs `code` in this interpreter."""
    return json.dumps([sys.executable, "-c", code])


def _block(*lines: str) -> str:
    return "\n".join([FENCE + "check", *lines, FENCE])


# ── Parsing ───────────────────────────────────────────────────────────────────


def test_two_fences_anywhere_in_the_text_parse_in_order():
    """Task text has no `## Done when` heading, so every check fence counts."""
    text = "\n".join(
        [
            "Build the widget and wire it into the panel.",
            "",
            _block(
                "# the unit tests",
                "$ python -m pytest tests/test_widget.py -q",
                "prints passed",
            ),
            "",
            "## Notes",
            "",
            FENCE + "python",
            "$ this fence is not a check block",
            FENCE,
            "",
            _block("", '$ python -c "print(1)"', "exit 2"),
        ]
    )

    assert checks_in(text) == [
        Check("python -m pytest tests/test_widget.py -q", 0, ("passed",)),
        Check('python -c "print(1)"', 2, ()),
    ]


def test_exit_nonzero_and_two_prints_lines():
    text = _block("$ make lint", "exit nonzero", "prints error", "prints two words")

    assert checks_in(text) == [Check("make lint", "nonzero", ("error", "two words"))]


def test_text_without_a_check_fence_has_no_checks():
    assert checks_in("Just prose.\n\n" + FENCE + "\n$ ls\n" + FENCE + "\n") == []


def test_prints_before_any_command_is_a_parse_error():
    with pytest.raises(ParseError, match="comes before the first"):
        checks_in(_block("prints passed", "$ python -m pytest"))


def test_unclosed_fence_is_a_parse_error():
    with pytest.raises(ParseError, match="never closed"):
        checks_in("intro\n" + FENCE + "check\n$ python -m pytest\nexit 0\n")


@pytest.mark.parametrize(
    "lines, message",
    [
        (["$ a", "exit 0", "exit 1"], "second exit line"),
        (["$ a", "exit sometimes"], "whole number or `nonzero`"),
        (["$ a", "run it twice"], "cannot read"),
    ],
)
def test_unreadable_lines_are_parse_errors(lines, message):
    with pytest.raises(ParseError, match=message):
        checks_in(_block(*lines))


# ── Running ───────────────────────────────────────────────────────────────────


def test_a_failing_check_reports_command_wanted_and_got(tmp_path):
    command = _py("print('E: widget is undefined'); raise SystemExit(3)")

    ok, report = run_checks([Check(command)], tmp_path, 30)

    assert ok is False
    assert "$ " + command in report
    assert "wanted: exit 0" in report
    assert "got: exit 3" in report
    assert "E: widget is undefined" in report  # the real output comes back


def test_missing_text_in_the_output_fails_a_zero_exit(tmp_path):
    ok, report = run_checks(
        [Check(_py("print('3 failed')"), 0, ("passed",))], tmp_path, 30
    )

    assert ok is False
    assert "wanted: exit 0 and output containing 'passed'" in report
    assert "got: exit 0" in report


def test_a_command_that_does_not_exist_could_not_run(tmp_path):
    ok, report = run_checks([Check("pathly-no-such-binary-xyz --run")], tmp_path, 30)

    assert ok is False
    assert "$ pathly-no-such-binary-xyz --run" in report
    assert "could not run" in report


def test_a_sleeping_command_is_reported_as_timed_out(tmp_path):
    ok, report = run_checks([Check(_py("import time; time.sleep(30)"))], tmp_path, 1)

    assert ok is False
    assert "timed out after 1s" in report


def test_every_check_runs_after_a_failure(tmp_path):
    first = _py("raise SystemExit(5)")
    second = _py("raise SystemExit(6)")

    ok, report = run_checks([Check(first), Check(second)], tmp_path, 30)

    assert ok is False
    assert "$ " + first in report and "got: exit 5" in report
    assert "$ " + second in report and "got: exit 6" in report


def test_a_passing_block_gives_true_and_an_empty_report(tmp_path):
    text = _block(
        "$ " + _py("print('4 passed in 0.1s')"),
        "prints passed",
        "$ " + _py("raise SystemExit(4)"),
        "exit nonzero",
        "$ " + _py("raise SystemExit(4)"),
        "exit 4",
    )

    assert run_checks(checks_in(text), tmp_path, 30) == (True, "")


def test_checks_run_in_the_given_directory(tmp_path):
    check = Check(_py("import os; print(os.getcwd())"), 0, (str(tmp_path),))

    assert run_checks([check], tmp_path, 30) == (True, "")


# ── The shared command runner ─────────────────────────────────────────────────


def test_run_command_passes_extra_env_and_captures_both_streams(tmp_path):
    code = (
        "import os, sys; "
        "print(os.environ['PATHLY_PROOF_TEST']); "
        "print('on stderr', file=sys.stderr)"
    )

    result = run_command(_py(code), tmp_path, 30, {"PATHLY_PROOF_TEST": "seen"})

    assert result.code == 0
    assert result.timed_out is False
    assert result.error is None
    assert "seen" in result.output
    assert "on stderr" in result.output


def test_run_command_never_raises_on_an_unparseable_command(tmp_path):
    result = run_command('["unterminated", ', tmp_path, 30)

    assert result.code is None
    assert result.timed_out is False
    assert result.error


def test_to_argv_takes_a_list_as_it_is():
    assert to_argv(["python", "-m", "pytest"]) == ["python", "-m", "pytest"]
