import pytest
from pathlib import Path

from install_cli.stitch import stitch_skill


@pytest.fixture
def skill_files(tmp_path):
    core = tmp_path / "go.md"
    core.write_text("# go\n\nSkill body content here.", encoding="utf-8")

    meta = tmp_path / "go_skill.yaml"
    meta.write_text(
        "skill: go\n"
        "invocation: /go\n"
        "natural_language: go, continue\n",
        encoding="utf-8",
    )
    return core, meta


def test_stitch_skill_returns_plain_body(skill_files):
    core, meta = skill_files
    result = stitch_skill(core, meta)
    assert not result.startswith("---")
    assert "Skill body content here." in result


def test_stitch_skill_wrapper_used_when_set(tmp_path):
    meta = tmp_path / "wrap_skill.yaml"
    meta.write_text(
        "skill: wrap\n"
        "invocation: /wrap\n"
        "wrapper: This is the wrapper content.\n",
        encoding="utf-8",
    )
    result = stitch_skill(tmp_path / "nonexistent.md", meta)
    assert result == "This is the wrapper content."


def test_stitch_skill_strip_frontmatter(tmp_path):
    core = tmp_path / "skill.md"
    core.write_text("---\nkey: val\n---\nBody.", encoding="utf-8")

    meta = tmp_path / "skill.yaml"
    meta.write_text(
        "skill: s\ninvocation: /s\nstrip_frontmatter: true\n",
        encoding="utf-8",
    )
    result = stitch_skill(core, meta)
    assert "key: val" not in result
    assert "Body." in result


def test_stitch_skill_no_strip_by_default(tmp_path):
    core = tmp_path / "skill.md"
    core.write_text("---\nkey: val\n---\nBody.", encoding="utf-8")

    meta = tmp_path / "skill.yaml"
    meta.write_text(
        "skill: s\ninvocation: /s\n",
        encoding="utf-8",
    )
    result = stitch_skill(core, meta)
    assert "key: val" in result
    assert "Body." in result


def test_stitch_skill_missing_required_fields_raises(tmp_path):
    core = tmp_path / "skill.md"
    core.write_text("# skill", encoding="utf-8")

    meta = tmp_path / "skill.yaml"
    meta.write_text("skill: s\n", encoding="utf-8")  # missing invocation

    with pytest.raises(ValueError, match="Missing required fields"):
        stitch_skill(core, meta)


def test_stitch_skill_malformed_yaml_raises(tmp_path):
    core = tmp_path / "skill.md"
    core.write_text("# skill", encoding="utf-8")

    meta = tmp_path / "skill.yaml"
    meta.write_text("skill: [unclosed bracket\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed YAML"):
        stitch_skill(core, meta)


def test_stitch_skill_missing_core_no_wrapper_raises(tmp_path):
    meta = tmp_path / "skill.yaml"
    meta.write_text(
        "skill: s\ninvocation: /s\n",
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        stitch_skill(tmp_path / "missing.md", meta)


def test_stitch_skill_real_go_claude(tmp_path):
    """Smoke test using real go.md core and go_skill.yaml for the claude adapter."""
    from install_cli.resources import core_skills_path, adapter_meta_path

    core_file = core_skills_path() / "go.md"
    meta_file = adapter_meta_path("claude") / "go_skill.yaml"

    if not core_file.exists() or not meta_file.exists():
        pytest.skip("Actual skill files not found in this environment")

    result = stitch_skill(core_file, meta_file)
    assert not result.startswith("---")
    assert len(result) > 0


# ---------------------------------------------------------------------------
# materialize — nested paths (structure: nested)
# ---------------------------------------------------------------------------

from install_cli.materialize import materialize


def test_materialize_nested_creates_subdirectory(tmp_path):
    files = {"go/SKILL.md": "# go skill\n\nBody."}
    written = materialize(files, tmp_path)
    assert written == ["go/SKILL.md"]
    assert (tmp_path / "go" / "SKILL.md").read_text() == "# go skill\n\nBody."


def test_materialize_nested_multiple_skills(tmp_path):
    files = {
        "go/SKILL.md": "go body",
        "help/SKILL.md": "help body",
    }
    written = materialize(files, tmp_path)
    assert set(written) == {"go/SKILL.md", "help/SKILL.md"}
    assert (tmp_path / "go" / "SKILL.md").exists()
    assert (tmp_path / "help" / "SKILL.md").exists()


def test_materialize_nested_dry_run_no_dirs_created(tmp_path):
    files = {"go/SKILL.md": "body"}
    written = materialize(files, tmp_path / "dest", dry_run=True)
    assert written == ["go/SKILL.md"]
    assert not (tmp_path / "dest").exists()


def test_materialize_nested_repair_overwrites_owned(tmp_path):
    materialize({"go/SKILL.md": "v1"}, tmp_path)
    written = materialize({"go/SKILL.md": "v2"}, tmp_path, repair=True)
    assert written == ["go/SKILL.md"]
    assert (tmp_path / "go" / "SKILL.md").read_text() == "v2"
