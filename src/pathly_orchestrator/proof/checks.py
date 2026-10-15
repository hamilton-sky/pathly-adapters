"""Parse and run ```check blocks in a task's text.

Ported from feature-flow's ``proof.checks_in`` / ``run_checks`` (MIT). Two differences: every
```check fence anywhere in the text counts (task text has no ``## Done when`` heading), and each
command runs through :func:`proof.command.run_command` (no shell) in the caller's ``cwd``.

Grammar, one item per line inside the fence::

    $ <command>         starts a check
    exit <N>            the exit code it must give (default ``exit 0``)
    exit nonzero        any exit code but 0
    prints <text>       its output must contain <text> (repeatable)
    # comment           ignored, as are blank lines
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .command import clip, run_command

FENCE = "```"
OPEN = FENCE + "check"


@dataclass(frozen=True)
class Check:
    """One `$ <command>`: exit is an int or "nonzero"; prints holds the substrings the output must contain."""

    command: str
    exit: int | str = 0
    prints: tuple[str, ...] = ()


class ParseError(ValueError):
    """A check block the parser cannot read. The message quotes the line."""


def checks_in(text: str) -> list[Check]:
    """The checks of every ```check block in the text, in order."""
    checks: list[Check] = []
    fence: str | None = None  # None outside a fence, else the line that opened it
    command: str | None = None  # the check being read
    exit_value: int | str = 0
    prints: list[str] = []
    exit_seen = False

    def finish() -> None:
        if command is not None:
            checks.append(Check(command, exit_value, tuple(prints)))

    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    for line in lines:
        if fence is None:
            if line.startswith(FENCE):
                fence = line
            continue
        if line == FENCE:
            if fence == OPEN:
                finish()
                command = None
            fence = None
            continue
        if fence != OPEN:
            continue
        if line.strip() == "" or line.startswith("#"):
            continue
        if line.startswith("$ ") and line[2:].strip():
            finish()
            command, exit_value, prints, exit_seen = line[2:].strip(), 0, [], False
            continue
        word = line.split(" ", 1)[0]
        if word in ("exit", "prints") and command is None:
            raise ParseError(
                "check block: %r comes before the first `$ <command>` line" % line
            )
        if word == "exit":
            value = line[len("exit ") :].strip() if line.startswith("exit ") else ""
            if exit_seen:
                raise ParseError(
                    "check block: %r is a second exit line for %r" % (line, command)
                )
            if value == "nonzero":
                exit_value = "nonzero"
            elif re.fullmatch(r"[0-9]+", value):
                exit_value = int(value)
            else:
                raise ParseError(
                    "check block: %r needs a whole number or `nonzero`" % line
                )
            exit_seen = True
            continue
        if word == "prints" and line.startswith("prints ") and line[len("prints ") :]:
            prints.append(line[len("prints ") :])
            continue
        raise ParseError(
            "check block: cannot read %r (expected `$ <command>`, `exit <N>`, "
            "`exit nonzero`, `prints <text>`, `#` or a blank line)" % line
        )
    if fence == OPEN:
        raise ParseError(
            "check block: %r is never closed by a %s line" % (fence, FENCE)
        )
    return checks


def _wanted(check: Check) -> str:
    want = "exit nonzero" if check.exit == "nonzero" else f"exit {check.exit}"
    return want + "".join(" and output containing %r" % text for text in check.prints)


def run_checks(
    checks: list[Check], cwd: str | Path, timeout: float
) -> tuple[bool, str]:
    """Run every check (none is skipped after a failure); timeout is seconds per command.

    Returns (ok, report). The report has one block per failing check: the command, what was
    wanted, what happened and its clipped output. A passing run gives ``(True, "")``.
    """
    failures = []
    for check in checks:
        result = run_command(check.command, cwd, timeout)
        output = result.output.replace("\r\n", "\n")
        if result.timed_out:
            got = "timed out after %ss" % format(timeout, "g")
        elif result.code is None:
            got = "could not run: %s" % result.error
        else:
            if check.exit == "nonzero":
                code_ok = result.code != 0
            else:
                code_ok = result.code == check.exit
            if code_ok and all(text in output for text in check.prints):
                continue
            got = "exit %d" % result.code
        failures.append(
            "$ %s\n  wanted: %s\n  got: %s\n  its output:\n%s"
            % (check.command, _wanted(check), got, clip(output) or "(no output)")
        )
    return not failures, "\n".join(failures)
