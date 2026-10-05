"""Per-skill ``requires:`` — install pulls requirements in, remove refuses to orphan them.

``requires:`` (in ``adapters/<host>/_meta/*_skill.yaml``) lists the skills a skill's *own
text* tells the host to invoke. It is a skill→skill edge only: the shell command
``pathly-fsm-call`` (a console script the skills run in bash) is not the ``fsm-call``
skill, an agent spawn is not a skill call, and the ``pathly`` router's fan-out is a
dispatcher, not a dependency (declaring it would drag 18 skills into the 6-skill default).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from _install_env import installed_skill_dirs, run_install_cli
from install_cli import skill_catalog
from install_cli.orchestrate import _build_skill_files, _load_install_yaml
from install_cli.skill_catalog import (
    DEFAULT_EXPOSED_SKILLS,
    SkillInfo,
    dependents_of,
    load_catalog,
    requires_closure,
)

DEFAULT_DIRS = {
    "pathly",
    "pathly-create-feature",
    "pathly-fsm-call",
    "pathly-help",
    "pathly-post",
    "pathly-status",
}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog("claude", nested=True)


# ── the declared graph ─────────────────────────────────────────────────────


def test_every_declared_requirement_is_a_real_skill(catalog):
    for key, info in catalog.items():
        for needed in info.requires:
            assert needed in catalog, f"{key} requires unknown skill {needed!r}"
    requires_closure(catalog, catalog)  # raises on any dangling reference


def test_the_default_tier_is_closed_under_requires(catalog):
    """A default skill may only require default skills, or `--apply` would not yield
    exactly the default set."""
    assert requires_closure(catalog, DEFAULT_EXPOSED_SKILLS) == set(
        DEFAULT_EXPOSED_SKILLS
    )


def test_requirements_are_acyclic(catalog):
    state: dict[str, int] = {}

    def visit(key: str, path: tuple[str, ...]) -> None:
        assert state.get(key) != 1, f"requires cycle: {' -> '.join((*path, key))}"
        if state.get(key) == 2:
            return
        state[key] = 1
        for needed in catalog[key].requires:
            visit(needed, (*path, key))
        state[key] = 2

    for key in catalog:
        visit(key, ())


def test_closure_is_transitive(catalog):
    assert requires_closure(catalog, ["build"]) == {"build", "review", "log-agent-done"}
    assert requires_closure(catalog, ["team/discover"]) >= {
        "team/plan",
        "prd-import",
        "explore",
    }
    assert requires_closure(catalog, ["status"]) == {"status"}


def test_dependents_include_indirect_ones(catalog):
    installed = {"build", "review", "log-agent-done", "status"}
    assert dependents_of(catalog, "review", installed) == ["build"]
    # log-agent-done is needed by review directly and by build through review
    assert dependents_of(catalog, "log-agent-done", installed) == ["build", "review"]
    assert dependents_of(catalog, "build", installed) == []


def test_a_dangling_requirement_is_an_error_not_a_skip(tmp_path):
    meta = tmp_path / "x_skill.yaml"
    info = SkillInfo(
        key="x",
        name="x",
        filename="pathly-x/SKILL.md",
        meta_file=meta,
        meta={},
        requires=("ghost",),
    )
    with pytest.raises(ValueError, match="requires 'ghost'"):
        requires_closure({"x": info}, ["x"])


def test_requires_must_be_a_list_of_keys(tmp_path, monkeypatch):
    (tmp_path / "x_skill.yaml").write_text("skill: x\nrequires: review\n", encoding="utf-8")
    monkeypatch.setattr(skill_catalog, "adapter_meta_path", lambda host: tmp_path)
    with pytest.raises(ValueError, match="must be a list"):
        load_catalog("claude", nested=True)


# ── drift guard: skill text vs declared requires ───────────────────────────

# Phrases a skill body uses to hand control to another skill. Deliberately NOT included:
# the bare "`x` skill" mention (also used for "consumed by"), `pathly-<x>` command names
# (console scripts), and "Spawn `x`" (an agent, not a skill).
_INVOCATION = [
    re.compile(r"[Ii]nvoke (?:the )?`([\w/-]+)` skill"),
    re.compile(r'Skill\("([\w-]+)"\)'),
    re.compile(r"[Rr]oute(?:s|d)? (?:to|via) `([\w/-]+)"),
    re.compile(r"[Cc]all `([\w/-]+)` with"),
    re.compile(r"→ \*\*([\w/-]+)\*\*"),
]
# (skill, target) pairs the patterns match but that are not dependencies.
_NOT_DEPENDENCIES = {
    ("team/discover", "build"): "'Never route to pathly-build' — a prohibition, not a call",
}


def _resolve(catalog: dict[str, SkillInfo], token: str) -> str | None:
    by_dir = {i.dirname: k for k, i in catalog.items()}
    for candidate in (token, f"pathly-{token}", token.replace("/", "-")):
        if candidate in catalog:
            return candidate
        if candidate in by_dir:
            return by_dir[candidate]
    return None


def test_every_skill_invocation_in_the_text_is_declared(catalog):
    install_cfg = _load_install_yaml("claude")
    dest = Path(install_cfg["destination"]).expanduser()
    _, files = _build_skill_files("claude", install_cfg, dest, all_skills=True)
    body = {info.key: files[info.filename] for info in catalog.values()}

    undeclared = []
    for key, text in body.items():
        if key == "pathly":  # the router fans out by design; see module docstring
            continue
        for pattern in _INVOCATION:
            for match in pattern.finditer(text):
                target = _resolve(catalog, match.group(1))
                if target in (None, key, "pathly"):
                    continue
                if (key, target) in _NOT_DEPENDENCIES:
                    continue
                if target not in catalog[key].requires:
                    undeclared.append(f"{key} -> {target}  ({match.group(0)!r})")
    assert not undeclared, (
        "skill text invokes another skill that its _meta/*_skill.yaml does not list in "
        "`requires:` (declare it, or — if it is not a call — add it to _NOT_DEPENDENCIES "
        "with a reason):\n  " + "\n  ".join(sorted(set(undeclared)))
    )


# ── the installer pulls requirements in ────────────────────────────────────


def test_build_skill_files_adds_requirements_and_says_so(capsys):
    install_cfg = _load_install_yaml("claude")
    dest = Path(install_cfg["destination"]).expanduser()
    _, files = _build_skill_files("claude", install_cfg, dest, export_skills={"build"})
    out = capsys.readouterr().out

    assert {
        "pathly-build/SKILL.md",
        "pathly-review/SKILL.md",
        "pathly-log-agent-done/SKILL.md",
    } <= set(files)
    assert "Also installing required skill(s)" in out
    assert "review (for build)" in out


def test_nothing_is_pulled_in_for_the_default_tier(capsys):
    install_cfg = _load_install_yaml("claude")
    dest = Path(install_cfg["destination"]).expanduser()
    _, files = _build_skill_files("claude", install_cfg, dest)
    assert {Path(f).parent.name for f in files} == DEFAULT_DIRS
    assert "Also installing" not in capsys.readouterr().out


@pytest.mark.slow
def test_export_installs_the_requirements_too(tmp_path):
    r = run_install_cli(["claude", "--apply", "--export", "build"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS | {
        "pathly-build",
        "pathly-review",
        "pathly-log-agent-done",
    }
    assert "Also installing required skill(s)" in r.stdout


@pytest.mark.slow
def test_declarative_repair_keeps_requirements_then_drops_them(tmp_path):
    cmd = ["claude", "--apply", "--repair", "--export", "build"]
    assert run_install_cli(cmd, tmp_path).returncode == 0
    assert {"pathly-build", "pathly-review", "pathly-log-agent-done"} <= installed_skill_dirs(
        tmp_path
    )
    # exactly {defaults ∪ requested ∪ requirements}; a bare repair is back to the defaults
    assert run_install_cli(["claude", "--apply", "--repair"], tmp_path).returncode == 0
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS


# ── remove refuses to orphan a requirement ─────────────────────────────────


def _install_build(tmp_path):
    assert run_install_cli(["claude", "--apply", "--export", "build"], tmp_path).returncode == 0


@pytest.mark.slow
def test_remove_refuses_a_skill_an_installed_skill_requires(tmp_path):
    _install_build(tmp_path)
    before = installed_skill_dirs(tmp_path)

    r = run_install_cli(["claude", "--remove", "review"], tmp_path)
    assert r.returncode == 1
    assert "required by installed skill(s): build" in r.stderr
    assert "--remove build --remove review" in r.stderr  # tells you how to cascade
    assert installed_skill_dirs(tmp_path) == before


@pytest.mark.slow
def test_remove_refuses_an_indirect_requirement(tmp_path):
    _install_build(tmp_path)
    r = run_install_cli(["claude", "--remove", "log-agent-done"], tmp_path)
    assert r.returncode == 1
    assert "build, review" in r.stderr
    assert "pathly-log-agent-done" in installed_skill_dirs(tmp_path)


@pytest.mark.slow
def test_remove_allows_dropping_a_skill_together_with_its_dependents(tmp_path):
    _install_build(tmp_path)
    r = run_install_cli(
        ["claude", "--remove", "build", "--remove", "review", "--remove", "log-agent-done"],
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS


@pytest.mark.slow
def test_removing_a_dependent_leaves_its_requirements_installed(tmp_path):
    _install_build(tmp_path)
    r = run_install_cli(["claude", "--remove", "build"], tmp_path)
    assert r.returncode == 0, r.stderr
    # review/log-agent-done were pulled in, but are standalone skills — not auto-removed
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS | {
        "pathly-review",
        "pathly-log-agent-done",
    }


@pytest.mark.slow
def test_list_shows_what_each_skill_requires(tmp_path):
    r = run_install_cli(["claude", "--list"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "REQUIRES" in r.stdout
    build_row = next(ln for ln in r.stdout.splitlines() if ln.startswith("  build "))
    assert build_row.rstrip().endswith("review")
    status_row = next(ln for ln in r.stdout.splitlines() if ln.startswith("  status "))
    assert status_row.rstrip().endswith("-")
