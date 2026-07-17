"""Layer-3 abilities — .md FILES (not DB rows): scoping, compose segments, board-run compose.

The autouse conftest fixture patches Path.home(), so the 'global' scope lands in a temp dir.
"""

from pathly_orchestrator.skills.abilities import (
    ability_segments,
    delete_ability,
    list_abilities,
    read_ability,
    write_ability,
)


def test_write_and_read_project_ability(tmp_path):
    proj = str(tmp_path / "proj")
    row = write_ability(
        "build",
        "react-web",
        "# React web\nPrefer function components.",
        project_root=proj,
    )
    assert row is not None
    assert row["id"] == "build/react-web"
    assert row["category"] == "build" and row["name"] == "react-web"
    assert row["label"] == "React web"  # from the first '# ' heading
    assert row["scope"] == "project"
    assert row["path"].endswith("pathly/abilities/build/react-web.md")
    assert read_ability("build/react-web", proj) == row


def test_label_falls_back_to_filename(tmp_path):
    proj = str(tmp_path / "proj")
    row = write_ability("plan", "tdd", "Write a test per task.", project_root=proj)
    assert row is not None and row["label"] == "tdd"


def test_project_overrides_global(tmp_path):
    proj = str(tmp_path / "proj")
    write_ability("build", "react", "# Global react\nglobal body", scope="global")
    write_ability("build", "react", "# Project react\nproject body", project_root=proj)

    # With a project root, the project file wins.
    got = read_ability("build/react", proj)
    assert (
        got is not None
        and got["label"] == "Project react"
        and got["scope"] == "project"
    )

    # Without one, only the global exists.
    glob = read_ability("build/react", None)
    assert (
        glob is not None
        and glob["label"] == "Global react"
        and glob["scope"] == "global"
    )


def test_list_merges_scopes(tmp_path):
    proj = str(tmp_path / "proj")
    write_ability("plan", "g-only", "# G\nx", scope="global")
    write_ability("build", "p-only", "# P\ny", project_root=proj)
    ids = [r["id"] for r in list_abilities(proj)]
    assert "plan/g-only" in ids and "build/p-only" in ids


def test_write_rejects_bad_input(tmp_path):
    proj = str(tmp_path / "proj")
    assert write_ability("build", "bad name", "x", project_root=proj) is None  # space
    assert (
        write_ability("../etc", "x", "y", project_root=proj) is None
    )  # path traversal
    assert (
        write_ability("build", "empty", "   ", project_root=proj) is None
    )  # blank body
    # project scope with no project_root is unresolvable
    assert write_ability("build", "x", "y", scope="project", project_root=None) is None


def test_ability_segments_from_files(tmp_path):
    proj = str(tmp_path / "proj")
    write_ability(
        "build",
        "react-web",
        "# React web\nPrefer function components.",
        project_root=proj,
    )
    segs = ability_segments(["build/react-web"], proj)
    assert len(segs) == 1
    s = segs[0]
    assert s["kind"] == "ability" and s["source"] == "ability" and s["optional"] is True
    assert s["id"] == "ability:build/react-web"
    assert "Prefer function components." in s["text"]

    # Unknown / malformed ids are skipped (fail-soft) — a stale selection never breaks compose.
    assert ability_segments(["build/nope", "garbage"], proj) == []
    assert ability_segments([], proj) == []


def test_delete_ability(tmp_path):
    proj = str(tmp_path / "proj")
    write_ability("test", "gone", "# Gone\nx", project_root=proj)
    assert delete_ability("test/gone", project_root=proj) is True
    assert read_ability("test/gone", proj) is None
    assert delete_ability("test/gone", project_root=proj) is False


def test_board_run_composes_abilities(tmp_path):
    """supervisor.board_run._compose_skill_body appends the selected ability FILES at spawn,
    and stays byte-identical to the plain board-default compose when none are selected.
    """
    from pathly_orchestrator.supervisor.board_run import _compose_skill_body
    from pathly_orchestrator.skills.compose import compose_skill

    proj = str(tmp_path / "proj")
    write_ability(
        "build", "react", "# React\nUse function components.", project_root=proj
    )

    body = _compose_skill_body(
        "development/build", "claude", ability_ids=["build/react"], project_root=proj
    )
    assert "Use function components." in body

    # No abilities → byte-identical to the plain board-default compose (no drift).
    assert _compose_skill_body("development/build", "claude") == compose_skill(
        "development/build", "claude", board_default=True
    )
