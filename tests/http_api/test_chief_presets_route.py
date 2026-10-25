"""GET /chief/presets: the styles Studio's Chief launcher lists, with the tier the server enforces.

The tier must be the one ``open_chief`` would resolve for the same preset name
(``chief_tiers.resolve_preset_tier``), so a user file that overrides a built-in name, or names a
tier of its own, is reported as the server will treat it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.skills import prompt_files
from pathly_orchestrator.supervisor.chief_presets import BUILT_IN


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def global_prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "global-prompts"
    monkeypatch.setattr(prompt_files, "_global_root", lambda: root)
    return root


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    return root


def _write(root: Path, name: str, body: str) -> None:
    d = root / "chief"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(body, encoding="utf-8")


def _by_name(resp) -> dict[str, dict]:
    assert resp.status_code == 200, resp.get_json()
    return {p["name"]: p for p in resp.get_json()["presets"]}


def test_lists_the_built_ins_with_their_own_tiers(client, global_prompts, project):
    resp = client.get("/chief/presets", query_string={"project_root": str(project)})
    body = resp.get_json()
    assert [p["name"] for p in body["presets"]] == ["status", "planner", "operator"]
    for p in body["presets"]:
        assert p["tier"] == p["name"]
        assert p["source"] == "builtin"
        assert p["scope"] is None
        assert p["text"] == BUILT_IN[p["name"]]
    assert body["tiers"]["status"] == ["read"]
    assert body["tiers"]["planner"] == ["read", "post", "plan"]
    assert "run" in body["tiers"]["operator"]
    assert body["limits"]["max_runs_per_session"] >= 0
    assert body["limits"]["max_cost_usd_per_run"] > 0


def test_a_user_file_reports_the_tier_its_front_matter_names(
    client, global_prompts, project
):
    _write(
        project / "pathly" / "prompts",
        "reviewer",
        "---\ntier: planner\n---\n# Reviewer\nWatch.",
    )
    _write(project / "pathly" / "prompts", "quiet", "# Quiet\nNo front matter.")
    presets = _by_name(
        client.get("/chief/presets", query_string={"project_root": str(project)})
    )
    assert presets["reviewer"]["tier"] == "planner"
    assert presets["reviewer"]["source"] == "user"
    assert presets["reviewer"]["scope"] == "project"
    assert presets["reviewer"]["label"] == "Reviewer"
    # The front matter is kept, so a saved copy keeps its tier line.
    assert presets["reviewer"]["text"].startswith("---\ntier: planner\n---")
    assert presets["quiet"]["tier"] == "status"


def test_a_file_named_like_a_built_in_replaces_it_and_can_lower_its_tier(
    client, global_prompts, project
):
    _write(
        project / "pathly" / "prompts",
        "operator",
        "My own operator text, no tier line.",
    )
    presets = _by_name(
        client.get("/chief/presets", query_string={"project_root": str(project)})
    )
    assert presets["operator"]["source"] == "user"
    assert presets["operator"]["tier"] == "status"
    assert presets["operator"]["text"].startswith("My own operator text")


def test_global_files_are_listed_and_a_project_file_wins(
    client, global_prompts, project
):
    _write(global_prompts, "night", "---\ntier: operator\n---\nGlobal night style.")
    _write(global_prompts, "shared", "---\ntier: planner\n---\nGlobal shared.")
    _write(
        project / "pathly" / "prompts",
        "shared",
        "---\ntier: status\n---\nProject shared.",
    )
    presets = _by_name(
        client.get("/chief/presets", query_string={"project_root": str(project)})
    )
    assert presets["night"]["scope"] == "global"
    assert presets["night"]["tier"] == "operator"
    assert presets["shared"]["scope"] == "project"
    assert presets["shared"]["tier"] == "status"


def test_without_a_project_root_only_built_ins_and_global_files(
    client, global_prompts, project
):
    _write(project / "pathly" / "prompts", "local", "---\ntier: planner\n---\nLocal.")
    _write(global_prompts, "night", "Global.")
    names = list(_by_name(client.get("/chief/presets")))
    assert names == ["status", "planner", "operator", "night"]
