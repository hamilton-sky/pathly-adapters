"""`pathly-setup <host> --list` / `--remove` — CLI parity with the Studio export picker.

Catalogue + name-resolution units, then hermetic end-to-end runs (HOME redirected into
tmp_path; the real ~/.claude is never touched).
"""

from __future__ import annotations

import re

import pytest

from _install_env import installed_skill_dirs, run_install_cli
from install_cli.materialize import MANIFEST_NAME
from install_cli.skill_catalog import (
    DEFAULT_EXPOSED_SKILLS,
    load_catalog,
    resolve_skill_args,
)

DEFAULT_DIRS = {
    "pathly",
    "pathly-create-feature",
    "pathly-fsm-call",
    "pathly-help",
    "pathly-post",
    "pathly-status",
}


def _snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _manifest_names(tmp_path):
    import json

    path = tmp_path / ".claude" / "skills" / MANIFEST_NAME
    return set(json.loads(path.read_text(encoding="utf-8"))["files"])


def _list_states(stdout: str) -> dict[str, str]:
    """{skill key: state} parsed from the --list table."""
    states: dict[str, str] = {}
    for line in stdout.splitlines():
        m = re.match(r"^  (\S+)\s{2,}(\S+)\s{2,}(.+)$", line)
        if m and m.group(1) != "SKILL":
            states[m.group(1)] = m.group(3).strip()
    return states


# ── catalogue + name resolution ────────────────────────────────────────────


@pytest.fixture(scope="module")
def catalog():
    return load_catalog("claude", nested=True)


def test_catalog_is_keyed_by_the_skill_field_with_dir_filenames(catalog):
    assert {"build", "fsm-call", "team/build", "debug/verify"} <= set(catalog)
    assert catalog["team/build"].filename == "pathly-team-build/SKILL.md"
    assert catalog["team/build"].dirname == "pathly-team-build"


def test_catalog_default_flag_is_the_installer_constant(catalog):
    assert {k for k, i in catalog.items() if i.default} == set(DEFAULT_EXPOSED_SKILLS)


def test_resolve_accepts_key_directory_name_and_meta_stem(catalog):
    keys, unknown = resolve_skill_args(
        catalog, ["build", "pathly-review", "team-plan", "team/test"]
    )
    assert keys == ["build", "review", "team/plan", "team/test"]
    assert unknown == []


def test_resolve_reports_unknown_and_dedupes(catalog):
    keys, unknown = resolve_skill_args(catalog, ["build", "pathly-build", "biuld"])
    assert keys == ["build"]
    assert unknown == ["biuld"]


def test_skill_owns_its_dir_but_not_a_prefix_sibling(catalog):
    debug = catalog["debug"]
    assert debug.owns("pathly-debug/SKILL.md")
    assert debug.owns("pathly-debug/agents/openai.yaml")
    assert not debug.owns("pathly-debug-build/SKILL.md")


# ── --list ─────────────────────────────────────────────────────────────────


@pytest.mark.slow
def test_list_on_a_fresh_home_shows_defaults_as_not_installed(tmp_path):
    r = run_install_cli(["claude", "--list"], tmp_path)
    assert r.returncode == 0, r.stderr
    states = _list_states(r.stdout)
    assert len(states) == 49
    assert states["status"] == "default (not installed)"
    assert states["build"] == "available"
    assert "0 of 49 skills installed" in r.stdout


@pytest.mark.slow
def test_list_reports_default_installed_untracked_and_available_and_writes_nothing(
    tmp_path,
):
    assert run_install_cli(["claude", "--apply", "--export", "build"], tmp_path).returncode == 0
    # a pathly skill dir that is on disk but absent from the manifest
    stray = tmp_path / ".claude" / "skills" / "pathly-end"
    stray.mkdir()
    (stray / "SKILL.md").write_text("---\nname: end\n---\nold copy", encoding="utf-8")
    before = _snapshot(tmp_path / ".claude")

    r = run_install_cli(["claude", "--list"], tmp_path)
    assert r.returncode == 0, r.stderr
    states = _list_states(r.stdout)
    assert states["status"] == "default"
    assert states["fsm-call"] == "default"
    assert states["build"] == "installed"
    assert states["end"] == "installed (untracked)"
    assert states["review"] == "available"
    assert "8 of 49 skills installed" in r.stdout and "(6 default)" in r.stdout
    assert _snapshot(tmp_path / ".claude") == before  # read-only


# ── --remove ───────────────────────────────────────────────────────────────


@pytest.mark.slow
def test_remove_deletes_only_the_named_skill_and_nothing_else(tmp_path):
    cmd = ["claude", "--apply", "--export", "build", "--export", "review"]
    assert run_install_cli(cmd, tmp_path).returncode == 0
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS | {"pathly-build", "pathly-review"}
    skills = tmp_path / ".claude" / "skills"
    review_before = (skills / "pathly-review" / "SKILL.md").read_bytes()
    outside_skills = {
        k: v
        for k, v in _snapshot(tmp_path / ".claude").items()
        if not k.startswith("skills/")
    }

    r = run_install_cli(["claude", "--remove", "build"], tmp_path)
    assert r.returncode == 0, r.stderr

    assert "Removed 1 requested skill file(s)" in r.stdout
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS | {"pathly-review"}
    assert "pathly-build/SKILL.md" not in _manifest_names(tmp_path)
    # kept skills are not rewritten, and agents/flows/hooks/MCP/templates are not touched
    assert (skills / "pathly-review" / "SKILL.md").read_bytes() == review_before
    assert {
        k: v
        for k, v in _snapshot(tmp_path / ".claude").items()
        if not k.startswith("skills/")
    } == outside_skills


