"""chief-agent 08 (round 7): the ``cli`` code backend builds its graph query safely.

``CliProvider._file_section`` puts the last two segments of a ``/code/query`` target into the
Cypher it sends to ``codebase-memory-mcp``, inside a double-quoted string. A target is a request
string (a chief sends one), so a quote in it must stay inside the string: it may not end the
literal and add conditions of its own. The same method hashes the file to key its cache; a
relative path is read under the project the call names, not the server's working directory.
"""

from __future__ import annotations

import hashlib
import json

import pytest

TAIL_PREFIX = 'MATCH (n) WHERE n.file_path CONTAINS "'
AFTER_LITERAL = ' AND n.label IN ["Function","Method","Class"] '


@pytest.fixture()
def sent(monkeypatch):
    """The Cypher strings a provider sends, with a graph that answers one row to each."""
    from pathly_orchestrator.runner import code_context_cli
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    queries: list[str] = []

    def run(self, exe, args):
        queries.append(json.loads(args[-1])["query"])
        return json.dumps({"rows": [["a_function", 1, 2]]})

    monkeypatch.setattr(CliProvider, "_run", run)
    monkeypatch.setattr(code_context_cli, "_CLI_CACHE", {})
    return queries


def _literal(cypher: str) -> tuple[str, str]:
    """Read the string literal that follows ``CONTAINS`` as a Cypher reader does: the value it
    holds (a backslash escapes the next character) and everything after its closing quote.
    """
    assert cypher.startswith(TAIL_PREFIX), cypher
    rest = cypher[len(TAIL_PREFIX) :]
    value, i = [], 0
    while i < len(rest):
        char = rest[i]
        if char == "\\":
            value.append(rest[i + 1])
            i += 2
            continue
        if char == '"':
            return "".join(value), rest[i + 1 :]
        value.append(char)
        i += 1
    raise AssertionError(f"the string literal is never closed: {cypher}")


@pytest.mark.parametrize(
    "path",
    [
        'a" OR 1=1 /x',
        'src/x" OR n.name <> "',
        '"/"',
        'dir/we"ird"/x.py',
        'src/x\\" OR 1=1 //',
    ],
)
def test_a_quote_in_a_target_cannot_end_the_string_literal(sent, path):
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    CliProvider()._file_section("exe", "proj", path)

    assert len(sent) == 1
    value, after = _literal(sent[0])
    assert after.startswith(AFTER_LITERAL), after
    assert after == (
        AFTER_LITERAL + "RETURN n.name, n.in_degree, n.out_degree "
        "ORDER BY n.in_degree DESC LIMIT 12"
    )
    tail = "/".join(path.replace("\\", "/").rstrip("/").split("/")[-2:])
    assert value == tail


def test_an_ordinary_target_is_matched_as_before(sent):
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    CliProvider()._file_section("exe", "proj", "/work/repo/src/pkg/mod.py")

    assert sent == [
        'MATCH (n) WHERE n.file_path CONTAINS "pkg/mod.py" '
        'AND n.label IN ["Function","Method","Class"] '
        "RETURN n.name, n.in_degree, n.out_degree "
        "ORDER BY n.in_degree DESC LIMIT 12"
    ]


def test_a_relative_target_is_hashed_under_the_project_not_the_working_directory(
    sent, tmp_path, monkeypatch
):
    """The cache key is the file's hash, so the file read is observable: the chief's project
    holds one ``src/x.py``, the server's working directory another.
    """
    from pathly_orchestrator.runner import code_context_cli
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    project = tmp_path / "proj"
    server = tmp_path / "server"
    for folder, text in ((project, b"project\n"), (server, b"server\n")):
        (folder / "src").mkdir(parents=True)
        (folder / "src" / "x.py").write_bytes(text)
    monkeypatch.chdir(server)

    section = CliProvider()._file_section(
        "exe", "proj", "src/x.py", project_root=str(project)
    )

    assert section.startswith("### src/x.py")
    keys = list(code_context_cli._CLI_CACHE)
    assert keys == [("src/x.py", hashlib.sha1(b"project\n").hexdigest())], keys


def test_build_block_gives_the_project_to_the_section(monkeypatch, tmp_path):
    from pathly_orchestrator.runner import code_context_cli
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    seen = []

    def run(self, exe, args):
        if "list_projects" in args:
            return json.dumps({"projects": [{"name": "p", "root_path": str(tmp_path)}]})
        return json.dumps({"rows": []})

    def section(self, exe, project, path, project_root=""):
        seen.append((project, path, project_root))
        return ""

    monkeypatch.setattr("shutil.which", lambda _t: "exe")
    monkeypatch.setattr(CliProvider, "_run", run)
    monkeypatch.setattr(CliProvider, "_file_section", section)
    monkeypatch.setattr(code_context_cli, "_CLI_CACHE", {})

    CliProvider().build_block("s", ["src/x.py"], "builder", 1500, str(tmp_path))

    assert seen == [("p", "src/x.py", str(tmp_path))]
