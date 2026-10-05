"""The default skill tier is ONE set for every adapter — but an adapter only has the skills it
defines (copilot has no `fsm-call`). A default it lacks must simply not be installed there.

Regression: `requires_closure` indexed every default key in the catalog, so
`pathly-setup copilot --apply` failed with `Error: 'fsm-call'` — and nothing caught it because no
test exercised a non-claude host's install.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _install_env import run_install_cli
from install_cli.materialize import MANIFEST_NAME
from install_cli.orchestrate import (
    ALLOWED_HOSTS,
    _build_skill_files,
    _load_install_yaml,
    _select_skill_keys,
)
from install_cli.skill_catalog import DEFAULT_EXPOSED_SKILLS, load_catalog

HOSTS = sorted(ALLOWED_HOSTS)


def _catalog(host):
    cfg = _load_install_yaml(host)
    return cfg, load_catalog(host, nested=cfg["skills"].get("structure") == "nested")


def _skill_md_dirs(files):
    return {f for f in files if not f.endswith(".yaml")}


@pytest.mark.parametrize("host", HOSTS)
def test_default_tier_builds_for_every_host(host):
    cfg, catalog = _catalog(host)
    dest = Path(cfg["destination"]).expanduser()

    _, files = _build_skill_files(host, cfg, dest)

    expected = {catalog[k].filename for k in DEFAULT_EXPOSED_SKILLS if k in catalog}
    assert _skill_md_dirs(files) == expected
    assert expected, "a host must install at least one default skill"


@pytest.mark.parametrize("host", HOSTS)
def test_export_builds_for_every_host(host):
    cfg, catalog = _catalog(host)
    dest = Path(cfg["destination"]).expanduser()

    _, files = _build_skill_files(host, cfg, dest, export_skills={"build"})

    assert catalog["build"].filename in files


def test_a_default_skill_the_adapter_lacks_is_skipped_not_an_error():
    """Independent of which adapters happen to lack fsm-call today."""
    _, claude = _catalog("claude")
    assert "fsm-call" in DEFAULT_EXPOSED_SKILLS and "fsm-call" in claude
    without = {k: v for k, v in claude.items() if k != "fsm-call"}

    wanted = _select_skill_keys("claude", without, None)

    assert wanted == set(DEFAULT_EXPOSED_SKILLS) - {"fsm-call"}


def test_an_exported_skill_the_adapter_lacks_is_still_warned_about(capsys):
    _, claude = _catalog("claude")
    wanted = _select_skill_keys("claude", claude, {"not-a-skill"})
    assert wanted == set(DEFAULT_EXPOSED_SKILLS)
    assert "unknown skill 'not-a-skill'" in capsys.readouterr().err


@pytest.mark.slow
@pytest.mark.parametrize("host", HOSTS)
def test_dry_run_succeeds_for_every_host(host, tmp_path):
    r = run_install_cli([host, "--dry-run", "--repair"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Error" not in r.stdout + r.stderr


@pytest.mark.slow
@pytest.mark.parametrize("host", ["claude", "copilot", "antigravity"])
def test_apply_installs_exactly_the_defaults_the_host_has(host, tmp_path):
    # (codex also registers a local plugin marketplace through the codex CLI — covered by
    # test_codex_plugin_config; its default tier is checked in-process above.)
    cfg, catalog = _catalog(host)
    # install.yaml destinations are "~/…"; the e2e runner redirects HOME to tmp_path
    raw = cfg["skills"]["destination"]
    assert raw.startswith("~/"), raw
    skills_dest = tmp_path / raw.removeprefix("~/")

    r = run_install_cli([host, "--apply"], tmp_path)

    assert r.returncode == 0, r.stderr
    written = json.loads((skills_dest / MANIFEST_NAME).read_text(encoding="utf-8"))[
        "files"
    ]
    expected = {catalog[k].filename for k in DEFAULT_EXPOSED_SKILLS if k in catalog}
    assert set(written) == expected
    assert all((skills_dest / name).is_file() for name in expected)


@pytest.mark.slow
@pytest.mark.parametrize("host", HOSTS)
def test_list_works_for_every_host(host, tmp_path):
    r = run_install_cli([host, "--list"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "default (not installed)" in r.stdout


@pytest.mark.slow
@pytest.mark.parametrize("host", ["copilot", "antigravity"])
def test_export_remove_repair_uninstall_lifecycle(host, tmp_path):
    """The whole command surface, not just --apply, on hosts other than claude."""
    cfg, catalog = _catalog(host)
    skills_dest = tmp_path / cfg["skills"]["destination"].removeprefix("~/")
    build = skills_dest / catalog["build"].filename

    def run(*args):
        r = run_install_cli([host, *args], tmp_path)
        assert r.returncode == 0, (args, r.stdout, r.stderr)
        return r

    run("--apply", "--export", "build")
    assert build.is_file()
    run("--remove", "build")
    assert not build.exists()
    run("--apply", "--repair", "--export", "design")
    assert (skills_dest / catalog["design"].filename).is_file()
    run("--apply", "--repair")  # back to exactly the defaults
    assert not (skills_dest / catalog["design"].filename).exists()
    run("--uninstall")
    assert not list(skills_dest.rglob("SKILL.md")) if skills_dest.exists() else True
