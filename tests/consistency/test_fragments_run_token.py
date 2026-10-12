"""Every board call in the core skills, fragments and agents sends the run token.

The server resolves who is calling from the `X-Pathly-Run-Token` header
(read-policy SPEC C4), so a board call that omits it posts as `anonymous`.
Agents reach the board in two written shapes under `src/pathly_data/core/`:

* a `curl` to `8765/comms`: the command (its line, plus following lines joined by
  a trailing backslash or an open quote) must carry the header itself;
* a bare pseudo-request line, `GET|POST|PUT|PATCH|DELETE [http://127.0.0.1:8765]/comms...`,
  in a markdown file: the agent turns it into a call, so the file must also tell it,
  outside any board curl, to send the header.

The scan is textual. A curl whose URL is a shell variable (`curl "$BASE/comms/post"`)
holds no `8765/comms` and is not seen, and a call written without a verb or without
the `/comms` path is not seen as a pseudo-request. Pseudo-requests are read in
markdown only, so a `/comms` mention in a yaml comment is not an agent instruction.
"""

from __future__ import annotations

import re
import shutil

import pytest

from tests._paths import SRC

_CORE = SRC / "pathly_data" / "core"
_HEADER = '-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"'
_TARGET = "8765/comms"
_PSEUDO = re.compile(
    r"\b(?:GET|POST|PUT|PATCH|DELETE) (?:http://127\.0\.0\.1:8765)?/comms"
)


def _goes_on(text, quote):
    """Walk one line of a shell command. Return (open quote or None, continues)."""
    text = text.rstrip()
    i = 0
    while i < len(text):
        ch = text[i]
        if quote == "'":
            quote = None if ch == "'" else quote
        elif ch == "\\":
            if i + 1 == len(text):
                return quote, True
            i += 1
        elif quote is None and ch in "'\"":
            quote = ch
        elif ch == quote:
            quote = None
        i += 1
    return quote, quote is not None


def _board_curls(text):
    """Return (first, last, command) for each `curl` to the board in `text`.

    `first` and `last` are 0-based line indexes. A command is its own line plus
    each next line while the previous one ends in a backslash or leaves a quote open.
    """
    lines = text.splitlines()
    found = []
    for first, line in enumerate(lines):
        pos = line.find("curl")
        if pos < 0:
            continue
        last, quote = first, None
        quote, goes_on = _goes_on(line[pos:], quote)
        while goes_on and last + 1 < len(lines):
            last += 1
            quote, goes_on = _goes_on(lines[last], quote)
        command = "\n".join(lines[first : last + 1])
        if _TARGET in command:
            found.append((first, last, command))
    return found


def _curls_missing_header(text):
    """Return (line_no, line) for each board curl without the header."""
    lines = text.splitlines()
    return [
        (first + 1, lines[first].strip())
        for first, _, command in _board_curls(text)
        if _HEADER not in command
    ]


def _pseudo_requests(text):
    """Return (line_no, line) for each pseudo-request line outside a board curl."""
    inside = {
        n for first, last, _ in _board_curls(text) for n in range(first, last + 1)
    }
    return [
        (n + 1, line.strip())
        for n, line in enumerate(text.splitlines())
        if n not in inside and _PSEUDO.search(line)
    ]


def _pseudo_requests_without_instruction(text):
    """Return the pseudo-request lines when no line outside a board curl names the header."""
    pseudo = _pseudo_requests(text)
    inside = {
        n for first, last, _ in _board_curls(text) for n in range(first, last + 1)
    }
    told = any(
        _HEADER in line for n, line in enumerate(text.splitlines()) if n not in inside
    )
    return [] if told else pseudo


def _files(root, pick):
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and pick(p.read_text(encoding="utf-8"), p)
    )


def _has_board_curls(text, path):
    return bool(_board_curls(text))


def _has_pseudo_requests(text, path):
    return path.suffix == ".md" and bool(_pseudo_requests(text))


def _id(path):
    return str(path.relative_to(_CORE))


def test_the_scan_finds_the_board_callers():
    # Guards the scan itself: an empty list would make every check below pass.
    assert len(_files(_CORE, _has_board_curls)) >= 20
    assert len(_files(_CORE, _has_pseudo_requests)) >= 8


