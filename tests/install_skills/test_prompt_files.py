"""System-prompts as .md FILES: scoping, label, CRUD, and the legacy DB→files migration.

The autouse conftest fixture patches Path.home() (so 'global' scope lands in a temp dir) and
points get_db() at a per-test temp DB with migrations applied.
"""

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.prompt_library import create_prompt, list_prompts
from pathly_orchestrator.skills.prompt_files import (
    delete_prompt_file,
    list_prompt_files,
    migrate_db_presets_to_files,
    read_prompt_file,
    write_prompt_file,
)


def test_write_and_read_project_prompt(tmp_path):
    proj = str(tmp_path / "proj")
    row = write_prompt_file(
        "analyze", "mylens", "# My lens\nAudit for clarity.", project_root=proj
    )
    assert row is not None
    assert row["id"] == "analyze/mylens"
    assert row["kind"] == "preset" and row["source"] == "user"
    assert row["category"] == "analyze" and row["name"] == "mylens"
    assert row["label"] == "My lens"  # from the first '# ' heading
    assert row["scope"] == "project"
    assert row["path"].endswith("pathly/prompts/analyze/mylens.md")
    assert read_prompt_file("analyze/mylens", proj) == row


def test_label_falls_back_to_filename(tmp_path):
    proj = str(tmp_path / "proj")
    row = write_prompt_file("system", "tone", "Be terse.", project_root=proj)
    assert row is not None and row["label"] == "tone"


def test_project_overrides_global(tmp_path):
    proj = str(tmp_path / "proj")
    write_prompt_file("split", "fine", "# Global\nglobal", scope="global")
    write_prompt_file("split", "fine", "# Project\nproject", project_root=proj)
    got = read_prompt_file("split/fine", proj)
    assert got is not None and got["label"] == "Project" and got["scope"] == "project"
    glob = read_prompt_file("split/fine", None)
    assert glob is not None and glob["label"] == "Global" and glob["scope"] == "global"


def test_list_merges_scopes_and_filters_category(tmp_path):
    proj = str(tmp_path / "proj")
    write_prompt_file("system", "g-only", "# G\nx", scope="global")
    write_prompt_file("analyze", "p-only", "# P\ny", project_root=proj)
    ids = [r["id"] for r in list_prompt_files(proj)]
    assert "system/g-only" in ids and "analyze/p-only" in ids
    only_analyze = [r["id"] for r in list_prompt_files(proj, category="analyze")]
    assert only_analyze == ["analyze/p-only"]


def test_write_rejects_bad_input(tmp_path):
    proj = str(tmp_path / "proj")
    assert write_prompt_file("analyze", "bad name", "x", project_root=proj) is None
    assert write_prompt_file("../etc", "x", "y", project_root=proj) is None
    assert write_prompt_file("system", "empty", "   ", project_root=proj) is None
    assert (
        write_prompt_file("system", "x", "y", scope="project", project_root=None)
        is None
    )


def test_delete_prompt_file(tmp_path):
    proj = str(tmp_path / "proj")
    write_prompt_file("diagram", "gone", "# Gone\nx", project_root=proj)
    assert delete_prompt_file("diagram/gone", project_root=proj) is True
    assert read_prompt_file("diagram/gone", proj) is None
    assert delete_prompt_file("diagram/gone", project_root=proj) is False


def test_migrate_db_presets_to_files_global_and_project(tmp_path):
    """Legacy kind='preset' DB rows are lifted into files (global + project), then removed."""
    proj = str(tmp_path / "proj")
    conn = get_db()
    # label == name (the modal's default) → no synthetic heading is prepended on migration.
    create_prompt(
        conn, kind="preset", category="analyze", name="g", label="g", body="global body"
    )
    create_prompt(
        conn,
        kind="preset",
        category="split",
        name="p",
        label="p",
        body="project body",
        project_root=proj,
    )
    # An ability-kind row must be LEFT ALONE by the preset migration.
    create_prompt(
        conn,
        kind="ability",
        category="build",
        name="keep",
        label="Keep",
        body="stay in db",
    )

    migrated = migrate_db_presets_to_files(conn, proj)
    assert migrated == 2

    files = {r["id"]: r for r in list_prompt_files(proj)}
    assert (
        files["analyze/g"]["scope"] == "global"
        and files["analyze/g"]["body"].strip() == "global body"
    )
    assert (
        files["split/p"]["scope"] == "project"
        and files["split/p"]["body"].strip() == "project body"
    )

    # Preset DB rows are gone; the ability row survives; a second run is a no-op.
    assert list_prompts(conn, kind="preset", project_root=proj) == []
    assert any(r["name"] == "keep" for r in list_prompts(conn, kind="ability"))
    assert migrate_db_presets_to_files(conn, proj) == 0


def test_migrate_preserves_custom_label(tmp_path):
    """A DB label the body wouldn't reproduce is kept as a leading heading on migration."""
    proj = str(tmp_path / "proj")
    conn = get_db()
    create_prompt(
        conn,
        kind="preset",
        category="system",
        name="terse",
        label="Very terse",
        body="No headings here.",
        project_root=proj,
    )
    assert migrate_db_presets_to_files(conn, proj) == 1
    row = read_prompt_file("system/terse", proj)
    assert row is not None and row["label"] == "Very terse"
