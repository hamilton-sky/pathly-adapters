"""POST /ops/export skill selection + GET /ops/export/skills tier listing."""

from __future__ import annotations

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_export_skills_lists_tiers(client):
    r = client.get("/ops/export/skills?adapter=claude")
    assert r.status_code == 200
    rows = r.get_json()["skills"]
    by = {s["name"]: s["default"] for s in rows}
    # Tier-1 on-ramps install by default…
    assert by.get("create-feature") is True
    assert by.get("post") is True
    # …plus the operational utilities (the picker hides defaults, so these drop out of it)…
    assert by.get("status") is True
    assert by.get("fsm-call") is True
    # …and the flag is the installer's constant, not a second copy that can drift.
    from install_cli.orchestrate import DEFAULT_EXPOSED_SKILLS

    assert {name for name, is_default in by.items() if is_default} == set(
        DEFAULT_EXPOSED_SKILLS
    )
    # …pipeline skills are export-only.
    assert by.get("build") is False
    assert by.get("goalize") is False
    # every row reports current install state (powers unexport in the picker)
    assert all(isinstance(s.get("installed"), bool) for s in rows)


def test_export_skills_reports_what_each_skill_requires(client):
    """The picker can show/disable what exporting a skill drags in (the installer adds it)."""
    rows = {
        s["name"]: s
        for s in client.get("/ops/export/skills?adapter=claude").get_json()["skills"]
    }
    assert rows["build"]["requires"] == ["review"]
    assert rows["review"]["requires"] == ["log-agent-done"]
    assert rows["status"]["requires"] == []
    assert all(isinstance(s["requires"], list) for s in rows.values())


def test_export_skills_rejects_bad_adapter(client):
    r = client.get("/ops/export/skills?adapter=nope")
    assert r.status_code == 400


def test_export_rejects_non_string_skills(client):
    r = client.post("/ops/export", json={"adapters": ["claude"], "skills": [1, 2]})
    assert r.status_code == 400


def test_run_export_threads_skill_flags(monkeypatch):
    from pathly_orchestrator.http_server.blueprints.ops import export as export_mod

    captured: dict = {}

    class _Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(
        export_mod.subprocess,
        "run",
        lambda cmd, **kw: captured.update(cmd=cmd) or _Result(),
    )

    # specific skills -> one --export per skill (+ --repair)
    export_mod._run_export("claude", True, skills=["build", "review"])
    assert captured["cmd"][1:4] == ["-m", "install_cli", "claude"]
    assert captured["cmd"].count("--export") == 2
    assert "build" in captured["cmd"] and "review" in captured["cmd"]
    assert "--repair" in captured["cmd"]

    # all_skills -> --all-skills, no --export, no --repair
    export_mod._run_export("codex", False, all_skills=True)
    assert "--all-skills" in captured["cmd"]
    assert "--export" not in captured["cmd"]
    assert "--repair" not in captured["cmd"]
