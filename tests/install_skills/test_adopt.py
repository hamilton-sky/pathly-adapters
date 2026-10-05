"""Adopting untracked pathly-* skill dirs into the manifest.

Repair, prune and --uninstall only reach manifest-owned files, so a skill dir the manifest
lost (the user's `pathly-end` and `pathly-team-build`) survived a trim and would survive an
uninstall. Adoption records a file as owned when it is at a path Pathly writes AND its
frontmatter name is that skill's key — provably Pathly-generated; anything else is left
alone with a warning.
"""

from __future__ import annotations

import json
import re

import pytest

from _install_env import installed_skill_dirs, run_install_cli
from install_cli.adopt import find_untracked, frontmatter_name
from install_cli.materialize import (
    MANIFEST_NAME,
    _hash_files_dict,
    _load_manifest,
    adopt,
    materialize,
    plan_prunes,
)
from install_cli.skill_catalog import load_catalog

DEFAULT_DIRS = {
    "pathly",
    "pathly-create-feature",
    "pathly-fsm-call",
    "pathly-help",
    "pathly-post",
    "pathly-status",
}
LOST = ("pathly-end/SKILL.md", "pathly-team-build/SKILL.md")  # keys: end, team/build


def _write_skill(dest, filename, name, body="body"):
    path = dest / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: d\n---\n{body}\n", encoding="utf-8")
    return path


def _drop_from_manifest(skills_dir, names):
    """Make the manifest forget `names` (valid hash), as in the user's real state."""
    mpath = skills_dir / MANIFEST_NAME
    data = json.loads(mpath.read_text(encoding="utf-8"))
    for name in names:
        del data["files"][name]
    data["_manifest_hash"] = _hash_files_dict(data["files"])
    mpath.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture(scope="module")
def catalog():
    return load_catalog("claude", nested=True)


# ── frontmatter signature ──────────────────────────────────────────────────


def test_frontmatter_name(tmp_path):
    f = _write_skill(tmp_path, "a/SKILL.md", "team/build")
    assert frontmatter_name(f) == "team/build"


@pytest.mark.parametrize(
    "text",
    ["no frontmatter at all", "---\nname: [unclosed\n---\n", "---\n- a\n- list\n---\n", "---\nname: 3\n---\n"],
)
def test_frontmatter_name_is_none_when_absent_or_malformed(tmp_path, text):
    f = tmp_path / "SKILL.md"
    f.write_text(text, encoding="utf-8")
    assert frontmatter_name(f) is None


def test_frontmatter_name_of_a_missing_file_is_none(tmp_path):
    assert frontmatter_name(tmp_path / "nope.md") is None


# ── find_untracked ─────────────────────────────────────────────────────────


def test_find_untracked_splits_adoptable_from_foreign(tmp_path, catalog):
    _write_skill(tmp_path, "pathly-end/SKILL.md", "end")  # signature matches
    _write_skill(tmp_path, "pathly-team-build/SKILL.md", "something-else")  # foreign
    _write_skill(tmp_path, "pathly-help/SKILL.md", "help")  # already tracked
    (tmp_path / "pathly-review").mkdir()  # dir without a SKILL.md: not a skill file

    adoptable, foreign = find_untracked(catalog, tmp_path, owned={"pathly-help/SKILL.md"})

    assert adoptable == ["pathly-end/SKILL.md"]
    assert list(foreign) == ["pathly-team-build/SKILL.md"]
    assert "'something-else'" in foreign["pathly-team-build/SKILL.md"]


def test_find_untracked_never_adopts_a_symlinked_skill_dir(tmp_path, catalog):
    real = tmp_path / "elsewhere"
    _write_skill(real, "SKILL.md", "end")
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "pathly-end").symlink_to(real, target_is_directory=True)

    adoptable, foreign = find_untracked(catalog, skills, owned=set())
    assert adoptable == []
    assert "symlink" in foreign["pathly-end/SKILL.md"]


# ── materialize.adopt / plan_prunes ────────────────────────────────────────


def test_adopt_records_the_file_without_rewriting_it(tmp_path):
    materialize({"keep.md": "k"}, tmp_path)
    stray = _write_skill(tmp_path, "pathly-end/SKILL.md", "end", body="OLD COPY")
    before = stray.read_bytes()

    assert adopt(tmp_path, ["pathly-end/SKILL.md"]) == ["pathly-end/SKILL.md"]

    assert stray.read_bytes() == before
    # the manifest stays valid (hash recomputed): a later load must not raise
    assert "pathly-end/SKILL.md" in _load_manifest(tmp_path)["files"]


def test_adopt_skips_owned_missing_and_is_idempotent(tmp_path):
    materialize({"a.md": "a"}, tmp_path)
    _write_skill(tmp_path, "b/SKILL.md", "b")
    assert adopt(tmp_path, ["a.md", "ghost.md", "b/SKILL.md"]) == ["b/SKILL.md"]
    assert adopt(tmp_path, ["a.md", "ghost.md", "b/SKILL.md"]) == []


