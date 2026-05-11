import pytest
from pathlib import Path

from install_cli.stitch import stitch_agent


@pytest.fixture
def agent_files(tmp_path):
    core = tmp_path / "test_agent.md"
    core.write_text("# test-agent\n\nAgent body content here.", encoding="utf-8")

    meta = tmp_path / "test_agent.yaml"
    meta.write_text(
        "name: test-agent\n"
        "description: A test agent for unit testing.\n"
        "model: haiku\n"
        "tools: [Read, Write]\n"
        "can_spawn: [quick]\n"
        "spawn_section: |\n"
        "  ## Sub-agent invocation\n"
        "  Agent(subagent_type=\"quick\", prompt=\"...\")\n",
        encoding="utf-8",
    )
    return core, meta


def test_stitch_starts_with_frontmatter(agent_files):
    core, meta = agent_files
    result = stitch_agent(core, meta)
    assert result.startswith("---\n")


def test_stitch_frontmatter_has_required_fields(agent_files):
    core, meta = agent_files
    result = stitch_agent(core, meta)
    assert "name: test-agent" in result
    assert "description:" in result
    assert "model: haiku" in result
    assert "tools:" in result


def test_stitch_includes_core_body(agent_files):
    core, meta = agent_files
    result = stitch_agent(core, meta)
    assert "Agent body content here." in result


def test_stitch_includes_spawn_section(agent_files):
    core, meta = agent_files
    result = stitch_agent(core, meta)
    assert "Sub-agent invocation" in result


def test_stitch_includes_can_spawn_in_frontmatter(agent_files):
    core, meta = agent_files
    result = stitch_agent(core, meta)
    assert "can_spawn:" in result


def test_stitch_missing_core_raises(tmp_path):
    meta = tmp_path / "meta.yaml"
    meta.write_text(
        "name: x\ndescription: y\nmodel: haiku\ntools: []\n", encoding="utf-8"
    )
    with pytest.raises(FileNotFoundError, match="Core agent file not found"):
        stitch_agent(tmp_path / "missing.md", meta)


def test_stitch_malformed_yaml_raises(tmp_path):
    core = tmp_path / "core.md"
    core.write_text("# agent", encoding="utf-8")
    meta = tmp_path / "meta.yaml"
    meta.write_text("name: [unclosed bracket\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed YAML"):
        stitch_agent(core, meta)


def test_stitch_missing_required_fields_raises(tmp_path):
    core = tmp_path / "core.md"
    core.write_text("# agent", encoding="utf-8")
    meta = tmp_path / "meta.yaml"
    meta.write_text("name: x\n", encoding="utf-8")  # missing description, model
    with pytest.raises(ValueError, match="Missing required fields"):
        stitch_agent(core, meta)


def test_stitch_no_spawn_section_omits_it(tmp_path):
    core = tmp_path / "core.md"
    core.write_text("# agent\n\nBody.", encoding="utf-8")
    meta = tmp_path / "meta.yaml"
    meta.write_text(
        "name: minimal\ndescription: Minimal agent.\nmodel: haiku\ntools: [Read]\n",
        encoding="utf-8",
    )
    result = stitch_agent(core, meta)
    assert "Sub-agent invocation" not in result
    assert "Body." in result


def test_stitch_real_agent(tmp_path):
    """Smoke test against the actual architect agent files."""
    from install_cli.resources import core_agents_path, adapter_meta_path

    core_file = core_agents_path() / "architect.md"
    meta_file = adapter_meta_path("claude") / "architect.yaml"

    if not core_file.exists() or not meta_file.exists():
        pytest.skip("Actual agent files not found in this environment")

    result = stitch_agent(core_file, meta_file)
    assert result.startswith("---\n")
    assert "architect" in result
    assert "sub-agent" in result.lower()
