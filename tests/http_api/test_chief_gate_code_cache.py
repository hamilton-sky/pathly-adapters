"""chief-agent 08 (round 8): a chief's code query is answered from its own project.

``POST /code/query`` caches what a project's graph answered. The caches had no project in their
key, so a block built for a call on project B (a human's, or another chief's) was served to a
chief on project A whose call the gate had passed as bound: the same relative target with the
same bytes, or a directory such as ``src`` (its content hash is ``""`` in every project). The
unit tests of the two caches are in ``tests/code_intel/test_code_cache_projects.py``; this is
the whole path, through the gate and the real ``cli`` provider with a graph that answers for the
project it was asked about.
"""

from __future__ import annotations

import json
import shutil

import pytest

from chief_gate_support import (
    TIERS,
    _chief,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)

SAME_BYTES = "def a_function():\n    return 1\n"


@pytest.fixture()
def graph(monkeypatch, project, other_project):
    """Two indexed projects and a ``codebase-memory-mcp`` that answers one row, named after the
    graph project it was asked about. Returns the list of graph projects it was asked about.
    """
    from pathly_orchestrator.http_server.blueprints.code import query
    from pathly_orchestrator.runner import code_context_cli
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    for root, own in ((project, "only_a.py"), (other_project, "only_b.py")):
        (root / "src").mkdir()
        (root / "src" / "a.py").write_text(SAME_BYTES)
        (root / "src" / own).write_text("x = 1\n")
    indexed = json.dumps(
        {
            "projects": [
                {"name": "graph-a", "root_path": str(project)},
                {"name": "graph-b", "root_path": str(other_project)},
            ]
        }
    )
    asked: list[str] = []
    real_which = shutil.which

    def which(cmd, *args, **kwargs):
        return (
            "/canned/tool"
            if cmd == "codebase-memory-mcp"
            else real_which(cmd, *args, **kwargs)
        )

    def run(self, exe, args):
        if "list_projects" in args:
            return indexed
        name = json.loads(args[-1])["project"]
        asked.append(name)
        return json.dumps({"rows": [[f"sym_of_{name}", 7, 9]]})

    monkeypatch.setattr(
        "pathly_orchestrator.runner.code_context._resolve_backend", lambda: "cli"
    )
    monkeypatch.setattr(shutil, "which", which)
    monkeypatch.setattr(CliProvider, "_run", run)
    monkeypatch.setattr(query, "_QUERY_CACHE", {})
    monkeypatch.setattr(code_context_cli, "_CLI_CACHE", {})
    return asked


def _query(client, root, target, headers=None):
    body = {
        "op": "symbol",
        "target": target,
        "role": "architect",
        "scope": "(interactive)",
        "project_root": str(root),
    }
    return client.post("/code/query", json=body, headers=headers or {})


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("target", ["src/a.py", "src"])
def test_a_chief_is_not_served_the_block_built_for_another_project(
    client, graph, project, other_project, tier, target
):
    human = _query(client, other_project, target)
    assert human.get_json()["result"].count("sym_of_graph-b") == 1, human.get_json()

    resp = _query(client, project, target, _chief(tier, project).headers)

    assert _passed(resp), resp.get_data(as_text=True)
    body = resp.get_json()
    assert "sym_of_graph-a" in body["result"], body
    assert "sym_of_graph-b" not in body["result"], body
    assert body["cached"] is False


def test_a_chief_that_asks_again_is_answered_from_the_cache(client, graph, project):
    chief = _chief("status", project)

    first = _query(client, project, "src/a.py", chief.headers).get_json()
    second = _query(client, project, "src/a.py", chief.headers).get_json()

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["result"] == first["result"]
    assert graph == ["graph-a"]


@pytest.mark.parametrize("cleared", ["provider cache", "gateway cache"])
def test_each_cache_keeps_the_projects_apart_on_its_own(
    client, graph, project, other_project, cleared
):
    """The route and the provider each cache the answer for a file, so clearing one between the
    two calls leaves the other holding project B's block: each must keep the projects apart
    without the other's help.
    """
    from pathly_orchestrator.http_server.blueprints.code import query
    from pathly_orchestrator.runner import code_context_cli

    _query(client, other_project, "src/a.py")
    (
        code_context_cli._CLI_CACHE
        if cleared == "provider cache"
        else query._QUERY_CACHE
    ).clear()

    body = _query(
        client, project, "src/a.py", _chief("status", project).headers
    ).get_json()

    assert "sym_of_graph-a" in body["result"], body
    assert "sym_of_graph-b" not in body["result"], body
