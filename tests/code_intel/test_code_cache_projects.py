"""chief-agent 08 (round 8): a code answer cached for one project is never served to another.

``POST /code/query`` keeps two caches, and neither had the project in its key. ``_QUERY_CACHE``
(the gateway, in ``blueprints/code/query.py``) was keyed by the operation, the target, the
target's content hash and the backend; ``_CLI_CACHE`` (the ``cli`` backend, in
``runner/code_context_cli.py``) by the path and the hash. A relative target such as ``src/a.py``
has the same key in every project that holds the same bytes, and a directory has the hash ``""``
in all of them, so the block built for project B was served to a call on project A. Both keys now
hold the project root, and a target with no content hash (a directory, a missing file, a symbol)
is not cached at all: its answer cannot be told stale from fresh.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

SAME_BYTES = b"def f():\n    return 1\n"


@pytest.fixture()
def projects(tmp_path: Path):
    """Two projects that hold the same ``src/a.py`` and a ``src`` directory of their own."""
    a, b = tmp_path / "proj-a", tmp_path / "proj-b"
    for root, own in ((a, "only_a.py"), (b, "only_b.py")):
        (root / "src").mkdir(parents=True)
        (root / "src" / "a.py").write_bytes(SAME_BYTES)
        (root / "src" / own).write_text("x = 1\n")
    return a, b


# --- the gateway cache (the route) ----------------------------------------------------------


@pytest.fixture()
def gateway(monkeypatch):
    """The ``/code/query`` route with a backend that names the project it answered for."""
    import pathly_orchestrator.runner.code_context as cc
    from pathly_orchestrator.http_server.blueprints.code import query

    monkeypatch.setattr(query, "_QUERY_CACHE", {})
    monkeypatch.setattr(cc, "maybe_reindex", lambda *a, **k: None)
    calls: list[str] = []

    def build_block(scope, files, role, budget, project_root="", backend=None):
        calls.append(Path(project_root).name)
        return f"block of {Path(project_root).name}"

    monkeypatch.setattr(cc, "build_block", build_block)
    app = Flask(__name__)
    app.register_blueprint(query.bp)
    client = app.test_client()

    def ask(project, target, **extra):
        body = {
            "op": "symbol",
            "target": target,
            "role": "architect",
            "engine": "graph",
            "project_root": str(project),
            **extra,
        }
        resp = client.post("/code/query", json=body)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return resp.get_json()

    return SimpleNamespace(ask=ask, calls=calls)


@pytest.mark.parametrize("target", ["src/a.py", "src"])
def test_a_relative_target_is_not_served_from_another_projects_answer(
    gateway, projects, target
):
    a, b = projects

    first = gateway.ask(b, target)
    second = gateway.ask(a, target)

    assert first["result"] == "block of proj-b"
    assert second["result"] == "block of proj-a"
    assert second["cached"] is False
    assert gateway.calls == ["proj-b", "proj-a"]


def test_a_second_call_on_the_same_project_is_a_cache_hit(gateway, projects):
    a, _ = projects

    first = gateway.ask(a, "src/a.py")
    second = gateway.ask(a, "src/a.py")

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["result"] == "block of proj-a"
    assert gateway.calls == ["proj-a"]


def test_the_same_project_spelled_with_a_trailing_slash_shares_its_cache(
    gateway, projects
):
    a, _ = projects

    gateway.ask(a, "src/a.py")
    second = gateway.ask(str(a) + "/", "src/a.py")

    assert second["cached"] is True
    assert gateway.calls == ["proj-a"]


def test_an_edited_file_is_queried_again(gateway, projects):
    a, _ = projects
    gateway.ask(a, "src/a.py")

    (a / "src" / "a.py").write_bytes(SAME_BYTES + b"x = 2\n")
    second = gateway.ask(a, "src/a.py")

    assert second["cached"] is False
    assert gateway.calls == ["proj-a", "proj-a"]


@pytest.mark.parametrize("target", ["src", "missing.py", "parse_result"])
def test_a_target_with_no_content_hash_is_never_cached(gateway, projects, target):
    a, _ = projects

    first = gateway.ask(a, target)
    second = gateway.ask(a, target)

    assert first["cached"] is False
    assert second["cached"] is False
    assert gateway.calls == ["proj-a", "proj-a"]


# --- the cli backend's cache ----------------------------------------------------------------


@pytest.fixture()
def graph(monkeypatch):
    """A ``cli`` provider whose graph names the indexed project it answered for."""
    from pathly_orchestrator.runner import code_context_cli
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    queries: list[str] = []

    def run(self, exe, args):
        payload = json.loads(args[-1])
        queries.append(payload["project"])
        return json.dumps({"rows": [[f"sym_of_{payload['project']}", 1, 2]]})

    monkeypatch.setattr(CliProvider, "_run", run)
    monkeypatch.setattr(code_context_cli, "_CLI_CACHE", {})
    return queries


def _section(project_name: str, path: str, root: Path) -> str:
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    return CliProvider()._file_section(
        "exe", project_name, path, project_root=str(root)
    )


def test_the_cli_cache_is_per_project(graph, projects):
    a, b = projects

    first = _section("graph-b", "src/a.py", b)
    second = _section("graph-a", "src/a.py", a)

    assert "sym_of_graph-b" in first
    assert "sym_of_graph-a" in second
    assert "sym_of_graph-b" not in second
    assert graph == ["graph-b", "graph-a"]


def test_the_cli_cache_still_hits_for_the_same_project(graph, projects):
    a, _ = projects

    first = _section("graph-a", "src/a.py", a)
    second = _section("graph-a", "src/a.py", a)

    assert second == first
    assert graph == ["graph-a"]


def test_the_cli_provider_does_not_cache_a_directory(graph, projects):
    a, b = projects

    _section("graph-b", "src", b)
    second = _section("graph-a", "src", a)
    _section("graph-a", "src", a)

    assert "sym_of_graph-a" in second
    assert graph == ["graph-b", "graph-a", "graph-a"]