def test_adopt_refuses_path_traversal(tmp_path):
    dest = tmp_path / "dest"
    materialize({"a.md": "a"}, dest)
    (tmp_path / "outside.md").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Path traversal"):
        adopt(dest, ["../outside.md"])


def test_plan_prunes_counts_files_about_to_be_adopted(tmp_path):
    materialize({"keep.md": "k"}, tmp_path)
    assert plan_prunes({"keep.md": ""}, tmp_path) == []
    assert plan_prunes({"keep.md": ""}, tmp_path, extra_owned=["lost.md"]) == ["lost.md"]


# ── the user's scenario, end to end ────────────────────────────────────────


def _lose_two_skills(tmp_path):
    """All skills installed, then the manifest forgets `end` and `team/build`."""
    assert run_install_cli(["claude", "--apply", "--all-skills"], tmp_path).returncode == 0
    skills = tmp_path / ".claude" / "skills"
    _drop_from_manifest(skills, LOST)
    return skills


@pytest.mark.slow
def test_list_flags_untracked_skills_and_says_they_will_be_adopted(tmp_path):
    skills = _lose_two_skills(tmp_path)
    before = _snapshot(skills)

    r = run_install_cli(["claude", "--list"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert re.search(r"^  end\s+pathly-end\s+installed \(untracked\)", r.stdout, re.M)
    assert re.search(r"^  team/build\s+pathly-team-build\s+installed \(untracked\)", r.stdout, re.M)
    assert "2 untracked Pathly skill(s) will be adopted" in r.stdout
    assert _snapshot(skills) == before  # listing never adopts


@pytest.mark.slow
def test_repair_adopts_then_prunes_the_untracked_skills(tmp_path):
    """The reported bug: a trim left pathly-end / pathly-team-build behind."""
    _lose_two_skills(tmp_path)

    r = run_install_cli(["claude", "--apply", "--repair"], tmp_path)
    assert r.returncode == 0, r.stderr

    assert "Adopted 2 untracked Pathly skill file(s)" in r.stdout
    assert installed_skill_dirs(tmp_path) == DEFAULT_DIRS


@pytest.mark.slow
def test_dry_run_previews_adoption_and_the_prune_and_changes_nothing(tmp_path):
    skills = _lose_two_skills(tmp_path)
    before = _snapshot(tmp_path / ".claude")

    r = run_install_cli(["claude", "--dry-run", "--repair"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Would adopt 2 untracked Pathly skill file(s)" in r.stdout
    removal = r.stdout.split("Would remove", 1)[1]
    assert "pathly-end/SKILL.md" in removal and "pathly-team-build/SKILL.md" in removal
    assert _snapshot(tmp_path / ".claude") == before
    assert (skills / "pathly-end" / "SKILL.md").exists()


@pytest.mark.slow
def test_uninstall_reaches_untracked_skills_too(tmp_path):
    skills = _lose_two_skills(tmp_path)

    dry = run_install_cli(["claude", "--uninstall", "--dry-run"], tmp_path)
    assert "pathly-end/SKILL.md" in dry.stdout and "pathly-team-build/SKILL.md" in dry.stdout
    assert (skills / "pathly-end" / "SKILL.md").exists()

    r = run_install_cli(["claude", "--uninstall"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert installed_skill_dirs(tmp_path) == set()


@pytest.mark.slow
def test_remove_adopts_an_untracked_skill_and_removes_it(tmp_path):
    _lose_two_skills(tmp_path)
    r = run_install_cli(["claude", "--remove", "end"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Adopted" in r.stdout
    dirs = installed_skill_dirs(tmp_path)
    assert "pathly-end" not in dirs
    assert "pathly-team-build" in dirs  # adopted too (same run), but not asked to go


@pytest.mark.slow
def test_plain_apply_adopts_without_pruning(tmp_path):
    skills = _lose_two_skills(tmp_path)
    r = run_install_cli(["claude", "--apply"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Adopted 2" in r.stdout
    assert (skills / "pathly-end" / "SKILL.md").exists()  # tracked now, not removed
    assert set(LOST) <= set(json.loads((skills / MANIFEST_NAME).read_text())["files"])

    again = run_install_cli(["claude", "--apply"], tmp_path)
    assert "Adopted" not in again.stdout  # idempotent


@pytest.mark.slow
def test_foreign_and_symlinked_skills_are_left_alone_with_a_warning(tmp_path):
    assert run_install_cli(["claude", "--apply"], tmp_path).returncode == 0
    skills = tmp_path / ".claude" / "skills"
    _write_skill(skills, "pathly-end/SKILL.md", "my-own-end", body="MINE")
    elsewhere = tmp_path / "elsewhere"
    _write_skill(elsewhere, "SKILL.md", "team/build", body="LINKED")
    (skills / "pathly-team-build").symlink_to(elsewhere, target_is_directory=True)

    r = run_install_cli(["claude", "--apply", "--repair"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "not adopting" in r.stderr
    assert "my-own-end" in r.stderr and "symlink" in r.stderr
    assert "MINE" in (skills / "pathly-end" / "SKILL.md").read_text()
    assert "LINKED" in (skills / "pathly-team-build" / "SKILL.md").read_text()
    assert "Adopted" not in r.stdout
