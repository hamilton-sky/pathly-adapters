import json
import tomllib

import pytest

from _paths import REPO_ROOT as _REPO_ROOT

_PLUGIN_JSON_PATHS = [
    _REPO_ROOT / "src/pathly_data/adapters/claude/.claude-plugin/plugin.json",
    _REPO_ROOT / "src/pathly_data/adapters/codex/.codex-plugin/plugin.json",
]

_MANIFEST_PATHS = _PLUGIN_JSON_PATHS + [
    _REPO_ROOT / "src/pathly_data/adapters/claude/.claude-plugin/marketplace.json",
]

_PLUGIN_JSON_STEMS = {p.stem for p in _PLUGIN_JSON_PATHS}


@pytest.mark.parametrize(
    "manifest_path",
    _MANIFEST_PATHS,
    ids=[p.stem for p in _MANIFEST_PATHS],
)
def test_manifest_required_fields(manifest_path):
    """Each manifest JSON must contain non-empty name, version, and description."""
    assert manifest_path.exists(), f"Manifest file not found: {manifest_path}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    for field in ("name", "version", "description"):
        assert (
            field in data
        ), f"Required field {field!r} missing from {manifest_path.name}"
        value = data[field]
        assert isinstance(
            value, str
        ), f"Field {field!r} in {manifest_path.name} must be a str, got {type(value).__name__}"
        assert (
            value.strip()
        ), f"Field {field!r} in {manifest_path.name} must not be empty"

    if manifest_path.stem in _PLUGIN_JSON_STEMS:
        assert (
            "author" in data
        ), f"Required field 'author' missing from {manifest_path.name}"
        assert (
            "skills" in data
        ), f"Required field 'skills' missing from {manifest_path.name}"


def test_codex_plugin_version_matches_distribution_version():
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads(_PLUGIN_JSON_PATHS[1].read_text(encoding="utf-8"))

    assert plugin["version"] == project["project"]["version"]
