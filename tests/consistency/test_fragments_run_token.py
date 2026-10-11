"""Every board `curl` in the core skills, fragments and agents sends the run token.

Agents reach the board through `curl` lines under `src/pathly_data/core/`.
The server resolves who is calling from the `X-Pathly-Run-Token` header
(read-policy SPEC C4), so a curl to `8765/comms` that omits it posts as
`anonymous`. This test fails on any such curl, so a new fragment cannot forget it.
"""

from __future__ import annotations

import shutil

import pytest

from tests._paths import SRC

_CORE = SRC / "pathly_data" / "core"
_HEADER = '-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"'
_TARGET = "8765/comms"


def _board_curls(path):
    """Return (line_no, line, command) for each `curl` to the board in a file.

    A curl command is its own line plus any following lines joined by a
    trailing backslash.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    found = []
    for i, line in enumerate(lines):
        if "curl" not in line:
            continue
        command = line
        j = i
        while command.rstrip().endswith("\\") and j + 1 < len(lines):
            j += 1
            command += "\n" + lines[j]
        if _TARGET in command:
            found.append((i + 1, line.strip(), command))
    return found


def _files_with_board_curls(root):
    return sorted(p for p in root.rglob("*") if p.is_file() and _board_curls(p))


def _curls_missing_header(path):
    return [
        (n, line) for n, line, command in _board_curls(path) if _HEADER not in command
    ]


def test_the_scan_finds_the_board_callers():
    # Guards the scan itself: an empty list would make every check below pass.
    assert len(_files_with_board_curls(_CORE)) >= 20


@pytest.mark.parametrize(
    "path", _files_with_board_curls(_CORE), ids=lambda p: str(p.relative_to(_CORE))
)
def test_every_board_curl_sends_the_run_token(path):
    assert _curls_missing_header(path) == []


@pytest.mark.parametrize(
    "path", _files_with_board_curls(_CORE), ids=lambda p: str(p.relative_to(_CORE))
)
def test_removing_the_header_from_a_file_is_caught(path, tmp_path):
    """The check fails if the header is removed from any one file (temp copy)."""
    copy = tmp_path / path.name
    shutil.copy(path, copy)
    copy.write_text(
        path.read_text(encoding="utf-8").replace(_HEADER, ""), encoding="utf-8"
    )
    assert _curls_missing_header(copy) != []
