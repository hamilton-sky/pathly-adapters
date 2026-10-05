"""--dry-run (and the real run) must say what a --repair removes, not only what it writes.

A repair is declarative: it writes exactly the requested set and prunes every other
Pathly-owned file. Before this, a dry-run listed the ~6 skills it would write and said
nothing about the ~40 it would delete, and the real run deleted them silently.
"""

from __future__ import annotations

import re

import pytest

from _install_env import installed_skill_dirs, run_install_cli
from install_cli.materialize import MANIFEST_NAME, materialize, plan_prunes


def _seed(dest, names):
    materialize({n: f"body of {n}" for n in names}, dest)


def _snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ── unit: plan_prunes / pruned_out ─────────────────────────────────────────


def test_plan_prunes_lists_owned_files_outside_the_requested_set(tmp_path):
    _seed(tmp_path, ["a/SKILL.md", "b/SKILL.md", "c/SKILL.md"])
    before = _snapshot(tmp_path)

    assert plan_prunes({"a/SKILL.md": "x"}, tmp_path) == ["b/SKILL.md", "c/SKILL.md"]
    assert _snapshot(tmp_path) == before  # read-only


def test_plan_prunes_honours_the_prune_filter(tmp_path):
    _seed(tmp_path, ["a.md", "keep.flow.yaml", "gone.flow.yaml"])
    only_flows = lambda n: n.endswith(".flow.yaml")  # noqa: E731
    assert plan_prunes({"a.md": ""}, tmp_path, prune_filter=only_flows) == [
        "gone.flow.yaml",
        "keep.flow.yaml",
    ]


def test_plan_prunes_ignores_files_the_manifest_does_not_own(tmp_path):
    _seed(tmp_path, ["a.md"])
    (tmp_path / "untracked.md").write_text("user file", encoding="utf-8")
    assert plan_prunes({"a.md": ""}, tmp_path) == []


def test_plan_prunes_is_empty_without_a_manifest(tmp_path):
    assert plan_prunes({"a.md": ""}, tmp_path) == []


def test_materialize_reports_what_it_pruned(tmp_path):
    _seed(tmp_path, ["a.md", "b.md", "c.md"])
    pruned: list[str] = []
    materialize({"a.md": "new"}, tmp_path, repair=True, pruned_out=pruned)
    assert sorted(pruned) == ["b.md", "c.md"]
    assert not (tmp_path / "b.md").exists()


def test_materialize_without_repair_prunes_and_reports_nothing(tmp_path):
    _seed(tmp_path, ["a.md", "b.md"])
    pruned: list[str] = []
    materialize({"a.md": "new"}, tmp_path, repair=False, pruned_out=pruned)
    assert pruned == [] and (tmp_path / "b.md").exists()


# ── e2e: the CLI output ────────────────────────────────────────────────────


@pytest.mark.slow
def test_dry_run_repair_lists_skills_it_would_prune_and_touches_nothing(tmp_path):
    assert (
        run_install_cli(["claude", "--apply", "--all-skills"], tmp_path).returncode == 0
    )
    full = installed_skill_dirs(tmp_path)
    assert {"pathly-review", "pathly-build", "pathly-post"} <= full
    before = _snapshot(tmp_path / ".claude")

    r = run_install_cli(
        ["claude", "--dry-run", "--repair", "--export", "design"], tmp_path
    )
    assert r.returncode == 0, r.stderr

    out = r.stdout
    would_remove = re.search(r"Would remove (\d+) obsolete skill file\(s\)", out)
    assert would_remove, out
    # kept = 6 defaults + design (it requires nothing); everything else installed is reported.
    kept = {
        "pathly",
        "pathly-create-feature",
        "pathly-fsm-call",
        "pathly-help",
        "pathly-post",
        "pathly-status",
        "pathly-design",
    }
    assert int(would_remove.group(1)) == len(full - kept)
    assert "pathly-review/SKILL.md" in out
    # the kept skills are never listed under the removal header
    removal_block = out.split("Would remove", 1)[1]
    assert "pathly-design/SKILL.md" not in removal_block
    assert "pathly-post/SKILL.md" not in removal_block
    # a preview is a preview: nothing on disk moved
    assert _snapshot(tmp_path / ".claude") == before


@pytest.mark.slow
def test_dry_run_without_repair_warns_that_repair_would_remove(tmp_path):
    assert (
        run_install_cli(["claude", "--apply", "--all-skills"], tmp_path).returncode == 0
    )

    r = run_install_cli(["claude", "--dry-run"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "--repair would remove" in r.stdout
    assert "Would remove" not in r.stdout  # without --repair nothing is removed


@pytest.mark.slow
def test_dry_run_on_a_fresh_home_reports_no_prunes(tmp_path):
    r = run_install_cli(["claude", "--dry-run", "--repair"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Would remove" not in r.stdout
    assert "--repair would remove" not in r.stdout


@pytest.mark.slow
def test_real_repair_reports_the_prune_and_leaves_flows_alone(tmp_path):
    assert (
        run_install_cli(["claude", "--apply", "--all-skills"], tmp_path).returncode == 0
    )
    full = installed_skill_dirs(tmp_path)

    r = run_install_cli(["claude", "--apply", "--repair"], tmp_path)
    assert r.returncode == 0, r.stderr

    assert re.search(r"Removed \d+ obsolete skill file\(s\)", r.stdout), r.stdout
    assert "pathly-review/SKILL.md" in r.stdout
    assert installed_skill_dirs(tmp_path) == {
        "pathly",
        "pathly-create-feature",
        "pathly-fsm-call",
        "pathly-help",
        "pathly-post",
        "pathly-status",
    }
    assert len(full) > 6
    # flows share the agents manifest but are reconciled separately: a repair must
    # not delete-and-rewrite them nor report them (or any agent) as pruned.
    assert "obsolete flow" not in r.stdout
    assert "obsolete agent" not in r.stdout
    agents = tmp_path / ".claude" / "agents"
    assert list(agents.glob("*.flow.yaml")), "flows are still installed"
    assert MANIFEST_NAME in {p.name for p in agents.iterdir()}