@pytest.mark.slow
def test_remove_accepts_the_directory_name_and_repeats(tmp_path):
    cmd = ["claude", "--apply", "--export", "build", "--export", "review"]
    assert run_install_cli(cmd, tmp_path).returncode == 0
    r = run_install_cli(
        ["claude", "--remove", "pathly-build", "--remove", "review"], tmp_path
    )
    assert r.returncode == 0, r.stderr
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS


@pytest.mark.slow
def test_remove_dry_run_previews_and_touches_nothing(tmp_path):
    assert run_install_cli(["claude", "--apply", "--export", "build"], tmp_path).returncode == 0
    before = _snapshot(tmp_path / ".claude")

    r = run_install_cli(["claude", "--remove", "build", "--dry-run"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Would remove 1 requested skill file(s)" in r.stdout
    assert "pathly-build/SKILL.md" in r.stdout
    assert _snapshot(tmp_path / ".claude") == before


@pytest.mark.slow
def test_remove_refuses_a_default_skill(tmp_path):
    assert run_install_cli(["claude", "--apply"], tmp_path).returncode == 0
    before = _snapshot(tmp_path / ".claude")

    r = run_install_cli(["claude", "--remove", "status"], tmp_path)
    assert r.returncode == 1
    assert "default tier" in r.stderr
    assert _snapshot(tmp_path / ".claude") == before


@pytest.mark.slow
def test_remove_is_all_or_nothing(tmp_path):
    cmd = ["claude", "--apply", "--export", "build"]
    assert run_install_cli(cmd, tmp_path).returncode == 0

    # a typo anywhere in the batch removes nothing
    r = run_install_cli(["claude", "--remove", "build", "--remove", "biuld"], tmp_path)
    assert r.returncode != 0
    assert "biuld" in r.stderr
    assert "pathly-build" in installed_skill_dirs(tmp_path)

    # …and so does a refused (default) skill
    r = run_install_cli(["claude", "--remove", "build", "--remove", "status"], tmp_path)
    assert r.returncode == 1
    assert "pathly-build" in installed_skill_dirs(tmp_path)


@pytest.mark.slow
def test_remove_of_a_skill_that_is_not_installed_is_a_noop(tmp_path):
    assert run_install_cli(["claude", "--apply"], tmp_path).returncode == 0
    r = run_install_cli(["claude", "--remove", "review"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "not installed" in r.stdout
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS


@pytest.mark.slow
def test_remove_will_not_delete_an_untracked_skill(tmp_path):
    assert run_install_cli(["claude", "--apply"], tmp_path).returncode == 0
    stray = tmp_path / ".claude" / "skills" / "pathly-end"
    stray.mkdir()
    (stray / "SKILL.md").write_text("---\nname: end\n---\nmine", encoding="utf-8")

    r = run_install_cli(["claude", "--remove", "end"], tmp_path)
    assert r.returncode == 1
    assert "not tracked" in r.stderr
    assert (stray / "SKILL.md").read_text(encoding="utf-8").endswith("mine")


@pytest.mark.slow
def test_remove_then_export_round_trips_and_repair_stays_declarative(tmp_path):
    assert run_install_cli(["claude", "--apply", "--export", "build"], tmp_path).returncode == 0
    assert run_install_cli(["claude", "--remove", "build"], tmp_path).returncode == 0
    assert "pathly-build" not in installed_skill_dirs(tmp_path)

    assert run_install_cli(["claude", "--export", "build"], tmp_path).returncode == 0
    assert "pathly-build" in installed_skill_dirs(tmp_path)

    # the declarative contract is unchanged: a bare repair keeps exactly the defaults
    assert run_install_cli(["claude", "--apply", "--repair"], tmp_path).returncode == 0
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS


@pytest.mark.slow
@pytest.mark.parametrize(
    "argv",
    [
        ["--remove", "build", "--apply"],
        ["--remove", "build", "--repair"],
        ["--remove", "build", "--export", "review"],
        ["--list", "--remove", "build"],
        ["--list", "--all-skills"],
        ["--list", "--uninstall"],
    ],
)
def test_list_and_remove_reject_clashing_flags(tmp_path, argv):
    r = run_install_cli(["claude", *argv], tmp_path)
    assert r.returncode == 2
    assert "cannot be combined" in r.stderr
    assert installed_skill_dirs(tmp_path) == set()


# ── --export typo guard (the same resolver) ────────────────────────────────


@pytest.mark.slow
def test_export_of_an_unknown_skill_fails_instead_of_silently_installing_nothing(
    tmp_path,
):
    r = run_install_cli(["claude", "--apply", "--export", "build", "--export", "biuld"], tmp_path)
    assert r.returncode == 1
    assert "biuld" in r.stderr
    assert installed_skill_dirs(tmp_path) == set()  # nothing half-applied


@pytest.mark.slow
def test_export_accepts_the_directory_name_too(tmp_path):
    r = run_install_cli(["claude", "--apply", "--export", "pathly-review"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "pathly-review" in installed_skill_dirs(tmp_path)