@pytest.mark.parametrize("path", _files(_CORE, _has_board_curls), ids=_id)
def test_every_board_curl_sends_the_run_token(path):
    assert _curls_missing_header(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("path", _files(_CORE, _has_pseudo_requests), ids=_id)
def test_a_file_with_pseudo_requests_tells_the_agent_to_send_the_token(path):
    text = path.read_text(encoding="utf-8")
    assert _pseudo_requests_without_instruction(text) == []


def test_removing_the_header_from_any_one_file_is_caught(tmp_path):
    """Temp copies of the real files: stripping one file's header fails the check."""
    stripped = 0
    for path in _files(_CORE, _has_board_curls):
        text = path.read_text(encoding="utf-8")
        copy = tmp_path / path.name
        shutil.copy(path, copy)
        copy.write_text(text.replace(_HEADER, ""), encoding="utf-8")
        assert _curls_missing_header(copy.read_text(encoding="utf-8")) != [], _id(path)
        stripped += 1
    assert stripped >= 20


def test_removing_the_instruction_from_any_one_file_is_caught(tmp_path):
    """Temp copies of the real files: stripping the instruction line fails the check."""
    for path in _files(_CORE, _has_pseudo_requests):
        text = path.read_text(encoding="utf-8")
        inside = {n for f, last, _ in _board_curls(text) for n in range(f, last + 1)}
        kept = [
            line
            for n, line in enumerate(text.splitlines())
            if n in inside or _HEADER not in line
        ]
        copy = tmp_path / path.name
        copy.write_text("\n".join(kept), encoding="utf-8")
        assert (
            _pseudo_requests_without_instruction(copy.read_text(encoding="utf-8")) != []
        ), _id(path)


CURL_A = 'curl -s -X POST http://127.0.0.1:8765/comms/post -d "{}"'


def test_two_curls_one_missing_flags_only_that_one():
    text = f"{CURL_A} {_HEADER}\n\n{CURL_A}\n"
    assert _curls_missing_header(text) == [(3, CURL_A)]


def test_header_on_a_later_continuation_line_counts():
    text = f'curl -s -X POST http://127.0.0.1:8765/comms/post \\\n  -d "{{}}" \\\n  {_HEADER}\n'
    assert _curls_missing_header(text) == []


def test_a_continuation_that_never_reaches_the_header_is_flagged():
    text = 'curl -s -X POST http://127.0.0.1:8765/comms/post \\\n  -d "{}"\n' + _HEADER
    assert len(_curls_missing_header(text)) == 1


def test_a_blank_line_after_a_backslash_ends_the_command():
    # The blank line ends curl 1, so curl 2's header must not count for curl 1.
    first = "curl -s -X POST http://127.0.0.1:8765/comms/post \\"
    second = f"curl -s {_HEADER} -X POST http://127.0.0.1:8765/comms/post"
    assert _curls_missing_header(f"{first}\n\n{second}\n") == [(1, first)]


def test_header_after_a_multiline_body_counts():
    body = "curl -s -X POST http://127.0.0.1:8765/comms/post -d '{\n  \"a\": 1\n}' "
    assert _curls_missing_header(body + _HEADER + "\n") == []
    assert len(_curls_missing_header(body + "-H 'X-Other: 1'\n")) == 1


def test_a_curl_to_a_shell_variable_url_is_not_seen():
    # Documented limit: only a literal `8765/comms` marks a board curl.
    assert _curls_missing_header('curl -s "$BASE/comms/post"\n') == []


def test_pseudo_requests_need_an_instruction_outside_the_curls():
    pseudo = "```\nGET /comms/tasks?ready=true\n```\n"
    curl = f"curl -s {_HEADER} -X POST http://127.0.0.1:8765/comms/post\n"
    note = f"Send `{_HEADER}` on every call.\n"
    assert _pseudo_requests_without_instruction(pseudo) == [
        (2, "GET /comms/tasks?ready=true")
    ]
    # The header inside a curl does not tell the agent anything about the bare requests.
    assert _pseudo_requests_without_instruction(pseudo + curl) != []
    assert _pseudo_requests_without_instruction(pseudo + note) == []
    # A `-X POST http://127.0.0.1:8765/comms` inside a curl is the curl, not a pseudo-request.
    assert _pseudo_requests(curl) == []
    assert _pseudo_requests("POST http://127.0.0.1:8765/comms/post\n") != []
