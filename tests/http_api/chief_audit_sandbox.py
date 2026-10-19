"""The sandbox fixture of the chief gate audit (chief-agent 08, rounds 6 and 7).

``world`` builds three directories (the chief's project, another project, the server's working
directory) under a fake home, a seeded board, a spawn host that spawns nothing and the file
system audit of ``chief_audit_support``. Two test files use it: ``test_chief_gate_audit.py``
(hostile values in every key of every route) and ``test_chief_gate_separators.py`` (the spellings
of the chief's own root).

The code-intelligence backend is a canned ``cli`` one: the real ``/code/query`` path
(``_content_hash``, ``CliProvider._file_hash`` and ``_file_section``) runs, against a
``codebase-memory-mcp`` that answers from a table. A test that imports ``world`` imports
``app``, ``client``, ``project`` and ``other_project`` from ``chief_gate_support`` too.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from types import SimpleNamespace

import pytest
from chief_audit_support import zones
from chief_audit_world import DEMO, World, settle

CODE_TOOL = "codebase-memory-mcp"


def drain_the_mirrors() -> None:
    """Let the debounced board and event mirrors write what they were asked to: flush, wait out
    one tick (a write the flusher thread took first finishes meanwhile), flush again.
    """
    from pathly_orchestrator import board_mirror, event_mirror
    from pathly_orchestrator.db.connection import get_db

    board_mirror.flush_dirty(get_db())
    event_mirror.flush_dirty(get_db())
    time.sleep(max(board_mirror.DEBOUNCE_SECONDS, event_mirror.DEBOUNCE_SECONDS) + 0.3)
    board_mirror.flush_dirty(get_db())
    event_mirror.flush_dirty(get_db())


def _canned_code_backend(monkeypatch, project) -> None:
    """``/code/query`` answers through the ``cli`` backend, whose binary is a function: one
    indexed project (the chief's) and one row per file. Without it the route stops at "backend
    none" before it reads the target.
    """
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    projects = json.dumps({"projects": [{"name": "audit", "root_path": str(project)}]})
    rows = json.dumps({"rows": [["a_function", 1, 2]]})
    real_which = shutil.which

    def which(cmd, *args, **kwargs):
        return f"/audit/{cmd}" if cmd == CODE_TOOL else real_which(cmd, *args, **kwargs)

    def run(self, exe, args):
        return projects if "list_projects" in args else rows

    monkeypatch.setattr(
        "pathly_orchestrator.runner.code_context._resolve_backend", lambda: "cli"
    )
    monkeypatch.setattr(shutil, "which", which)
    monkeypatch.setattr(CliProvider, "_run", run)


@pytest.fixture()
def world(app, client, project, other_project, tmp_path, monkeypatch):
    """Three directories, a seeded board, a spawn host that spawns nothing, and the audit."""
    server = tmp_path / "server"
    server.mkdir()
    (other_project / "pathly" / "features" / DEMO).mkdir(parents=True)
    (other_project / "pathly" / "features" / DEMO / "PLAN.md").write_text("# other\n")
    # A relative entry of sys.path would make a lazy import search the server's directory.
    monkeypatch.setattr(sys, "path", [os.path.abspath(p or ".") for p in sys.path])
    monkeypatch.chdir(server)
    # A view that raises on a hostile value answers 500 as it does in production; the test
    # client would raise it into the test instead.
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)

    from pathly_orchestrator.supervisor import board_lock, file_claims, registry

    board_lock._held.clear()
    registry._registry.clear()
    monkeypatch.setattr(file_claims, "_claims", {})
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.board_run._default_spawn",
        lambda **kwargs: {"result": "a real analysis of the board"},
    )
    monkeypatch.setattr(
        "pathly_orchestrator.http_server.sse._broadcast_runner", lambda *a, **k: None
    )

    def loop(state, broadcast_fn=None):
        state.status = "done"

    monkeypatch.setattr("pathly_orchestrator.supervisor.orchestrator._loop", loop)
    _canned_code_backend(monkeypatch, project)

    audit = zones(project, other_project, server, tmp_path)
    audit.label = "seeding"
    with audit:
        built = World(client, project, other_project, server)
        # The seeding is a human's, who may write anywhere (a post indexes its artifact on a
        # background thread): only the chief's requests are judged.
        settle()
        time.sleep(0.3)
        audit.violations.clear()
        audit.seen.clear()
        yield SimpleNamespace(world=built, audit=audit)
        settle()
    board_lock._held.clear()
    registry._registry.clear()
